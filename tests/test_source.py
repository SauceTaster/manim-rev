from __future__ import annotations

import pytest
from manim import RIGHT, Animation, Rectangle, VGroup

from manim_rev.models import XRefSpec
from manim_rev.refs import AddressRangeRef, AddressRef, BlockRef, SourceRef
from manim_rev.source import (
    CrossReferencePanel,
    SourceAssemblyLinkSpec,
    SourceAssemblyMap,
    SourceListing,
)


class AssemblyStub(VGroup):
    def __init__(self, addresses: tuple[int, ...]) -> None:
        super().__init__()
        self.targets = {
            address: Rectangle(width=1.3, height=0.35).shift(RIGHT * (3 + index * 0.2))
            for index, address in enumerate(addresses)
        }
        self.add(*self.targets.values())

    def resolve(self, ref):  # type: ignore[no-untyped-def]
        if isinstance(ref, AddressRef) and ref.address in self.targets:
            return (self.targets[ref.address],)
        return ()


def test_source_listing_exposes_lines_text_and_file_aware_refs() -> None:
    listing = SourceListing(
        "if (x) {\n    sink(x);\n}",
        filename="src/demo.c",
        start_line=10,
    )

    assert listing.text_at(10) == "if (x) {"
    assert listing.text_at(11) == "    sink(x);"
    assert listing.resolve(SourceRef(11)) == (listing.line(11),)
    assert listing.resolve(SourceRef(11, "demo.c")) == (listing.line(11),)
    assert listing.resolve(SourceRef(11, "other.c")) == ()
    assert isinstance(listing.focus(11), Animation)

    with pytest.raises(KeyError, match="outside"):
        listing.line(9)


def test_source_listing_resolves_address_mappings_and_ranges() -> None:
    listing = SourceListing(
        ["int x = read();", "return x + 1;"],
        filename="main.c",
        address_map={1: (0x401000, 0x401004), 2: 0x401010},
    )

    assert listing.addresses_for_line(1) == (0x401000, 0x401004)
    assert listing.lines_for_address(0x401010) == (2,)
    assert listing.resolve(AddressRef(0x401004)) == (listing.line(1),)
    assert listing.resolve(AddressRangeRef(0x401003, 0xE)) == (
        listing.line(1),
        listing.line(2),
    )

    with pytest.raises(KeyError, match="unknown source line"):
        SourceListing("return 0;", address_map={2: 0x401000})


def test_cross_reference_panel_has_stable_queries_and_semantic_resolution() -> None:
    references = [
        XRefSpec("demo.c:12", "0x401000", "call", "parse"),
        XRefSpec("entry", "success", "code"),
        XRefSpec("0x401020", "global_counter", "write"),
    ]
    panel = CrossReferencePanel(references)

    assert panel.row(0) is panel.reference("demo.c:12", "0x401000", kind="call")
    assert panel.references_from("entry") == (panel.row(1),)
    assert panel.references_to("success") == (panel.row(1),)
    assert panel.resolve(SourceRef(12, "demo.c")) == (panel.row(0),)
    assert panel.resolve(AddressRef(0x401000)) == (panel.row(0),)
    assert panel.resolve(AddressRangeRef(0x401010, 0x20)) == (panel.row(2),)
    assert panel.resolve(BlockRef("success")) == (panel.row(1),)
    assert isinstance(panel.follow(0), Animation)


def test_cross_reference_panel_handles_duplicates_and_empty_state() -> None:
    duplicate = XRefSpec("a", "b", "call")
    panel = CrossReferencePanel([duplicate, duplicate])

    assert panel.reference("a", "b", occurrence=0) is panel.row(0)
    assert panel.reference("a", "b", occurrence=1) is panel.row(1)
    with pytest.raises(KeyError, match="does not exist"):
        panel.reference("a", "b", occurrence=2)

    empty = CrossReferencePanel([])
    assert empty.resolve(BlockRef("anything")) == ()
    with pytest.raises(IndexError, match="does not exist"):
        empty.row(0)


def test_source_assembly_map_links_and_follows_resolvable_addresses() -> None:
    listing = SourceListing(
        ["value = load();", "return value;"],
        filename="demo.c",
        address_map={1: (0x401000, 0x401004), 2: 0x401010},
    )
    listing.shift(RIGHT * -3)
    assembly = AssemblyStub((0x401000, 0x401004, 0x401010))
    links = SourceAssemblyMap(listing, assembly)

    assert len(links.connection(1, 0x401000)) == 1
    assert len(links.resolve(SourceRef(1, "demo.c"))) == 2
    assert len(links.resolve(AddressRef(0x401010))) == 1
    assert isinstance(links.follow(1, 0x401004), Animation)


def test_source_assembly_map_supports_explicit_specs_and_rejects_missing_targets() -> None:
    listing = SourceListing("return 0;", filename="demo.c")
    assembly = AssemblyStub((0x401000,))
    link = SourceAssemblyMap(
        listing,
        assembly,
        [SourceAssemblyLinkSpec(1, 0x401000, "return")],
    )
    assert len(link.connection(1, 0x401000)) == 1

    with pytest.raises(LookupError, match="cannot resolve address"):
        SourceAssemblyMap(
            listing,
            assembly,
            [SourceAssemblyLinkSpec(1, 0xDEADBEEF)],
        )
