"""Shared layout helpers for the curated 16:9 security examples.

The helpers intentionally use Pango-backed Manim ``Text`` objects only.  They
keep examples compact without hiding any Manim Rev component construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from textwrap import wrap

from manim import DOWN, LEFT, RIGHT, UP, Mobject, RoundedRectangle, VGroup

from manim_rev import DEFAULT_THEME, RevTheme, label_text, mono_text

FRAME_BOTTOM = -4.0
CONTENT_WIDTH = 13.2
SIDE_MARGIN = 0.48
BOTTOM_MARGIN = 0.3


def scene_heading(title: str, kicker: str, *, theme: RevTheme = DEFAULT_THEME) -> VGroup:
    """Return a consistent, compact heading for a 16:9 talk slide."""

    kicker_text = mono_text(
        kicker.upper(),
        font_size=14,
        color=theme.info,
        theme=theme,
        weight="BOLD",
    )
    title_text = label_text(
        title,
        font_size=32,
        color=theme.text,
        theme=theme,
        weight="BOLD",
    )
    heading = VGroup(kicker_text, title_text).arrange(DOWN, aligned_edge=LEFT, buff=0.06)
    if heading.width > CONTENT_WIDTH:
        heading.scale_to_fit_width(CONTENT_WIDTH)
    heading.to_edge(UP, buff=0.18).to_edge(LEFT, buff=SIDE_MARGIN)
    return heading


def place_content(
    content: Mobject,
    heading: Mobject,
    *,
    max_width: float = CONTENT_WIDTH,
    gap: float = 0.28,
) -> Mobject:
    """Fit content into the safe area below ``heading`` without changing aspect ratio."""

    available_height = heading.get_bottom()[1] - FRAME_BOTTOM - BOTTOM_MARGIN - gap
    if content.width > max_width:
        content.scale_to_fit_width(max_width)
    if content.height > available_height:
        content.scale_to_fit_height(available_height)
    content.next_to(heading, DOWN, buff=gap)
    content.set_x(0)
    if content.get_bottom()[1] < FRAME_BOTTOM + BOTTOM_MARGIN:
        content.shift(UP * (FRAME_BOTTOM + BOTTOM_MARGIN - content.get_bottom()[1]))
    return content


def callout(
    title: str,
    body: str,
    *,
    width: float = 4.0,
    color: str | None = None,
    theme: RevTheme = DEFAULT_THEME,
) -> VGroup:
    """Build a small claim/evidence card used to narrate a scene's talk beat."""

    accent = color or theme.info
    body_lines = wrap(body, width=max(22, int(width * 10))) or [""]
    height = 0.78 + len(body_lines) * 0.27
    background = RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.1,
        stroke_color=accent,
        stroke_width=1.4,
        fill_color=theme.panel,
        fill_opacity=1,
    )
    title_text = mono_text(
        title.upper(),
        font_size=14,
        color=accent,
        theme=theme,
        weight="BOLD",
    )
    body_text = label_text(
        "\n".join(body_lines),
        font_size=15,
        color=theme.text,
        theme=theme,
        line_spacing=0.82,
    )
    text = VGroup(title_text, body_text).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
    if text.width > width - 0.34:
        text.scale_to_fit_width(width - 0.34)
    text.move_to(background).align_to(background, LEFT).shift(RIGHT * 0.17)
    return VGroup(background, text)


def legend(
    items: Sequence[tuple[str, str]],
    *,
    theme: RevTheme = DEFAULT_THEME,
) -> VGroup:
    """Build a compact color legend whose labels remain meaningful in narration."""

    entries = VGroup()
    for name, color in items:
        swatch = RoundedRectangle(
            width=0.22,
            height=0.22,
            corner_radius=0.035,
            stroke_width=0,
            fill_color=color,
            fill_opacity=0.9,
        )
        text = mono_text(name, font_size=13, color=theme.muted, theme=theme)
        entries.add(VGroup(swatch, text).arrange(RIGHT, buff=0.09))
    return entries.arrange(RIGHT, buff=0.34)
