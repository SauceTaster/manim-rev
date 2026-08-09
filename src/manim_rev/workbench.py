"""Composable multi-pane layouts for debugger and analysis talk scenes."""

from __future__ import annotations

from collections.abc import Mapping

from manim import (
    RIGHT,
    Animation,
    AnimationGroup,
    Arrow,
    Create,
    FadeIn,
    Indicate,
    Mobject,
    ShowPassingFlash,
    VGroup,
)

from .primitives import mono_text
from .refs import ExecutedAddressRef, MemoryRangeRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme


class ReferenceLink(VGroup):
    """A labeled arrow between semantic objects in two views."""

    def __init__(
        self,
        source: Mobject,
        target: Mobject,
        *,
        label: str = "",
        color: str = DEFAULT_THEME.warning,
        path_arc: float = 0.0,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.path_arc = path_arc
        self.arrow = Arrow(
            source,
            target,
            buff=0.08,
            path_arc=path_arc,
            color=color,
            stroke_width=2.4,
            max_tip_length_to_length_ratio=0.12,
        )
        self.add(self.arrow)
        self.label = None
        if label:
            self.label = mono_text(label, font_size=15, color=color, theme=theme)
            self.label.move_to(self.arrow.get_center())
            self.label.add_background_rectangle(
                color=theme.background,
                opacity=0.88,
                buff=0.05,
            )
            self.add(self.label)

    def animate_flow(self) -> Animation:
        """Reveal the relationship, then send a bright pulse along it."""

        reveal = [Create(self.arrow)]
        if self.label is not None:
            reveal.append(FadeIn(self.label))
        pulse = self.arrow.copy().set_stroke(width=6)
        return AnimationGroup(
            *reveal,
            ShowPassingFlash(pulse, time_width=0.45),
            lag_ratio=0.12,
        )


class AnalysisWorkbench(VGroup):
    """Arrange named views and coordinate semantic focus between them."""

    def __init__(
        self,
        panels: Mapping[str, Mobject],
        *,
        columns: int = 2,
        horizontal_buff: float = 0.35,
        vertical_buff: float = 0.35,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if not panels:
            raise ValueError("workbench needs at least one panel")
        if columns < 1:
            raise ValueError("columns must be at least 1")
        self.theme = theme
        self.columns = columns
        self.panels = dict(panels)
        self.panel_group = VGroup(*self.panels.values())
        self.panel_group.arrange_in_grid(
            cols=columns,
            buff=(horizontal_buff, vertical_buff),
        )
        remainder = len(self.panels) % columns
        if remainder and len(self.panels) > remainder:
            panel_items = tuple(self.panels.values())
            full_row = VGroup(*panel_items[:columns])
            trailing_row = VGroup(*panel_items[-remainder:])
            trailing_row.shift((full_row.get_center()[0] - trailing_row.get_center()[0]) * RIGHT)
        self.links = VGroup()
        self.add(self.panel_group, self.links)

    def panel(self, name: str) -> Mobject:
        return self.panels[name]

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        resolved: list[Mobject] = []
        seen: set[int] = set()
        for panel in self.panels.values():
            resolver = getattr(panel, "resolve", None)
            if resolver is None:
                continue
            for mobject in resolver(ref):
                identity = id(mobject)
                if identity not in seen:
                    resolved.append(mobject)
                    seen.add(identity)
        return tuple(resolved)

    def focus(
        self,
        ref: VisualRef,
        *,
        color: str | None = None,
        scale_factor: float = 1.05,
    ) -> Animation:
        targets = self.resolve(ref)
        if not targets:
            raise LookupError(f"no workbench panel resolved {ref!r}")
        return AnimationGroup(
            *(
                Indicate(
                    target,
                    color=color or self.theme.warning,
                    scale_factor=scale_factor,
                )
                for target in targets
            )
        )

    def link(
        self,
        source_panel: str,
        source_ref: VisualRef,
        target_panel: str,
        target_ref: VisualRef,
        *,
        source_occurrence: int = 0,
        target_occurrence: int = 0,
        label: str = "",
        color: str | None = None,
        path_arc: float = 0.0,
    ) -> ReferenceLink:
        """Create and retain a link between selected reference occurrences."""

        if source_occurrence < 0 or target_occurrence < 0:
            raise ValueError("link occurrences must be non-negative")

        source_view = self.panels[source_panel]
        target_view = self.panels[target_panel]
        source_resolver = getattr(source_view, "resolve", None)
        target_resolver = getattr(target_view, "resolve", None)
        if not callable(source_resolver) or not callable(target_resolver):
            raise LookupError("source or target panel does not support semantic references")
        source_targets = tuple(source_resolver(source_ref))
        target_targets = tuple(target_resolver(target_ref))
        if not source_targets or not target_targets:
            raise LookupError("source or target reference did not resolve")
        if source_occurrence >= len(source_targets):
            raise LookupError(
                f"source occurrence {source_occurrence} is out of range "
                f"for {len(source_targets)} resolved target(s)"
            )
        if target_occurrence >= len(target_targets):
            raise LookupError(
                f"target occurrence {target_occurrence} is out of range "
                f"for {len(target_targets)} resolved target(s)"
            )
        link = ReferenceLink(
            source_targets[source_occurrence],
            target_targets[target_occurrence],
            label=label,
            color=color or self.theme.warning,
            path_arc=path_arc,
            theme=self.theme,
        )
        self.links.add(link)
        return link

    def breakpoint_to_memory(
        self,
        *,
        breakpoint_panel: str,
        instruction_address: int,
        memory_panel: str,
        memory_address: int,
        length: int = 1,
        breakpoint_occurrence: int = 0,
        memory_occurrence: int = 0,
        label: str = "memory access",
        path_arc: float = 0.0,
    ) -> ReferenceLink:
        """Convenience link from an instruction/breakpoint to touched bytes."""

        return self.link(
            breakpoint_panel,
            ExecutedAddressRef(instruction_address),
            memory_panel,
            MemoryRangeRef(memory_address, length),
            source_occurrence=breakpoint_occurrence,
            target_occurrence=memory_occurrence,
            label=label,
            color=self.theme.danger,
            path_arc=path_arc,
        )


DebuggerWorkbench = AnalysisWorkbench
