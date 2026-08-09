"""Execution-trace rows, breakpoints, and memory-access visualizations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any, ClassVar

from manim import (
    DOWN,
    LEFT,
    PI,
    RIGHT,
    Animation,
    AnimationGroup,
    Dot,
    Indicate,
    Rectangle,
    RoundedRectangle,
    Transform,
    Triangle,
    VGroup,
)

from .models import AccessKind, Address, MemoryAccess, TraceEvent, TracePhase, format_address
from .primitives import Panel, mono_text
from .refs import (
    AddressRangeRef,
    AddressRef,
    ExecutedAddressRef,
    MemoryAddressRef,
    MemoryRangeRef,
    RegisterRef,
    VisualRef,
)
from .theme import DEFAULT_THEME, RevTheme

__all__ = [
    "ExecutionTrace",
    "MemoryAccessBadge",
    "TraceRow",
    "TraceTimeline",
]


def _format_scalar(value: int | bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"0x{value:X}"
    if isinstance(value, bytes):
        return " ".join(f"{byte:02X}" for byte in value)
    return str(value)


def _memory_contains(access: MemoryAccess, address: Address) -> bool:
    if isinstance(access.address, int) and isinstance(address, int):
        return access.address <= address < access.address + access.size
    return access.address == address


def _memory_intersects(access: MemoryAccess, start: int, end: int) -> bool:
    if not isinstance(access.address, int):
        return False
    return access.address < end and start < access.address + access.size


class MemoryAccessBadge(VGroup):
    """Compact read/write/execute annotation for one trace event."""

    _PREFIX: ClassVar[dict[AccessKind, str]] = {
        AccessKind.READ: "R",
        AccessKind.WRITE: "W",
        AccessKind.EXECUTE: "X",
    }

    def __init__(
        self,
        access: MemoryAccess | None,
        *,
        width: float = 2.55,
        height: float = 0.43,
        address_width: int = 8,
        additional_accesses: Sequence[MemoryAccess] = (),
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if access is not None and access.size < 1:
            raise ValueError("memory access size must be positive")
        if any(item.size < 1 for item in additional_accesses):
            raise ValueError("memory access size must be positive")
        self.access = access
        self.accesses = (() if access is None else (access,)) + tuple(additional_accesses)
        self.theme = theme
        self.address_width = address_width
        color = self._color(access)
        self.background = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.07,
            stroke_color=color,
            stroke_width=1,
            fill_color=color if access is not None else theme.panel_alt,
            fill_opacity=0.12 if access is not None else 1,
        )
        self.display = self._display_group()
        self.text = mono_text(
            self.display,
            font_size=12,
            color=color,
            theme=theme,
        )
        if self.text.width > width - 0.12:
            self.text.scale_to_fit_width(width - 0.12)
        if self.text.height > height - 0.08:
            self.text.scale_to_fit_height(height - 0.08)
        self.text.move_to(self.background)
        self.add(self.background, self.text)

    def _color(self, access: MemoryAccess | None) -> str:
        if access is None:
            return self.theme.muted
        return {
            AccessKind.READ: self.theme.info,
            AccessKind.WRITE: self.theme.danger,
            AccessKind.EXECUTE: self.theme.opcode,
        }[access.kind]

    def _display(self, access: MemoryAccess | None) -> str:
        if access is None:
            return "—"
        address = format_address(access.address, width=self.address_width)
        value = _format_scalar(access.value)
        suffix = f" = {value}" if value else ""
        return f"{self._PREFIX[access.kind]} [{address}] {access.size}B{suffix}"

    def _display_group(self) -> str:
        if len(self.accesses) <= 1:
            return self._display(self.access)
        visible = self.accesses[:2]
        parts = [
            f"{self._PREFIX[item.kind]} [{format_address(item.address, width=self.address_width)}]"
            for item in visible
        ]
        if len(self.accesses) > len(visible):
            parts[-1] += f"  +{len(self.accesses) - len(visible)}"
        return "\n".join(parts)

    def highlight(
        self,
        *,
        access: MemoryAccess | None = None,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        """Return an emphasis animation for this memory access."""

        selected = access or self.access
        if selected is None:
            raise LookupError("trace event has no memory access")
        return Indicate(
            self,
            color=color or self._color(selected),
            scale_factor=1.05,
            run_time=run_time,
        )


class TraceRow(VGroup):
    """One instruction event with breakpoint and memory-access handles."""

    def __init__(
        self,
        event: TraceEvent,
        index: int,
        *,
        width: float = 8.25,
        height: float = 0.66,
        breakpoint: bool = False,
        address_width: int = 8,
        show_registers: bool = True,
        show_memory: bool = True,
        memory_width: float = 2.55,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        if width < 5.2:
            raise ValueError("trace row width must be at least 5.2")
        if height < 0.35:
            raise ValueError("trace row height must be at least 0.35")
        if memory_width < 1.2:
            raise ValueError("memory_width must be at least 1.2")
        self.event = event
        self.memory_accesses = event.memory_accesses
        self.index = index
        self.theme = theme
        self.is_breakpoint = breakpoint
        self.is_active = False
        self.background = Rectangle(
            width=width,
            height=height,
            stroke_color=theme.border,
            stroke_width=1,
            fill_color=theme.panel,
            fill_opacity=1,
        )
        # Background transforms can be temporarily promoted by the renderer;
        # an explicit z-index keeps the row's text visible throughout stepping.
        self.background.set_z_index(-1)
        self.breakpoint_marker = Dot(radius=0.055, color=theme.danger)
        self.breakpoint_marker.set_opacity(1 if breakpoint else 0.14)
        self.index_text = mono_text(
            f"{index:02d}",
            font_size=12,
            color=theme.muted,
            theme=theme,
        )
        if self.index_text.width > 0.32:
            self.index_text.scale_to_fit_width(0.32)
        self.address_text = mono_text(
            format_address(event.address, width=address_width),
            font_size=14,
            color=theme.address,
            theme=theme,
        )
        self.instruction_text = mono_text(
            event.instruction,
            font_size=17,
            color=theme.text,
            theme=theme,
        )
        details: list[str] = []
        if event.phase is not TracePhase.UNKNOWN:
            details.append("PRE-STATE" if event.phase is TracePhase.BEFORE else "POST-STATE")
        if show_registers and event.registers:
            details.append(
                " ".join(
                    f"{name}={_format_scalar(value)}" for name, value in event.registers.items()
                )
            )
        if event.note:
            details.append(event.note)
        self.detail_text = mono_text(
            "  •  ".join(details),
            font_size=10,
            color=theme.muted,
            theme=theme,
        )
        self.instruction_group = VGroup(self.instruction_text)
        if details:
            self.instruction_group.add(self.detail_text)
            self.instruction_group.arrange(DOWN, buff=0.035, aligned_edge=LEFT)

        self.memory_view: MemoryAccessBadge | None = None
        if show_memory:
            memory_height = 0.62 if len(event.memory_accesses) > 1 else 0.43
            self.memory_view = MemoryAccessBadge(
                event.memory,
                width=memory_width,
                height=min(memory_height, height - 0.08),
                address_width=address_width,
                additional_accesses=event.memory_accesses[1:],
                theme=theme,
            )
        left_x = self.background.get_left()[0]
        self.breakpoint_marker.move_to([left_x + 0.13, 0, 0])
        self.index_text.move_to([left_x + 0.38, 0, 0])
        self.address_text.move_to([left_x + 0.69, 0, 0], aligned_edge=LEFT)
        instruction_x = left_x + 2.16
        if self.memory_view is not None:
            self.memory_view.move_to(
                self.background.get_right() + LEFT * 0.12,
                aligned_edge=RIGHT,
            )
            instruction_right = self.memory_view.get_left()[0] - 0.12
        else:
            instruction_right = self.background.get_right()[0] - 0.12
        available_width = instruction_right - instruction_x
        for text in (self.instruction_text, self.detail_text):
            if text.width > available_width:
                text.scale_to_fit_width(available_width)
        self.instruction_group.move_to([instruction_x, 0, 0], aligned_edge=LEFT)
        row_parts = [
            self.background,
            self.breakpoint_marker,
            self.index_text,
            self.address_text,
            self.instruction_group,
        ]
        if self.memory_view is not None:
            row_parts.append(self.memory_view)
        self.add(*row_parts)

    def _background_target(self, active: bool):  # type: ignore[no-untyped-def]
        target = self.background.copy()
        target.set_fill(
            self.theme.info if active else self.theme.panel,
            opacity=0.16 if active else 1,
        )
        target.set_stroke(
            self.theme.info if active else self.theme.border,
            width=1.7 if active else 1,
        )
        return target

    def set_active(self, active: bool = True) -> TraceRow:
        """Set the active-row style immediately."""

        self.is_active = active
        self.background.become(self._background_target(active))
        return self

    def animate_active(self, active: bool = True) -> Animation:
        """Build an animation that changes the active-row style."""

        self.is_active = active
        return Transform(self.background, self._background_target(active))

    def set_breakpoint(self, enabled: bool = True) -> TraceRow:
        """Show or hide the breakpoint marker immediately."""

        self.is_breakpoint = enabled
        self.breakpoint_marker.set_opacity(1 if enabled else 0.14)
        return self

    def animate_breakpoint(self, enabled: bool = True) -> Animation:
        """Build an animation that shows or hides the breakpoint marker."""

        self.is_breakpoint = enabled
        target = self.breakpoint_marker.copy().set_opacity(1 if enabled else 0.14)
        return Transform(self.breakpoint_marker, target)

    def highlight(
        self,
        *,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        return Indicate(
            self,
            color=color or self.theme.warning,
            scale_factor=1.02,
            run_time=run_time,
        )


class ExecutionTrace(Panel):
    """A step-able dynamic execution trace with breakpoint support."""

    def __init__(
        self,
        events: Sequence[TraceEvent],
        *,
        breakpoints: Sequence[Address] = (),
        width: float = 8.8,
        row_height: float = 0.66,
        address_width: int = 8,
        show_registers: bool = True,
        show_memory: bool = True,
        memory_width: float = 2.55,
        start_index: int | None = None,
        index_offset: int = 0,
        title: str = "execution trace",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width < 5.75:
            raise ValueError("trace width must be at least 5.75")
        if row_height < 0.35:
            raise ValueError("row_height must be at least 0.35")
        if index_offset < 0:
            raise ValueError("index_offset must be non-negative")
        self.events = tuple(events)
        self.index_offset = index_offset
        self._breakpoints = set(breakpoints)
        executed_addresses = {event.address for event in self.events}
        absent_breakpoints = self._breakpoints - executed_addresses
        if absent_breakpoints:
            absent = ", ".join(repr(address) for address in absent_breakpoints)
            raise KeyError(f"breakpoint address(es) absent from trace: {absent}")
        row_items = tuple(
            TraceRow(
                event,
                index + index_offset,
                width=width - 0.52,
                height=row_height,
                breakpoint=event.address in self._breakpoints,
                address_width=address_width,
                show_registers=show_registers,
                show_memory=show_memory,
                memory_width=memory_width,
                theme=theme,
            )
            for index, event in enumerate(self.events)
        )
        self.rows = row_items
        self.row_group = VGroup(*row_items)
        if row_items:
            self.row_group.arrange(DOWN, buff=0.045)
            content_height = self.row_group.height
        else:
            self.empty_label = mono_text(
                "<empty trace>", font_size=15, color=theme.muted, theme=theme
            )
            content_height = max(row_height, self.empty_label.height)
        panel_height = content_height + (0.76 if title else 0.36)
        super().__init__(
            width=width,
            height=panel_height,
            title=title or None,
            theme=theme,
        )

        by_address: defaultdict[Address, list[TraceRow]] = defaultdict(list)
        for row in row_items:
            by_address[row.event.address].append(row)
        self.rows_by_address = {
            address: tuple(address_rows) for address, address_rows in by_address.items()
        }
        if row_items:
            self.row_group.move_to(self.background).shift(DOWN * (0.18 if title else 0))
            self.add(self.row_group)
        else:
            self.empty_label.move_to(self.background).shift(DOWN * (0.16 if title else 0))
            self.add(self.empty_label)

        self.cursor = Triangle(
            stroke_color=theme.info,
            stroke_width=1,
            fill_color=theme.info,
            fill_opacity=1,
        )
        self.cursor.scale_to_fit_height(min(0.17, row_height * 0.34)).rotate(-PI / 2)
        if row_items:
            self.cursor.next_to(row_items[0].background, LEFT, buff=0.035)
        else:
            self.cursor.move_to(self.background.get_left() + RIGHT * 0.12)
        self.current_index: int | None = None
        self.cursor.set_opacity(0)
        self.add(self.cursor)
        if start_index is not None:
            self._validate_index(start_index)
            self.current_index = start_index
            row_items[start_index].set_active()
            self.cursor.next_to(row_items[start_index].background, LEFT, buff=0.035)
            self.cursor.set_opacity(1)

    @classmethod
    def window(
        cls,
        events: Sequence[TraceEvent],
        *,
        start: int,
        count: int = 7,
        breakpoints: Sequence[Address] = (),
        title: str = "execution trace",
        **kwargs: Any,
    ) -> ExecutionTrace:
        """Build a readable slice of a longer trace while retaining event numbers.

        Row lookup, stepping, and highlighting use local indexes within the visible
        window. The row labels keep their original indexes from ``events``.
        Breakpoints outside the window are omitted so callers can pass a complete
        breakpoint set while paging through a recording.
        """

        if start < 0:
            raise ValueError("window start must be non-negative")
        if count < 1:
            raise ValueError("window count must be positive")
        if start >= len(events):
            raise IndexError(f"trace window start {start} is out of range")
        stop = min(start + count, len(events))
        visible = tuple(events[start:stop])
        visible_addresses = {event.address for event in visible}
        visible_breakpoints = tuple(
            address for address in breakpoints if address in visible_addresses
        )
        context = f"events {start}-{stop - 1} of {len(events)}"
        window_title = f"{title} · {context}" if title else context
        return cls(
            visible,
            breakpoints=visible_breakpoints,
            index_offset=start,
            title=window_title,
            **kwargs,
        )

    @property
    def breakpoints(self) -> frozenset[Address]:
        return frozenset(self._breakpoints)

    @property
    def current_event(self) -> TraceEvent | None:
        if self.current_index is None:
            return None
        return self.events[self.current_index]

    @property
    def current_row(self) -> TraceRow | None:
        """Return the row under the cursor, or ``None`` before execution."""

        if self.current_index is None:
            return None
        return self.rows[self.current_index]

    @property
    def at_breakpoint(self) -> bool:
        event = self.current_event
        return event is not None and event.address in self._breakpoints

    def _validate_index(self, index: int) -> None:
        if not 0 <= index < len(self.events):
            raise IndexError(f"trace event index {index} is out of range")

    def event(self, index: int) -> TraceEvent:
        """Return an event by its stable zero-based index."""

        self._validate_index(index)
        return self.events[index]

    def row(self, index: int) -> TraceRow:
        """Return a row by its stable zero-based index."""

        self._validate_index(index)
        return self.rows[index]

    def rows_for_address(
        self,
        address: Address,
        *,
        include_memory: bool = False,
    ) -> tuple[TraceRow, ...]:
        """Return rows executing, or optionally accessing, an address."""

        return tuple(
            row
            for row in self.rows
            if row.event.address == address
            or (
                include_memory
                and any(_memory_contains(access, address) for access in row.event.memory_accesses)
            )
        )

    def row_for_address(
        self,
        address: Address,
        *,
        occurrence: int = 0,
        include_memory: bool = False,
    ) -> TraceRow:
        """Return one row matching an address and occurrence number."""

        rows = self.rows_for_address(address, include_memory=include_memory)
        if not 0 <= occurrence < len(rows):
            raise KeyError(f"address {address!r} occurrence {occurrence} is not in the trace")
        return rows[occurrence]

    def has_breakpoint(self, address: Address) -> bool:
        return address in self._breakpoints

    def _breakpoint_rows(self, address: Address) -> tuple[TraceRow, ...]:
        rows = self.rows_by_address.get(address, ())
        if not rows:
            raise KeyError(f"cannot place a breakpoint at absent trace address {address!r}")
        return rows

    def set_breakpoint(
        self,
        address: Address,
        enabled: bool = True,
    ) -> ExecutionTrace:
        """Show or hide all markers at an executed address immediately."""

        rows = self._breakpoint_rows(address)
        if enabled:
            self._breakpoints.add(address)
        else:
            self._breakpoints.discard(address)
        for row in rows:
            row.set_breakpoint(enabled)
        return self

    def animate_breakpoint(
        self,
        address: Address,
        enabled: bool = True,
        *,
        run_time: float = 0.35,
    ) -> Animation:
        """Build an animation that changes every marker at an address."""

        rows = self._breakpoint_rows(address)
        if enabled:
            self._breakpoints.add(address)
        else:
            self._breakpoints.discard(address)
        return AnimationGroup(
            *(row.animate_breakpoint(enabled) for row in rows),
            lag_ratio=0,
            run_time=run_time,
        )

    def toggle_breakpoint(
        self,
        address: Address,
        *,
        run_time: float = 0.35,
    ) -> Animation:
        """Build an animation toggling an executed address's breakpoint."""

        return self.animate_breakpoint(
            address,
            not self.has_breakpoint(address),
            run_time=run_time,
        )

    def step(
        self,
        index: int | None = None,
        *,
        run_time: float = 0.45,
    ) -> Animation:
        """Advance one event, or move directly to ``index``."""

        if index is None:
            index = 0 if self.current_index is None else self.current_index + 1
            if index >= len(self.events):
                raise StopIteration("execution trace is already at its final event")
        return self.step_to(index, run_time=run_time)

    def step_to(self, index: int, *, run_time: float = 0.45) -> Animation:
        """Build the cursor and row transition to an event index."""

        self._validate_index(index)
        target_row = self.rows[index]
        if self.current_index == index:
            return target_row.highlight(color=self.theme.info, run_time=run_time)
        animations: list[Animation] = []
        if self.current_index is not None:
            animations.append(self.rows[self.current_index].animate_active(False))
        animations.append(target_row.animate_active(True))
        cursor_target = self.cursor.copy()
        cursor_target.next_to(target_row.background, LEFT, buff=0.035)
        cursor_target.set_opacity(1)
        animations.append(Transform(self.cursor, cursor_target))
        self.current_index = index
        return AnimationGroup(*animations, lag_ratio=0, run_time=run_time)

    def next_breakpoint_index(self) -> int | None:
        """Return the next breakpoint event after the current cursor."""

        start = 0 if self.current_index is None else self.current_index + 1
        for index in range(start, len(self.events)):
            if self.events[index].address in self._breakpoints:
                return index
        return None

    def run_to_breakpoint(self, *, run_time: float = 0.65) -> Animation:
        """Build a cursor transition to the next breakpoint."""

        index = self.next_breakpoint_index()
        if index is None:
            raise LookupError("no later breakpoint exists in this trace")
        return self.step_to(index, run_time=run_time)

    def reset(self) -> ExecutionTrace:
        """Reset the cursor immediately to its pre-execution state."""

        if self.current_index is not None:
            self.rows[self.current_index].set_active(False)
        self.current_index = None
        self.cursor.set_opacity(0)
        return self

    def animate_reset(self, *, run_time: float = 0.35) -> Animation:
        """Build an animation that returns to the pre-execution state."""

        animations: list[Animation] = []
        if self.current_index is not None:
            animations.append(self.rows[self.current_index].animate_active(False))
        cursor_target = self.cursor.copy().set_opacity(0)
        animations.append(Transform(self.cursor, cursor_target))
        self.current_index = None
        return AnimationGroup(*animations, lag_ratio=0, run_time=run_time)

    def highlight_memory_access(
        self,
        index: int,
        *,
        occurrence: int = 0,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        """Emphasize the memory-access badge for one event."""

        row = self.row(index)
        memory_view = row.memory_view
        if memory_view is None:
            raise LookupError("memory-access badges are hidden for this trace")
        if not row.memory_accesses:
            raise LookupError("trace event has no memory access")
        if not 0 <= occurrence < len(row.memory_accesses):
            raise LookupError(
                f"memory access occurrence {occurrence} is out of range "
                f"for event {index} ({len(row.memory_accesses)} access(es))"
            )
        return memory_view.highlight(
            access=row.memory_accesses[occurrence],
            color=color,
            run_time=run_time,
        )

    def resolve(self, ref: VisualRef) -> tuple[TraceRow, ...]:
        if isinstance(ref, ExecutedAddressRef):
            return self.rows_for_address(ref.address)
        if isinstance(ref, MemoryAddressRef):
            return tuple(
                row
                for row in self.rows
                if any(
                    _memory_contains(access, ref.address) for access in row.event.memory_accesses
                )
            )
        if isinstance(ref, MemoryRangeRef):
            end = ref.start + ref.length
            return tuple(
                row
                for row in self.rows
                if any(
                    _memory_intersects(access, ref.start, end)
                    for access in row.event.memory_accesses
                )
            )
        if isinstance(ref, AddressRef):
            return self.rows_for_address(ref.address, include_memory=True)
        if isinstance(ref, AddressRangeRef):
            end = ref.start + ref.length
            matches: list[TraceRow] = []
            for row in self.rows:
                event_address = row.event.address
                executes_range = isinstance(event_address, int) and ref.start <= event_address < end
                accesses_range = any(
                    _memory_intersects(access, ref.start, end)
                    for access in row.event.memory_accesses
                )
                if executes_range or accesses_range:
                    matches.append(row)
            return tuple(matches)
        if isinstance(ref, RegisterRef):
            folded = ref.name.casefold()
            return tuple(
                row
                for row in self.rows
                if any(name.casefold() == folded for name in row.event.registers)
            )
        return ()


# A descriptive alias for users who prefer timeline terminology in talks.
TraceTimeline = ExecutionTrace
