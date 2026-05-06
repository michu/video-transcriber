"""UI component factory functions for VideoTranscriber."""
import customtkinter as ctk


def _apply_layout(widget, pack_kwargs: dict, grid_kwargs: dict) -> None:
    """Apply grid or pack layout to a widget."""
    if grid_kwargs is not None:
        widget.grid(**grid_kwargs)
    else:
        widget.pack(**(pack_kwargs or {}))


def create_label(
    parent,
    text: str,
    pack_kwargs: dict = None,
    grid_kwargs: dict = None,
    **kwargs
) -> ctk.CTkLabel:
    """Create and layout a CTkLabel."""
    label = ctk.CTkLabel(parent, text=text, **kwargs)
    _apply_layout(label, pack_kwargs, grid_kwargs)
    return label


def create_combo(
    parent,
    values: list,
    default: str = None,
    pack_kwargs: dict = None,
    grid_kwargs: dict = None,
    **kwargs
) -> ctk.CTkComboBox:
    """Create and layout a non-editable CTkComboBox."""
    kwargs.setdefault("state", "readonly")
    combo = ctk.CTkComboBox(parent, values=values, **kwargs)
    if default is not None:
        combo.set(default)
    _apply_layout(combo, pack_kwargs, grid_kwargs)
    return combo


def create_button(
    parent,
    text: str,
    command,
    width: int = None,
    pack_kwargs: dict = None,
    grid_kwargs: dict = None,
    **kwargs
) -> ctk.CTkButton:
    """Create and layout a CTkButton."""
    if width is not None:
        kwargs["width"] = width
    btn = ctk.CTkButton(parent, text=text, command=command, **kwargs)
    _apply_layout(btn, pack_kwargs, grid_kwargs)
    return btn


def create_entry(
    parent,
    pack_kwargs: dict = None,
    grid_kwargs: dict = None,
    **kwargs
) -> ctk.CTkEntry:
    """Create and layout a CTkEntry."""
    entry = ctk.CTkEntry(parent, **kwargs)
    _apply_layout(entry, pack_kwargs, grid_kwargs)
    return entry


def create_frame(
    parent,
    pack_kwargs: dict = None,
    grid_kwargs: dict = None,
    **kwargs
) -> ctk.CTkFrame:
    """Create and layout a CTkFrame."""
    frame = ctk.CTkFrame(parent, **kwargs)
    _apply_layout(frame, pack_kwargs, grid_kwargs)
    return frame


def create_checkbox(
    parent,
    text: str,
    command=None,
    pack_kwargs: dict = None,
    grid_kwargs: dict = None,
    **kwargs
) -> ctk.CTkCheckBox:
    """Create and layout a CTkCheckBox."""
    checkbox = ctk.CTkCheckBox(parent, text=text, command=command, **kwargs)
    _apply_layout(checkbox, pack_kwargs, grid_kwargs)
    return checkbox