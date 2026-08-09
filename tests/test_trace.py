from __future__ import annotations

import pytest
from manim import Animation

from manim_rev.models import AccessKind, MemoryAccess, TraceEvent, TracePhase
from manim_rev.refs import (
    AddressRangeRef,
    AddressRef,
    ExecutedAddressRef,
    MemoryAddressRef,
    MemoryRangeRef,
    RegisterRef,
)
from manim_rev.trace import ExecutionTrace, MemoryAccessBadge, TraceTimeline


def _events() -> list[TraceEvent]:
    return [
        TraceEvent(0x401000, "mov rax, [rbx]", {"rax": 0}, note="load input"),
        TraceEvent(
            0x401004,
            "mov [rcx], al",
            {"rax": 0x41, "rcx": 0x600100},
            MemoryAccess(0x600100, 1, AccessKind.WRITE, 0x41),
        ),
        TraceEvent(
            0x401007,
            "cmp al, 0",
            {"rax": 0x41},
            MemoryAccess(0x600100, 4, AccessKind.READ, b"ABCD"),
        ),
    ]


def test_trace_rows_events_and_memory_access_display() -> None:
    trace = ExecutionTrace(_events(), breakpoints=(0x401007,))

    assert trace.event(1) is trace.events[1]
    assert trace.row_for_address(0x401004) is trace.rows[1]
    assert trace.rows[2].is_breakpoint
    assert trace.rows[1].memory_view.access is trace.events[1].memory
    assert trace.rows[1].memory_view.display == "W [0x00600100] 1B = 0x41"
    assert trace.rows[2].memory_view.display.endswith("= 41 42 43 44")
    assert TraceTimeline is ExecutionTrace

    empty_badge = MemoryAccessBadge(None)
    assert empty_badge.display == "—"
    with pytest.raises(LookupError, match="no memory"):
        empty_badge.highlight()


def test_trace_step_and_run_to_breakpoint_update_logical_state() -> None:
    trace = ExecutionTrace(_events(), breakpoints=(0x401007,))

    assert trace.current_event is None
    assert trace.current_row is None
    assert isinstance(trace.step(), Animation)
    assert trace.current_index == 0
    assert trace.current_event is trace.event(0)
    assert trace.current_row is trace.row(0)
    assert not trace.at_breakpoint
    assert trace.next_breakpoint_index() == 2
    assert isinstance(trace.run_to_breakpoint(), Animation)
    assert trace.current_index == 2
    assert trace.at_breakpoint
    with pytest.raises(StopIteration, match="final"):
        trace.step()
    assert trace.reset() is trace
    assert trace.current_index is None
    assert trace.current_row is None


def test_trace_breakpoints_and_memory_highlights_are_animated() -> None:
    trace = ExecutionTrace(_events())

    assert isinstance(trace.animate_breakpoint(0x401004), Animation)
    assert trace.has_breakpoint(0x401004)
    assert trace.rows[1].is_breakpoint
    assert isinstance(trace.toggle_breakpoint(0x401004), Animation)
    assert not trace.has_breakpoint(0x401004)
    assert isinstance(trace.highlight_memory_access(1), Animation)
    with pytest.raises(LookupError, match="no memory"):
        trace.highlight_memory_access(0)
    with pytest.raises(KeyError, match="absent"):
        trace.set_breakpoint(0xDEADBEEF)
    with pytest.raises(KeyError, match="absent from trace"):
        ExecutionTrace(_events(), breakpoints=(0xDEADBEEF,))


def test_trace_resolves_code_memory_ranges_and_registers() -> None:
    trace = ExecutionTrace(_events())

    assert trace.resolve(AddressRef(0x401000)) == (trace.rows[0],)
    assert trace.resolve(AddressRef(0x600102)) == (trace.rows[2],)
    assert trace.resolve(AddressRangeRef(0x6000FF, 3)) == (
        trace.rows[1],
        trace.rows[2],
    )
    assert trace.resolve(RegisterRef("RAX")) == tuple(trace.rows)
    assert trace.rows_for_address(0x600100, include_memory=True) == (
        trace.rows[1],
        trace.rows[2],
    )
    with pytest.raises(IndexError, match="out of range"):
        trace.event(-1)


