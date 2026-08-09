from __future__ import annotations

import pytest
from manim import Animation

from manim_rev.memory import HexDump, MemoryMap
from manim_rev.models import MemorySegmentSpec
from manim_rev.refs import AddressRangeRef, AddressRef


def test_hex_dump_exposes_address_byte_and_ascii_cells() -> None:
    dump = HexDump(b"A\x00BC\xff", base_address=0x401000, bytes_per_row=4)

    assert dump.data == b"A\x00BC\xff"
    assert len(dump.rows) == 2
    assert dump.row_for_address(0x401002) is dump.rows[0]
    assert dump.rows[0].address_cell.display == "0x00401000"
    assert dump.byte_cell(0x401000).display == "41"
    assert dump.rows[0].ascii_cell is not None
    assert dump.rows[0].ascii_cell.display == "A.BC"
    assert dump.rows[1].ascii_cell is not None
    assert dump.rows[1].ascii_cell.display == "."
    assert dump.bytes_at(0x401001, 3) == b"\x00BC"


def test_hex_dump_write_highlight_and_semantic_resolution() -> None:
    dump = HexDump(b"hello", base_address=0x1000, bytes_per_row=4)

    assert isinstance(dump.highlight(0x1001, 2), Animation)
    assert isinstance(dump.animate_write(0x1003, b"!!"), Animation)
    assert dump.bytes_at(0x1000, 5) == b"hel!!"
    assert dump.byte_cell(0x1004).value == ord("!")
    assert dump.rows[0].ascii_cell is not None
    assert dump.rows[0].ascii_cell.display == "hel!"
    assert dump.resolve(AddressRef(0x1004)) == (dump.byte_cell(0x1004),)
    assert dump.resolve(AddressRangeRef(0x1002, 2)) == (
        dump.byte_cell(0x1002),
        dump.byte_cell(0x1003),
    )


def test_hex_dump_validates_ranges_and_supports_immediate_writes() -> None:
    dump = HexDump(b"\x00\x01", base_address=0x2000, show_ascii=False)
    assert dump.set_bytes(0x2000, 0xFE) is dump
    assert dump.data == b"\xfe\x01"
    assert dump.rows[0].ascii_cell is None

    with pytest.raises(IndexError, match="outside"):
        dump.bytes_at(0x1FFF)
    with pytest.raises(IndexError, match="outside"):
        dump.animate_write(0x2001, b"too long")
    with pytest.raises(ValueError, match="positive"):
        dump.highlight(0x2000, 0)


def test_memory_map_lookups_permissions_and_refs() -> None:
    specs = [
        MemorySegmentSpec("text", 0x400000, 0x401000, "r-x"),
        MemorySegmentSpec("heap", 0x600000, 0x610000, "rw-"),
        MemorySegmentSpec("stack", 0x7FFF0000, 0x80000000, "rw-"),
    ]
    memory_map = MemoryMap(specs)

    assert [block.spec.name for block in memory_map.segment_blocks] == [
        "stack",
        "heap",
        "text",
    ]
    assert memory_map.segment("TEXT").spec is specs[0]
    assert memory_map.segment_for_address(0x600123).spec is specs[1]
    assert memory_map.resolve(AddressRef(0x400010)) == (memory_map.segment("text"),)
    assert memory_map.resolve(AddressRangeRef(0x400FF0, 0x20)) == (memory_map.segment("text"),)
    assert isinstance(memory_map.highlight("heap"), Animation)

    with pytest.raises(KeyError, match="not mapped"):
        memory_map.segment_for_address(0x500000)
    with pytest.raises(ValueError, match="unique"):
        MemoryMap(
            [
                MemorySegmentSpec("same", 0, 1),
                MemorySegmentSpec("SAME", 2, 3),
            ]
        )


def test_memory_map_compact_rows_fit_labels_without_overlap() -> None:
    memory_map = MemoryMap(
        [MemorySegmentSpec("long executable mapping name", 0x400000, 0x401000, "r-x")],
        width=4.2,
        segment_height=0.5,
    )
    segment = memory_map.segment_blocks[0]

    assert segment.name.get_right()[0] < segment.permissions.get_left()[0]
    assert segment.name.get_bottom()[1] > segment.address_range.get_top()[1]
    assert segment.label_stack.height <= segment.background.height - 0.1
