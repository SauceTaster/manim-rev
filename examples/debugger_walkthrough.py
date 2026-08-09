"""Debugger-style walkthrough linking a breakpoint to the bytes it changes.

Render with::

    manim -pql --renderer cairo examples/debugger_walkthrough.py DebuggerMemoryWalkthrough
"""

from __future__ import annotations

from manim import DOWN, LEFT, RIGHT, UP, FadeIn, Transform, VGroup

from manim_rev.cpu import RegisterBank
from manim_rev.memory import HexDump
from manim_rev.models import AccessKind, MemoryAccess, TraceEvent, TracePhase, format_address
from manim_rev.primitives import StatusDot, mono_text
from manim_rev.refs import AddressRef
from manim_rev.scene import RevScene
from manim_rev.trace import ExecutionTrace
from manim_rev.workbench import AnalysisWorkbench

BREAKPOINT = 0x40117D
MEMORY_BASE = 0x7FFFE21C
MEMORY_TARGET = MEMORY_BASE + 5


class DebuggerMemoryWalkthrough(RevScene):
    """Follow one store from an instruction trace into stack memory."""

    def status_line(self, text: str, color: str) -> VGroup:
        """Build a compact footer status without relying on text glyph spacing."""

        return VGroup(
            StatusDot(color, theme=self.theme),
            mono_text(text, font_size=16, color=self.theme.muted, theme=self.theme),
        ).arrange(RIGHT, buff=0.12)

    def construct(self) -> None:
        title = self.title_card(
            "Breakpoint to Memory",
            "connect the stopped instruction, live registers, and touched bytes",
        )
        title.scale(0.62).to_edge(UP, buff=0.2)

        events = (
            TraceEvent(
                0x401176,
                "lea rax, [rsp + 0x25]",
                {"rax": MEMORY_TARGET, "rsp": MEMORY_BASE - 0x20, "al": 0x21},
                note="resolve destination",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                BREAKPOINT,
                "mov byte ptr [rax], al",
                {"rax": MEMORY_TARGET, "al": 0x21},
                memory=MemoryAccess(
                    MEMORY_TARGET,
                    size=1,
                    kind=AccessKind.WRITE,
                    value=0x21,
                ),
                note="breakpoint",
                phase=TracePhase.BEFORE,
            ),
            TraceEvent(
                0x401180,
                "cmp byte ptr [rax], 0",
                {"rax": MEMORY_TARGET, "al": 0x21, "zf": 0},
                memory=MemoryAccess(
                    MEMORY_TARGET,
                    size=1,
                    kind=AccessKind.READ,
                    value=0x21,
                ),
                note="verify write",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401184,
                "jne authenticated",
                {"rax": MEMORY_TARGET, "al": 0x21, "zf": 0},
                note="branch taken",
                phase=TracePhase.BEFORE,
            ),
        )
        trace = ExecutionTrace(
            events,
            breakpoints=(BREAKPOINT,),
            width=8.15,
            row_height=0.61,
            title="instruction trace",
            theme=self.theme,
        )
        registers = RegisterBank(
            {
                "rip": 0x401170,
                "rsp": MEMORY_BASE - 0x20,
                "rax": 0,
                "al": 0,
            },
            bits=64,
            width=3.35,
            title="live registers",
            theme=self.theme,
        )
        memory = HexDump(
            b"ADMIN\x00",
            base_address=MEMORY_BASE,
            bytes_per_row=6,
            title="stack memory",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {
                "memory": memory,
                "trace": trace,
                "registers": registers,
            },
            columns=2,
            horizontal_buff=0.34,
            vertical_buff=0.28,
            theme=self.theme,
        )
        if workbench.width > 13.15:
            workbench.scale_to_fit_width(13.15)
        workbench.next_to(title, DOWN, buff=0.22)

        status = self.status_line(
            f"breakpoint armed at {format_address(BREAKPOINT)}",
            self.theme.danger,
        )
        status.to_edge(LEFT, buff=0.5).to_edge(DOWN, buff=0.25)

        self.play(FadeIn(title, shift=UP * 0.12), run_time=0.55)
        self.play(
            FadeIn(workbench, shift=UP * 0.1),
            FadeIn(status, shift=RIGHT * 0.1),
            run_time=0.75,
        )

        self.play(
            trace.step(),
            registers.animate_set("rip", events[0].address),
            registers.animate_set("rax", MEMORY_TARGET),
            registers.animate_set("al", 0x21),
            run_time=0.65,
        )

        hit_status = self.status_line(
            "breakpoint hit — store has not executed yet",
            self.theme.danger,
        ).move_to(status, aligned_edge=LEFT)
        self.play(
            trace.step(),
            registers.animate_set("rip", BREAKPOINT),
            Transform(status, hit_status),
            run_time=0.72,
        )
        self.play(
            workbench.focus(AddressRef(BREAKPOINT), color=self.theme.danger),
            run_time=0.45,
        )

        link = workbench.breakpoint_to_memory(
            breakpoint_panel="trace",
            instruction_address=BREAKPOINT,
            memory_panel="memory",
            memory_address=MEMORY_TARGET,
            length=1,
            label="write",
        )
        link.arrow.put_start_and_end_on(
            trace.row_for_address(BREAKPOINT).background.get_left() + LEFT * 0.025,
            memory.byte_cell(MEMORY_TARGET).background.get_right() + RIGHT * 0.025,
        )
        if link.label is not None:
            link.label.move_to(link.arrow.get_center() + UP * 0.18)
        self.play(link.animate_flow(), run_time=0.85)
        memory.set_bytes(MEMORY_TARGET, 0x21)
        self.play(
            memory.highlight(MEMORY_TARGET, color=self.theme.success),
            run_time=0.8,
        )

        self.play(
            trace.step(),
            registers.animate_set("rip", events[2].address),
            run_time=0.58,
        )
        self.play(
            workbench.focus(AddressRef(MEMORY_TARGET), color=self.theme.success),
            run_time=0.45,
        )
        self.play(
            trace.step(),
            registers.animate_set("rip", events[3].address),
            run_time=0.58,
        )

        summary = self.status_line(
            "linked: AL value → [RAX] → stack byte 0x21",
            self.theme.success,
        )
        summary.move_to([0, status.get_center()[1], 0])
        self.play(Transform(status, summary), run_time=0.5)
        self.wait(0.8)
