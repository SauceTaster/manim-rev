from __future__ import annotations

from copy import deepcopy

import pytest

from manim_rev.models import (
    AccessKind,
    BasicBlockSpec,
    CFGEdgeSpec,
    InstructionSpec,
    MemoryAccess,
    MemorySegmentSpec,
    PipelineInstruction,
    StateStatus,
    SymbolicStateSpec,
    TraceEvent,
    TracePhase,
    format_address,
)


def test_format_address_preserves_symbols_and_expands_large_values() -> None:
    assert format_address(0x2A) == "0x0000002A"
    assert format_address(0x1_0000_0000) == "0x100000000"
    assert format_address("entry+4") == "entry+4"
    with pytest.raises(ValueError, match="non-negative"):
        format_address(-1)
    with pytest.raises(ValueError, match="width"):
        format_address(0, width=0)
    with pytest.raises(ValueError, match="empty"):
        format_address("  ")


def test_models_snapshot_mutable_sequences() -> None:
    instructions = [InstructionSpec(0x1000, "ret")]
    block = BasicBlockSpec("entry", 0x1000, instructions)
    instructions.append(InstructionSpec(0x1001, "nop"))
    assert len(block.instructions) == 1
    assert isinstance(block.instructions, tuple)


def test_sequence_fields_reject_bare_strings_and_invalid_members() -> None:
    with pytest.raises(TypeError, match=r"instructions.*bare string"):
        BasicBlockSpec("entry", 0x1000, "nop")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="InstructionSpec or str"):
        BasicBlockSpec("entry", 0x1000, [1])  # type: ignore[list-item]
    with pytest.raises(TypeError, match=r"constraints.*bare string"):
        SymbolicStateSpec("s0", 0x1000, "x > 0")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="only str"):
        SymbolicStateSpec("s0", 0x1000, [1])  # type: ignore[list-item]


def test_validations_reject_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="greater than start"):
        MemorySegmentSpec("bad", 0x2000, 0x1000)
    with pytest.raises(ValueError, match="non-negative"):
        PipelineInstruction("bad", -1)
    with pytest.raises(ValueError, match="instruction address"):
        InstructionSpec(-1, "nop")
    with pytest.raises(ValueError, match="segment start"):
        MemorySegmentSpec("bad", -1, 1)


def test_symbolic_constraints_are_immutable_snapshot() -> None:
    constraints = ["x > 4"]
    state = SymbolicStateSpec("s0", 0x401000, constraints)
    constraints.append("x < 9")
    assert state.constraints == ("x > 4",)


@pytest.mark.parametrize("key", ("", "   ", "\t\n"))
def test_symbolic_state_key_cannot_be_empty(key: str) -> None:
    with pytest.raises(ValueError, match="key cannot be empty"):
        SymbolicStateSpec(key, 0x401000)


def test_enums_and_mappings_are_normalized_to_immutable_snapshots() -> None:
    registers = {"rax": 1}
    event = TraceEvent(0x1000, "nop", registers)
    registers["rax"] = 2
    assert event.registers["rax"] == 1
    assert deepcopy(event) == event
    assert CFGEdgeSpec("a", "b", "call").kind.value == "call"  # type: ignore[arg-type]
    assert MemoryAccess(0x2000, kind="write").kind is AccessKind.WRITE  # type: ignore[arg-type]
    assert SymbolicStateSpec("s", 0, status="found").status is StateStatus.FOUND  # type: ignore[arg-type]


def test_trace_event_normalizes_phase_and_memory_compatibility_views() -> None:
    first = MemoryAccess(0x2000, kind="read")  # type: ignore[arg-type]
    second = MemoryAccess(0x3000, kind="write")  # type: ignore[arg-type]

    legacy = TraceEvent(0x1000, "nop", {}, first, "legacy")
    assert legacy.memory is first
    assert legacy.memory_accesses == (first,)
    assert legacy.note == "legacy"
    assert legacy.phase is TracePhase.UNKNOWN

    multi = TraceEvent(
        0x1000,
        "movsb",
        phase="after",  # type: ignore[arg-type]
        memory_accesses=[first, second],
    )
    assert multi.phase is TracePhase.AFTER
    assert multi.memory is first
    assert multi.memory_accesses == (first, second)
    assert isinstance(multi.memory_accesses, tuple)

    with pytest.raises(ValueError, match="either memory or memory_accesses"):
        TraceEvent(0x1000, "movsb", memory=first, memory_accesses=(second,))
    with pytest.raises(TypeError, match="only MemoryAccess"):
        TraceEvent(0x1000, "nop", memory_accesses=["read"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="memory must be"):
        TraceEvent(0x1000, "nop", memory="read")  # type: ignore[arg-type]


def test_memory_and_pipeline_sizes_must_be_positive() -> None:
    with pytest.raises(ValueError, match="access size"):
        MemoryAccess(0x2000, size=0)
    with pytest.raises(ValueError, match="stalled cycles"):
        PipelineInstruction("bad stall", 0, stalled_cycles=(-1,))
    with pytest.raises(ValueError, match="precede"):
        PipelineInstruction("early stall", 3, stalled_cycles=(2,))
    with pytest.raises(ValueError, match="squash cycle"):
        PipelineInstruction("early squash", 3, squashed_at_cycle=2)
    with pytest.raises(ValueError, match="either"):
        PipelineInstruction("ambiguous squash", 0, squashed=True, squashed_at_cycle=2)


def test_memory_byte_values_must_exactly_match_access_size() -> None:
    assert MemoryAccess(0x2000, size=4, value=b"ABCD").value == b"ABCD"
    with pytest.raises(ValueError, match="length must equal"):
        MemoryAccess(0x2000, size=4, value=b"ABC")
    with pytest.raises(ValueError, match="length must equal"):
        MemoryAccess(0x2000, size=4, value=b"ABCDE")


def test_pipeline_stall_cycles_are_sorted_and_deduplicated() -> None:
    instruction = PipelineInstruction("load", 1, stalled_cycles=(4, 2, 4, 3))
    assert instruction.stalled_cycles == (2, 3, 4)


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(lambda: format_address(0, width=8.0), id="address-width-float"),  # type: ignore[arg-type]
        pytest.param(lambda: format_address(0, width=True), id="address-width-bool"),  # type: ignore[arg-type]
        pytest.param(lambda: MemoryAccess(0, size=1.0), id="access-size-float"),  # type: ignore[arg-type]
        pytest.param(lambda: MemoryAccess(0, size=True), id="access-size-bool"),
        pytest.param(lambda: MemorySegmentSpec("bad", 0.0, 1), id="segment-start-float"),  # type: ignore[arg-type]
        pytest.param(lambda: MemorySegmentSpec("bad", 0, False), id="segment-end-bool"),
        pytest.param(lambda: PipelineInstruction("bad", 0.0), id="start-cycle-float"),  # type: ignore[arg-type]
        pytest.param(
            lambda: PipelineInstruction("bad", 0, stalled_cycles=(True,)),
            id="stall-cycle-bool",
        ),
        pytest.param(
            lambda: PipelineInstruction("bad", 0, squashed_at_cycle=1.5),
            id="squash-cycle-float",
        ),  # type: ignore[arg-type]
    ],
)
def test_integer_fields_reject_floats_and_booleans(factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(TypeError, match="must be an integer"):
        factory()
