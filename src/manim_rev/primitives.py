"""Low-level visual building blocks used throughout the package."""

from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    Dot,
    Rectangle,
    RoundedRectangle,
    Text,
    VGroup,
)

from .theme import DEFAULT_THEME, RevTheme


def mono_text(
    value: object,
    *,
    font_size: float = 24,
    color: str | None = None,
    theme: RevTheme = DEFAULT_THEME,
    **kwargs: object,
) -> Text:
    """Create consistently styled monospace text."""

    return Text(
        str(value),
        font=theme.mono_font,
        font_size=font_size,
        color=color or theme.text,
        **kwargs,
    )


def label_text(
    value: object,
    *,
    font_size: float = 24,
    color: str | None = None,
    theme: RevTheme = DEFAULT_THEME,
    **kwargs: object,
) -> Text:
    """Create consistently styled UI text."""

    return Text(
        str(value),
        font=theme.sans_font,
        font_size=font_size,
        color=color or theme.text,
        **kwargs,
    )


class Panel(VGroup):
    """A titled rounded panel that other components can compose."""

    def __init__(
        self,
        *,
        width: float,
        height: float,
        title: str | None = None,
        theme: RevTheme = DEFAULT_THEME,
        fill_color: str | None = None,
        corner_radius: float = 0.08,
        title_font_size: float = 20,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.theme = theme
        shape = Rectangle if corner_radius <= 0 else RoundedRectangle
        shape_kwargs: dict[str, object] = {
            "width": width,
            "height": height,
            "stroke_color": theme.border,
            "stroke_width": 1.5,
            "fill_color": fill_color or theme.panel,
            "fill_opacity": 1,
        }
        if shape is RoundedRectangle:
            shape_kwargs["corner_radius"] = corner_radius
        self.background = shape(**shape_kwargs)
        self.add(self.background)
        self.title_mobject: Text | None = None
        if title:
            self.title_mobject = label_text(
                title,
                font_size=title_font_size,
                color=theme.text,
                theme=theme,
                weight="BOLD",
            )
            self.title_mobject.move_to(self.background.get_top() + DOWN * 0.27)
            self.title_mobject.align_to(self.background, LEFT).shift(RIGHT * 0.22)
            self.add(self.title_mobject)

    @property
    def inner_top(self):  # type: ignore[no-untyped-def]
        offset = 0.55 if self.title_mobject else 0.18
        return self.background.get_top() + DOWN * offset


class StatusDot(VGroup):
    """A colored status dot with an optional label."""

    def __init__(
        self,
        color: str,
        label: str = "",
        *,
        radius: float = 0.07,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.dot = Dot(radius=radius, color=color)
        self.add(self.dot)
        if label:
            self.label = label_text(label, font_size=17, color=theme.muted, theme=theme)
            self.label.next_to(self.dot, RIGHT, buff=0.1)
            self.add(self.label)


class KeyValueRow(VGroup):
    """A compact key/value row with stable handles for value transforms."""

    def __init__(
        self,
        key: str,
        value: object,
        *,
        width: float = 2.6,
        font_size: float = 20,
        value_color: str | None = None,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.theme = theme
        self.row_width = width
        self.font_size = font_size
        self.key = mono_text(key, font_size=font_size, color=theme.muted, theme=theme)
        self.value = mono_text(
            value,
            font_size=font_size,
            color=value_color or theme.text,
            theme=theme,
        )
        self.value_max_width = max(0.2, width - self.key.width - 0.36)
        if self.value.width > self.value_max_width:
            self.value.scale_to_fit_width(self.value_max_width)
        self.key.move_to(LEFT * width / 2, aligned_edge=LEFT)
        self.value.move_to(RIGHT * width / 2, aligned_edge=RIGHT)
        self.add(self.key, self.value)
