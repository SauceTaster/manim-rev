from __future__ import annotations

import pytest
from manim import Animation

from manim_rev.cfg import BasicBlock, ControlFlowGraph
from manim_rev.models import BasicBlockSpec, CFGEdgeSpec, EdgeKind, InstructionSpec
from manim_rev.refs import AddressRangeRef, AddressRef, BlockRef


def _diamond() -> tuple[list[BasicBlockSpec], list[CFGEdgeSpec]]:
    blocks = [
        BasicBlockSpec(
            "entry",
            0x401000,
            [
                InstructionSpec(0x401000, "test", "eax, eax", b"\x85\xc0"),
                InstructionSpec(0x401002, "jne", "0x401010", b"\x75\x0c"),
            ],
        ),
        BasicBlockSpec("zero", 0x401004, ["xor eax, eax"]),
        BasicBlockSpec("nonzero", 0x401010, ["mov eax, 1"]),
        BasicBlockSpec("return", 0x401020, ["ret"]),
    ]
    edges = [
        CFGEdgeSpec("entry", "zero", EdgeKind.FALSE),
        CFGEdgeSpec("entry", "nonzero", EdgeKind.TRUE),
        CFGEdgeSpec("zero", "return"),
        CFGEdgeSpec("nonzero", "return"),
    ]
    return blocks, edges


def test_basic_block_has_stable_instruction_lookups_and_refs() -> None:
    spec = BasicBlockSpec(
        "check",
        0x401000,
        [
            InstructionSpec(0x401000, "cmp", "eax, 1", b"\x83\xf8\x01"),
            InstructionSpec(0x401003, "je", "0x401020", b"\x74\x1b"),
        ],
    )
    block = BasicBlock(spec)

    assert block.row(0) is block.instruction(0x401000)
    assert block.resolve(BlockRef("check")) == (block,)
    assert block.resolve(AddressRef(0x401003)) == (block.instruction(0x401003),)
    assert block.resolve(AddressRangeRef(0x401001, 3)) == (
        block.instruction(0x401000),
        block.instruction(0x401003),
    )
    assert block.resolve(BlockRef("other")) == ()
    assert isinstance(block.focus(AddressRef(0x401000)), Animation)


def test_basic_block_rejects_duplicate_instruction_addresses() -> None:
    spec = BasicBlockSpec(
        "bad",
        0x1000,
        [InstructionSpec(0x1000, "nop"), InstructionSpec(0x1000, "ret")],
    )
    with pytest.raises(ValueError, match="duplicate instruction address"):
        BasicBlock(spec)


def test_layered_cfg_is_deterministic_and_top_to_bottom() -> None:
    blocks, edges = _diamond()
    first = ControlFlowGraph(blocks, edges)
    second = ControlFlowGraph(blocks, edges)

    assert first.levels == {"entry": 0, "zero": 1, "nonzero": 1, "return": 2}
    assert first.layers == {
        0: ("entry",),
        1: ("zero", "nonzero"),
        2: ("return",),
    }
    assert first.layout_positions == second.layout_positions
    assert first.block("entry").get_center()[1] > first.block("zero").get_center()[1]
    assert first.block("zero").get_center()[0] < first.block("nonzero").get_center()[0]
    assert first.block("return").get_center()[1] < first.block("zero").get_center()[1]


def test_cfg_uses_explicit_two_and_three_dimensional_positions() -> None:
    blocks, edges = _diamond()
    positions = {
        "entry": (0, 2),
        "zero": (-3, 0, 0.25),
        "nonzero": (3, 0),
        "return": (0, -2, -0.25),
    }

    first = ControlFlowGraph(blocks, edges, positions=positions)
    second = ControlFlowGraph(blocks, edges, positions=positions)

    expected = {
        "entry": (0, 2, 0),
        "zero": (-3, 0, 0.25),
        "nonzero": (3, 0, 0),
        "return": (0, -2, -0.25),
    }
    for key, position in expected.items():
        assert first.layout_positions[key] == pytest.approx(position)
    assert first.layout_positions == second.layout_positions


