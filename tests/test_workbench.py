from __future__ import annotations

import numpy as np
import pytest
from manim import Animation, Circle, Square, VGroup

from manim_rev.refs import (
    AddressRangeRef,
    AddressRef,
    ExecutedAddressRef,
    MemoryRangeRef,
)
from manim_rev.workbench import AnalysisWorkbench, ReferenceLink


class AddressPanel(VGroup):
    def __init__(self, address: int) -> None:
        super().__init__()
        self.address = address
        self.target = Square()
        self.add(self.target)

    def resolve(self, ref):  # type: ignore[no-untyped-def]
        if isinstance(ref, AddressRef) and ref.address == self.address:
            return (self.target,)
        if isinstance(ref, AddressRangeRef) and ref.start <= self.address < ref.start + ref.length:
            return (self.target,)
        return ()


class RecordingPanel(VGroup):
    def __init__(self, targets: tuple[Square, ...]) -> None:
        super().__init__(*targets)
        self.targets = targets
        self.seen = []

    def resolve(self, ref):  # type: ignore[no-untyped-def]
        self.seen.append(ref)
        return self.targets


def test_workbench_focus_and_link() -> None:
    left = AddressPanel(0x1000)
    right = AddressPanel(0x2000)
    workbench = AnalysisWorkbench({"trace": left, "memory": right})
    assert workbench.panel("trace") is left
    assert isinstance(workbench.focus(AddressRef(0x1000)), Animation)
    link = workbench.link(
        "trace",
        AddressRef(0x1000),
        "memory",
        AddressRangeRef(0x2000, 4),
        label="write",
        path_arc=0.25,
    )
    assert isinstance(link, ReferenceLink)
    assert link.path_arc == pytest.approx(0.25)
    assert isinstance(link.animate_flow(), Animation)
    assert not np.allclose(link.arrow.get_start(), left.get_center())
    assert not np.allclose(link.arrow.get_end(), right.get_center())


def test_workbench_validation_and_missing_refs() -> None:
    with pytest.raises(ValueError, match="at least one"):
        AnalysisWorkbench({})
    workbench = AnalysisWorkbench({"only": AddressPanel(1)})
    with pytest.raises(LookupError, match="no workbench"):
        workbench.focus(AddressRef(2))
    mixed = AnalysisWorkbench({"resolver": AddressPanel(1), "plain": Circle()})
    with pytest.raises(LookupError, match="does not support"):
        mixed.link("plain", AddressRef(1), "resolver", AddressRef(1))


def test_workbench_link_selects_reference_occurrences() -> None:
    sources = (
        Square().shift(np.array([-1.0, 1.0, 0.0])),
        Square().shift(np.array([-1.0, -1.0, 0.0])),
    )
    targets = (
        Square().shift(np.array([1.0, 1.0, 0.0])),
        Square().shift(np.array([1.0, -1.0, 0.0])),
    )
    source_panel = RecordingPanel(sources)
    target_panel = RecordingPanel(targets)
    workbench = AnalysisWorkbench({"source": source_panel, "target": target_panel})

    link = workbench.link(
        "source",
        AddressRef(1),
        "target",
        AddressRef(2),
        source_occurrence=1,
        target_occurrence=1,
    )

    assert link.source is sources[1]
    assert link.target is targets[1]
    with pytest.raises(ValueError, match="non-negative"):
        workbench.link("source", AddressRef(1), "target", AddressRef(2), source_occurrence=-1)
    with pytest.raises(LookupError, match="source occurrence"):
        workbench.link("source", AddressRef(1), "target", AddressRef(2), source_occurrence=2)


def test_breakpoint_to_memory_uses_explicit_semantic_refs() -> None:
    breakpoint_panel = RecordingPanel((Square(),))
    memory_panel = RecordingPanel((Square(),))
    workbench = AnalysisWorkbench(
        {"trace": breakpoint_panel, "memory": memory_panel},
    )

    workbench.breakpoint_to_memory(
        breakpoint_panel="trace",
        instruction_address=0x401000,
        memory_panel="memory",
        memory_address=0x600000,
        length=4,
    )

    assert breakpoint_panel.seen == [ExecutedAddressRef(0x401000)]
    assert memory_panel.seen == [MemoryRangeRef(0x600000, 4)]


def test_workbench_uses_horizontal_then_vertical_spacing() -> None:
    panels = {str(index): AddressPanel(index) for index in range(4)}
    _workbench = AnalysisWorkbench(
        panels,
        columns=2,
        horizontal_buff=0.8,
        vertical_buff=0.1,
    )
    horizontal_gap = panels["1"].get_left()[0] - panels["0"].get_right()[0]
    vertical_gap = panels["0"].get_bottom()[1] - panels["2"].get_top()[1]
    assert horizontal_gap == pytest.approx(0.8)
    assert vertical_gap == pytest.approx(0.1)


def test_workbench_centers_an_incomplete_trailing_row() -> None:
    panels = {str(index): AddressPanel(index) for index in range(3)}
    _workbench = AnalysisWorkbench(panels, columns=2)
    first_row_center = VGroup(panels["0"], panels["1"]).get_center()[0]

    assert panels["2"].get_center()[0] == pytest.approx(first_row_center)
