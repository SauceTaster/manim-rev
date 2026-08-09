"""Optional, duck-typed adapters for common reverse-engineering tools.

The module deliberately imports neither Capstone nor angr.  Pass their objects
in when those packages are available; the resulting models remain portable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .models import (
    AccessKind,
    BasicBlockSpec,
    CFGEdgeSpec,
    EdgeKind,
    InstructionSpec,
    MemoryAccess,
    TraceEvent,
    TracePhase,
)

_DECIMAL_ADDRESS = re.compile(r"[+]?[0-9]+\Z")
_HEX_ADDRESS = re.compile(r"[+]?0[xX][0-9a-fA-F]+\Z")


def _coerce_address(value: Any, *, field: str) -> int:
    """Return one concrete address with an error that names its input field."""

    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer or numeric string, not {value!r}")
    if isinstance(value, int):
        address = value
    elif isinstance(value, str):
        text = value.strip()
        if _HEX_ADDRESS.fullmatch(text):
            address = int(text, 16)
        elif _DECIMAL_ADDRESS.fullmatch(text):
            address = int(text, 10)
        else:
            raise ValueError(
                f"{field} must be an integer or a decimal/0x-prefixed hexadecimal string; "
                f"got {value!r}"
            )
    else:
        raise ValueError(
            f"{field} must be an integer or a decimal/0x-prefixed hexadecimal string; got {value!r}"
        )
    if address < 0:
        raise ValueError(f"{field} must be non-negative; got {value!r}")
    return address


def _memory_access_from_record(
    record: Mapping[str, Any],
    *,
    field: str,
) -> MemoryAccess:
    if "address" not in record:
        raise ValueError(f"{field} must include an 'address' field")
    return MemoryAccess(
        address=_coerce_address(record["address"], field=f"{field} address"),
        size=int(record.get("size", 1)),
        kind=AccessKind(str(record.get("kind", "read"))),
        value=record.get("value"),
    )


def instruction_from_capstone(instruction: Any) -> InstructionSpec:
    """Convert a Capstone instruction using its public object attributes."""

    return InstructionSpec(
        address=_coerce_address(instruction.address, field="Capstone instruction address"),
        mnemonic=str(instruction.mnemonic),
        operands=str(getattr(instruction, "op_str", "")),
        raw_bytes=bytes(getattr(instruction, "bytes", b"")),
    )


def instructions_from_capstone(instructions: Iterable[Any]) -> tuple[InstructionSpec, ...]:
    return tuple(instruction_from_capstone(instruction) for instruction in instructions)


def cfg_from_angr(cfg: Any) -> tuple[tuple[BasicBlockSpec, ...], tuple[CFGEdgeSpec, ...]]:
    """Snapshot an angr CFG model without retaining an angr dependency.

    ``cfg`` may be a CFG analysis result (with ``.graph``) or its NetworkX-like
    graph directly.  Nodes without a concrete address are ignored.
    """

    graph = getattr(cfg, "graph", cfg)
    nodes = [node for node in graph.nodes() if getattr(node, "addr", None) is not None]
    nodes.sort(key=lambda node: (int(node.addr), str(getattr(node, "name", ""))))
    node_keys: dict[Any, str] = {}
    key_counts: dict[str, int] = {}
    for node in nodes:
        base_key = f"block_{int(node.addr):X}"
        occurrence = key_counts.get(base_key, 0)
        node_keys[node] = base_key if occurrence == 0 else f"{base_key}_{occurrence}"
        key_counts[base_key] = occurrence + 1
    blocks: list[BasicBlockSpec] = []
    for node in nodes:
        instructions: list[InstructionSpec | str] = []
        block = getattr(node, "block", None)
        capstone = getattr(block, "capstone", None)
        for wrapped in getattr(capstone, "insns", ()):
            instruction = getattr(wrapped, "insn", wrapped)
            instructions.append(instruction_from_capstone(instruction))
        if not instructions:
            instructions.append(str(getattr(node, "name", "unresolved block")))
        blocks.append(
            BasicBlockSpec(
                key=node_keys[node],
                address=int(node.addr),
                instructions=instructions,
                label=str(getattr(node, "name", "") or ""),
            )
        )

    edges: list[CFGEdgeSpec] = []
    for source, target, data in graph.edges(data=True):
        if source not in node_keys or target not in node_keys:
            continue
        metadata = data if isinstance(data, Mapping) else {}
        kind = _angr_edge_kind(metadata)
        edges.append(CFGEdgeSpec(node_keys[source], node_keys[target], kind=kind))
    return tuple(blocks), tuple(edges)


def _angr_edge_kind(metadata: Mapping[str, Any]) -> EdgeKind:
    """Infer only control-flow facts explicitly represented by angr metadata."""

    jumpkind = str(metadata.get("jumpkind", "")).strip().casefold()
    # Fake-return edges model the continuation after a call, not a real return.
    if jumpkind.endswith("_call") or jumpkind == "call":
        return EdgeKind.CALL
    if jumpkind.endswith("_ret") or jumpkind == "ret":
        return EdgeKind.RETURN

    explicit = _metadata_edge_kind(metadata)
    if explicit is not None:
        return explicit
    return EdgeKind.FALLTHROUGH


def _metadata_edge_kind(metadata: Mapping[str, Any]) -> EdgeKind | None:
    aliases = {
        "call": EdgeKind.CALL,
        "return": EdgeKind.RETURN,
        "ret": EdgeKind.RETURN,
        "loop": EdgeKind.LOOP,
        "backedge": EdgeKind.LOOP,
        "back_edge": EdgeKind.LOOP,
        "true": EdgeKind.TRUE,
        "conditional_true": EdgeKind.TRUE,
        "taken": EdgeKind.TRUE,
        "false": EdgeKind.FALSE,
        "conditional_false": EdgeKind.FALSE,
        "not_taken": EdgeKind.FALSE,
        "unconditional": EdgeKind.UNCONDITIONAL,
        "jump": EdgeKind.UNCONDITIONAL,
        "fallthrough": EdgeKind.FALLTHROUGH,
        "fake_return": EdgeKind.FALLTHROUGH,
        "fakeret": EdgeKind.FALLTHROUGH,
    }
    for key in ("kind", "edge_kind", "type", "branch_type"):
        value = metadata.get(key)
        if isinstance(value, EdgeKind):
            return value
        if isinstance(value, str):
            normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
            if normalized in aliases:
                return aliases[normalized]

    for key in ("is_back_edge", "back_edge", "is_loop_edge"):
        if metadata.get(key) is True:
            return EdgeKind.LOOP

    for key in ("taken", "is_true_branch", "branch", "condition"):
        value = metadata.get(key)
        if isinstance(value, bool):
            return EdgeKind.TRUE if value else EdgeKind.FALSE
        if isinstance(value, str):
            normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
            if normalized in aliases and aliases[normalized] in (EdgeKind.TRUE, EdgeKind.FALSE):
                return aliases[normalized]

    if metadata.get("is_unconditional") is True:
        return EdgeKind.UNCONDITIONAL
    return None


def trace_events_from_records(records: Iterable[Mapping[str, Any]]) -> tuple[TraceEvent, ...]:
    """Convert JSON/GDB/LLDB-style trace dictionaries into trace events."""

    events: list[TraceEvent] = []
    for record_index, record in enumerate(records):
        if "address" in record:
            raw_address = record["address"]
        elif "pc" in record:
            raw_address = record["pc"]
        else:
            raise ValueError(f"trace record {record_index} must include an 'address' or 'pc' field")
        memory_record = record.get("memory")
        memory = None
        if memory_record is not None:
            if not isinstance(memory_record, Mapping):
                raise ValueError(f"trace record {record_index} memory must be a mapping")
            memory = _memory_access_from_record(
                memory_record,
                field=f"trace record {record_index} memory",
            )

        memory_access_records = record.get("memory_accesses", ())
        if isinstance(memory_access_records, (str, bytes, Mapping)) or not isinstance(
            memory_access_records, Iterable
        ):
            raise ValueError(f"trace record {record_index} memory_accesses must be a sequence")
        memory_accesses: list[MemoryAccess] = []
        for access_index, access_record in enumerate(memory_access_records):
            if not isinstance(access_record, Mapping):
                raise ValueError(
                    f"trace record {record_index} memory_accesses[{access_index}] must be a mapping"
                )
            memory_accesses.append(
                _memory_access_from_record(
                    access_record,
                    field=f"trace record {record_index} memory_accesses[{access_index}]",
                )
            )
        events.append(
            TraceEvent(
                address=_coerce_address(
                    raw_address,
                    field=f"trace record {record_index} address",
                ),
                instruction=str(record.get("instruction", "")),
                registers=dict(record.get("registers", {})),
                memory=memory,
                note=str(record.get("note", "")),
                phase=TracePhase(str(record.get("phase", "unknown"))),
                memory_accesses=memory_accesses,
            )
        )
    return tuple(events)


def cfg_from_ghidra_json(
    payload: Mapping[str, Any],
) -> tuple[tuple[BasicBlockSpec, ...], tuple[CFGEdgeSpec, ...]]:
    """Convert a small, documented export shape from a Ghidra script."""

    blocks = []
    for block_index, raw_block in enumerate(payload.get("blocks", ())):  # type: ignore[union-attr]
        instructions = [
            InstructionSpec(
                address=_coerce_address(
                    raw_instruction["address"],
                    field=(f"Ghidra block {block_index} instruction {instruction_index} address"),
                ),
                mnemonic=str(raw_instruction["mnemonic"]),
                operands=str(raw_instruction.get("operands", "")),
                raw_bytes=bytes.fromhex(str(raw_instruction.get("bytes", ""))),
            )
            for instruction_index, raw_instruction in enumerate(raw_block.get("instructions", ()))
        ]
        blocks.append(
            BasicBlockSpec(
                key=str(raw_block["id"]),
                address=_coerce_address(
                    raw_block["address"], field=f"Ghidra block {block_index} address"
                ),
                label=str(raw_block.get("label", "")),
                instructions=instructions,
            )
        )
    edges = [
        CFGEdgeSpec(
            source=str(edge["source"]),
            target=str(edge["target"]),
            kind=EdgeKind(str(edge.get("kind", "fallthrough"))),
            label=str(edge.get("label", "")),
        )
        for edge in payload.get("edges", ())  # type: ignore[union-attr]
    ]
    return tuple(blocks), tuple(edges)
