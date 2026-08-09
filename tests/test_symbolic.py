from __future__ import annotations

import pytest
from manim import Animation

from manim_rev.models import StateStatus, SymbolicEdgeSpec, SymbolicStateSpec
from manim_rev.refs import AddressRangeRef, AddressRef, SymbolicStateRef
from manim_rev.symbolic import ConstraintPanel, StashPanel, SymbolicExecutionTree


def _fork() -> tuple[list[SymbolicStateSpec], list[SymbolicEdgeSpec]]:
    states = [
        SymbolicStateSpec("root", 0x401000, ("x >= 0",)),
        SymbolicStateSpec("good", 0x401010, ("x >= 0", "x == 7"), StateStatus.FOUND),
        SymbolicStateSpec("bad", 0x401020, ("x >= 0", "x != 7"), StateStatus.AVOIDED),
        SymbolicStateSpec("done", 0x401030, (), StateStatus.DEADENDED),
    ]
    edges = [
        SymbolicEdgeSpec("root", "good", "x == 7"),
        SymbolicEdgeSpec("root", "bad", "x != 7"),
        SymbolicEdgeSpec("good", "done"),
    ]
    return states, edges


def test_constraint_panel_exposes_visible_rows_and_bound_state_ref() -> None:
    panel = ConstraintPanel(
        ("x > 0", "x < 10", "y == x + 1"),
        state_key="state-1",
        max_visible=2,
    )

    assert panel.constraint(0) is panel.rows[0]
    assert panel.resolve(SymbolicStateRef("state-1")) == (panel,)
    assert panel.resolve(SymbolicStateRef("other")) == ()
    assert isinstance(panel.focus(1), Animation)

    with pytest.raises(IndexError, match="hidden"):
        panel.constraint(2)


def test_symbolic_tree_layout_lookups_refs_and_animations() -> None:
    states, edges = _fork()
    tree = SymbolicExecutionTree(states, edges)

    assert tree.levels == {"root": 0, "good": 1, "bad": 1, "done": 2}
    assert tree.layers == {0: ("root",), 1: ("good", "bad"), 2: ("done",)}
    assert tree.state("root").spec is states[0]
    assert tree.edge("root", "good").spec is edges[0]
    assert tree.successors("root") == ("good", "bad")
    assert tree.predecessors("done") == ("good",)
    assert tree.resolve(SymbolicStateRef("good")) == (tree.state("good"),)
    assert tree.resolve(AddressRef(0x401010)) == (tree.state("good").address_mobject,)
    assert tree.resolve(AddressRangeRef(0x401018, 0x10)) == (tree.state("bad").address_mobject,)
    assert isinstance(tree.focus("root"), Animation)
    assert isinstance(tree.trace(("root", "good", "done")), Animation)
    assert isinstance(tree.animate_fork("root"), Animation)

    panel = tree.constraint_panel("good", max_visible=4)
    assert panel.constraints == states[1].constraints
    assert panel.resolve(SymbolicStateRef("good")) == (panel,)


def test_symbolic_tree_validates_structure_and_paths() -> None:
    states, edges = _fork()
    tree = SymbolicExecutionTree(states, edges)

    with pytest.raises(KeyError, match="unknown symbolic edge"):
        tree.trace(("good", "bad"))
    with pytest.raises(ValueError, match="cannot be empty"):
        tree.trace(())
    with pytest.raises(ValueError, match="not successors"):
        tree.animate_fork("good", ("bad",))
    with pytest.raises(KeyError, match="unknown state"):
        SymbolicExecutionTree(states, [SymbolicEdgeSpec("root", "missing")])


def test_stash_panel_tracks_members_counts_and_state_refs() -> None:
    panel = StashPanel(
        {
            StateStatus.ACTIVE: ("s0", "s1"),
            StateStatus.FOUND: ("win",),
            StateStatus.UNSAT: 3,
        }
    )

    assert panel.stash("active") is panel.rows[StateStatus.ACTIVE]
    assert panel.states(StateStatus.ACTIVE) == ("s0", "s1")
    assert panel.counts[StateStatus.UNSAT] == 3
    assert panel.resolve(SymbolicStateRef("win")) == (panel.stash("found"),)
    assert panel.resolve(SymbolicStateRef("unknown")) == ()
    assert isinstance(panel.animate_update("active", ("s2",)), Animation)
    assert panel.states("active") == ("s2",)
    assert panel.counts[StateStatus.ACTIVE] == 1
    assert isinstance(panel.focus(SymbolicStateRef("s2")), Animation)

    with pytest.raises(KeyError, match="not displayed"):
        panel.stash("errored")
    with pytest.raises(ValueError, match="unique"):
        panel.animate_update("active", ("same", "same"))
