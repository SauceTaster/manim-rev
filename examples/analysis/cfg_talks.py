"""Control-flow recovery examples for reverse-engineering talks.

Render every scene in this file with::

    manim -ql --renderer cairo examples/analysis/cfg_talks.py \
        LoopAndCallRecovery DenseDispatchRecovery TraceBackedBranchRecovery

The examples intentionally use Manim Rev's deterministic layout.  They do not
require Graphviz or LaTeX.
"""

from __future__ import annotations

from manim import DOWN, UP, FadeIn, VGroup

from manim_rev import (
    AddressRef,
    AnalysisWorkbench,
    BasicBlock,
    BasicBlockSpec,
    CFGEdgeSpec,
    ControlFlowGraph,
    EdgeKind,
    ExecutionTrace,
    InstructionSpec,
    RevScene,
    TraceEvent,
    TracePhase,
    label_text,
)


def _title(scene: RevScene, heading: str, subtitle: str) -> VGroup:
    card = scene.title_card(heading, subtitle)
    card.scale(0.56)
    if card.width > 12.8:
        card.scale_to_fit_width(12.8)
    card.to_edge(UP, buff=0.13)
    return card


def _under_title(
    content: VGroup,
    title: VGroup,
    *,
    max_width: float = 12.9,
    max_height: float = 6.1,
) -> VGroup:
    if content.width > max_width:
        content.scale_to_fit_width(max_width)
    if content.height > max_height:
        content.scale_to_fit_height(max_height)
    content.next_to(title, DOWN, buff=0.2)
    return content


def _footer(scene: RevScene, text: str):  # type: ignore[no-untyped-def]
    note = label_text(text, font_size=16, color=scene.theme.muted, theme=scene.theme)
    if note.width > 12.7:
        note.scale_to_fit_width(12.7)
    note.to_edge(DOWN, buff=0.13)
    return note


def _block(
    spec: BasicBlockSpec,
    scene: RevScene,
    *,
    width: float = 2.65,
) -> BasicBlock:
    return BasicBlock(
        spec,
        width=width,
        row_height=0.32,
        compact_addresses=True,
        theme=scene.theme,
    )


