"""Representative Manim Rev scenes.

Render one scene with, for example:

    manim examples/showcase.py ReverseEngineeringShowcase -pql
"""

from manim import DOWN, LEFT, RIGHT, UP, FadeIn, VGroup

from manim_rev import (
    DEFAULT_THEME,
    BasicBlockSpec,
    CFGEdgeSpec,
    ControlFlowGraph,
    CoverageBitmap,
    CPUBlockDiagram,
    EdgeKind,
    FlagRegister,
    FuzzingDashboard,
    HexDump,
    InstructionSpec,
    PipelineDiagram,
    PipelineInstruction,
    RegisterBank,
    RevScene,
    StackOverflowDiagram,
    StashPanel,
    StateStatus,
    SymbolicEdgeSpec,
    SymbolicExecutionTree,
    SymbolicStateSpec,
    TaintFlowDiagram,
    VulnerabilityCard,
    label_text,
)


def scene_heading(value: str):  # type: ignore[no-untyped-def]
    return label_text(
        value,
        font_size=34,
        color=DEFAULT_THEME.text,
        weight="BOLD",
    ).to_edge(UP, buff=0.22)


class ReverseEngineeringShowcase(RevScene):
    """CFG, registers, flags, and a stack-memory window in one scene."""

    def construct(self) -> None:
        heading = scene_heading("A branch, from instruction to memory")
        blocks = [
            BasicBlockSpec(
                "check",
                0x401000,
                [
                    InstructionSpec(0x401000, "test", "eax, eax", b"\x85\xc0"),
                    InstructionSpec(0x401002, "jne", "0x401010", b"\x75\x0c"),
                ],
                label="input check",
            ),
            BasicBlockSpec(
                "copy",
                0x401010,
                [InstructionSpec(0x401010, "mov", "[rbx], al", b"\x88\x03")],
                label="copy byte",
            ),
            BasicBlockSpec(
                "reject",
                0x401004,
                [InstructionSpec(0x401004, "xor", "eax, eax", b"\x31\xc0")],
                label="reject",
            ),
        ]
        cfg = ControlFlowGraph(
            blocks,
            [
                CFGEdgeSpec("check", "copy", EdgeKind.TRUE, "ZF = 0"),
                CFGEdgeSpec("check", "reject", EdgeKind.FALSE, "ZF = 1"),
            ],
            block_width=3.0,
            compact_addresses=True,
            horizontal_gap=0.45,
            vertical_gap=0.55,
        )
        cfg.next_to(heading, DOWN, buff=0.42)

        registers = RegisterBank(
            {"rip": 0x401000, "rax": 0x41, "rbx": 0x7FFFFFFFE128},
            bits=64,
            width=3.65,
        )
        flags = FlagRegister({"ZF": None, "CF": False, "SF": None, "OF": False})
        memory = HexDump(
            bytes.fromhex("00 00 00 00 00 00 00 00 10 40 40 00 00 00 00 00"),
            base_address=0x7FFFFFFFE120,
            bytes_per_row=8,
            title="stack memory",
        )
        side = VGroup(registers, flags, memory).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
        side.scale_to_fit_width(5.8).to_edge(RIGHT, buff=0.35).shift(DOWN * 0.22)

        self.play(FadeIn(heading), FadeIn(cfg), run_time=0.6)
        self.play(cfg.traverse(["check", "copy"]))
        self.play(
            cfg.animate.scale(0.82).to_edge(LEFT, buff=0.4).shift(DOWN * 0.3),
            FadeIn(side, shift=LEFT * 0.12),
            run_time=0.65,
        )
        self.play(flags.animate_set("ZF", False))
        self.play(registers.animate_set("rip", 0x401010))
        self.play(memory.animate_write(0x7FFFFFFFE128, b"A", color=self.theme.danger))
        self.play(memory.highlight(0x7FFFFFFFE128, color=self.theme.danger))
        self.wait(0.4)


class PipelineShowcase(RevScene):
    """A load-use stall connected to a simplified CPU data path."""

    def construct(self) -> None:
        heading = scene_heading("Why the dependent add stalls")
        pipeline = PipelineDiagram(
            [
                PipelineInstruction("load rax", 0),
                PipelineInstruction("add rcx, rax", 1, stalled_cycles=(3,)),
                PipelineInstruction("cmp rcx, 0", 2, stalled_cycles=(3,)),
                PipelineInstruction("jnz retry", 3, stalled_cycles=(3,)),
            ]
        )
        pipeline.scale_to_fit_width(12.4).next_to(heading, DOWN, buff=0.35)
        datapath = CPUBlockDiagram()
        datapath.scale_to_fit_width(12.2).next_to(pipeline, DOWN, buff=0.55)

        self.play(FadeIn(heading), FadeIn(pipeline), FadeIn(datapath), run_time=0.7)
        self.play(pipeline.highlight_cycle(3))
        self.play(datapath.pulse(["Fetch", "Decode", "Registers", "Execute", "Memory"]))
        self.wait(0.4)