def test_trace_semantic_address_refs_disambiguate_execution_and_memory() -> None:
    events = [
        TraceEvent(
            0x401000,
            "load",
            memory=MemoryAccess(0x401000, 4, AccessKind.READ),
        ),
        TraceEvent(
            0x401004,
            "store",
            memory=MemoryAccess(0x401000, 2, AccessKind.WRITE),
        ),
    ]
    trace = ExecutionTrace(events)

    assert trace.resolve(ExecutedAddressRef(0x401000)) == (trace.rows[0],)
    assert trace.resolve(MemoryAddressRef(0x401000)) == tuple(trace.rows)
    assert trace.resolve(MemoryRangeRef(0x401002, 2)) == (trace.rows[0],)
    assert trace.resolve(AddressRef(0x401000)) == tuple(trace.rows)


def test_trace_renders_phase_and_resolves_every_memory_access() -> None:
    read = MemoryAccess(0x600000, 1, AccessKind.READ, b"A")
    write = MemoryAccess(0x700000, 1, AccessKind.WRITE, b"A")
    event = TraceEvent(
        0x401000,
        "movsb",
        {"rsi": 0x600000, "rdi": 0x700000},
        phase=TracePhase.AFTER,
        memory_accesses=(read, write),
    )
    trace = ExecutionTrace((event,))

    assert trace.rows[0].memory_view is not None
    assert trace.rows[0].memory_view.display == "R [0x00600000]\nW [0x00700000]"
    assert "POST-STATE".replace(" ", "") in trace.rows[0].detail_text.text
    assert trace.resolve(MemoryAddressRef(0x700000)) == (trace.rows[0],)
    assert trace.resolve(MemoryRangeRef(0x6FFFFF, 2)) == (trace.rows[0],)
    assert isinstance(trace.highlight_memory_access(0, occurrence=1), Animation)
    with pytest.raises(LookupError, match="occurrence 2"):
        trace.highlight_memory_access(0, occurrence=2)


def test_trace_can_hide_memory_column_without_reserving_a_badge() -> None:
    events = [
        TraceEvent(
            0x401000,
            "mov rax, qword ptr [rbx + rcx*8 + 0x12345678] ; long decoded operation",
        )
    ]
    shown = ExecutionTrace(events, show_memory=True)
    hidden = ExecutionTrace(events, show_memory=False)

    assert shown.rows[0].memory_view is not None
    assert hidden.rows[0].memory_view is None
    assert hidden.rows[0].instruction_text.width > shown.rows[0].instruction_text.width
    assert not any(isinstance(mobject, MemoryAccessBadge) for mobject in hidden.get_family())
    with pytest.raises(LookupError, match="hidden"):
        hidden.highlight_memory_access(0)


def test_trace_window_retains_original_row_indexes_and_filters_breakpoints() -> None:
    events = _events()
    trace = ExecutionTrace.window(
        events,
        start=1,
        count=2,
        breakpoints=(events[0].address, events[2].address),
        title="recording",
    )

    assert trace.events == tuple(events[1:])
    assert trace.index_offset == 1
    assert tuple(row.index for row in trace.rows) == (1, 2)
    assert trace.breakpoints == frozenset({events[2].address})
    assert trace.title_mobject is not None
    assert trace.title_mobject.text == "RECORDING·EVENTS1-2OF3"
    assert trace.event(0) is events[1]

    with pytest.raises(ValueError, match="non-negative"):
        ExecutionTrace.window(events, start=-1)
    with pytest.raises(ValueError, match="positive"):
        ExecutionTrace.window(events, start=0, count=0)
    with pytest.raises(IndexError, match="out of range"):
        ExecutionTrace.window(events, start=len(events))
