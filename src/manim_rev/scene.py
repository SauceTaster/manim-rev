"""Scene conveniences for consistent reverse-engineering slide styling."""

from __future__ import annotations

from manim import DOWN, UP, FadeIn, Scene, VGroup

from .primitives import label_text
from .theme import DEFAULT_THEME, RevTheme


class RevScene(Scene):
    """A Scene with Manim-colored defaults and presentation helpers."""

    theme: RevTheme = DEFAULT_THEME

    def setup(self) -> None:
        self.camera.background_color = self.theme.background
        super().setup()

    def title_card(self, title: str, subtitle: str = "") -> VGroup:
        heading = label_text(
            title,
            font_size=48,
            color=self.theme.text,
            theme=self.theme,
            weight="BOLD",
        )
        parts = VGroup(heading)
        if subtitle:
            subheading = label_text(
                subtitle,
                font_size=22,
                color=self.theme.muted,
                theme=self.theme,
            )
            subheading.next_to(heading, DOWN, buff=0.22)
            parts.add(subheading)
        return parts

    def show_title(self, title: str, subtitle: str = "", *, run_time: float = 0.6) -> VGroup:
        card = self.title_card(title, subtitle)
        self.play(FadeIn(card, shift=UP * 0.15), run_time=run_time)
        return card
