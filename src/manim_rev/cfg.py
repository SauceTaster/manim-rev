"""Deterministic control-flow graph and basic-block visualizations."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from itertools import pairwise
from math import isfinite

from manim import (
    DOWN,
    LEFT,
    PI,
    RIGHT,
    UP,
    Animation,
    AnimationGroup,
    Arrow,
    Indicate,
    Mobject,
    RoundedRectangle,
    ShowPassingFlash,
    Succession,
    VGroup,
)

from .models import (
    Address,
    BasicBlockSpec,
    CFGEdgeSpec,
    EdgeKind,
    InstructionSpec,
    format_address,
)
from .primitives import Panel, mono_text
from .refs import AddressRangeRef, AddressRef, BlockRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme


def _fit_width(mobject: Mobject, width: float) -> Mobject:
    """Shrink a text mobject only when it would overflow its allotted width."""

    if mobject.width > width:
        mobject.scale_to_fit_width(width)
    return mobject


class BasicBlock(Panel):
    """A compact basic-block card with addressable instruction rows."""

    def __init__(
        self,
        block: BasicBlockSpec,
        *,
        width: float = 4.45,
        row_height: float = 0.34,
        show_bytes: bool = False,
        address_width: int = 8,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width <= 1:
            raise ValueError("basic-block width must be greater than 1")
        if row_height <= 0:
            raise ValueError("row height must be positive")

        self.spec = block
        self.key = block.key
        self.address_width = address_width
        self.show_bytes = show_bytes
        instruction_count = max(1, len(block.instructions))
        height = 0.7 + instruction_count * (row_height + 0.035)
        title = block.label or f"{block.key}  {format_address(block.address, width=address_width)}"
        super().__init__(
            width=width,
            height=height,
            title=title,
            theme=theme,
            title_font_size=16,
        )

        self.rows = VGroup()
        self.instruction_rows: dict[Address, VGroup] = {}
        self._row_specs: dict[Address, InstructionSpec] = {}
        if block.instructions:
            for index, instruction in enumerate(block.instructions):
                row = self._make_row(instruction, index, width - 0.26, row_height)
                self.rows.add(row)
                if isinstance(instruction, InstructionSpec):
                    if instruction.address in self.instruction_rows:
                        raise ValueError(
                            f"duplicate instruction address {instruction.address!r} in block {block.key!r}"
                        )
                    self.instruction_rows[instruction.address] = row
                    self._row_specs[instruction.address] = instruction
        else:
            empty = mono_text("<empty>", font_size=15, color=theme.muted, theme=theme)
            self.rows.add(empty)

        self.rows.arrange(DOWN, buff=0.035, aligned_edge=LEFT)
        self.rows.move_to(self.background).shift(DOWN * 0.16)
        self.add(self.rows)

    def _make_row(
        self,
        instruction: InstructionSpec | str,
        index: int,
        width: float,
        height: float,
    ) -> VGroup:
        background = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.045,
            stroke_width=0,
            fill_color=self.theme.panel_alt,
            fill_opacity=0.48 if index % 2 == 0 else 0.23,
        )
        if isinstance(instruction, str):
            text = mono_text(instruction, font_size=16, color=self.theme.text, theme=self.theme)
            _fit_width(text, width - 0.2)
            text.align_to(background, LEFT).shift(RIGHT * 0.1)
            return VGroup(background, text)

        address = mono_text(
            format_address(instruction.address, width=self.address_width),
            font_size=13,
            color=self.theme.address,
            theme=self.theme,
        )
        mnemonic = mono_text(
            instruction.mnemonic,
            font_size=16,
            color=self.theme.opcode,
            theme=self.theme,
            weight="BOLD",
        )
        operands = mono_text(
            instruction.operands,
            font_size=15,
            color=self.theme.register,
            theme=self.theme,
        )
        parts = VGroup(address)
        if self.show_bytes:
            raw_bytes = mono_text(
                instruction.bytes_text or "--",
                font_size=11,
                color=self.theme.muted,
                theme=self.theme,
            )
            parts.add(raw_bytes)
        parts.add(mnemonic)
        if instruction.operands:
            parts.add(operands)
        parts.arrange(RIGHT, buff=0.13)
        _fit_width(parts, width - 0.2)
        parts.align_to(background, LEFT).shift(RIGHT * 0.1)
        return VGroup(background, parts)

    def row(self, index: int) -> Mobject:
        """Return an instruction row by zero-based display index."""

        try:
            return self.rows[index]
        except IndexError as error:
            raise IndexError(f"instruction row {index} is outside block {self.key!r}") from error

    def instruction(self, address: Address) -> VGroup:
        """Return the structured instruction row at ``address``."""

        try:
            return self.instruction_rows[address]
        except KeyError as error:
            raise KeyError(f"block {self.key!r} has no instruction at {address!r}") from error

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, BlockRef):
            return (self,) if ref.key == self.key else ()
        if isinstance(ref, AddressRef):
            row = self.instruction_rows.get(ref.address)
            if row is not None:
                return (row,)
            return (self,) if ref.address == self.spec.address else ()
        if isinstance(ref, AddressRangeRef):
            matches: list[Mobject] = []
            range_end = ref.start + ref.length
            for address, row in self.instruction_rows.items():
                if not isinstance(address, int):
                    continue
                instruction = self._row_specs[address]
                instruction_end = address + max(1, len(instruction.raw_bytes))
                if address < range_end and ref.start < instruction_end:
                    matches.append(row)
            if (
                not matches
                and isinstance(self.spec.address, int)
                and ref.start <= self.spec.address < range_end
            ):
                return (self,)
            return tuple(matches)
        return ()

    def focus(
        self,
        ref: VisualRef | None = None,
        *,
        color: str | None = None,
        scale_factor: float = 1.04,
    ) -> Animation:
        """Emphasize this block or one of its semantic targets."""

        targets = (self,) if ref is None else self.resolve(ref)
        if not targets:
            raise LookupError(f"block {self.key!r} cannot resolve {ref!r}")
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


class _CFGEdge(VGroup):
    """Internal edge group retaining its specification and arrow handle."""

    def __init__(
        self,
        spec: CFGEdgeSpec,
        source: BasicBlock,
        target: BasicBlock,
        *,
        color: str,
        path_arc: float = 0,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.spec = spec
        if source is target:
            start = source.get_right() + UP * 0.11
            end = source.get_right() + DOWN * 0.11
            path_arc = -1.55 * PI
        else:
            start = source
            end = target
        self.arrow = Arrow(
            start,
            end,
            buff=0.08,
            path_arc=path_arc,
            color=color,
            stroke_width=2.1,
            max_tip_length_to_length_ratio=0.16,
        )
        self.add(self.arrow)
        self.label = None
        label_value = spec.label or _default_edge_label(spec.kind)
        if label_value:
            self.label = mono_text(label_value, font_size=12, color=color, theme=theme)
            self.label.move_to(self.arrow.point_from_proportion(0.5) + RIGHT * 0.08)
            self.add(self.label)


def _default_edge_label(kind: EdgeKind) -> str:
    if kind is EdgeKind.TRUE:
        return "T"
    if kind is EdgeKind.FALSE:
        return "F"
    return ""


def _edge_color(kind: EdgeKind, theme: RevTheme) -> str:
    return {
        EdgeKind.TRUE: theme.branch_true,
        EdgeKind.FALSE: theme.branch_false,
        EdgeKind.FALLTHROUGH: theme.fallthrough,
        EdgeKind.CALL: theme.call,
        EdgeKind.RETURN: theme.call,
        EdgeKind.LOOP: theme.loop,
        EdgeKind.UNCONDITIONAL: theme.info,
    }[kind]


class ControlFlowGraph(VGroup):
    """A deterministic top-to-bottom control-flow graph.

    The layout uses breadth-first layers rooted at ``entry``. Back edges never
    alter an already assigned layer, making loop-heavy graphs stable without
    Graphviz or a random layout engine. Optional two- or three-dimensional
    ``positions`` override named block centers after that layout is computed.
    """

    def __init__(
        self,
        blocks: Sequence[BasicBlockSpec | BasicBlock],
        edges: Sequence[CFGEdgeSpec],
        *,
        entry: str | None = None,
        positions: Mapping[str, Sequence[float]] | None = None,
        block_width: float = 4.45,
        horizontal_gap: float = 0.75,
        vertical_gap: float = 0.85,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if not blocks:
            raise ValueError("a control-flow graph requires at least one block")
        if horizontal_gap < 0 or vertical_gap < 0:
            raise ValueError("CFG layout gaps must be non-negative")
        self.theme = theme
        self.specs = tuple(
            block.spec if isinstance(block, BasicBlock) else block for block in blocks
        )
        keys = [spec.key for spec in self.specs]
        if len(keys) != len(set(keys)):
            raise ValueError("basic-block keys must be unique")
        normalized_positions = self._normalize_positions(keys, positions)
        self.entry = entry or keys[0]
        if self.entry not in keys:
            raise KeyError(f"unknown entry block {self.entry!r}")

        self.edge_specs = tuple(edges)
        for edge in self.edge_specs:
            if edge.source not in keys or edge.target not in keys:
                raise KeyError(
                    f"edge {edge.source!r} -> {edge.target!r} references an unknown block"
                )

        self.block_mobjects: dict[str, BasicBlock] = {}
        for item in blocks:
            block = (
                item
                if isinstance(item, BasicBlock)
                else BasicBlock(item, width=block_width, theme=theme)
            )
            self.block_mobjects[block.key] = block

        self.levels = self._compute_levels(keys)
        self.layers = self._position_layers(keys, horizontal_gap, vertical_gap)
        for key, position in normalized_positions.items():
            self.block_mobjects[key].move_to(position)
        self.layout_positions = {
            key: (
                float(block.get_center()[0]),
                float(block.get_center()[1]),
                float(block.get_center()[2]),
            )
            for key, block in self.block_mobjects.items()
        }

        self.edge_mobjects: dict[tuple[str, str, EdgeKind], _CFGEdge] = {}
        pair_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
        edge_group = VGroup()
        for spec in self.edge_specs:
            kind = EdgeKind(spec.kind)
            edge_key = (spec.source, spec.target, kind)
            if edge_key in self.edge_mobjects:
                raise ValueError(f"duplicate {kind.value} edge {spec.source!r} -> {spec.target!r}")
            source_level = self.levels[spec.source]
            target_level = self.levels[spec.target]
            path_arc = 0.0
            if target_level <= source_level:
                path_arc = 0.52 + pair_counts[(spec.source, spec.target)] * 0.12
            pair_counts[(spec.source, spec.target)] += 1
            edge_view = _CFGEdge(
                spec,
                self.block(spec.source),
                self.block(spec.target),
                color=_edge_color(kind, theme),
                path_arc=path_arc,
                theme=theme,
            )
            self.edge_mobjects[edge_key] = edge_view
            edge_group.add(edge_view)

        block_group = VGroup(*(self.block_mobjects[key] for key in keys))
        self.edges_group = edge_group
        self.blocks_group = block_group
        self.add(edge_group, block_group)

    @staticmethod
    def _normalize_positions(
        keys: Sequence[str],
        positions: Mapping[str, Sequence[float]] | None,
    ) -> dict[str, tuple[float, float, float]]:
        if positions is None:
            return {}
        unknown = set(positions).difference(keys)
        if unknown:
            formatted = ", ".join(sorted(repr(key) for key in unknown))
            raise KeyError(f"position mapping references unknown block(s): {formatted}")

        normalized: dict[str, tuple[float, float, float]] = {}
        for key, coordinate in positions.items():
            if isinstance(coordinate, (str, bytes)):
                raise ValueError(f"position for block {key!r} must contain two or three numbers")
            try:
                values = tuple(float(value) for value in coordinate)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"position for block {key!r} must contain two or three numbers"
                ) from error
            if len(values) not in (2, 3):
                raise ValueError(f"position for block {key!r} must contain two or three numbers")
            if not all(isfinite(value) for value in values):
                raise ValueError(f"position for block {key!r} must contain finite coordinates")
            if len(values) == 2:
                values = (*values, 0.0)
            normalized[key] = (values[0], values[1], values[2])
        return normalized

    def _compute_levels(self, keys: Sequence[str]) -> dict[str, int]:
        adjacency: dict[str, list[str]] = {key: [] for key in keys}
        for edge in self.edge_specs:
            if edge.target not in adjacency[edge.source]:
                adjacency[edge.source].append(edge.target)

        levels: dict[str, int] = {}
        roots = [self.entry, *(key for key in keys if key != self.entry)]
        for root in roots:
            if root in levels:
                continue
            base_level = max(levels.values(), default=-1) + 1
            queue: deque[str] = deque((root,))
            levels[root] = base_level
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

        layers = {level: tuple(layer_keys) for level, layer_keys in sorted(by_level.items())}
        previous_height = 0.0
        y = 0.0
        for index, (_, layer_keys) in enumerate(layers.items()):
            row = VGroup(*(self.block_mobjects[key] for key in layer_keys))
            row.arrange(RIGHT, buff=horizontal_gap)
            current_height = row.height
            if index:
                y -= previous_height / 2 + vertical_gap + current_height / 2
            row.move_to([0, y, 0])
            previous_height = current_height
        return layers

    def block(self, key: str) -> BasicBlock:
        """Return a block by its stable model key."""

        try:
            return self.block_mobjects[key]
        except KeyError as error:
            raise KeyError(f"unknown basic block {key!r}") from error

    def edge(
        self,
        source: str,
        target: str,
        kind: EdgeKind | str | None = None,
    ) -> VGroup:
        """Return a directed edge, optionally selecting its semantic kind."""

        if kind is not None:
            normalized = EdgeKind(kind)
            try:
                return self.edge_mobjects[(source, target, normalized)]
            except KeyError as error:
                raise KeyError(
                    f"unknown {normalized.value} edge {source!r} -> {target!r}"
                ) from error
        matches = [
            edge
            for (edge_source, edge_target, _), edge in self.edge_mobjects.items()
            if edge_source == source and edge_target == target
        ]
        if not matches:
            raise KeyError(f"unknown CFG edge {source!r} -> {target!r}")
        if len(matches) > 1:
            raise KeyError(f"multiple CFG edges exist from {source!r} to {target!r}; specify kind")
        return matches[0]

    def successors(self, key: str) -> tuple[str, ...]:
        self.block(key)
        return tuple(edge.target for edge in self.edge_specs if edge.source == key)

    def predecessors(self, key: str) -> tuple[str, ...]:
        self.block(key)
        return tuple(edge.source for edge in self.edge_specs if edge.target == key)

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, BlockRef):
            block = self.block_mobjects.get(ref.key)
            return (block,) if block is not None else ()
        if isinstance(ref, (AddressRef, AddressRangeRef)):
            targets: list[Mobject] = []
            for block in self.block_mobjects.values():
                targets.extend(block.resolve(ref))
            return tuple(targets)
        return ()

    def focus(
        self,
        target: str | VisualRef,
        *,
        color: str | None = None,
        scale_factor: float = 1.05,
    ) -> Animation:
        """Emphasize a block key or any semantic reference resolved by the graph."""

        targets = (self.block(target),) if isinstance(target, str) else self.resolve(target)
        if not targets:
            raise LookupError(f"control-flow graph cannot resolve {target!r}")
        return AnimationGroup(
            *(
                Indicate(
                    mobject,
                    color=color or self.theme.warning,
                    scale_factor=scale_factor,
                )
                for mobject in targets
            )
        )

    def traverse(
        self,
        path: Sequence[str],
        *,
        color: str | None = None,
        run_time: float = 0.45,
    ) -> Animation:
        """Build a block/edge traversal animation for a validated path."""

        if not path:
            raise ValueError("a CFG traversal path cannot be empty")
        for key in path:
            self.block(key)

        traversal_color = color or self.theme.warning
        animations: list[Animation] = [
            Indicate(
                self.block(path[0]),
                color=traversal_color,
                scale_factor=1.04,
                run_time=run_time,
            )
        ]
        for source, target in pairwise(path):
            edge = self.edge(source, target)
            animations.extend(
                (
                    ShowPassingFlash(
                        edge.arrow.copy().set_color(traversal_color),  # type: ignore[attr-defined]
                        time_width=0.55,
                        run_time=run_time,
                    ),
                    Indicate(
                        self.block(target),
                        color=traversal_color,
                        scale_factor=1.04,
                        run_time=run_time,
                    ),
                )
            )
        return Succession(*animations)
