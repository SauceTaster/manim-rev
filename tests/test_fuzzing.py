from __future__ import annotations

import pytest
from manim import Animation

from manim_rev.fuzzing import CoverageBitmap, CoverageMap, CrashCard, FuzzingDashboard
from manim_rev.refs import AddressRangeRef, AddressRef


def test_coverage_bitmap_exposes_counts_cells_and_address_refs() -> None:
    bitmap = CoverageBitmap([0, 1, 0, 8], columns=2, base_address=0x5000)

    assert CoverageMap is CoverageBitmap
    assert bitmap.hits == (0, 1, 0, 8)
    assert bitmap.covered_count == 2
    assert bitmap.coverage_ratio == pytest.approx(0.5)
    assert bitmap.resolve(AddressRef(0x5001)) == (bitmap.cell(1),)
    assert bitmap.resolve(AddressRangeRef(0x5001, 2)) == (
        bitmap.cell(1),
        bitmap.cell(2),
    )
    assert bitmap.resolve(AddressRef(0x6000)) == ()

    sparse = CoverageBitmap([1, 0, 2], addresses=(0x401000, 0x401020, 0x402000))
    assert sparse.resolve(AddressRef(0x401020)) == (sparse.cell(1),)
    assert sparse.resolve(AddressRangeRef(0x401010, 0x20)) == (sparse.cell(1),)


def test_coverage_bitmap_updates_state_and_returns_animations() -> None:
    bitmap = CoverageBitmap({0: 0, 2: 3}, columns=3, show_counts=True)

    assert isinstance(bitmap.animate_hit(0), Animation)
    assert bitmap.hits == (1, 0, 3)
    assert isinstance(bitmap.animate_update([0, 2, 0]), Animation)
    assert bitmap.hits == (0, 2, 0)
    assert bitmap.set_hit(2, 9) is bitmap
    assert bitmap.hits == (0, 2, 9)
    assert isinstance(bitmap.focus(2), Animation)

    with pytest.raises(IndexError, match="outside"):
        bitmap.cell(3)
    with pytest.raises(ValueError, match="preserve"):
        bitmap.animate_update([1, 2])


def test_fuzzing_dashboard_has_stable_metrics_and_crash_animation() -> None:
    dashboard = FuzzingDashboard(
        executions=1000,
        execs_per_second=250,
        coverage=0.25,
        crashes=1,
        corpus_size=12,
    )

    assert dashboard.metric("coverage") is dashboard.rows["coverage"]
    assert isinstance(dashboard.animate_update(executions=2000, coverage=0.5), Animation)
    assert dashboard.metrics["executions"] == 2000
    assert dashboard.metrics["coverage"] == 0.5
    assert isinstance(dashboard.animate_crash(), Animation)
    assert dashboard.metrics["crashes"] == 2
    assert dashboard.set_metric("corpus_size", 20) is dashboard

    with pytest.raises(KeyError, match="unknown fuzzing metric"):
        dashboard.metric("paths")
    with pytest.raises(ValueError, match="at least one"):
        dashboard.animate_update()
    with pytest.raises(ValueError, match="non-negative"):
        dashboard.set_metric("coverage", -0.1)


def test_crash_card_resolves_fault_address_and_builds_reveal() -> None:
    card = CrashCard(
        "SIGSEGV",
        0x41414141,
        b"A" * 32,
        reason="instruction pointer controlled by the test case",
    )

    assert card.resolve(AddressRef(0x41414141)) == (card.address,)
    assert card.resolve(AddressRangeRef(0x41414140, 4)) == (card.address,)
    assert card.resolve(AddressRef(0xDEADBEEF)) == ()
    assert isinstance(card.focus_fault(), Animation)
    assert isinstance(card.animate_reveal(), Animation)


@pytest.mark.parametrize(
    ("hits", "columns", "message"),
    [([], 4, "at least one"), ([0], 0, "positive"), ([0, -1], 2, "cannot be negative")],
)
def test_coverage_bitmap_validates_input(
    hits: list[int],
    columns: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CoverageBitmap(hits, columns=columns)


def test_coverage_bitmap_validates_explicit_address_mapping() -> None:
    with pytest.raises(ValueError, match="either"):
        CoverageBitmap([1], base_address=0x1000, addresses=(0x1000,))
    with pytest.raises(ValueError, match="bitmap size"):
        CoverageBitmap([1, 0], addresses=(0x1000,))
    with pytest.raises(ValueError, match="unique"):
        CoverageBitmap([1, 0], addresses=(0x1000, 0x1000))
