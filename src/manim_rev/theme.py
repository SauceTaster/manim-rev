"""Color and typography tokens shared by all Manim Rev components."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class RevTheme:
    """A compact, high-contrast palette designed for projected slides."""

    background: str = "#090D16"
    panel: str = "#121A2A"
    panel_alt: str = "#182236"
    border: str = "#3A4965"
    text: str = "#ECF3FF"
    muted: str = "#91A0BA"
    address: str = "#62D9FF"
    opcode: str = "#B89CFF"
    register: str = "#FFCB6B"
    immediate: str = "#F78C6C"
    success: str = "#5DE4A8"
    warning: str = "#FFD166"
    danger: str = "#FF5C7A"
    info: str = "#5EA1FF"
    taint: str = "#FF7EDB"
    branch_true: str = "#5DE4A8"
    branch_false: str = "#FF6B81"
    fallthrough: str = "#62D9FF"
    call: str = "#B89CFF"
    loop: str = "#FFD166"
    mono_font: str = "monospace"
    sans_font: str = "sans-serif"

    def derive(self, **changes: str) -> RevTheme:
        """Return a copy with selected tokens replaced."""

        return replace(self, **changes)


DEFAULT_THEME = RevTheme()


def light_theme() -> RevTheme:
    """Return a projector-friendly light alternative."""

    return RevTheme(
        background="#F5F7FB",
        panel="#FFFFFF",
        panel_alt="#E9EEF7",
        border="#8390A8",
        text="#111827",
        muted="#5B6577",
        address="#006D9C",
        opcode="#6542B5",
        register="#9A6200",
        immediate="#B64220",
        success="#087F5B",
        warning="#9A6700",
        danger="#C32745",
        info="#245BCE",
        taint="#B51E8C",
        branch_true="#087F5B",
        branch_false="#C32745",
        fallthrough="#006D9C",
        call="#6542B5",
        loop="#9A6700",
    )
