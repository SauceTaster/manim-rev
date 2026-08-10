from __future__ import annotations

from types import SimpleNamespace

import pytest
from manim import Animation, Circumscribe

from manim_rev.cfg import BasicBlock, ControlFlowGraph
from manim_rev.models import BasicBlockSpec, CFGEdgeSpec, EdgeKind, InstructionSpec
from manim_rev.refs import AddressRangeRef, AddressRef, BlockRef


def _overlaps(first, second) -> bool:  # type: ignore[no-untyped-def]
    return (
        first.get_right()[0] > second.get_left()[0]
        and first.get_left()[0] < second.get_right()[0]
        and first.get_top()[1] > second.get_bottom()[1]
        and first.get_bottom()[1] < second.get_top()[1]
    )


def _assert_content_is_contained(block: BasicBlock) -> None:
    for content in (block.header, block.divider, *block.rows):
        assert content.get_left()[0] >= block.background.get_left()[0] - 1e-6
        assert content.get_right()[0] <= block.background.get_right()[0] + 1e-6
        assert content.get_top()[1] <= block.background.get_top()[1] + 1e-6
        assert content.get_bottom()[1] >= block.background.get_bottom()[1] - 1e-6


def _assert_edge_labels_clear_blocks(graph: ControlFlowGraph) -> None:
    previous_labels = []
    for edge in graph.edge_mobjects.values():
        if edge.label_background is None:
            continue
        for block in graph.block_mobjects.values():
            assert not _overlaps(edge.label_background, block.background)
        for previous in previous_labels:
            assert not _overlaps(edge.label_background, previous)
        previous_labels.append(edge.label_background)


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


def test_basic_block_content_stays_inside_outline_and_uses_shared_columns() -> None:
    block = BasicBlock(
        BasicBlockSpec(
            "dispatch",
            0x402000,
            [
                InstructionSpec(0x402000, "cmp", "edi, 3"),
                InstructionSpec(0x402003, "jmp", "[table+rdi*8]"),
            ],
            label="jump-table dispatch with a fitted title",
        ),
        width=2.25,
    )

    _assert_content_is_contained(block)
    first_parts = block.row(0)[1]
    second_parts = block.row(1)[1]
    assert first_parts[0].get_left()[0] == pytest.approx(second_parts[0].get_left()[0])
    assert first_parts[1].get_left()[0] == pytest.approx(second_parts[1].get_left()[0])
    assert first_parts[0].text == "0x00402000"
    assert second_parts[0].text == "0x00402003"


@pytest.mark.parametrize(
    ("width", "show_bytes"),
    ((2.24, False), (3.09, True)),
)
def test_basic_block_rejects_widths_that_cannot_contain_columns(
    width: float,
    show_bytes: bool,
) -> None:
    spec = BasicBlockSpec("small", 0x1234ABCD, [InstructionSpec(0x1234ABCD, "ret")])

    with pytest.raises(ValueError, match="width must be at least"):
        BasicBlock(spec, width=width, show_bytes=show_bytes)


@pytest.mark.parametrize(
    ("width", "show_bytes"),
    ((2.25, False), (3.10, True)),
)
def test_basic_block_preserves_and_fits_high_and_symbolic_addresses(
    width: float,
    show_bytes: bool,
) -> None:
    block = BasicBlock(
        BasicBlockSpec(
            "symbolic",
            "loc_very_long_name",
            [
                InstructionSpec(0x1234ABCD, "mov", "eax, 1", b"\xb8\x01\x00\x00\x00"),
                InstructionSpec("sym_main+0x10", "ret", raw_bytes=b"\xc3"),
            ],
            label="symbolic address block",
        ),
        width=width,
        show_bytes=show_bytes,
    )

    _assert_content_is_contained(block)
    assert block.block_address.text == "loc_very_long_name"
    assert block.row(0)[1][0].text == "0x1234ABCD"
    assert block.row(1)[1][0].text == "sym_main+0x10"


