"""Walk from a source condition to its assembly and cross references.

Render with::

    manim -pql --renderer cairo examples/source_xrefs.py SourceXRefWalkthrough
"""

from __future__ import annotations

from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, VGroup

from manim_rev import (
    BasicBlockSpec,
    CFGEdgeSpec,
    ControlFlowGraph,
    CrossReferencePanel,
    EdgeKind,
    InstructionSpec,
    RevScene,
    SourceAssemblyMap,
    SourceListing,
    SourceRef,
    XRefSpec,
    focus_across,
    label_text,
    mono_text,
)

COMPARE = 0x40100B
TEST_RESULT = 0x401010
BRANCH = 0x401012
AUDIT_SUCCESS = 0x401017
REJECT = 0x401030


class SourceXRefWalkthrough(RevScene):
    """Connect one C branch to its basic blocks, calls, and code references."""

    def construct(self) -> None:
        title = self.title_card(
            "Source to Cross-Reference",
            "follow one condition through lowered instructions and outgoing calls",
        )
        title.scale(0.58).to_edge(UP, buff=0.16)

        source = SourceListing(
            """int authenticate(char *user) {
    char key[8];
    load_key(key);
    if (strcmp(user, key) == 0) {
        audit_success(user);
        return 1;
    }
    return 0;
}""",
            filename="auth.c",
            width=5.15,
            row_height=0.31,
            address_map={
                4: (COMPARE, TEST_RESULT, BRANCH),
                5: AUDIT_SUCCESS,
                8: REJECT,
            },
            theme=self.theme,
        )

        cfg = ControlFlowGraph(
            (
                BasicBlockSpec(
                    "check",
                    COMPARE,
                    (
                        InstructionSpec(COMPARE, "call", "strcmp@plt", b"\xe8\x20\x00\x00\x00"),
                        InstructionSpec(TEST_RESULT, "test", "eax, eax", b"\x85\xc0"),
                        InstructionSpec(BRANCH, "jne", "0x401030", b"\x75\x1c"),
                    ),
                    label="compare credentials",
                ),
                BasicBlockSpec(
                    "accept",
                    AUDIT_SUCCESS,
                    (
                        InstructionSpec(
                            AUDIT_SUCCESS,
                            "call",
                            "audit_success",
                            b"\xe8\x54\x00\x00\x00",
                        ),
                        InstructionSpec(0x40101C, "mov", "eax, 1", b"\xb8\x01\x00\x00\x00"),
                        InstructionSpec(0x401021, "ret", raw_bytes=b"\xc3"),
                    ),
                    label="accepted path",
                ),
                BasicBlockSpec(
                    "reject",
                    REJECT,
                    (
                        InstructionSpec(REJECT, "xor", "eax, eax", b"\x31\xc0"),
                        InstructionSpec(0x401032, "ret", raw_bytes=b"\xc3"),
                    ),
                    label="rejected path",
                ),
            ),
            (
                CFGEdgeSpec("check", "accept", EdgeKind.FALSE, "ZF = 1"),
                CFGEdgeSpec("check", "reject", EdgeKind.TRUE, "ZF = 0"),
            ),
            block_width=3.15,
            compact_addresses=True,
            horizontal_gap=0.38,
            vertical_gap=0.46,
            theme=self.theme,
        )

        xrefs = CrossReferencePanel(
            (
                XRefSpec("auth.c:4", "0x0040100B", "call", "strcmp@plt"),
                XRefSpec("auth.c:5", "0x00401017", "call", "audit_success"),
                XRefSpec("0x00401012", "reject", "code", "JNE when unequal"),
            ),
            width=7.5,
            row_height=0.38,
            title="outgoing cross references",
            theme=self.theme,
        )

        top = VGroup(source, cfg).arrange(RIGHT, buff=0.72, aligned_edge=UP)
        top.scale_to_fit_width(12.7).next_to(title, DOWN, buff=0.22)
        xrefs.scale(0.88).next_to(top, DOWN, buff=0.24)
        xrefs.align_to(source, LEFT)

        links = SourceAssemblyMap(
            source,
            cfg,
            {
                4: (COMPARE, BRANCH),
                5: AUDIT_SUCCESS,
                8: REJECT,
            },
            color=self.theme.info,
            theme=self.theme,
        )

        source_label = label_text(
            "SOURCE",
            font_size=14,
            color=self.theme.muted,
            theme=self.theme,
            weight="BOLD",
        ).next_to(source, UP, buff=0.08, aligned_edge=LEFT)
        cfg_label = label_text(
            "LOWERED CONTROL FLOW",
            font_size=14,
            color=self.theme.muted,
            theme=self.theme,
            weight="BOLD",
        ).next_to(cfg, UP, buff=0.08, aligned_edge=LEFT)

        footer = mono_text(
            "same fact, three views: source line  ->  instruction address  ->  xref",
            font_size=16,
            color=self.theme.muted,
            theme=self.theme,
        ).to_edge(DOWN, buff=0.16)

        self.play(FadeIn(title, shift=UP * 0.1), run_time=0.5)
        self.play(
            FadeIn(top, shift=UP * 0.08),
            FadeIn(source_label),
            FadeIn(cfg_label),
            FadeIn(xrefs, shift=UP * 0.08),
            run_time=0.75,
        )
        self.play(Create(links), run_time=0.65)

        condition = SourceRef(4, "auth.c")
        self.play(
            focus_across(condition, source, xrefs, color=self.theme.warning),
            run_time=0.55,
        )
        self.play(links.follow(4, COMPARE), run_time=0.7)
        self.play(cfg.traverse(("check", "accept")), run_time=0.85)

        self.play(source.focus(5, color=self.theme.call), run_time=0.42)
        self.play(links.follow(5, AUDIT_SUCCESS, color=self.theme.call), run_time=0.7)
        self.play(xrefs.follow(1, color=self.theme.warning), run_time=0.7)
        self.play(FadeIn(footer, shift=UP * 0.08), run_time=0.45)
        self.wait(0.8)
