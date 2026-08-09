"""Symbolic-execution state, constraint, and stash visualizations."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from itertools import pairwise

from manim import (
    DOWN,
    LEFT,
    PI,
    RIGHT,
    UP,
    Animation,
    AnimationGroup,
    Arrow,
    Circumscribe,
    Indicate,
    Mobject,
    RoundedRectangle,
    ShowPassingFlash,
    Succession,
    Transform,
    VGroup,
)

from .models import StateStatus, SymbolicEdgeSpec, SymbolicStateSpec, format_address
from .primitives import KeyValueRow, Panel, mono_text
from .refs import AddressRangeRef, AddressRef, SymbolicStateRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme

__all__ = [
    "ConstraintPanel",
    "StashPanel",
    "StashValue",
    "SymbolicExecutionTree",
    "SymbolicStateNode",
]


def _fit_width(mobject: Mobject, width: float) -> Mobject:
    if mobject.width > width:
        mobject.scale_to_fit_width(width)
    return mobject


def _status_color(status: StateStatus, theme: RevTheme) -> str:
    return {
        StateStatus.ACTIVE: theme.info,
        StateStatus.FOUND: theme.success,
        StateStatus.AVOIDED: theme.warning,
        StateStatus.DEADENDED: theme.muted,
        StateStatus.UNSAT: theme.danger,
        StateStatus.ERRORED: theme.danger,
    }[status]


class ConstraintPanel(Panel):
    """A numbered list of solver constraints, optionally bound to one state."""

    def __init__(
        self,
        constraints: Sequence[str],
        *,
        state_key: str | None = None,
        width: float = 5.4,
        max_visible: int = 8,
        title: str = "constraints",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width <= 1:
            raise ValueError("constraint-panel width must be greater than 1")
        if max_visible < 1:
            raise ValueError("max_visible must be positive")
        self.constraints = tuple(str(constraint) for constraint in constraints)
        self.state_key = state_key
        self.max_visible = max_visible
        visible_count = min(len(self.constraints), max_visible)
        overflow_count = max(0, len(self.constraints) - visible_count)
        body_rows = max(1, visible_count) + bool(overflow_count)
        height = 0.78 + body_rows * 0.39
        super().__init__(width=width, height=height, title=title, theme=theme)

        self.rows: dict[int, VGroup] = {}
        content = VGroup()
        for index, constraint in enumerate(self.constraints[:max_visible]):
            row = self._make_row(index, constraint, width - 0.34)
            self.rows[index] = row
            content.add(row)

        self.empty_mobject: Mobject | None = None
        self.overflow_mobject: Mobject | None = None
        if not self.constraints:
            self.empty_mobject = mono_text(
                "<unconstrained>",
                font_size=16,
                color=theme.muted,
                theme=theme,
            )
            content.add(self.empty_mobject)
        elif overflow_count:
            self.overflow_mobject = mono_text(
                f"+ {overflow_count} more",
                font_size=14,
                color=theme.muted,
                theme=theme,
            )
            content.add(self.overflow_mobject)

        content.arrange(DOWN, buff=0.055, aligned_edge=LEFT)
        content.move_to(self.background).shift(DOWN * 0.15)
        self.content = content
        self.add(content)

    def _make_row(self, index: int, constraint: str, width: float) -> VGroup:
        background = RoundedRectangle(
            width=width,
            height=0.33,
            corner_radius=0.04,
            stroke_width=0,
            fill_color=self.theme.panel_alt,
            fill_opacity=0.56 if index % 2 == 0 else 0.3,
        )
        number = mono_text(
            f"{index + 1:02}",
            font_size=13,
            color=self.theme.address,
            theme=self.theme,
        )
        expression = mono_text(
            constraint,
            font_size=15,
            color=self.theme.text,
            theme=self.theme,
        )
        _fit_width(expression, width - 0.62)
        number.align_to(background, LEFT).shift(RIGHT * 0.09)
        expression.next_to(number, RIGHT, buff=0.14)
        return VGroup(background, number, expression)

    def constraint(self, index: int) -> VGroup:
        """Return a visible constraint row by its original zero-based index."""

        try:
            return self.rows[index]
        except KeyError as error:
            if 0 <= index < len(self.constraints):
                raise IndexError(
                    f"constraint {index} is hidden by max_visible={self.max_visible}"
                ) from error
            raise IndexError(f"constraint {index} is outside the panel") from error

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, SymbolicStateRef) and ref.key == self.state_key:
            return (self,)
        return ()

    def focus(self, target: int | SymbolicStateRef | None = None) -> Animation:
        """Emphasize the panel, a row, or the bound symbolic state reference."""

        if target is None:
            targets: tuple[Mobject, ...] = (self,)
        elif isinstance(target, int):
            targets = (self.constraint(target),)
        else:
            targets = self.resolve(target)
        if not targets:
            raise LookupError(f"constraint panel cannot resolve {target!r}")
        return AnimationGroup(
            *(Indicate(item, color=self.theme.warning, scale_factor=1.04) for item in targets)
        )


class SymbolicStateNode(Panel):
    """A compact symbolic-state card with stable semantic handles."""

    def __init__(
        self,
        state: SymbolicStateSpec,
        *,
        width: float = 3.25,
        address_width: int = 8,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width <= 1:
            raise ValueError("symbolic-state width must be greater than 1")
        self.spec = state
        self.key = state.key
        self.status = StateStatus(state.status)
        self.address_width = address_width
        color = _status_color(self.status, theme)
        super().__init__(
            width=width,
            height=1.45,
            title=state.label or state.key,
            theme=theme,
            title_font_size=16,
        )
        self.background.set_stroke(color, width=1.8)

        self.address_mobject = mono_text(
            format_address(state.address, width=address_width),
            font_size=16,
            color=theme.address,
            theme=theme,
        )
        self.status_mobject = mono_text(
            self.status.value.upper(),
            font_size=14,
            color=color,
            theme=theme,
            weight="BOLD",
        )
        constraint_word = "constraint" if len(state.constraints) == 1 else "constraints"
        self.constraint_count_mobject = mono_text(
            f"{len(state.constraints)} {constraint_word}",
            font_size=13,
            color=theme.muted,
            theme=theme,
        )
        row = VGroup(self.address_mobject, self.status_mobject).arrange(RIGHT, buff=0.24)
        _fit_width(row, width - 0.32)
        content = VGroup(row, self.constraint_count_mobject).arrange(
            DOWN,
            buff=0.1,
            aligned_edge=LEFT,
        )
        content.move_to(self.background).shift(DOWN * 0.16)
        self.content = content
        self.add(content)

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, SymbolicStateRef):
            return (self,) if ref.key == self.key else ()
        if isinstance(ref, AddressRef):
            return (self.address_mobject,) if ref.address == self.spec.address else ()
        if (
            isinstance(ref, AddressRangeRef)
            and isinstance(self.spec.address, int)
            and ref.start <= self.spec.address < ref.start + ref.length
        ):
            return (self.address_mobject,)
        return ()

    def focus(self) -> Animation:
        """Emphasize this symbolic state using its status color."""

        return Indicate(
            self,
            color=_status_color(self.status, self.theme),
            scale_factor=1.045,
        )


class _SymbolicEdge(VGroup):
    def __init__(
        self,
        spec: SymbolicEdgeSpec,
        source: SymbolicStateNode,
        target: SymbolicStateNode,
        *,
        path_arc: float = 0,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.spec = spec
        if source is target:
            start = source.get_right() + UP * 0.1
            end = source.get_right() + DOWN * 0.1
            path_arc = -1.55 * PI
        else:
            start = source
            end = target
        self.arrow = Arrow(
            start,
            end,
            buff=0.08,
            path_arc=path_arc,
            color=theme.info,
            stroke_width=2,
            max_tip_length_to_length_ratio=0.16,
        )
        self.add(self.arrow)
        self.label: Mobject | None = None
        if spec.condition:
            self.label = mono_text(
                spec.condition,
                font_size=12,
                color=theme.warning,
                theme=theme,
            )
            _fit_width(self.label, 1.9)
            self.label.move_to(self.arrow.point_from_proportion(0.5) + RIGHT * 0.08)
            self.add(self.label)


class SymbolicExecutionTree(VGroup):
    """A deterministic tree-like view of symbolic states and branch conditions."""

    def __init__(
        self,
        states: Sequence[SymbolicStateSpec | SymbolicStateNode],
        edges: Sequence[SymbolicEdgeSpec],
        *,
        root: str | None = None,
        node_width: float = 3.25,
        horizontal_gap: float = 0.7,
        vertical_gap: float = 0.8,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if not states:
            raise ValueError("a symbolic-execution tree requires at least one state")
        if horizontal_gap < 0 or vertical_gap < 0:
            raise ValueError("symbolic-tree layout gaps must be non-negative")
        self.theme = theme
        self.specs = tuple(
            state.spec if isinstance(state, SymbolicStateNode) else state for state in states
        )
        keys = [state.key for state in self.specs]
        if len(keys) != len(set(keys)):
            raise ValueError("symbolic-state keys must be unique")
        self.root = root or keys[0]
        if self.root not in keys:
            raise KeyError(f"unknown root state {self.root!r}")

        self.edge_specs = tuple(edges)
        seen_edges: set[tuple[str, str]] = set()
        for edge in self.edge_specs:
            if edge.source not in keys or edge.target not in keys:
                raise KeyError(
                    f"edge {edge.source!r} -> {edge.target!r} references an unknown state"
                )
            key = (edge.source, edge.target)
            if key in seen_edges:
                raise ValueError(f"duplicate symbolic edge {edge.source!r} -> {edge.target!r}")
            seen_edges.add(key)

        self.state_mobjects: dict[str, SymbolicStateNode] = {}
        for item in states:
            node = (
                item
                if isinstance(item, SymbolicStateNode)
                else SymbolicStateNode(item, width=node_width, theme=theme)
            )
            self.state_mobjects[node.key] = node

        self.levels = self._compute_levels(keys)
        self.layers = self._position_layers(keys, horizontal_gap, vertical_gap)
        self.layout_positions = {
            key: tuple(float(value) for value in node.get_center())
            for key, node in self.state_mobjects.items()
        }

        self.edge_mobjects: dict[tuple[str, str], _SymbolicEdge] = {}
        edges_group = VGroup()
        for spec in self.edge_specs:
            path_arc = 0.0
            if self.levels[spec.target] <= self.levels[spec.source]:
                path_arc = 0.55
            view = _SymbolicEdge(
                spec,
                self.state(spec.source),
                self.state(spec.target),
                path_arc=path_arc,
                theme=theme,
            )
            self.edge_mobjects[(spec.source, spec.target)] = view
            edges_group.add(view)

        states_group = VGroup(*(self.state_mobjects[key] for key in keys))
        self.edges_group = edges_group
        self.states_group = states_group
        self.add(edges_group, states_group)

    def _compute_levels(self, keys: Sequence[str]) -> dict[str, int]:
        adjacency: dict[str, list[str]] = {key: [] for key in keys}
        for edge in self.edge_specs:
            adjacency[edge.source].append(edge.target)

        levels: dict[str, int] = {}
        roots = [self.root, *(key for key in keys if key != self.root)]
        for root in roots:
            if root in levels:
                continue
            base_level = max(levels.values(), default=-1) + 1
            levels[root] = base_level
            queue: deque[str] = deque((root,))
            while queue:
                source = queue.popleft()
                for target in adjacency[source]:
                    if target in levels:
                        continue
                    levels[target] = levels[source] + 1
                    queue.append(target)
        return levels

    def _position_layers(
        self,
        keys: Sequence[str],
        horizontal_gap: float,
        vertical_gap: float,
    ) -> dict[int, tuple[str, ...]]:
        by_level: defaultdict[int, list[str]] = defaultdict(list)
        for key in keys:
            by_level[self.levels[key]].append(key)
        layers = {level: tuple(layer) for level, layer in sorted(by_level.items())}
        previous_height = 0.0
        y = 0.0
        for index, layer_keys in enumerate(layers.values()):
            row = VGroup(*(self.state_mobjects[key] for key in layer_keys))
            row.arrange(RIGHT, buff=horizontal_gap)
            current_height = row.height
            if index:
                y -= previous_height / 2 + vertical_gap + current_height / 2
            row.move_to([0, y, 0])
            previous_height = current_height
        return layers

    def state(self, key: str) -> SymbolicStateNode:
        """Return a state node by its stable model key."""

        try:
            return self.state_mobjects[key]
        except KeyError as error:
            raise KeyError(f"unknown symbolic state {key!r}") from error

    def edge(self, source: str, target: str) -> _SymbolicEdge:
        """Return a directed symbolic edge by source and target keys."""

        try:
            return self.edge_mobjects[(source, target)]
        except KeyError as error:
            raise KeyError(f"unknown symbolic edge {source!r} -> {target!r}") from error

    def successors(self, key: str) -> tuple[str, ...]:
        self.state(key)
        return tuple(edge.target for edge in self.edge_specs if edge.source == key)

    def predecessors(self, key: str) -> tuple[str, ...]:
        self.state(key)
        return tuple(edge.source for edge in self.edge_specs if edge.target == key)

    def constraint_panel(
        self,
        key: str,
        *,
        width: float = 5.4,
        max_visible: int = 8,
        title: str = "constraints",
    ) -> ConstraintPanel:
        """Create a constraint panel bound to one existing state."""

        node = self.state(key)
        return ConstraintPanel(
            node.spec.constraints,
            state_key=key,
            width=width,
            max_visible=max_visible,
            title=title,
            theme=self.theme,
        )

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, SymbolicStateRef):
            state = self.state_mobjects.get(ref.key)
            return (state,) if state is not None else ()
        if isinstance(ref, (AddressRef, AddressRangeRef)):
            targets: list[Mobject] = []
            for state in self.state_mobjects.values():
                targets.extend(state.resolve(ref))
            return tuple(targets)
        return ()

    def focus(self, target: str | VisualRef) -> Animation:
        """Emphasize a state key or any semantic reference resolved by the tree."""

        targets = (self.state(target),) if isinstance(target, str) else self.resolve(target)
        if not targets:
            raise LookupError(f"symbolic tree cannot resolve {target!r}")
        return AnimationGroup(
            *(Indicate(item, color=self.theme.warning, scale_factor=1.045) for item in targets)
        )

    def trace(
        self,
        path: Sequence[str],
        *,
        color: str | None = None,
        run_time: float = 0.45,
    ) -> Animation:
        """Build an animation that follows a validated path through the tree."""

        if not path:
            raise ValueError("a symbolic trace path cannot be empty")
        for key in path:
            self.state(key)
        trace_color = color or self.theme.warning
        animations: list[Animation] = [
            Indicate(
                self.state(path[0]),
                color=trace_color,
                scale_factor=1.045,
                run_time=run_time,
            )
        ]
        for source, target in pairwise(path):
            edge = self.edge(source, target)
            animations.extend(
                (
                    ShowPassingFlash(
                        edge.arrow.copy().set_color(trace_color),
                        time_width=0.55,
                        run_time=run_time,
                    ),
                    Indicate(
                        self.state(target),
                        color=trace_color,
                        scale_factor=1.045,
                        run_time=run_time,
                    ),
                )
            )
        return Succession(*animations)

    def animate_fork(
        self,
        parent: str,
        children: Sequence[str] | None = None,
        *,
        run_time: float = 0.45,
    ) -> Animation:
        """Emphasize existing successor states as one symbolic fork."""

        parent_node = self.state(parent)
        selected = self.successors(parent) if children is None else tuple(children)
        if not selected:
            raise ValueError(f"symbolic state {parent!r} has no children to animate")
        available = set(self.successors(parent))
        if unknown := [child for child in selected if child not in available]:
            raise ValueError(f"states {unknown!r} are not successors of {parent!r}")
        branches: list[Animation] = []
        for child in selected:
            edge = self.edge(parent, child)
            branches.append(
                Succession(
                    ShowPassingFlash(
                        edge.arrow.copy().set_color(self.theme.warning),
                        time_width=0.55,
                        run_time=run_time,
                    ),
                    Indicate(
                        self.state(child),
                        color=self.theme.warning,
                        scale_factor=1.045,
                        run_time=run_time,
                    ),
                )
            )
        return Succession(
            Indicate(
                parent_node,
                color=self.theme.warning,
                scale_factor=1.045,
                run_time=run_time,
            ),
            AnimationGroup(*branches, lag_ratio=0.08),
        )


StashValue = Sequence[str] | int


def _normalize_stash(value: StashValue) -> tuple[tuple[str, ...] | None, int]:
    if isinstance(value, int):
        if value < 0:
            raise ValueError("stash counts cannot be negative")
        return None, value
    states = (value,) if isinstance(value, str) else tuple(str(key) for key in value)
    if len(states) != len(set(states)):
        raise ValueError("state keys within a stash must be unique")
    return states, len(states)


class StashPanel(Panel):
    """Counts and optional state membership for angr-style state stashes."""

    def __init__(
        self,
        stashes: Mapping[StateStatus | str, StashValue],
        *,
        width: float = 3.9,
        title: str = "state stashes",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width <= 1:
            raise ValueError("stash-panel width must be greater than 1")
        if not stashes:
            raise ValueError("a stash panel requires at least one stash")
        normalized: dict[StateStatus, tuple[tuple[str, ...] | None, int]] = {}
        for raw_status, value in stashes.items():
            status = StateStatus(raw_status)
            if status in normalized:
                raise ValueError(f"duplicate normalized stash {status.value!r}")
            normalized[status] = _normalize_stash(value)

        self.members = {status: value[0] for status, value in normalized.items()}
        self.counts = {status: value[1] for status, value in normalized.items()}
        height = 0.76 + len(normalized) * 0.43
        super().__init__(width=width, height=height, title=title, theme=theme)

        self.rows: dict[StateStatus, KeyValueRow] = {}
        content = VGroup()
        for status in normalized:
            row = KeyValueRow(
                status.value.upper(),
                self.counts[status],
                width=width - 0.52,
                font_size=17,
                value_color=_status_color(status, theme),
                theme=theme,
            )
            self.rows[status] = row
            content.add(row)
        content.arrange(DOWN, buff=0.16, aligned_edge=LEFT)
        content.move_to(self.background).shift(DOWN * 0.16)
        self.content = content
        self.add(content)

    @staticmethod
    def _status(status: StateStatus | str) -> StateStatus:
        try:
            return StateStatus(status)
        except ValueError as error:
            raise KeyError(f"unknown symbolic stash {status!r}") from error

    def stash(self, status: StateStatus | str) -> KeyValueRow:
        """Return a stash row by enum or its lowercase string value."""

        normalized = self._status(status)
        try:
            return self.rows[normalized]
        except KeyError as error:
            raise KeyError(f"stash {normalized.value!r} is not displayed") from error

    def states(self, status: StateStatus | str) -> tuple[str, ...]:
        """Return known member keys, or an empty tuple for count-only stashes."""

        normalized = self._status(status)
        self.stash(normalized)
        return self.members[normalized] or ()

    def animate_update(self, status: StateStatus | str, value: StashValue) -> Animation:
        """Replace one stash count or membership list and emphasize its row."""

        normalized = self._status(status)
        row = self.stash(normalized)
        members, count = _normalize_stash(value)
        self.members[normalized] = members
        self.counts[normalized] = count
        target = mono_text(
            count,
            font_size=row.font_size,
            color=_status_color(normalized, self.theme),
            theme=self.theme,
        )
        target.scale_to_fit_height(row.value.height)
        target.move_to(row.value, aligned_edge=RIGHT)
        return AnimationGroup(
            Transform(row.value, target),
            Circumscribe(
                row,
                color=_status_color(normalized, self.theme),
                buff=0.045,
            ),
        )

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if not isinstance(ref, SymbolicStateRef):
            return ()
        return tuple(
            self.rows[status]
            for status, members in self.members.items()
            if members is not None and ref.key in members
        )

    def focus(self, target: StateStatus | str | SymbolicStateRef) -> Animation:
        """Emphasize a stash or all stashes containing a known state key."""

        if isinstance(target, SymbolicStateRef):
            targets = self.resolve(target)
        else:
            targets = (self.stash(target),)
        if not targets:
            raise LookupError(f"stash panel cannot resolve {target!r}")
        return AnimationGroup(
            *(Indicate(row, color=self.theme.warning, scale_factor=1.04) for row in targets)
        )
