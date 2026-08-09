"""CPU, instruction, register, flag, and pipeline visualizations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Animation,
    AnimationGroup,
    Arrow,
    Circumscribe,
    Indicate,
    Rectangle,
    RoundedRectangle,
    Succession,
    Transform,
    VGroup,
)

from .architecture import ArchitectureSpec
from .models import InstructionSpec, PipelineInstruction, format_address
from .primitives import KeyValueRow, Panel, label_text, mono_text
from .refs import (
    AddressRangeRef,
    AddressRef,
    FlagRef,
    PipelineSlotRef,
    RegisterRef,
    VisualRef,
)
from .theme import DEFAULT_THEME, RevTheme


def _format_value(value: int | str, bits: int) -> str:
    if isinstance(value, int):
        width = max(1, bits // 4)
        return f"0x{value & ((1 << bits) - 1):0{width}X}"
    return str(value)


class InstructionView(Panel):
    """A disassembled instruction card with stable semantic sub-parts."""

    def __init__(
        self,
        instruction: InstructionSpec,
        *,
        width: float = 5.8,
        height: float = 1.15,
        address_width: int = 8,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__(width=width, height=height, theme=theme)
        self.instruction = instruction
        self.address = mono_text(
            format_address(instruction.address, width=address_width),
            font_size=18,
            color=theme.address,
            theme=theme,
        )
        self.raw_bytes = mono_text(
            instruction.bytes_text or "--",
            font_size=16,
            color=theme.muted,
            theme=theme,
        )
        self.mnemonic = mono_text(
            instruction.mnemonic,
            font_size=25,
            color=theme.opcode,
            theme=theme,
            weight="BOLD",
        )
        self.operands = mono_text(
            instruction.operands,
            font_size=22,
            color=theme.register,
            theme=theme,
        )
        assembly = VGroup(self.mnemonic, self.operands).arrange(RIGHT, buff=0.18)
        meta = VGroup(self.address, self.raw_bytes).arrange(DOWN, aligned_edge=LEFT, buff=0.09)
        content = VGroup(meta, assembly)
        self.comment = None
        if instruction.comment:
            self.comment = mono_text(
                f"; {instruction.comment}",
                font_size=15,
                color=theme.muted,
                theme=theme,
            )
            content.add(self.comment)
        content.arrange(RIGHT, buff=0.3)
        if content.width > width - 0.44:
            content.scale_to_fit_width(width - 0.44)
        content.move_to(self.background)
        content.align_to(self.background, LEFT).shift(RIGHT * 0.22)
        self.add(content)

    def resolve(self, ref: VisualRef) -> tuple[VGroup | Panel, ...]:
        if isinstance(ref, AddressRef) and ref.address == self.instruction.address:
            return (self,)
        if isinstance(ref, AddressRangeRef) and isinstance(self.instruction.address, int):
            instruction_start = self.instruction.address
            instruction_end = instruction_start + max(1, len(self.instruction.raw_bytes))
            range_end = ref.start + ref.length
            if instruction_start < range_end and instruction_end > ref.start:
                return (self,)
        return ()


class RegisterBank(Panel):
    """A register file whose values can be updated in-place or animated."""

    def __init__(
        self,
        registers: Mapping[str, int | str],
        *,
        bits: int = 64,
        columns: int = 1,
        width: float | None = None,
        title: str = "registers",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if columns < 1:
            raise ValueError("columns must be at least 1")
        if bits < 1:
            raise ValueError("register width must be positive")
        names = list(registers)
        if any(not name for name in names):
            raise ValueError("register names cannot be empty")
        folded_names = [name.casefold() for name in names]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("register names must be unique ignoring case")
        self.bits = bits
        self.columns = columns
        self._values = dict(registers)
        rows_per_column = max(1, (len(names) + columns - 1) // columns)
        panel_width = width or (3.05 * columns + 0.25)
        panel_height = 0.76 + rows_per_column * 0.39
        super().__init__(
            width=panel_width,
            height=panel_height,
            title=title,
            theme=theme,
        )
        self.rows: dict[str, KeyValueRow] = {}
        column_groups = VGroup()
        for column in range(columns):
            group = VGroup()
            for name in names[column * rows_per_column : (column + 1) * rows_per_column]:
                row = KeyValueRow(
                    name.upper(),
                    _format_value(registers[name], bits),
                    width=2.55,
                    font_size=18,
                    value_color=theme.register,
                    theme=theme,
                )
                self.rows[name] = row
                group.add(row)
            group.arrange(DOWN, buff=0.12, aligned_edge=LEFT)
            column_groups.add(group)
        column_groups.arrange(RIGHT, buff=0.32, aligned_edge=UP)
        column_groups.move_to(self.background).shift(DOWN * 0.16)
        self.add(column_groups)

    @classmethod
    def from_architecture(
        cls,
        architecture: ArchitectureSpec,
        values: Mapping[str, int | str],
        *,
        columns: int = 1,
        width: float | None = None,
        title: str | None = None,
        theme: RevTheme = DEFAULT_THEME,
    ) -> RegisterBank:
        """Build a bank with aliases normalized by an architecture snapshot."""

        normalized: dict[str, int | str] = {}
        for supplied_name, value in values.items():
            canonical = architecture.register(supplied_name).name
            if canonical in normalized:
                raise ValueError(f"multiple values supplied for register {canonical!r}")
            normalized[canonical] = value
        return cls(
            normalized,
            bits=architecture.bits,
            columns=columns,
            width=width,
            title=title or f"{architecture.name} registers",
            theme=theme,
        )

    def _key_for(self, register: str) -> str:
        for key in self.rows:
            if key.casefold() == register.casefold():
                return key
        raise KeyError(register)

    def __getitem__(self, register: str) -> KeyValueRow:
        return self.rows[self._key_for(register)]

    def set_value(self, register: str, value: int | str) -> RegisterBank:
        """Replace a register value immediately and return ``self``."""

        key = self._key_for(register)
        row = self.rows[key]
        target = mono_text(
            _format_value(value, self.bits),
            font_size=row.font_size,
            color=self.theme.register,
            theme=self.theme,
        )
        target.scale_to_fit_height(row.value.height)
        available_width = max(0.1, row.width - row.key.width - 0.08)
        if target.width > available_width:
            target.scale_to_fit_width(available_width)
        target.move_to(row.value, aligned_edge=RIGHT)
        row.value.become(target)
        self._values[key] = value
        return self

    def animate_set(
        self,
        register: str,
        value: int | str,
        *,
        color: str | None = None,
    ) -> Animation:
        """Build an animation that changes and emphasizes one register."""

        key = self._key_for(register)
        row = self.rows[key]
        target = mono_text(
            _format_value(value, self.bits),
            font_size=row.font_size,
            color=color or self.theme.register,
            theme=self.theme,
        )
        target.scale_to_fit_height(row.value.height)
        available_width = max(0.1, row.width - row.key.width - 0.08)
        if target.width > available_width:
            target.scale_to_fit_width(available_width)
        target.move_to(row.value, aligned_edge=RIGHT)
        self._values[key] = value
        return AnimationGroup(
            Transform(row.value, target),
            Circumscribe(row, color=color or self.theme.warning, buff=0.06),
        )

    def resolve(self, ref: VisualRef) -> tuple[VGroup, ...]:
        if not isinstance(ref, RegisterRef):
            return ()
        for name, row in self.rows.items():
            if name.casefold() == ref.name.casefold():
                return (row,)
        return ()


class FlagRegister(Panel):
    """A compact row of named CPU flags with true/false/unknown states."""

    def __init__(
        self,
        flags: Mapping[str, bool | None],
        *,
        title: str = "flags",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        names = list(flags)
        if any(not name for name in names):
            raise ValueError("flag names cannot be empty")
        folded_names = [name.casefold() for name in names]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("flag names must be unique ignoring case")
        width = max(2.2, len(flags) * 0.66 + 0.34)
        super().__init__(width=width, height=1.25, title=title, theme=theme)
        self._states = dict(flags)
        self.cells: dict[str, VGroup] = {}
        row = VGroup()
        for name, state in flags.items():
            cell = self._make_cell(name, state)
            self.cells[name] = cell
            row.add(cell)
        row.arrange(RIGHT, buff=0.08)
        row.move_to(self.background).shift(DOWN * 0.17)
        self.add(row)

    @classmethod
    def from_architecture(
        cls,
        architecture: ArchitectureSpec,
        flags: Mapping[str, bool | None] | None = None,
        *,
        title: str | None = None,
        theme: RevTheme = DEFAULT_THEME,
    ) -> FlagRegister:
        """Build a flag bank in architecture order with normalized names."""

        known = {flag.name.casefold(): flag.name for flag in architecture.flags}
        supplied = {flag.name: None for flag in architecture.flags} if flags is None else flags
        normalized: dict[str, bool | None] = {}
        for supplied_name, state in supplied.items():
            try:
                canonical = known[supplied_name.casefold()]
            except KeyError as error:
                raise KeyError(f"unknown {architecture.name} flag: {supplied_name}") from error
            if canonical in normalized:
                raise ValueError(f"multiple values supplied for flag {canonical!r}")
            normalized[canonical] = state
        return cls(
            normalized,
            title=title or f"{architecture.name} flags",
            theme=theme,
        )

    def _state_color(self, state: bool | None) -> str:
        if state is True:
            return self.theme.success
        if state is False:
            return self.theme.danger
        return self.theme.muted

    def _make_cell(self, name: str, state: bool | None) -> VGroup:
        background = RoundedRectangle(
            width=0.55,
            height=0.48,
            corner_radius=0.08,
            stroke_color=self._state_color(state),
            stroke_width=1.3,
            fill_color=self.theme.panel_alt,
            fill_opacity=1,
        )
        name_text = mono_text(name.upper(), font_size=14, color=self.theme.text, theme=self.theme)
        value_text = mono_text(
            "?" if state is None else int(state),
            font_size=13,
            color=self._state_color(state),
            theme=self.theme,
        )
        VGroup(name_text, value_text).arrange(DOWN, buff=0.01).move_to(background)
        return VGroup(background, name_text, value_text)

    def _key_for(self, flag: str) -> str:
        for key in self.cells:
            if key.casefold() == flag.casefold():
                return key
        raise KeyError(flag)

    def animate_set(self, flag: str, state: bool | None) -> Animation:
        key = self._key_for(flag)
        cell = self.cells[key]
        target = self._make_cell(key, state)
        target.scale_to_fit_width(cell.width).move_to(cell)
        self._states[key] = state
        return Transform(cell, target)

    def resolve(self, ref: VisualRef) -> tuple[VGroup, ...]:
        if not isinstance(ref, FlagRef):
            return ()
        for name, cell in self.cells.items():
            if name.casefold() == ref.name.casefold():
                return (cell,)
        return ()


@dataclass(frozen=True, slots=True)
class InstructionField:
    name: str
    width: int
    value: str
    color: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("instruction field name cannot be empty")
        if self.width <= 0:
            raise ValueError("instruction field width must be positive")


class InstructionEncoding(VGroup):
    """A proportional bit-field diagram for decoded instruction words."""

    def __init__(
        self,
        fields: Sequence[InstructionField],
        *,
        width: float = 7.0,
        height: float = 0.85,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if not fields:
            raise ValueError("instruction fields must have positive widths")
        self.fields = tuple(fields)
        folded_names = [field.name.casefold() for field in fields]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("instruction field names must be unique ignoring case")
        total_bits = sum(field.width for field in fields)
        palette = [theme.opcode, theme.register, theme.immediate, theme.info, theme.taint]
        cells = VGroup()
        self.field_mobjects: dict[str, VGroup] = {}
        for index, field in enumerate(fields):
            cell_width = width * field.width / total_bits
            box = Rectangle(
                width=cell_width,
                height=height,
                stroke_color=field.color or palette[index % len(palette)],
                stroke_width=1.8,
                fill_color=theme.panel,
                fill_opacity=1,
            )
            name = label_text(field.name, font_size=15, color=theme.muted, theme=theme)
            value = mono_text(
                field.value,
                font_size=17,
                color=field.color or palette[index % len(palette)],
                theme=theme,
            )
            VGroup(name, value).arrange(DOWN, buff=0.04).move_to(box)
            group = VGroup(box, name, value)
            self.field_mobjects[field.name] = group
            cells.add(group)
        cells.arrange(RIGHT, buff=0)
        self.add(cells)


class PipelineDiagram(Panel):
    """A cycle-indexed grid for simple in-order pipeline explanations."""

    def __init__(
        self,
        instructions: Sequence[PipelineInstruction | str],
        *,
        stages: Sequence[str] = ("IF", "ID", "EX", "MEM", "WB"),
        cell_width: float = 0.68,
        cell_height: float = 0.38,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if isinstance(instructions, (str, bytes)):
            raise TypeError("pipeline instructions must be a sequence, not a bare string")
        normalized = [
            item if isinstance(item, PipelineInstruction) else PipelineInstruction(item, index)
            for index, item in enumerate(instructions)
        ]
        if not stages:
            raise ValueError("pipeline requires at least one stage")
        if cell_width <= 0 or cell_height <= 0:
            raise ValueError("pipeline cell dimensions must be positive")
        self.instructions = tuple(normalized)
        self.stages = tuple(stages)
        if any(not stage for stage in self.stages):
            raise ValueError("pipeline stage names cannot be empty")
        folded_stages = [stage.casefold() for stage in self.stages]
        if len(folded_stages) != len(set(folded_stages)):
            raise ValueError("pipeline stage names must be unique ignoring case")
        self.schedule = [self._schedule(item) for item in normalized]
        self.squashed_slots = frozenset(
            (row_index, cycle)
            for row_index, item in enumerate(normalized)
            for cycle in self.schedule[row_index]
            if item.squashed
            or (item.squashed_at_cycle is not None and cycle == item.squashed_at_cycle)
        )
        max_cycle = max((max(row, default=-1) for row in self.schedule), default=-1)
        self.cycle_count = max_cycle + 1
        width = 1.82 + max(1, self.cycle_count) * cell_width
        height = 0.95 + max(1, len(normalized)) * cell_height
        super().__init__(width=width, height=height, title="pipeline", theme=theme)
        self.cells: dict[tuple[int, int], VGroup] = {}
        self.cycle_headers: dict[int, object] = {}
        origin = self.background.get_corner(UP + LEFT) + RIGHT * 1.55 + DOWN * 0.58
        headers = VGroup()
        for cycle in range(self.cycle_count):
            header = mono_text(cycle, font_size=13, color=theme.muted, theme=theme)
            header.move_to(origin + RIGHT * (cycle + 0.5) * cell_width)
            self.cycle_headers[cycle] = header
            headers.add(header)
        self.add(headers)
        palette = [theme.info, theme.opcode, theme.warning, theme.success, theme.taint]
        for row_index, item in enumerate(normalized):
            y = origin[1] - (row_index + 0.66) * cell_height
            instruction_label = mono_text(
                item.label,
                font_size=13,
                color=(
                    theme.danger
                    if item.squashed or item.squashed_at_cycle is not None
                    else theme.text
                ),
                theme=theme,
            )
            instruction_label.move_to(
                [self.background.get_left()[0] + 0.17, y, 0], aligned_edge=LEFT
            )
            self.add(instruction_label)
            for cycle, stage in self.schedule[row_index].items():
                is_stall = stage == "STALL"
                is_squashed = (row_index, cycle) in self.squashed_slots
                stage_index = self.stages.index(stage) if not is_stall else 0
                color = (
                    theme.danger if is_stall or is_squashed else palette[stage_index % len(palette)]
                )
                box = Rectangle(
                    width=cell_width,
                    height=cell_height,
                    stroke_color=theme.border,
                    stroke_width=0.8,
                    fill_color=color,
                    fill_opacity=0.2 if is_squashed else 0.34,
                )
                box.move_to([origin[0] + (cycle + 0.5) * cell_width, y, 0])
                text = mono_text(
                    "X" if is_squashed else ("•" if is_stall else stage),
                    font_size=12,
                    color=color,
                    theme=theme,
                ).move_to(box)
                cell = VGroup(box, text)
                self.cells[(row_index, cycle)] = cell
                self.add(cell)

    def _schedule(self, instruction: PipelineInstruction) -> dict[int, str]:
        schedule: dict[int, str] = {}
        cycle = instruction.start_cycle
        stage_index = 0
        stalled = set(instruction.stalled_cycles)
        while stage_index < len(self.stages):
            if instruction.squashed_at_cycle is not None and cycle > instruction.squashed_at_cycle:
                break
            if cycle in stalled:
                schedule[cycle] = "STALL"
            else:
                schedule[cycle] = self.stages[stage_index]
                stage_index += 1
            cycle += 1
        return schedule

    def highlight_cycle(self, cycle: int) -> Animation:
        """Emphasize every occupied slot in one cycle."""

        targets = [cell for (row, column), cell in self.cells.items() if column == cycle]
        if not targets:
            raise IndexError(f"cycle {cycle} has no occupied pipeline slots")
        return AnimationGroup(
            *(Indicate(cell, color=self.theme.warning, scale_factor=1.06) for cell in targets),
            lag_ratio=0.08,
        )

    def resolve(self, ref: VisualRef) -> tuple[VGroup, ...]:
        if not isinstance(ref, PipelineSlotRef):
            return ()
        cell = self.cells.get((ref.instruction, ref.cycle))
        return (cell,) if cell is not None else ()


class CPUBlockDiagram(VGroup):
    """A compact fetch/decode/execute/memory CPU data-path diagram."""

    DEFAULT_BLOCKS = ("Fetch", "Decode", "Registers", "Execute", "Memory", "Writeback")

    def __init__(
        self,
        *,
        blocks: Sequence[str] = DEFAULT_BLOCKS,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if isinstance(blocks, str):
            raise TypeError("CPU blocks must be a sequence of names, not one string")
        if len(blocks) < 2:
            raise ValueError("CPU diagram needs at least two blocks")
        if any(not name for name in blocks):
            raise ValueError("CPU block names cannot be empty")
        folded_names = [name.casefold() for name in blocks]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("CPU block names must be unique ignoring case")
        self.theme = theme
        self.blocks: dict[str, VGroup] = {}
        block_row = VGroup()
        for index, name in enumerate(blocks):
            color = [theme.info, theme.opcode, theme.register, theme.warning, theme.success][
                index % 5
            ]
            box = RoundedRectangle(
                width=1.45,
                height=0.78,
                corner_radius=0.1,
                stroke_color=color,
                stroke_width=1.6,
                fill_color=theme.panel,
                fill_opacity=1,
            )
            title = label_text(name, font_size=16, color=color, theme=theme)
            title.move_to(box)
            group = VGroup(box, title)
            self.blocks[name] = group
            block_row.add(group)
        block_row.arrange(RIGHT, buff=0.45)
        self.add(block_row)
        self.arrows = VGroup()
        for left, right in pairwise(block_row):
            arrow = Arrow(
                left.get_right(),
                right.get_left(),
                buff=0.05,
                stroke_width=2,
                max_tip_length_to_length_ratio=0.18,
                color=theme.muted,
            )
            self.arrows.add(arrow)
        self.add_to_back(self.arrows)

    def pulse(self, path: Sequence[str], *, color: str | None = None) -> Animation:
        """Animate data moving through a named sequence of CPU blocks."""

        if not path:
            raise ValueError("CPU pulse path cannot be empty")
        missing = [name for name in path if name not in self.blocks]
        if missing:
            raise KeyError(f"unknown CPU block(s): {', '.join(missing)}")
        return Succession(
            *(
                Indicate(
                    self.blocks[name],
                    color=color or self.theme.warning,
                    scale_factor=1.05,
                )
                for name in path
            )
        )