class LoopAndCallRecovery(RevScene):
    """Explain a recovered loop whose body crosses a call boundary."""

    def construct(self) -> None:
        title = _title(
            self,
            "Recovering a Loop Across a Call",
            "the back edge is obvious only after matching CALL and RETURN",
        )
        specs = (
            BasicBlockSpec(
                "entry",
                0x401000,
                (InstructionSpec(0x401000, "xor", "ecx, ecx"),),
                label="initialize index",
            ),
            BasicBlockSpec(
                "header",
                0x401006,
                (
                    InstructionSpec(0x401006, "cmp", "ecx, 4"),
                    InstructionSpec(0x401009, "jae", "done"),
                ),
                label="loop header",
            ),
            BasicBlockSpec(
                "body",
                0x40100B,
                (
                    InstructionSpec(0x40100B, "mov", "edi, ecx"),
                    InstructionSpec(0x40100D, "call", "inspect_item"),
                ),
                label="loop body",
            ),
            BasicBlockSpec(
                "helper",
                0x401020,
                (
                    InstructionSpec(0x401020, "test", "edi, edi"),
                    InstructionSpec(0x401022, "ret"),
                ),
                label="inspect_item",
            ),
            BasicBlockSpec(
                "latch",
                0x401015,
                (
                    InstructionSpec(0x401015, "inc", "ecx"),
                    InstructionSpec(0x401017, "jmp", "loop header"),
                ),
                label="latch",
            ),
            BasicBlockSpec(
                "done",
                0x40102A,
                (InstructionSpec(0x40102A, "ret"),),
                label="exit",
            ),
        )
        graph = ControlFlowGraph(
            tuple(_block(spec, self) for spec in specs),
            (
                CFGEdgeSpec("entry", "header"),
                CFGEdgeSpec("header", "body", EdgeKind.FALSE, "continue"),
                CFGEdgeSpec("header", "done", EdgeKind.TRUE, "exit"),
                CFGEdgeSpec("body", "helper", EdgeKind.CALL, "call"),
                CFGEdgeSpec("helper", "latch", EdgeKind.RETURN, "return"),
                CFGEdgeSpec("latch", "header", EdgeKind.LOOP, "repeat"),
            ),
            positions={
                "entry": (-2.0, 2.55),
                "header": (-2.0, 1.05),
                "body": (-2.0, -0.7),
                "helper": (1.25, -0.7),
                "latch": (-2.0, -2.35),
                "done": (2.1, 1.05),
            },
            horizontal_gap=0.4,
            vertical_gap=0.3,
            theme=self.theme,
        )
        _under_title(graph, title, max_width=11.7, max_height=5.85)
        footer = _footer(self, "entry -> header -> body -> helper -> latch -> header -> exit")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(graph, shift=UP * 0.08), run_time=0.4)
        self.play(
            graph.traverse(("entry", "header", "body", "helper", "latch", "header", "done")),
            run_time=2.0,
        )
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class DenseDispatchRecovery(RevScene):
    """Triage a dense switch-like branch without losing the merge point."""

    def construct(self) -> None:
        title = _title(
            self,
            "Taming a Dense Dispatch Block",
            "five outgoing cases still converge on one shared epilogue",
        )
        case_specs = (
            *(
                BasicBlockSpec(
                    f"case{index}",
                    0x402020 + index * 0x10,
                    (InstructionSpec(0x402020 + index * 0x10, "mov", f"eax, {value}"),),
                    label=f"case {index}",
                )
                for index, value in enumerate((7, 11, 19, 23))
            ),
            BasicBlockSpec(
                "default",
                0x402060,
                (InstructionSpec(0x402060, "mov", "eax, 29"),),
                label="default",
            ),
        )
        case_keys = tuple(spec.key for spec in case_specs)
        table_case_keys = case_keys[:-1]
        specs = (
            BasicBlockSpec(
                "guard",
                0x402000,
                (
                    InstructionSpec(0x402000, "cmp", "edi, 3"),
                    InstructionSpec(0x402003, "ja", "default"),
                ),
                label="bounds check",
            ),
            BasicBlockSpec(
                "dispatch",
                0x402005,
                (InstructionSpec(0x402005, "jmp", "[table+rdi*8]"),),
                label="dispatch",
            ),
            *case_specs,
            BasicBlockSpec(
                "join",
                0x402080,
                (InstructionSpec(0x402080, "ret"),),
                label="epilogue",
            ),
        )
        graph = ControlFlowGraph(
            tuple(
                _block(
                    spec,
                    self,
                    width=2.8 if spec.key in {"guard", "dispatch"} else 2.25,
                )
                for spec in specs
            ),
            (
                CFGEdgeSpec("guard", "default", EdgeKind.TRUE, "> 3"),
                CFGEdgeSpec("guard", "dispatch", EdgeKind.FALSE, "0..3"),
                *(CFGEdgeSpec("dispatch", key, EdgeKind.UNCONDITIONAL) for key in table_case_keys),
                *(CFGEdgeSpec(key, "join", EdgeKind.UNCONDITIONAL) for key in case_keys),
            ),
            block_width=2.25,
            horizontal_gap=0.25,
            vertical_gap=0.58,
            theme=self.theme,
        )
        _under_title(graph, title, max_width=13.0, max_height=5.9)
        footer = _footer(self, "selected input: mode 3  |  recovered value: 23")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(graph, shift=UP * 0.08), run_time=0.45)
        self.play(graph.focus("guard", color=self.theme.info), run_time=0.35)
        self.play(graph.traverse(("guard", "dispatch", "case3", "join")), run_time=1.1)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class TraceBackedBranchRecovery(RevScene):
    """Use one recorded execution to validate a recovered CFG path."""

    def construct(self) -> None:
        title = _title(
            self,
            "Validate Static Control Flow with a Trace",
            "semantic addresses tie recovered blocks to the path actually observed",
        )
        branch = 0x403008
        accepted = 0x403010
        graph = ControlFlowGraph(
            (
                _block(
                    BasicBlockSpec(
                        "decode",
                        0x403000,
                        (
                            InstructionSpec(0x403000, "movzx", "eax, byte [rdi]"),
                            InstructionSpec(0x403004, "cmp", "al, 0x52"),
                            InstructionSpec(branch, "je", "accept"),
                        ),
                        label="decode tag",
                    ),
                    self,
                    width=2.75,
                ),
                _block(
                    BasicBlockSpec(
                        "reject",
                        0x403030,
                        (InstructionSpec(0x403030, "xor", "eax, eax"),),
                        label="unknown tag",
                    ),
                    self,
                    width=2.75,
                ),
                _block(
                    BasicBlockSpec(
                        "accept",
                        accepted,
                        (InstructionSpec(accepted, "call", "parse_record"),),
                        label="known tag",
                    ),
                    self,
                    width=2.75,
                ),
            ),
            (
                CFGEdgeSpec("decode", "accept", EdgeKind.TRUE, "tag = 0x52"),
                CFGEdgeSpec("decode", "reject", EdgeKind.FALSE, "other"),
            ),
            horizontal_gap=0.32,
            vertical_gap=0.62,
            theme=self.theme,
        )
        trace = ExecutionTrace(
            (
                TraceEvent(
                    0x403000,
                    "movzx eax, byte [rdi]",
                    {"eax": 0x52},
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x403004,
                    "cmp al, 0x52",
                    {"zf": 1},
                    note="known tag",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    branch,
                    "je 0x403010",
                    {"zf": 1},
                    note="taken",
                    phase=TracePhase.BEFORE,
                ),
                TraceEvent(
                    accepted,
                    "call parse_record",
                    {"rdi": 0x605100},
                    phase=TracePhase.BEFORE,
                ),
                TraceEvent(
                    0x403015,
                    "test eax, eax",
                    {"eax": 1},
                    note="valid record",
                    phase=TracePhase.AFTER,
                ),
            ),
            breakpoints=(branch,),
            width=7.25,
            row_height=0.56,
            title="recorded trace",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {"recovered CFG": graph, "runtime trace": trace},
            columns=2,
            horizontal_buff=0.45,
            theme=self.theme,
        )
        _under_title(workbench, title, max_width=12.9, max_height=5.7)
        footer = _footer(
            self, "the trace confirms the TRUE edge; the reject block remains unobserved"
        )

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(workbench, shift=UP * 0.08), run_time=0.45)
        self.play(trace.run_to_breakpoint(), run_time=0.55)
        self.play(workbench.focus(AddressRef(branch), color=self.theme.warning), run_time=0.4)
        link = workbench.link(
            "recovered CFG",
            AddressRef(accepted),
            "runtime trace",
            AddressRef(accepted),
            label="observed",
            color=self.theme.success,
        )
        self.play(link.animate_flow(), graph.traverse(("decode", "accept")), run_time=0.9)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)