def test_compact_addresses_are_explicit_and_do_not_truncate_symbols() -> None:
    block = BasicBlock(
        BasicBlockSpec(
            "compact",
            0x1234ABCD,
            [
                InstructionSpec(0x1234ABCD, "nop"),
                InstructionSpec("sym_main+0x10", "ret"),
            ],
        ),
        width=2.25,
        compact_addresses=True,
    )

    assert block.row(0)[1][0].text == "0x…ABCD"
    assert block.row(1)[1][0].text == "sym_main+0x10"


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
    _assert_edge_labels_clear_blocks(first)


def test_cfg_ranks_merge_below_every_forward_predecessor() -> None:
    blocks = [
        BasicBlockSpec(key, 0x4000 + index * 0x10, ["nop"])
        for index, key in enumerate(("guard", "dispatch", "default", "case0", "case1", "join"))
    ]
    edges = [
        CFGEdgeSpec("guard", "dispatch", EdgeKind.FALSE),
        CFGEdgeSpec("guard", "default", EdgeKind.TRUE),
        CFGEdgeSpec("dispatch", "case0"),
        CFGEdgeSpec("dispatch", "case1"),
        CFGEdgeSpec("default", "join"),
        CFGEdgeSpec("case0", "join"),
        CFGEdgeSpec("case1", "join"),
    ]

    graph = ControlFlowGraph(blocks, edges, block_width=2.25)

    assert graph.levels["join"] == 3
    for predecessor in graph.predecessors("join"):
        assert graph.levels[predecessor] < graph.levels["join"]
        assert graph.block(predecessor).get_y() > graph.block("join").get_y()


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
    assert all(isinstance(animation, Circumscribe) for animation in graph.focus("entry").animations)

    true_edge = graph.edge("entry", "nonzero", EdgeKind.TRUE)
    assert true_edge.arrow.get_start()[1] == pytest.approx(graph.block("entry").get_bottom()[1])
    assert true_edge.arrow.get_end()[1] == pytest.approx(graph.block("nonzero").get_top()[1])
    assert true_edge.label.text == "true"
    assert true_edge.label_background is not None
    assert (
        graph.block("nonzero").get_top()[1]
        < true_edge.label.get_y()
        < graph.block("entry").get_bottom()[1]
    )

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
    loop_edge = graph.edge("loop", "loop", EdgeKind.LOOP)
    block_bounds = [block.get_left()[0] for block in graph.block_mobjects.values()] + [
        block.get_right()[0] for block in graph.block_mobjects.values()
    ]
    edge_points = loop_edge.arrow.get_all_points()
    assert edge_points[:, 0].max() > max(block_bounds)
    assert graph.resolve(AddressRangeRef(0x1000, 1)) == (graph.block("entry"),)


def test_cfg_label_backgrounds_clear_blocks_in_manual_loop_layout() -> None:
    blocks = [
        BasicBlockSpec("header", 0x1000, ["cmp ecx, 4"]),
        BasicBlockSpec("body", 0x1010, ["call helper"]),
        BasicBlockSpec("helper", 0x1020, ["ret"]),
        BasicBlockSpec("latch", 0x1030, ["inc ecx"]),
        BasicBlockSpec("done", 0x1040, ["ret"]),
    ]
    graph = ControlFlowGraph(
        blocks,
        [
            CFGEdgeSpec("header", "body", EdgeKind.FALSE, "continue"),
            CFGEdgeSpec("header", "done", EdgeKind.TRUE, "exit"),
            CFGEdgeSpec("body", "helper", EdgeKind.CALL, "call"),
            CFGEdgeSpec("helper", "latch", EdgeKind.RETURN, "return"),
            CFGEdgeSpec("latch", "header", EdgeKind.LOOP, "repeat"),
        ],
        positions={
            "header": (-2.0, 1.0),
            "body": (-2.0, -0.7),
            "helper": (1.25, -0.7),
            "latch": (-2.0, -2.3),
            "done": (2.1, 1.0),
        },
        block_width=2.65,
    )

    _assert_edge_labels_clear_blocks(graph)


