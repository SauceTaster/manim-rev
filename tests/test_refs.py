from __future__ import annotations

import pytest
from manim import Animation, Square

from manim_rev.refs import (
    AddressRangeRef,
    AddressRef,
    ExecutedAddressRef,
    MemoryAddressRef,
    MemoryRangeRef,
    focus_across,
)


class Resolver:
    def __init__(self) -> None:
        self.square = Square()

    def resolve(self, ref):  # type: ignore[no-untyped-def]
        return (self.square,) if ref == AddressRef(0x10) else ()


def test_address_range_requires_positive_length() -> None:
    with pytest.raises(ValueError, match="positive"):
        AddressRangeRef(0x1000, 0)


def test_semantic_address_refs_remain_compatible_with_address_resolvers() -> None:
    assert isinstance(ExecutedAddressRef(0x1000), AddressRef)
    assert isinstance(MemoryAddressRef(0x2000), AddressRef)
    assert isinstance(MemoryRangeRef(0x2000, 4), AddressRangeRef)
    with pytest.raises(ValueError, match="positive"):
        MemoryRangeRef(0x2000, 0)


def test_focus_across_collects_matching_views() -> None:
    assert isinstance(focus_across(AddressRef(0x10), Resolver(), Resolver()), Animation)
    with pytest.raises(LookupError, match="no view"):
        focus_across(AddressRef(0x11), Resolver())
