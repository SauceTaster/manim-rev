"""Color and typography tokens shared by all Manim Rev components."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class RevTheme:
    """A restrained palette built from Manim Community's default colors."""

    background: str = "#000000"
    panel: str = "#111111"
    panel_alt: str = "#222222"
    border: str = "#888888"
    text: str = "#FFFFFF"
    muted: str = "#BBBBBB"
    address: str = "#58C4DD"
    opcode: str = "#58C4DD"
    register: str = "#FFFFFF"
    immediate: str = "#F0AC5F"
    success: str = "#83C167"
    warning: str = "#F7D96F"
    danger: str = "#FC6255"
    info: str = "#58C4DD"
    taint: str = "#9A72AC"
    branch_true: str = "#83C167"
    branch_false: str = "#FC6255"
    fallthrough: str = "#888888"
    call: str = "#58C4DD"
    loop: str = "#F7D96F"
    mono_font: str = "monospace"
    sans_font: str = "sans-serif"

    def derive(self, **changes: str) -> RevTheme:
        """Return a copy with selected tokens replaced."""

        return replace(self, **changes)


DEFAULT_THEME = RevTheme()


def light_theme() -> RevTheme:
    """Return a projector-friendly light alternative."""

    return RevTheme(
        background="#FFFFFF",
        panel="#FFFFFF",
        panel_alt="#EEEEEE",
        border="#888888",
        text="#000000",
        muted="#444444",
        address="#29ABCA",
        opcode="#29ABCA",
        register="#000000",
        immediate="#C78D46",
        success="#699C52",
        warning="#C78D46",
        danger="#E04A3F",
        info="#29ABCA",
        taint="#715582",
        branch_true="#699C52",
        branch_false="#E04A3F",
        fallthrough="#888888",
        call="#29ABCA",
        loop="#C78D46",
    )