def test_cfg_moves_a_label_out_of_a_crowded_manual_gap() -> None:
    graph = ControlFlowGraph(
        [
            BasicBlockSpec("top", 0x1000, ["test eax, eax"]),
            BasicBlockSpec("bottom", 0x1010, ["ret"]),
        ],
        [CFGEdgeSpec("top", "bottom", EdgeKind.TRUE, "taken branch")],
        positions={"top": (0, 0.515), "bottom": (0, -0.515)},
        block_width=2.65,
    )

    _assert_edge_labels_clear_blocks(graph)


def test_cfg_back_edge_detection_handles_graphs_larger_than_recursion_limit() -> None:
    keys = tuple(f"node-{index}" for index in range(1500))
    edges = (
        *(CFGEdgeSpec(keys[index], keys[index + 1]) for index in range(len(keys) - 1)),
        CFGEdgeSpec(keys[-1], keys[500]),
    )
    graph_stub = SimpleNamespace(entry=keys[0], edge_specs=edges)

    back_edges = ControlFlowGraph._find_back_edges(graph_stub, keys)  # type: ignore[arg-type]

    assert back_edges == {len(edges) - 1}


@pytest.mark.parametrize(
    ("horizontal_gap", "vertical_gap"),
    ((0.0, 0.5), (0.5, 0.0), (0.24, 0.5), (0.5, 0.24)),
)
def test_cfg_rejects_layout_gaps_below_visual_minimum(
    horizontal_gap: float,
    vertical_gap: float,
) -> None:
    with pytest.raises(ValueError, match=r"layout gaps must be at least 0\.25"):
        ControlFlowGraph(
            [BasicBlockSpec("entry", 0x1000, ["ret"])],
            [],
            horizontal_gap=horizontal_gap,
            vertical_gap=vertical_gap,
        )


def test_cfg_routes_manual_same_row_edges_side_to_side() -> None:
    blocks = [
        BasicBlockSpec("left", 0x1000, ["call helper"]),
        BasicBlockSpec("right", 0x1010, ["ret"]),
    ]
    graph = ControlFlowGraph(
        blocks,
        [CFGEdgeSpec("left", "right", EdgeKind.CALL, "call")],
        positions={"left": (-2, 0), "right": (2, 0)},
        block_width=2.5,
    )
    edge = graph.edge("left", "right", EdgeKind.CALL)

    assert edge.arrow.get_start() == pytest.approx(graph.block("left").get_right())
    assert edge.arrow.get_end() == pytest.approx(graph.block("right").get_left())
    assert edge.label.get_bottom()[1] > edge.arrow.get_center()[1]


def test_cfg_separates_parallel_semantic_edges_and_their_labels() -> None:
    blocks = [
        BasicBlockSpec("check", 0x1000, ["test eax, eax"]),
        BasicBlockSpec("next", 0x1010, ["ret"]),
    ]
    graph = ControlFlowGraph(
        blocks,
        [
            CFGEdgeSpec("check", "next", EdgeKind.TRUE),
            CFGEdgeSpec("check", "next", EdgeKind.FALSE),
        ],
        block_width=2.6,
    )
    true_edge = graph.edge("check", "next", EdgeKind.TRUE)
    false_edge = graph.edge("check", "next", EdgeKind.FALSE)

    assert true_edge.arrow.get_start()[0] != pytest.approx(false_edge.arrow.get_start()[0])
    assert true_edge.arrow.get_end()[0] != pytest.approx(false_edge.arrow.get_end()[0])
    assert true_edge.label.get_center()[0] != pytest.approx(false_edge.label.get_center()[0])

    _assert_edge_labels_clear_blocks(graph)


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