class FuzzingShowcase(RevScene):
    """Coverage growth followed by a unique crash."""

    def construct(self) -> None:
        heading = scene_heading("Coverage-guided fuzzing finds a new path")
        dashboard = FuzzingDashboard(
            executions=12_400,
            execs_per_second=8_200,
            coverage="34.1%",
            corpus_size=27,
            crashes=0,
        )
        coverage = CoverageBitmap([0] * 64, columns=16, show_counts=False)
        content = VGroup(dashboard, coverage).arrange(RIGHT, buff=0.7)
        content.scale_to_fit_width(11.6).next_to(heading, DOWN, buff=0.5)

        self.play(FadeIn(heading), FadeIn(content), run_time=0.7)
        self.play(coverage.animate_update({0: 4, 1: 7, 16: 2, 17: 8, 18: 1}))
        self.play(
            dashboard.animate_update(
                executions=48_210,
                coverage="39.8%",
                corpus_size=35,
            )
        )
        self.play(coverage.animate_hit(47, 1), dashboard.animate_crash())
        self.wait(0.4)


class SymbolicExecutionShowcase(RevScene):
    """An angr-style fork, path constraint, and state-stash summary."""

    def construct(self) -> None:
        heading = scene_heading("Symbolic execution forks on user input")
        states = [
            SymbolicStateSpec("s0", 0x401000, ["input[0] symbolic"], label="entry"),
            SymbolicStateSpec(
                "s1",
                0x401010,
                ["input[0] == 0x41"],
                StateStatus.FOUND,
                label="target",
            ),
            SymbolicStateSpec(
                "s2",
                0x401020,
                ["input[0] != 0x41"],
                StateStatus.AVOIDED,
                label="reject",
            ),
        ]
        tree = SymbolicExecutionTree(
            states,
            [
                SymbolicEdgeSpec("s0", "s1", "input[0] == 'A'"),
                SymbolicEdgeSpec("s0", "s2", "input[0] != 'A'"),
            ],
            node_width=2.7,
        )
        stashes = StashPanel(
            {
                StateStatus.ACTIVE: 0,
                StateStatus.FOUND: ("s1",),
                StateStatus.AVOIDED: ("s2",),
                StateStatus.DEADENDED: 0,
            }
        )
        content = VGroup(tree, stashes).arrange(RIGHT, buff=0.65)
        content.scale_to_fit_width(12).next_to(heading, DOWN, buff=0.45)

        self.play(FadeIn(heading), FadeIn(content), run_time=0.7)
        self.play(tree.animate_fork("s0"))
        self.play(tree.trace(["s0", "s1"]), stashes.focus(StateStatus.FOUND))
        self.wait(0.4)


class VulnerabilityShowcase(RevScene):
    """Stack overwrite, tainted data path, and an actionable finding card."""

    def construct(self) -> None:
        heading = scene_heading("The input reaches saved control flow")
        stack = StackOverflowDiagram(
            b"hello",
            buffer_size=16,
            return_address=0x401245,
            base_address=0x7FFFFFFFE100,
        )
        taint = TaintFlowDiagram(
            ["socket", "parser", "strcpy", "stack buffer", "saved RIP"],
            addresses={"strcpy": 0x4011A0, "saved RIP": 0x7FFFFFFFE118},
            gap=0.48,
        )
        left = VGroup(stack, taint).arrange(DOWN, buff=0.38)
        left.scale_to_fit_width(7.0)
        finding = VulnerabilityCard(
            "Unbounded stack copy",
            "critical",
            "User-controlled bytes replace the saved return address.",
            cwe=121,
            address=0x4011A0,
            source_file="parser.c",
            source_line=42,
            evidence=("strcpy(dst, packet)", "32 bytes reach a 16-byte buffer"),
            width=5.0,
        )
        content = VGroup(left, finding).arrange(RIGHT, buff=0.5)
        content.scale_to_fit_width(12.5).next_to(heading, DOWN, buff=0.35)

        self.play(FadeIn(heading), FadeIn(content), run_time=0.7)
        payload = b"A" * 24 + (0xDEADBEEFCAFEBABE).to_bytes(8, "little")
        self.play(
            stack.animate_overflow(payload, overwritten_return=0xDEADBEEFCAFEBABE),
            taint.animate_taint(),
        )
        self.play(finding.focus_severity())
        self.wait(0.4)
