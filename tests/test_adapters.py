from __future__ import annotations

from dataclasses import dataclass

import pytest

from manim_rev.adapters import (
    cfg_from_angr,
    cfg_from_ghidra_json,
    instruction_from_capstone,
    trace_events_from_records,
)
from manim_rev.models import AccessKind, EdgeKind, TracePhase


@dataclass
class FakeCapstoneInstruction:
    address: int = 0x401000
    mnemonic: str = "xor"
    op_str: str = "eax, eax"
    bytes: bytes = b"\x31\xc0"


@dataclass(eq=False)
class FakeCFGNode:
    addr: int
    name: str
    block: object | None = None


class FakeGraph:
    def __init__(
        self,
        nodes: list[FakeCFGNode],
        edges: list[tuple[FakeCFGNode, FakeCFGNode, dict[str, object]]] | None = None,
    ) -> None:
        self._nodes = nodes
        self._edges = edges or []

    def nodes(self):  # type: ignore[no-untyped-def]
        return list(self._nodes)

    def edges(self, *, data: bool = False):  # type: ignore[no-untyped-def]
        assert data
        return list(self._edges)


def test_capstone_adapter_is_duck_typed() -> None:
    converted = instruction_from_capstone(FakeCapstoneInstruction())
    assert converted.address == 0x401000
    assert converted.bytes_text == "31 C0"


def test_trace_record_adapter_includes_memory_access() -> None:
    events = trace_events_from_records(
        [
            {
                "pc": 0x1000,
                "instruction": "mov [rax], bl",
                "registers": {"rax": 0x2000},
                "memory": {"address": 0x2000, "kind": "write", "value": 0x41},
            }
        ]
    )
    assert events[0].memory is not None
    assert events[0].memory.kind is AccessKind.WRITE


def test_trace_record_adapter_coerces_decimal_and_hex_addresses() -> None:
    events = trace_events_from_records(
        [
            {
                "pc": "4096",
                "instruction": "mov al, [rbx]",
                "memory": {"address": "0x2000", "size": 1},
            }
        ]
    )
    assert events[0].address == 0x1000
    assert events[0].memory is not None
    assert events[0].memory.address == 0x2000


def test_trace_record_adapter_accepts_phases_and_multiple_memory_accesses() -> None:
    events = trace_events_from_records(
        [
            {
                "pc": "0x1000",
                "instruction": "movsb",
                "phase": "after",
                "memory_accesses": [
                    {"address": "0x2000", "kind": "read", "value": 0x41},
                    {"address": "12288", "kind": "write", "value": 0x41},
                ],
            }
        ]
    )
    assert events[0].phase is TracePhase.AFTER
    assert [access.address for access in events[0].memory_accesses] == [0x2000, 0x3000]
    assert events[0].memory is events[0].memory_accesses[0]

    with pytest.raises(ValueError, match="either memory or memory_accesses"):
        trace_events_from_records(
            [
                {
                    "pc": 0x1000,
                    "memory": {"address": 0x2000},
                    "memory_accesses": [{"address": 0x3000}],
                }
            ]
        )


def test_trace_record_adapter_reports_invalid_addresses_with_context() -> None:
    with pytest.raises(ValueError, match=r"trace record 0 address.*symbol"):
        trace_events_from_records([{"pc": "symbol", "instruction": "nop"}])
    with pytest.raises(ValueError, match=r"trace record 0.*address.*pc"):
        trace_events_from_records([{"instruction": "nop"}])


def test_ghidra_json_adapter() -> None:
    blocks, edges = cfg_from_ghidra_json(
        {
            "blocks": [
                {
                    "id": "entry",
                    "address": "0x1000",
                    "instructions": [{"address": "4096", "mnemonic": "ret", "bytes": "C3"}],
                },
                {"id": "exit", "address": 0x1001, "instructions": []},
            ],
            "edges": [{"source": "entry", "target": "exit", "kind": "unconditional"}],
        }
    )
    assert blocks[0].address == 0x1000
    assert blocks[0].instructions[0].address == 0x1000
    assert blocks[0].instructions[0].bytes_text == "C3"
    assert edges[0].kind is EdgeKind.UNCONDITIONAL


def test_ghidra_json_adapter_reports_the_invalid_address_field() -> None:
    with pytest.raises(ValueError, match=r"Ghidra block 0 address.*not-an-address"):
        cfg_from_ghidra_json(
            {"blocks": [{"id": "entry", "address": "not-an-address", "instructions": []}]}
        )


def test_angr_adapter_disambiguates_context_nodes_at_same_address() -> None:
    blocks, _ = cfg_from_angr(
        FakeGraph(
            [
                FakeCFGNode(0x401000, "main in context A"),
                FakeCFGNode(0x401000, "main in context B"),
            ]
        )
    )
    assert [block.key for block in blocks] == ["block_401000", "block_401000_1"]


def test_angr_adapter_infers_supported_edge_kinds_conservatively() -> None:
    nodes = [FakeCFGNode(0x1000 + index * 0x10, f"n{index}") for index in range(8)]
    fixture = [
        (nodes[0], nodes[1], {"jumpkind": "Ijk_Call"}),
        (nodes[1], nodes[2], {"jumpkind": "Ijk_Ret"}),
        (nodes[2], nodes[3], {"jumpkind": "Ijk_Boring", "branch": True}),
        (nodes[2], nodes[4], {"jumpkind": "Ijk_Boring", "branch": False}),
        (nodes[4], nodes[5], {"kind": "unconditional"}),
        (nodes[5], nodes[4], {"is_back_edge": True}),
        (nodes[6], nodes[7], {"jumpkind": "Ijk_Boring"}),
        (nodes[0], nodes[2], {"jumpkind": "Ijk_FakeRet"}),
        (nodes[0], nodes[3], {"jumpkind": "Ijk_Sys_syscall"}),
    ]
    _, edges = cfg_from_angr(FakeGraph(nodes, fixture))
    assert [edge.kind for edge in edges] == [
        EdgeKind.CALL,
        EdgeKind.RETURN,
        EdgeKind.TRUE,
        EdgeKind.FALSE,
        EdgeKind.UNCONDITIONAL,
        EdgeKind.LOOP,
        EdgeKind.FALLTHROUGH,
        EdgeKind.FALLTHROUGH,
        EdgeKind.FALLTHROUGH,
    ]
