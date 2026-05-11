"""Subtitles translator service for translating SRT files using NLLB models."""
import re
import logging
import pysrt
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logger = logging.getLogger(__name__)


class SubtitlesTranslatorService:
    """Translates SRT subtitle files between languages using an NLLB model."""

    SUPPORTED = {
        "pol_Latn", "eng_Latn", "deu_Latn", "spa_Latn", "fra_Latn",
        "ita_Latn", "por_Latn", "nld_Latn", "swe_Latn", "dan_Latn",
        "fin_Latn", "ces_Latn", "slk_Latn", "rus_Cyrl", "ukr_Cyrl",
        "bul_Cyrl", "srp_Cyrl", "hrv_Latn", "ron_Latn", "hun_Latn",
        "tur_Latn", "arb_Arab", "zho_Hans", "zho_Hant", "jpn_Jpan",
        "kor_Hang", "hin_Deva"
    }

    ISO1_TO_ISO3 = {
        "pl": "pol", "en": "eng", "de": "deu", "es": "spa",
        "fr": "fra", "it": "ita", "pt": "por", "nl": "nld",
        "sv": "swe", "da": "dan", "fi": "fin", "cs": "ces",
        "sk": "slk", "ru": "rus", "uk": "ukr", "bg": "bul",
        "sr": "srp", "hr": "hrv", "ro": "ron", "hu": "hun",
        "tr": "tur", "ar": "arb", "zh": "zho", "ja": "jpn",
        "ko": "kor", "hi": "hin"
    }

    ALIASES = {
        "cz": "cs",
        "ua": "uk",
        "en-us": "en",
        "en-gb": "en",
        "pt-br": "pt",
        "zh-cn": "zh",
        "zh-tw": "zh"
    }

    def __init__(self, model_name: str, device: str = None):
        """Load the NLLB model and tokenizer."""
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.length_penalty = 0
        self.num_beams = 12
        self.max_new_tokens = 512

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def translate_file(self, input_path: str, output_path: str, src_lang: str, tgt_lang: str) -> None:
        """Translate an SRT file and write the result to output_path.

        src_lang and tgt_lang may be ISO-1 ('en', 'pl'), ISO-3 ('eng'),
        or full NLLB codes ('eng_Latn'). Raises ValueError if either
        language cannot be resolved.
        """
        subs = pysrt.open(input_path, encoding="utf-8")

        resolved_tgt = self._resolve_nllb(tgt_lang)
        resolved_src = self._resolve_nllb(src_lang) if src_lang else None

        translated = self._translate_subs(subs, resolved_src, resolved_tgt)
        translated.save(output_path, encoding="utf-8")

    @classmethod
    def _resolve_nllb(cls, code: str) -> str:
        """Convert an arbitrary language code to a full NLLB code like 'pol_Latn'."""
        if not code:
            raise ValueError("Language code is empty")

        c = code.lower().strip()
        c = cls.ALIASES.get(c, c)

        if c in cls.SUPPORTED:
            return c

        if c in cls.ISO1_TO_ISO3:
            iso3 = cls.ISO1_TO_ISO3[c]
            return cls._find_best_match(iso3)

        if len(c) == 3:
            return cls._find_best_match(c)

        raise ValueError(f"Unsupported language code: {code}")

    @classmethod
    def _find_best_match(cls, iso3: str) -> str:
        """Return the best NLLB code for a given ISO-3 prefix, preferring Latin script."""
        matches = [lang for lang in cls.SUPPORTED if lang.startswith(iso3 + "_")]
        if not matches:
            raise ValueError(f"No supported NLLB language for: {iso3}")
        for match in matches:
            if match.endswith("_Latn"):
                return match
        return matches[0]

    def _translate_subs(self, subs, src_lang: str, tgt_lang: str) -> pysrt.SubRipFile:
        """Translate all subtitle entries in-place and return the modified file."""
        max_tokens = self._resolve_max_tokens()
        margin = 64
        effective_max = max(32, max_tokens - margin)
        logger.info(f"effective_max={effective_max} (max_tokens={max_tokens}, margin={margin})")

        texts_original = [self._normalize_text(s.text) for s in subs]
        flat_texts = []
        sentence_map = [] 

        for text in texts_original:
            sentences = self._split_into_sentences(text)
            if not sentences:
                sentences = [text]
            sentence_map.append(len(sentences))
            flat_texts.extend(sentences)

        logger.info(f"sentence_map={sentence_map} → {len(flat_texts)} sentences from {len(subs)} entries")

        token_lengths = self._compute_token_lengths(flat_texts)

        flat_results = self._translate_flat(flat_texts, token_lengths, effective_max, src_lang, tgt_lang)

        cursor = 0
        for sub, count in zip(subs, sentence_map):
            translated_sentences = flat_results[cursor: cursor + count]
            cursor += count
            merged = " ".join(
                self._restore_case(orig, trans)
                for orig, trans in zip(
                    flat_texts[cursor - count: cursor],
                    translated_sentences
                )
                if trans
            )
            sub.text = self._restore_format(merged if merged else "")

        return subs

    def _resolve_max_tokens(self) -> int:
        """Determine the effective token limit from model and tokenizer config."""
        model_max = None
        try:
            model_max = getattr(self.model.config, "max_length", None)
        except Exception:
            pass

        if not model_max:
            try:
                model_max = getattr(self.model.config, "max_position_embeddings", None)
            except Exception:
                pass

        tokenizer_max = getattr(self.tokenizer, "model_max_length", None)
        if isinstance(tokenizer_max, int) and tokenizer_max > 1_000_000:
            tokenizer_max = None

        if model_max and tokenizer_max:
            max_tokens = min(model_max, tokenizer_max)
            source = "model+tokenizer"
        elif model_max:
            max_tokens = model_max
            source = "model"
        elif tokenizer_max:
            max_tokens = tokenizer_max
            source = "tokenizer"
        else:
            max_tokens = 1024
            source = "fallback(1024)"

        logger.info(f"resolved max_tokens={max_tokens} from {source}")
        return max_tokens

    def _compute_token_lengths(self, texts: list[str]) -> list[int]:
        """Return token lengths for each text, falling back to word count on error."""
        lengths = []
        for text in texts:
            try:
                ids = self.tokenizer(text, add_special_tokens=True)["input_ids"]
                lengths.append(len(ids))
            except Exception:
                lengths.append(len(text.split()))
        return lengths

    def _translate_flat(
        self,
        flat_texts: list[str],
        token_lengths: list[int],
        effective_max: int,
        src_lang: str,
        tgt_lang: str
    ) -> list[str]:
        """Translate a flat list of sentences using token-budget chunking."""
        flat_results = [None] * len(flat_texts)
        i = 0

        while i < len(flat_texts):
            # single line exceeds budget — translate it alone
            if token_lengths[i] > effective_max:
                logger.info(f"sentence {i} tokens={token_lengths[i]} > effective_max, single-line")
                flat_results[i] = self._translate_single_with_fallback(flat_texts[i], src_lang, tgt_lang)
                i += 1
                continue

            # build the largest chunk that fits within the padded-batch token budget
            j = i
            chunk_texts = []
            chunk_max_len = 0

            while j < len(flat_texts):
                tl = token_lengths[j]
                tentative_max = max(chunk_max_len, tl)
                tentative_cost = tentative_max * ((j - i) + 1)
                if tentative_cost > effective_max:
                    break
                chunk_texts.append(flat_texts[j])
                chunk_max_len = tentative_max
                j += 1

            estimated_cost = chunk_max_len * max(1, len(chunk_texts))
            logger.info(f"chunk {i}-{j-1} estimated_cost={estimated_cost} (max_len={chunk_max_len}, lines={len(chunk_texts)})")

            # guard against unexpected empty chunk
            if not chunk_texts:
                logger.warning(f"empty chunk at index {i}, single-line fallback")
                flat_results[i] = self._translate_single_with_fallback(flat_texts[i], src_lang, tgt_lang)
                i += 1
                continue

            # translate chunk as a batch
            try:
                translated_list = self._translate_batch_texts(chunk_texts, src_lang, tgt_lang)
                logger.info(f"batch returned {len(translated_list)} items for chunk {i}-{j-1}")
                if len(translated_list) != len(chunk_texts):
                    logger.warning(f"batch size mismatch, falling back to line-by-line for chunk {i}-{j-1}")
                    translated_list = self._fallback_line_by_line(chunk_texts, src_lang, tgt_lang)
            except Exception as e:
                logger.warning(f"batch failed for chunk {i}-{j-1}: {e}, falling back to line-by-line")
                translated_list = self._fallback_line_by_line(chunk_texts, src_lang, tgt_lang)

            for k, translated in enumerate(translated_list):
                flat_results[i + k] = translated

            i = j

        return flat_results

    def _translate_single_with_fallback(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate a single text, falling back to line-by-line on error."""
        try:
            return self._translate_text(text, src_lang, tgt_lang)
        except Exception:
            return self._fallback_line_by_line([text], src_lang, tgt_lang)[0]

    def _get_forced_bos_token_id(self, tgt_lang: str) -> int:
        """Resolve the forced BOS token ID for the target language."""
        lang_map = getattr(self.tokenizer, "lang_code_to_id", None)
        if lang_map:
            forced_id = lang_map.get(tgt_lang)
            if forced_id:
                return forced_id

        tok_id = self.tokenizer.convert_tokens_to_ids(tgt_lang)
        if tok_id and tok_id != getattr(self.tokenizer, "unk_token_id", None):
            return tok_id

        raise ValueError(f"Unknown target language token for model: {tgt_lang}")

    def _translate_text(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate a single text string."""
        if src_lang:
            self.tokenizer.src_lang = src_lang

        encoded = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True
        ).to(self.device)

        encoded_len = encoded["input_ids"].shape[1]
        logger.debug(f"_translate_text encoded_len={encoded_len} src={src_lang} tgt={tgt_lang}")

        forced_id = self._get_forced_bos_token_id(tgt_lang)

        with torch.no_grad():
            generated = self.model.generate(
                **encoded,
                forced_bos_token_id=forced_id,
                length_penalty=self.length_penalty,
                max_new_tokens=self.max_new_tokens,
                num_beams=self.num_beams
            )

        logger.debug(f"_translate_text generated_shape={generated.shape} forced_id={forced_id}")
        return self.tokenizer.decode(generated[0], skip_special_tokens=True)

    def _translate_batch_texts(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        """Translate a list of texts in a single batched forward pass."""
        if src_lang:
            self.tokenizer.src_lang = src_lang

        encoded = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True
        ).to(self.device)

        logger.debug(f"_translate_batch_texts batch_size={len(texts)} encoded_shape={encoded['input_ids'].shape} src={src_lang} tgt={tgt_lang}")

        forced_id = self._get_forced_bos_token_id(tgt_lang)

        with torch.no_grad():
            generated = self.model.generate(
                **encoded,
                forced_bos_token_id=forced_id,
                length_penalty=self.length_penalty,
                max_new_tokens=self.max_new_tokens,
                num_beams=self.num_beams
            )

        logger.debug(f"_translate_batch_texts generated_shape={generated.shape} forced_id={forced_id}")
        return self.tokenizer.batch_decode(generated, skip_special_tokens=True)

    def _fallback_line_by_line(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        """Translate texts one by one — used as a fallback when batch translation fails."""
        return [self._translate_text(t, src_lang, tgt_lang) for t in texts]

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Collapse newlines and strip surrounding whitespace."""
        return text.replace("\n", " ").strip()

    @staticmethod
    def _restore_case(original: str, translated: str) -> str:
        """Restore the original leading case of a sentence after translation."""
        if not translated or not original:
            return translated
        if original and original[0].islower():
            return translated[0].lower() + translated[1:]
        return translated

    @staticmethod
    def _restore_format(text: str) -> str:
        """Post-process translated text before writing back to subtitle entry.

        Kept as a dedicated method to allow future formatting restoration
        (e.g. line-length wrapping, punctuation fixes) without changing callers.
        """
        return text.strip()
    
    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """Split text into sentences on punctuation boundaries."""
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p for p in parts if p.strip()]