def test_partial_cfg_positions_leave_other_blocks_on_layered_layout() -> None:
    blocks, edges = _diamond()
    layered = ControlFlowGraph(blocks, edges)
    positioned = ControlFlowGraph(blocks, edges, positions={"entry": (1.25, 2.5)})

    assert positioned.layout_positions["entry"] == pytest.approx((1.25, 2.5, 0))
    for key in ("zero", "nonzero", "return"):
        assert positioned.layout_positions[key] == pytest.approx(layered.layout_positions[key])


@pytest.mark.parametrize("coordinate", [(1,), (1, 2, 3, 4)])
def test_cfg_rejects_positions_that_are_not_two_or_three_dimensional(
    coordinate: tuple[int, ...],
) -> None:
    blocks, edges = _diamond()

    with pytest.raises(ValueError, match="two or three numbers"):
        ControlFlowGraph(blocks, edges, positions={"entry": coordinate})


def test_cfg_rejects_unknown_position_keys() -> None:
    blocks, edges = _diamond()

    with pytest.raises(KeyError, match="position mapping references unknown block"):
        ControlFlowGraph(blocks, edges, positions={"missing": (0, 0)})


def test_cfg_lookups_adjacency_resolution_and_traversal() -> None:
    blocks, edges = _diamond()
    graph = ControlFlowGraph(blocks, edges)

    assert graph.block("entry").spec is blocks[0]
    assert graph.edge("entry", "nonzero") is graph.edge("entry", "nonzero", EdgeKind.TRUE)
    assert graph.successors("entry") == ("zero", "nonzero")
    assert graph.predecessors("return") == ("zero", "nonzero")
    assert graph.resolve(BlockRef("zero")) == (graph.block("zero"),)
    assert graph.resolve(AddressRef(0x401000)) == (graph.block("entry").instruction(0x401000),)
    assert isinstance(graph.focus("entry"), Animation)
    assert isinstance(graph.traverse(("entry", "nonzero", "return")), Animation)

    with pytest.raises(KeyError, match="unknown CFG edge"):
        graph.traverse(("zero", "nonzero"))
    with pytest.raises(ValueError, match="cannot be empty"):
        graph.traverse(())


def test_cfg_handles_loops_and_disconnected_blocks_without_random_layout() -> None:
    blocks = [
        BasicBlockSpec("entry", 0x1000, ["jmp loop"]),
        BasicBlockSpec("loop", 0x1010, ["dec ecx", "jnz loop"]),
        BasicBlockSpec("orphan", 0x2000, ["ret"]),
    ]
    graph = ControlFlowGraph(
        blocks,
        [
            CFGEdgeSpec("entry", "loop"),
            CFGEdgeSpec("loop", "loop", EdgeKind.LOOP),
        ],
    )

    assert graph.levels == {"entry": 0, "loop": 1, "orphan": 2}
    assert graph.edge("loop", "loop", EdgeKind.LOOP) is not None
    assert graph.resolve(AddressRangeRef(0x1000, 1)) == (graph.block("entry"),)


@pytest.mark.parametrize(
    ("blocks", "edges", "message"),
    [
        ([], [], "requires at least one block"),
        (
            [BasicBlockSpec("same", 0x1000, ["nop"]), BasicBlockSpec("same", 0x2000, ["ret"])],
            [],
            "keys must be unique",
        ),
        (
            [BasicBlockSpec("entry", 0x1000, ["ret"])],
            [CFGEdgeSpec("entry", "missing")],
            "unknown block",
        ),
    ],
)
def test_cfg_validates_structure(
    blocks: list[BasicBlockSpec],
    edges: list[CFGEdgeSpec],
    message: str,
) -> None:
    with pytest.raises((ValueError, KeyError), match=message):
        ControlFlowGraph(blocks, edges)
