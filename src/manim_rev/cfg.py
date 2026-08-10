"""Deterministic control-flow graph and basic-block visualizations."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from itertools import pairwise
from math import atan2, hypot, isfinite, pi
from typing import Any

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Animation,
    AnimationGroup,
    Arrow,
    ArrowTriangleFilledTip,
    BackgroundRectangle,
    Circumscribe,
    CubicBezier,
    Line,
    Mobject,
    Rectangle,
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
from .primitives import Panel, label_text, mono_text
from .refs import AddressRangeRef, AddressRef, BlockRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme


def _fit_width(mobject: Mobject, width: float) -> Mobject:
    """Shrink a text mobject only when it would overflow its allotted width."""

    if mobject.width > width:
        mobject.scale_to_fit_width(width)
    return mobject


_MIN_BLOCK_WIDTH = 2.25
_MIN_BLOCK_WIDTH_WITH_BYTES = 3.10
_MIN_CFG_GAP = 0.25


def _overlap_area(first: Mobject, second: Mobject, *, first_buff: float = 0.0) -> float:
    """Return axis-aligned overlap area, expanding ``first`` by ``first_buff``."""

    width = min(first.get_right()[0] + first_buff, second.get_right()[0]) - max(
        first.get_left()[0] - first_buff,
        second.get_left()[0],
    )
    height = min(first.get_top()[1] + first_buff, second.get_top()[1]) - max(
        first.get_bottom()[1] - first_buff,
        second.get_bottom()[1],
    )
    return max(0.0, float(width)) * max(0.0, float(height))


class BasicBlock(Panel):
    """A clean, addressable basic block for mathematical-style CFG diagrams."""

    def __init__(
        self,
        block: BasicBlockSpec,
        *,
        width: float = 4.45,
        row_height: float = 0.34,
        show_bytes: bool = False,
        address_width: int = 8,
        compact_addresses: bool = False,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        minimum_width = _MIN_BLOCK_WIDTH_WITH_BYTES if show_bytes else _MIN_BLOCK_WIDTH
        if width < minimum_width:
            mode = " when showing bytes" if show_bytes else ""
            raise ValueError(f"basic-block width must be at least {minimum_width:.2f}{mode}")
        if row_height <= 0:
            raise ValueError("row height must be positive")

        self.spec = block
        self.key = block.key
        self.address_width = address_width
        self.show_bytes = show_bytes
        self.compact_addresses = compact_addresses
        instruction_count = max(1, len(block.instructions))
        row_gap = 0.025
        header_height = 0.46
        height = 0.22 + header_height + instruction_count * row_height
        height += max(0, instruction_count - 1) * row_gap
        super().__init__(
            width=width,
            height=height,
            title=None,
            theme=theme,
            fill_color=theme.background,
            corner_radius=0,
        )
        self.background.set_stroke(theme.border, width=1.7)

        display_label = block.label or block.key
        self.block_label = label_text(
            display_label,
            font_size=17,
            color=theme.text,
            theme=theme,
            weight="BOLD",
        )
        self.block_address = mono_text(
            format_address(block.address, width=address_width),
            font_size=11,
            color=theme.muted,
            theme=theme,
        )
        address_room = min(max(0.64, width * 0.36), width - 0.82)
        _fit_width(self.block_address, address_room)
        label_room = max(0.3, width - self.block_address.width - 0.48)
        _fit_width(self.block_label, label_room)
        self.block_label.move_to(
            self.background.get_top() + DOWN * 0.23 + RIGHT * 0.14,
            aligned_edge=LEFT,
        )
        self.block_label.align_to(self.background, LEFT).shift(RIGHT * 0.14)
        self.block_address.move_to(
            self.background.get_top() + DOWN * 0.23 + LEFT * 0.14,
            aligned_edge=RIGHT,
        )
        self.block_address.align_to(self.background, RIGHT).shift(LEFT * 0.14)
        self.title_mobject = self.block_label
        self.header = VGroup(self.block_label, self.block_address)
        self.divider = Line(
            self.background.get_left() + RIGHT * 0.12,
            self.background.get_right() + LEFT * 0.12,
            color=theme.border,
            stroke_width=0.8,
        )
        self.divider.set_y(self.background.get_top()[1] - header_height)
        self.add(self.header, self.divider)

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
            empty = self._make_row("empty", 0, width - 0.24, row_height)
            self.rows.add(empty)

        self.rows.arrange(DOWN, buff=row_gap, aligned_edge=LEFT)
        self.rows.next_to(self.divider, DOWN, buff=0.07)
        self.add(self.rows)

    def _make_row(
        self,
        instruction: InstructionSpec | str,
        _index: int,
        width: float,
        height: float,
    ) -> VGroup:
        background = Rectangle(
            width=width,
            height=height,
            stroke_width=0,
            fill_color=self.theme.background,
            fill_opacity=0,
        )
        if isinstance(instruction, str):
            text = mono_text(instruction, font_size=15, color=self.theme.text, theme=self.theme)
            _fit_width(text, width - 0.24)
            text.align_to(background, LEFT).shift(RIGHT * 0.12)
            return VGroup(background, text)

        compact = width < 2.6
        formatted_address = format_address(instruction.address, width=self.address_width)
        if self.compact_addresses and isinstance(instruction.address, int):
            formatted_address = f"0x…{formatted_address[-4:]}"
        address = mono_text(
            formatted_address,
            font_size=12 if compact else 13,
            color=self.theme.muted,
            theme=self.theme,
        )
        mnemonic = mono_text(
            instruction.mnemonic,
            font_size=16 if compact else 17,
            color=self.theme.opcode,
            theme=self.theme,
            weight="BOLD",
        )
        operands = mono_text(
            instruction.operands,
            font_size=14 if compact else 16,
            color=self.theme.text,
            theme=self.theme,
        )
        parts = VGroup(address)
        cursor = 0.12
        address_width = min(1.12, max(0.68, width * 0.28))
        _fit_width(address, address_width - 0.08)
        address.move_to(background.get_left() + RIGHT * cursor, aligned_edge=LEFT)
        cursor += address_width
        if self.show_bytes:
            raw_bytes = mono_text(
                instruction.bytes_text or "--",
                font_size=10 if compact else 11,
                color=self.theme.muted,
                theme=self.theme,
            )
            parts.add(raw_bytes)
            bytes_width = min(1.34, max(0.72, width * 0.28))
            _fit_width(raw_bytes, bytes_width - 0.08)
            raw_bytes.move_to(background.get_left() + RIGHT * cursor, aligned_edge=LEFT)
            cursor += bytes_width
        parts.add(mnemonic)
        mnemonic_width = min(0.9, max(0.52, width * 0.2))
        _fit_width(mnemonic, mnemonic_width - 0.06)
        mnemonic.move_to(background.get_left() + RIGHT * cursor, aligned_edge=LEFT)
        cursor += mnemonic_width
        if instruction.operands:
            parts.add(operands)
            operand_width = max(0.18, width - cursor - 0.12)
            _fit_width(operands, operand_width)
            operands.move_to(background.get_left() + RIGHT * cursor, aligned_edge=LEFT)
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
                Circumscribe(
                    target.background if isinstance(target, BasicBlock) else target,
                    color=color or self.theme.warning,
                    buff=max(0.04, (scale_factor - 1) * 0.7),
                )
                for target in targets
            )
        )


class _CFGEdge(VGroup):
    """Internal edge group retaining its specification and arrow handle."""

    def __init__(
        self,
        spec: CFGEdgeSpec,
        *,
        start: Any,
        end: Any,
        color: str,
        route_lane_x: float | None = None,
        label_side: float = 1,
        obstacles: Sequence[Mobject] = (),
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.spec = spec
        if route_lane_x is None:
            self.arrow = Arrow(
                start,
                end,
                buff=0,
                color=color,
                stroke_width=2,
                max_tip_length_to_length_ratio=0.11,
                max_stroke_width_to_length_ratio=2,
            )
            self.arrow_tip = None
        else:
            first_control = start.copy()
            first_control[0] = route_lane_x
            second_control = end.copy()
            second_control[0] = route_lane_x
            self.arrow = CubicBezier(
                start,
                first_control,
                second_control,
                end,
                color=color,
                stroke_width=2,
            )
            tangent = end - self.arrow.point_from_proportion(0.98)
            angle = float(atan2(tangent[1], tangent[0]))
            self.arrow_tip = ArrowTriangleFilledTip(
                length=0.13,
                width=0.13,
                color=color,
                stroke_width=0,
            )
            self.arrow_tip.rotate(angle - pi)
            self.arrow_tip.shift(end - self.arrow_tip.tip_point)
        self.add(self.arrow)
        if self.arrow_tip is not None:
            self.add(self.arrow_tip)
        self.label = None
        self.label_background = None
        label_value = spec.label or _default_edge_label(spec.kind)
        if label_value:
            self.label = label_text(label_value, font_size=12, color=color, theme=theme)
            proportions = (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74)
            sides = (label_side, -label_side)
            offsets: tuple[float, ...]
            if obstacles:
                obstacle_left = min(obstacle.get_left()[0] for obstacle in obstacles)
                obstacle_right = max(obstacle.get_right()[0] for obstacle in obstacles)
                obstacle_bottom = min(obstacle.get_bottom()[1] for obstacle in obstacles)
                obstacle_top = max(obstacle.get_top()[1] for obstacle in obstacles)
                escape_offset = (
                    hypot(
                        float(obstacle_right - obstacle_left),
                        float(obstacle_top - obstacle_bottom),
                    )
                    + self.label.width
                    + self.label.height
                    + 0.5
                )
                offsets = (0.18, 0.0, 0.28, 0.4, 0.54, 0.72, 0.95, 1.25, escape_offset)
            else:
                offsets = (0.18,)
            best_position = self.arrow.point_from_proportion(0.5)
            best_overlap = float("inf")
            placed = False
            for proportion in proportions:
                point = self.arrow.point_from_proportion(proportion)
                before = self.arrow.point_from_proportion(max(0, proportion - 0.025))
                after = self.arrow.point_from_proportion(min(1, proportion + 0.025))
                tangent = after - before
                normal = RIGHT.copy()
                normal[0] = -tangent[1]
                normal[1] = tangent[0]
                normal[2] = 0
                length = float((normal[0] ** 2 + normal[1] ** 2) ** 0.5)
                if length:
                    normal /= length
                else:
                    normal = RIGHT.copy()
                for side in sides:
                    for offset in offsets:
                        position = point + normal * offset * side
                        self.label.move_to(position)
                        overlap = sum(
                            _overlap_area(self.label, obstacle, first_buff=0.06)
                            for obstacle in obstacles
                        )
                        if overlap < best_overlap:
                            best_overlap = overlap
                            best_position = position.copy()
                        if overlap <= 1e-9:
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break
            if best_overlap > 1e-9:
                raise RuntimeError("could not place CFG edge label outside diagram content")
            self.label.move_to(best_position)
            self.label_background = BackgroundRectangle(
                self.label,
                color=theme.background,
                fill_color=theme.background,
                fill_opacity=0.94,
                stroke_width=0,
                buff=0.045,
            )
            self.add(self.label_background, self.label)


def _default_edge_label(kind: EdgeKind) -> str:
    if kind is EdgeKind.TRUE:
        return "true"
    if kind is EdgeKind.FALSE:
        return "false"
    return ""


def _edge_color(kind: EdgeKind, theme: RevTheme) -> str:
    return {
        EdgeKind.TRUE: theme.branch_true,
        EdgeKind.FALSE: theme.branch_false,
        EdgeKind.FALLTHROUGH: theme.fallthrough,
        EdgeKind.CALL: theme.call,
        EdgeKind.RETURN: theme.call,
        EdgeKind.LOOP: theme.loop,
        EdgeKind.UNCONDITIONAL: theme.fallthrough,
    }[kind]


class ControlFlowGraph(VGroup):
    """A deterministic top-to-bottom control-flow graph.

    The layout uses deterministic longest-path layers over the forward-edge
    DAG. Loop and DFS back edges are routed outside the block bounds, keeping
    merge nodes below all of their forward predecessors. Optional two- or
    three-dimensional ``positions`` override named block centers before edges
    are routed.
    """

    def __init__(
        self,
        blocks: Sequence[BasicBlockSpec | BasicBlock],
        edges: Sequence[CFGEdgeSpec],
        *,
        entry: str | None = None,
        positions: Mapping[str, Sequence[float]] | None = None,
        block_width: float = 4.45,
        compact_addresses: bool = False,
        horizontal_gap: float = 0.75,
        vertical_gap: float = 0.85,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if not blocks:
            raise ValueError("a control-flow graph requires at least one block")
        if horizontal_gap < _MIN_CFG_GAP or vertical_gap < _MIN_CFG_GAP:
            raise ValueError(f"CFG layout gaps must be at least {_MIN_CFG_GAP:.2f}")
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
                else BasicBlock(
                    item,
                    width=block_width,
                    compact_addresses=compact_addresses,
                    theme=theme,
                )
            )
            self.block_mobjects[block.key] = block

        self._back_edge_indices = self._find_back_edges(keys)
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
        edge_group = VGroup()
        routes = self._edge_routes()
        label_obstacles: list[Mobject] = [
            block.background for block in self.block_mobjects.values()
        ]
        for index, spec in enumerate(self.edge_specs):
            kind = EdgeKind(spec.kind)
            edge_key = (spec.source, spec.target, kind)
            if edge_key in self.edge_mobjects:
                raise ValueError(f"duplicate {kind.value} edge {spec.source!r} -> {spec.target!r}")
            start, end, route_lane_x, label_side = routes[index]
            edge_view = _CFGEdge(
                spec,
                start=start,
                end=end,
                color=_edge_color(kind, theme),
                route_lane_x=route_lane_x,
                label_side=label_side,
                obstacles=tuple(label_obstacles),
                theme=theme,
            )
            self.edge_mobjects[edge_key] = edge_view
            edge_group.add(edge_view)
            if edge_view.label_background is not None:
                label_obstacles.append(edge_view.label_background)

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

    def _find_back_edges(self, keys: Sequence[str]) -> set[int]:
        """Return explicit loop and DFS back-edge indices in stable order."""

        adjacency: dict[str, list[tuple[int, str]]] = {key: [] for key in keys}
        back_edges = {
            index
            for index, edge in enumerate(self.edge_specs)
            if EdgeKind(edge.kind) is EdgeKind.LOOP or edge.source == edge.target
        }
        for index, edge in enumerate(self.edge_specs):
            if index not in back_edges:
                adjacency[edge.source].append((index, edge.target))

        state = {key: 0 for key in keys}
        for root in (self.entry, *(key for key in keys if key != self.entry)):
            if state[root] != 0:
                continue
            state[root] = 1
            stack = [(root, iter(adjacency[root]))]
            while stack:
                source, children = stack[-1]
                try:
                    index, target = next(children)
                except StopIteration:
                    state[source] = 2
                    stack.pop()
                    continue
                if state[target] == 0:
                    state[target] = 1
                    stack.append((target, iter(adjacency[target])))
                elif state[target] == 1:
                    back_edges.add(index)
        return back_edges

    def _compute_levels(self, keys: Sequence[str]) -> dict[str, int]:
        """Rank nodes by longest forward path, stacking disconnected components."""

        order = {key: index for index, key in enumerate(keys)}
        successors: dict[str, list[str]] = {key: [] for key in keys}
        predecessors: dict[str, list[str]] = {key: [] for key in keys}
        neighbors: dict[str, list[str]] = {key: [] for key in keys}
        for index, edge in enumerate(self.edge_specs):
            neighbors[edge.source].append(edge.target)
            neighbors[edge.target].append(edge.source)
            if index in self._back_edge_indices:
                continue
            if edge.target not in successors[edge.source]:
                successors[edge.source].append(edge.target)
                predecessors[edge.target].append(edge.source)

        components: list[tuple[str, ...]] = []
        remaining = set(keys)
        component_roots = (self.entry, *(key for key in keys if key != self.entry))
        for root in component_roots:
            if root not in remaining:
                continue
            queue: deque[str] = deque((root,))
            remaining.remove(root)
            members: list[str] = []
            while queue:
                node = queue.popleft()
                members.append(node)
                for neighbor in sorted(neighbors[node], key=order.__getitem__):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
            components.append(tuple(sorted(members, key=order.__getitem__)))

        levels: dict[str, int] = {}
        next_base = 0
        for component_nodes in components:
            component_set = set(component_nodes)
            indegree = {
                node: sum(pred in component_set for pred in predecessors[node])
                for node in component_nodes
            }
            ready = deque(node for node in component_nodes if indegree[node] == 0)
            topo_order: list[str] = []
            while ready:
                node = ready.popleft()
                topo_order.append(node)
                for target in successors[node]:
                    if target not in component_set:
                        continue
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        ready.append(target)
            if len(topo_order) != len(component_nodes):
                raise RuntimeError("CFG forward-edge classification did not produce a DAG")

            local_levels: dict[str, int] = {}
            for node in topo_order:
                incoming = [
                    local_levels[pred] for pred in predecessors[node] if pred in local_levels
                ]
                local_levels[node] = max(incoming, default=-1) + 1
            for node in component_nodes:
                levels[node] = next_base + local_levels[node]
            next_base = max(levels[node] for node in component_nodes) + 1
        return levels

    @staticmethod
    def _spread_offsets(count: int, span: float) -> tuple[float, ...]:
        if count <= 1:
            return (0.0,)
        return tuple(-span / 2 + span * index / (count - 1) for index in range(count))

    def _edge_routes(
        self,
    ) -> dict[int, tuple[Any, Any, float | None, float]]:
        """Resolve stable block ports and outside lanes from final block positions."""

        vertical_indices = [
            index
            for index, edge in enumerate(self.edge_specs)
            if index not in self._back_edge_indices
            and self.levels[edge.target] == self.levels[edge.source] + 1
            and self.block(edge.target).get_y() < self.block(edge.source).get_y() - 0.12
        ]
        horizontal_indices = [
            index
            for index, edge in enumerate(self.edge_specs)
            if index not in self._back_edge_indices
            and self.levels[edge.target] == self.levels[edge.source] + 1
            and abs(self.block(edge.target).get_y() - self.block(edge.source).get_y()) <= 0.12
            and abs(self.block(edge.target).get_x() - self.block(edge.source).get_x()) > 0.12
        ]
        outgoing: defaultdict[str, list[int]] = defaultdict(list)
        incoming: defaultdict[str, list[int]] = defaultdict(list)
        for index in vertical_indices:
            edge = self.edge_specs[index]
            outgoing[edge.source].append(index)
            incoming[edge.target].append(index)

        source_offsets: dict[int, float] = {}
        target_offsets: dict[int, float] = {}
        for source, indices in outgoing.items():
            indices.sort(
                key=lambda index: (
                    self.block(self.edge_specs[index].target).get_x(),
                    index,
                )
            )
            span = min(self.block(source).width * 0.7, 1.25)
            source_offsets.update(
                zip(indices, self._spread_offsets(len(indices), span), strict=True)
            )
        for target, indices in incoming.items():
            indices.sort(
                key=lambda index: (
                    self.block(self.edge_specs[index].source).get_x(),
                    index,
                )
            )
            span = min(self.block(target).width * 0.7, 1.25)
            target_offsets.update(
                zip(indices, self._spread_offsets(len(indices), span), strict=True)
            )

        left_bound = min(block.get_left()[0] for block in self.block_mobjects.values())
        right_bound = max(block.get_right()[0] for block in self.block_mobjects.values())
        center_x = (left_bound + right_bound) / 2
        lane_counts = {"left": 0, "right": 0}
        routes: dict[int, tuple[Any, Any, float | None, float]] = {}
        for index, edge in enumerate(self.edge_specs):
            source = self.block(edge.source)
            target = self.block(edge.target)
            if index in vertical_indices:
                start = source.get_bottom() + RIGHT * source_offsets[index]
                end = target.get_top() + RIGHT * target_offsets[index]
                label_side = -1 if target.get_x() < source.get_x() else 1
                routes[index] = (start, end, None, label_side)
                continue
            if index in horizontal_indices:
                if target.get_x() > source.get_x():
                    start = source.get_right()
                    end = target.get_left()
                    label_side = 1
                else:
                    start = source.get_left()
                    end = target.get_right()
                    label_side = -1
                routes[index] = (start, end, None, label_side)
                continue

            average_x = (source.get_x() + target.get_x()) / 2
            side = "right" if average_x >= center_x else "left"
            lane_index = lane_counts[side]
            lane_counts[side] += 1
            if side == "right":
                port_offset = min(source.height, target.height) * 0.24
                start = source.get_right() + UP * port_offset
                end = target.get_right() + DOWN * port_offset
                lane_x = right_bound + 0.46 + lane_index * 0.22
                label_side = -1
            else:
                port_offset = min(source.height, target.height) * 0.24
                start = source.get_left() + UP * port_offset
                end = target.get_left() + DOWN * port_offset
                lane_x = left_bound - 0.46 - lane_index * 0.22
                label_side = 1
            routes[index] = (start, end, lane_x, label_side)
        return routes

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
                Circumscribe(
                    mobject.background if isinstance(mobject, BasicBlock) else mobject,
                    color=color or self.theme.warning,
                    buff=max(0.04, (scale_factor - 1) * 0.7),
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

        traversal_color = color or self.theme.info
        animations: list[Animation] = [
            Circumscribe(
                self.block(path[0]).background,
                color=traversal_color,
                buff=0.05,
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
                    Circumscribe(
                        self.block(target).background,
                        color=traversal_color,
                        buff=0.05,
                        run_time=run_time,
                    ),
                )
            )
        return Succession(*animations)
