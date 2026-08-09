"""angr-style symbolic fork, constraint, and stash talk examples.

Render all scenes in this file with:

    manim -ql examples/security/symbolic_execution.py
"""

from __future__ import annotations

from _common import callout, place_content, scene_heading
from manim import DOWN, RIGHT, AnimationGroup, FadeIn, VGroup

from manim_rev import (
    RevScene,
    StashPanel,
    StateStatus,
    SymbolicEdgeSpec,
    SymbolicExecutionTree,
    SymbolicStateRef,
    SymbolicStateSpec,
)


class SymbolicForkConstraintWalkthrough(RevScene):
    """Trace the satisfiable fork that reaches a guarded parser target."""

    def construct(self) -> None:
        heading = scene_heading("Which bytes reach the hidden parser?", "symbolic constraints")
        states = (
            SymbolicStateSpec("entry", 0x401000, ("packet bytes are symbolic",), label="entry"),
            SymbolicStateSpec(
                "magic",
                0x401020,
                ("packet[0:4] == 'MSG!'",),
                label="magic matched",
            ),
            SymbolicStateSpec(
                "reject",
                0x401090,
                ("packet[0:4] != 'MSG!'",),
                StateStatus.AVOIDED,
                label="reject",
            ),
            SymbolicStateSpec(
                "target",
                0x40105C,
                (
                    "packet[0:4] == 'MSG!'",
                    "length == 8",
                    "kind == 3",
                    "checksum == 0xA7",
                ),
                StateStatus.FOUND,
                label="hidden parser",
            ),
            SymbolicStateSpec(
                "oversize",
                0x4010B0,
                ("packet[0:4] == 'MSG!'", "length > 4096"),
                StateStatus.AVOIDED,
                label="oversize avoided",
            ),
        )
        edges = (
            SymbolicEdgeSpec("entry", "magic", "magic == 'MSG!'"),
            SymbolicEdgeSpec("entry", "reject", "otherwise"),
            SymbolicEdgeSpec("magic", "target", "len == 8"),
            SymbolicEdgeSpec("magic", "oversize", "len > 4096"),
        )
        tree = SymbolicExecutionTree(
            states,
            edges,
            node_width=2.7,
            horizontal_gap=0.42,
            vertical_gap=0.5,
        )
        constraints = tree.constraint_panel(
            "target",
            width=4.9,
            max_visible=5,
            title="winning solver query",
        )
        takeaway = callout(
            "model",
            "One satisfying packet is MSG! + length 8 + kind 3 + checksum A7.",
            width=4.9,
            color=self.theme.success,
        )
        side = VGroup(constraints, takeaway).arrange(DOWN, buff=0.3)
        content = VGroup(tree, side).arrange(RIGHT, buff=0.5)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(tree), run_time=0.5)
        self.play(tree.animate_fork("entry"), run_time=0.68)
        self.play(tree.animate_fork("magic"), run_time=0.68)
        self.play(FadeIn(constraints), tree.trace(("entry", "magic", "target")), run_time=0.9)
        self.play(constraints.focus(3), FadeIn(takeaway), run_time=0.45)
        self.wait(0.2)


class SymbolicStashLifecycle(RevScene):
    """Explain how a SimulationManager moves states between named stashes."""

    def construct(self) -> None:
        heading = scene_heading(
            "States move; the search policy stays visible", "angr-style stashes"
        )
        tree = SymbolicExecutionTree(
            (
                SymbolicStateSpec("root", 0x400F00, ("stdin symbolic",), label="initial state"),
                SymbolicStateSpec(
                    "candidate",
                    0x401010,
                    ("byte0 == 0x41",),
                    label="candidate",
                ),
                SymbolicStateSpec(
                    "reject",
                    0x401080,
                    ("byte0 != 0x41",),
                    StateStatus.AVOIDED,
                    label="avoid hook",
                ),
                SymbolicStateSpec(
                    "goal",
                    0x401044,
                    ("byte0 == 0x41", "byte1 == 0x42"),
                    StateStatus.FOUND,
                    label="find hook",
                ),
            ),
            (
                SymbolicEdgeSpec("root", "candidate", "'A'"),
                SymbolicEdgeSpec("root", "reject", "not 'A'"),
                SymbolicEdgeSpec("candidate", "goal", "next == 'B'"),
            ),
            node_width=2.75,
            horizontal_gap=0.46,
            vertical_gap=0.55,
        )
        stashes = StashPanel(
            {
                StateStatus.ACTIVE: ("root",),
                StateStatus.FOUND: (),
                StateStatus.AVOIDED: (),
                StateStatus.UNSAT: 0,
                StateStatus.DEADENDED: 0,
            },
            width=4.0,
        )
        takeaway = callout(
            "search invariant",
            "Found and avoided states stop consuming the active-step budget.",
            width=4.0,
            color=self.theme.info,
        )
        side = VGroup(stashes, takeaway).arrange(DOWN, buff=0.32)
        content = VGroup(tree, side).arrange(RIGHT, buff=0.58)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(tree), FadeIn(side), run_time=0.5)
        self.play(
            tree.animate_fork("root"),
            stashes.animate_update(StateStatus.ACTIVE, ("candidate",)),
            stashes.animate_update(StateStatus.AVOIDED, ("reject",)),
            run_time=0.8,
        )
        self.play(
            tree.trace(("root", "candidate", "goal")),
            AnimationGroup(
                stashes.animate_update(StateStatus.ACTIVE, ()),
                stashes.animate_update(StateStatus.FOUND, ("goal",)),
                lag_ratio=0.08,
            ),
            run_time=0.9,
        )
        self.play(
            tree.focus(SymbolicStateRef("goal")),
            stashes.focus(SymbolicStateRef("goal")),
            run_time=0.48,
        )
        self.wait(0.2)
