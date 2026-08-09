"""Debugger and execution-trace examples for reverse-engineering talks.

Render every scene in this file with::

    manim -ql --renderer cairo examples/analysis/debugger_traces.py \
        RunToBreakpointWalkthrough ReadModifyWriteTrace RepeatedLoopBreakpoint

The traces are deterministic recordings, not live debugger sessions.
"""

from __future__ import annotations

from manim import DOWN, RIGHT, UP, FadeIn, Transform, VGroup

from manim_rev import (
    AccessKind,
    AddressRef,
    AnalysisWorkbench,
    ExecutionTrace,
    HexDump,
    MemoryAccess,
    RegisterBank,
    RevScene,
    TraceEvent,
    TracePhase,
    format_address,
    mono_text,
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
    max_height: float = 5.95,
) -> VGroup:
    if content.width > max_width:
        content.scale_to_fit_width(max_width)
    if content.height > max_height:
        content.scale_to_fit_height(max_height)
    content.next_to(title, DOWN, buff=0.2)
    return content


def _footer(scene: RevScene, text: str):  # type: ignore[no-untyped-def]
    note = mono_text(text, font_size=16, color=scene.theme.muted, theme=scene.theme)
    if note.width > 12.7:
        note.scale_to_fit_width(12.7)
    note.to_edge(DOWN, buff=0.13)
    return note


