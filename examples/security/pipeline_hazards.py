"""Pipeline hazard and speculative-execution talk examples.

Render all scenes in this file with:

    manim -ql examples/security/pipeline_hazards.py
"""

from __future__ import annotations

from _common import callout, legend, place_content, scene_heading
from manim import DOWN, RIGHT, FadeIn, VGroup

from manim_rev import PipelineDiagram, PipelineInstruction, RevScene


class PipelineLoadUseHazard(RevScene):
    """Show the bubble needed when an ALU instruction consumes a load too early."""

    def construct(self) -> None:
        heading = scene_heading("The value arrives one cycle too late", "load-use hazard")
        pipeline = PipelineDiagram(
            (
                PipelineInstruction("ld r1,[r2]", 0),
                PipelineInstruction("add r3,r1", 1, stalled_cycles=(3,)),
                PipelineInstruction("xor r4,r4", 2, stalled_cycles=(3,)),
            ),
            cell_width=0.92,
            cell_height=0.56,
        )
        key = legend(
            (
                ("normal stage", self.theme.info),
                ("stall bubble", self.theme.danger),
                ("cycle under discussion", self.theme.warning),
            )
        )
        notes = VGroup(
            callout(
                "cycle 3",
                "The load is still in MEM while ADD needs r1 for EX.",
                width=5.15,
                color=self.theme.danger,
            ),
            callout(
                "cycle 4",
                "Forward the loaded value, then let ADD enter EX.",
                width=5.15,
                color=self.theme.success,
            ),
        ).arrange(RIGHT, buff=0.3)
        content = VGroup(pipeline, key, notes).arrange(DOWN, buff=0.38)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(pipeline), FadeIn(key), run_time=0.48)
        self.play(pipeline.highlight_cycle(3), run_time=0.6)
        self.play(FadeIn(notes[0], shift=DOWN * 0.08), run_time=0.32)
        self.play(pipeline.highlight_cycle(4), run_time=0.6)
        self.play(FadeIn(notes[1], shift=DOWN * 0.08), run_time=0.32)
        self.wait(0.2)


class PipelineBranchMispredictSquash(RevScene):
    """Make the cost of a branch misprediction visible as squashed younger work."""

    def construct(self) -> None:
        heading = scene_heading("A wrong prediction wastes two instructions", "branch recovery")
        pipeline = PipelineDiagram(
            (
                PipelineInstruction("cmp r0,#0", 0),
                PipelineInstruction("b.eq ok", 1),
                PipelineInstruction("wrong: ld", 2, squashed_at_cycle=3),
                PipelineInstruction("wrong: add", 3, squashed_at_cycle=3),
                PipelineInstruction("ok: ret", 4),
            ),
            cell_width=0.78,
            cell_height=0.48,
        )
        notes = VGroup(
            callout(
                "resolve",
                "The branch outcome becomes known in EX at cycle 3.",
                width=3.55,
                color=self.theme.warning,
            ),
            callout(
                "squash",
                "X marks younger wrong-path work that cannot retire.",
                width=3.55,
                color=self.theme.danger,
            ),
            callout(
                "redirect",
                "Fetch restarts at the correct target in cycle 4.",
                width=3.55,
                color=self.theme.success,
            ),
        ).arrange(RIGHT, buff=0.24)
        content = VGroup(pipeline, notes).arrange(DOWN, buff=0.45)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(pipeline), run_time=0.48)
        self.play(pipeline.highlight_cycle(3), run_time=0.58)
        self.play(FadeIn(notes[0]), run_time=0.28)
        self.play(pipeline.highlight_cycle(4), FadeIn(notes[1]), run_time=0.58)
        self.play(FadeIn(notes[2]), run_time=0.28)
        self.wait(0.2)
