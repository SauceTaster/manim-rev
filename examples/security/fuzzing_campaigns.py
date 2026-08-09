"""Coverage-growth and crash-triage talk examples.

Render all scenes in this file with:

    manim -ql examples/security/fuzzing_campaigns.py
"""

from __future__ import annotations

from collections.abc import Mapping

from _common import callout, place_content, scene_heading
from manim import DOWN, RIGHT, AnimationGroup, FadeIn, VGroup

from manim_rev import CoverageBitmap, CrashCard, FuzzingDashboard, RevScene


def _coverage_snapshot(size: int, counts: Mapping[int, int]) -> list[int]:
    """Expand a sparse recorded coverage snapshot for ``CoverageBitmap``."""

    snapshot = [0] * size
    for index, count in counts.items():
        snapshot[index] = count
    return snapshot


class FuzzCoverageGrowthCampaign(RevScene):
    """Present three meaningful campaign snapshots instead of every generated input."""

    def construct(self) -> None:
        heading = scene_heading(
            "One mutation unlocks a new parser state", "coverage-guided fuzzing"
        )
        seed_hits = _coverage_snapshot(
            96,
            {0: 91, 1: 91, 2: 91, 16: 40, 17: 40, 32: 7},
        )
        grammar_hits = _coverage_snapshot(
            96,
            {
                0: 255,
                1: 255,
                2: 255,
                16: 180,
                17: 180,
                18: 31,
                32: 76,
                33: 18,
                34: 4,
                49: 2,
            },
        )
        checksum_hits = _coverage_snapshot(
            96,
            {
                0: 255,
                1: 255,
                2: 255,
                3: 1,
                16: 255,
                17: 255,
                18: 63,
                19: 1,
                32: 120,
                33: 38,
                34: 9,
                35: 1,
                49: 5,
                50: 1,
                66: 1,
            },
        )
        dashboard = FuzzingDashboard(
            executions=128,
            execs_per_second=7_850,
            coverage="6 / 96",
            corpus_size=4,
            crashes=0,
            title="recorded campaign",
        )
        coverage = CoverageBitmap(seed_hits, columns=16, title="edge hit counts")
        notes = VGroup(
            callout("seed corpus", "Six edges establish the parser's shallow path.", width=3.55),
            callout(
                "grammar token",
                "A valid length field grows coverage from six edges to ten.",
                width=3.55,
                color=self.theme.opcode,
            ),
            callout(
                "checksum byte",
                "A single retained mutation opens five new edges.",
                width=3.55,
                color=self.theme.success,
            ),
        ).arrange(RIGHT, buff=0.24)
        top = VGroup(dashboard, coverage).arrange(RIGHT, buff=0.62)
        content = VGroup(top, notes).arrange(DOWN, buff=0.42)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(top), FadeIn(notes[0]), run_time=0.48)
        self.play(
            coverage.animate_update(grammar_hits),
            dashboard.animate_update(executions=18_420, coverage="10 / 96", corpus_size=11),
            FadeIn(notes[1]),
            run_time=0.75,
        )
        self.play(
            coverage.animate_update(checksum_hits),
            dashboard.animate_update(executions=74_903, coverage="15 / 96", corpus_size=17),
            FadeIn(notes[2]),
            run_time=0.75,
        )
        self.play(coverage.focus(66), run_time=0.38)
        self.wait(0.2)


class FuzzCrashTriageWalkthrough(RevScene):
    """Move from a new edge to a reproducible, deduplicated crash report."""

    def construct(self) -> None:
        heading = scene_heading("Turn a red counter into a useful crash", "crash triage")
        dashboard = FuzzingDashboard(
            executions=2_483_110,
            execs_per_second=9_120,
            coverage="71.4%",
            corpus_size=263,
            crashes=0,
        )
        coverage = CoverageBitmap(
            _coverage_snapshot(
                48,
                {0: 255, 1: 255, 2: 255, 12: 81, 13: 31, 24: 8, 25: 2},
            ),
            columns=12,
            cell_size=0.3,
            title="faulting path",
        )
        left = VGroup(dashboard, coverage).arrange(DOWN, buff=0.28)
        crash = CrashCard(
            "SIGSEGV",
            0x4012D7,
            b"LEN=65535;DATA=" + b"A" * 32,
            reason="heap-buffer-overflow in decode_record while copying DATA",
            reproducible=True,
            max_input_bytes=8,
        )
        decision = callout(
            "deduplication",
            "Stable input + new top frame = one new root-cause bucket.",
            width=5.8,
            color=self.theme.success,
        )
        right = VGroup(crash, decision).arrange(DOWN, buff=0.35)
        content = VGroup(left, right).arrange(RIGHT, buff=0.58)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(left), run_time=0.48)
        self.play(
            AnimationGroup(
                coverage.animate_hit(37, 1),
                dashboard.animate_update(executions=2_483_111, coverage="72.0%"),
                lag_ratio=0.06,
            ),
            run_time=0.62,
        )
        self.play(dashboard.animate_crash(), coverage.focus(37), run_time=0.55)
        self.play(crash.animate_reveal(), run_time=0.7)
        self.play(FadeIn(decision, shift=DOWN * 0.08), run_time=0.35)
        self.wait(0.2)