class RunToBreakpointWalkthrough(RevScene):
    """Arm a breakpoint, run to it, and inspect the stopped register state."""

    def construct(self) -> None:
        title = _title(
            self,
            "Run to the Parser Boundary",
            "stop before the indirect call so the target and packet pointer remain visible",
        )
        breakpoint = 0x406018
        events = (
            TraceEvent(
                0x406000,
                "push rbp",
                {"rsp": 0x7FFFFFFFDFF8},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x406004,
                "mov rbx, rdi",
                {"rbx": 0x607000},
                note="packet",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x40600A,
                "mov rax, [rbx + 8]",
                {"rax": 0x401980},
                note="handler",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                breakpoint,
                "call rax",
                {"rax": 0x401980, "rdi": 0x607000},
                phase=TracePhase.BEFORE,
            ),
            TraceEvent(
                0x40601A,
                "test eax, eax",
                {"eax": 1},
                note="returned success",
                phase=TracePhase.AFTER,
            ),
        )
        trace = ExecutionTrace(
            events,
            width=8.25,
            row_height=0.58,
            title="debugger trace",
            theme=self.theme,
        )
        registers = RegisterBank(
            {
                "rip": events[0].address,
                "rsp": 0x7FFFFFFFE000,
                "rax": 0,
                "rbx": 0,
                "rdi": 0x607000,
            },
            bits=64,
            width=3.65,
            title="live registers",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {"trace": trace, "registers": registers},
            columns=2,
            horizontal_buff=0.45,
            theme=self.theme,
        )
        _under_title(workbench, title, max_width=12.8, max_height=5.7)
        footer = _footer(self, f"break before CALL: RIP = {format_address(breakpoint)}")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(workbench, shift=UP * 0.08), run_time=0.45)
        self.play(trace.animate_breakpoint(breakpoint), run_time=0.35)
        self.play(
            trace.step(),
            registers.animate_set("rip", events[0].address),
            registers.animate_set("rsp", 0x7FFFFFFFDFF8),
            run_time=0.4,
        )
        self.play(
            trace.run_to_breakpoint(),
            registers.animate_set("rip", breakpoint, color=self.theme.danger),
            registers.animate_set("rax", 0x401980, color=self.theme.warning),
            registers.animate_set("rbx", 0x607000),
            run_time=0.7,
        )
        self.play(workbench.focus(AddressRef(breakpoint), color=self.theme.danger), run_time=0.4)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class ReadModifyWriteTrace(RevScene):
    """Follow a little-endian counter through one read-modify-write sequence."""

    def construct(self) -> None:
        title = _title(
            self,
            "Follow a Read-Modify-Write",
            "the trace names the access; the hex view makes the byte order concrete",
        )
        base = 0x607100
        counter = base + 4
        read_at = 0x406120
        write_at = 0x406128
        trace = ExecutionTrace(
            (
                TraceEvent(
                    read_at,
                    "mov eax, [rbx + 4]",
                    {"eax": 41, "rbx": base},
                    MemoryAccess(counter, 4, AccessKind.READ, 41),
                    note="load counter",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x406124,
                    "add eax, 1",
                    {"eax": 42},
                    note="increment",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    write_at,
                    "mov [rbx + 4], eax",
                    {"eax": 42, "rbx": base},
                    MemoryAccess(counter, 4, AccessKind.WRITE, 42),
                    note="store counter",
                    phase=TracePhase.BEFORE,
                ),
                TraceEvent(
                    0x40612C,
                    "ret",
                    {"eax": 42},
                    phase=TracePhase.BEFORE,
                ),
            ),
            breakpoints=(write_at,),
            width=7.65,
            row_height=0.62,
            title="recorded instructions",
            theme=self.theme,
        )
        memory = HexDump(
            b"CNT\x00" + (41).to_bytes(4, "little") + b"READY\x00\x00\x00",
            base_address=base,
            bytes_per_row=8,
            title="counter object",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {"trace": trace, "memory": memory},
            columns=2,
            horizontal_buff=0.4,
            theme=self.theme,
        )
        _under_title(workbench, title, max_width=12.9, max_height=5.75)
        footer = _footer(self, "29 00 00 00 becomes 2A 00 00 00 at 0x607104")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(workbench, shift=UP * 0.08), run_time=0.45)
        self.play(trace.step(), run_time=0.4)
        self.play(
            trace.highlight_memory_access(0, color=self.theme.info),
            workbench.focus(AddressRef(counter), color=self.theme.info),
            run_time=0.5,
        )
        self.play(trace.run_to_breakpoint(), run_time=0.55)
        link = workbench.breakpoint_to_memory(
            breakpoint_panel="trace",
            instruction_address=write_at,
            memory_panel="memory",
            memory_address=counter,
            length=4,
            label="4-byte write",
        )
        self.play(link.animate_flow(), run_time=0.65)
        self.play(
            memory.animate_write(counter, (42).to_bytes(4, "little"), color=self.theme.success),
            trace.highlight_memory_access(2, color=self.theme.warning),
            run_time=0.65,
        )
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class RepeatedLoopBreakpoint(RevScene):
    """Demonstrate repeated addresses and repeated hits on one breakpoint."""

    def construct(self) -> None:
        title = _title(
            self,
            "One Address, Three Breakpoint Hits",
            "loop traces keep each occurrence while sharing one semantic address",
        )
        loop_test = 0x406210
        events = (
            TraceEvent(
                0x406208,
                "xor ecx, ecx",
                {"ecx": 0},
                note="initialize",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x406214,
                "inc ecx",
                {"ecx": 1},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                loop_test,
                "cmp ecx, 3",
                {"ecx": 1},
                note="hit 1",
                phase=TracePhase.BEFORE,
            ),
            TraceEvent(
                0x406214,
                "inc ecx",
                {"ecx": 2},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                loop_test,
                "cmp ecx, 3",
                {"ecx": 2},
                note="hit 2",
                phase=TracePhase.BEFORE,
            ),
            TraceEvent(
                0x406214,
                "inc ecx",
                {"ecx": 3},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                loop_test,
                "cmp ecx, 3",
                {"ecx": 3},
                note="hit 3",
                phase=TracePhase.BEFORE,
            ),
            TraceEvent(
                0x40621A,
                "ret",
                {"ecx": 3},
                note="loop complete",
                phase=TracePhase.BEFORE,
            ),
        )
        trace = ExecutionTrace(
            events,
            breakpoints=(loop_test,),
            width=8.15,
            row_height=0.47,
            title="loop trace",
            theme=self.theme,
        )
        registers = RegisterBank(
            {"rip": events[0].address, "ecx": 0, "eflags": "ZF=0"},
            bits=32,
            width=3.55,
            title="stopped state",
            theme=self.theme,
        )
        content = VGroup(trace, registers).arrange(RIGHT, buff=0.45, aligned_edge=UP)
        _under_title(content, title, max_width=12.8, max_height=5.8)
        status = _footer(self, "waiting for first hit")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(content, shift=UP * 0.08), FadeIn(status), run_time=0.45)
        self.play(
            trace.run_to_breakpoint(),
            registers.animate_set("rip", loop_test),
            registers.animate_set("ecx", 1),
            run_time=0.55,
        )
        hit_one = _footer(self, "hit 1 / 3  |  ECX = 1")
        self.play(Transform(status, hit_one), run_time=0.25)
        self.play(trace.step(), registers.animate_set("ecx", 2), run_time=0.4)
        self.play(trace.run_to_breakpoint(), run_time=0.5)
        hit_two = _footer(self, "hit 2 / 3  |  ECX = 2")
        self.play(Transform(status, hit_two), run_time=0.25)
        self.play(trace.step(), registers.animate_set("ecx", 3), run_time=0.4)
        self.play(trace.run_to_breakpoint(), run_time=0.5)
        hit_three = _footer(
            self, "hit 3 / 3  |  ECX = 3  |  duplicate addresses remain distinct rows"
        )
        self.play(Transform(status, hit_three), run_time=0.3)
        self.wait(0.2)
