"""High-pressure layout examples used as a visual regression corpus."""

from __future__ import annotations

from manim import DOWN, RIGHT, UP, FadeIn, LaggedStart, VGroup

from manim_rev import (
    AccessKind,
    AnalysisWorkbench,
    ExecutionTrace,
    FlagRegister,
    HexDump,
    InstructionSpec,
    InstructionView,
    MemoryAccess,
    MemoryAddressRef,
    MemoryMap,
    MemorySegmentSpec,
    PipelineDiagram,
    PipelineInstruction,
    RegisterBank,
    RevScene,
    TraceEvent,
    TracePhase,
    label_text,
)


def _heading(text: str, scene: RevScene):  # type: ignore[no-untyped-def]
    return label_text(
        text,
        font_size=34,
        color=scene.theme.text,
        theme=scene.theme,
        weight="BOLD",
    ).to_edge(UP, buff=0.2)


def _fit_content(content, heading, *, width: float = 13.2, height: float = 6.1):  # type: ignore[no-untyped-def]
    if content.width > width:
        content.scale_to_fit_width(width)
    if content.height > height:
        content.scale_to_fit_height(height)
    return content.next_to(heading, DOWN, buff=0.28)


class MixedInstructionWidthStress(RevScene):
    """Prove that short and maximum-length instructions remain legible together."""

    def construct(self) -> None:
        heading = _heading("Instruction cards under operand pressure", self)
        specs = (
            InstructionSpec(0x401000, "ret", raw_bytes=b"\xc3", comment="shortest common exit"),
            InstructionSpec(
                0x401010,
                "vperm2f128",
                "ymm15, ymm14, ymmword ptr [r13 + r12*8 + 0x1234], 0x31",
                bytes(range(15)),
                "15-byte x86 instruction",
            ),
            InstructionSpec(
                0x401020, "lock cmpxchg16b", "xmmword ptr [rdi]", b"\xf0\x48\x0f\xc7\x0f"
            ),
            InstructionSpec(
                0x1000, "ldp", "x29, x30, [sp], #0x40", b"\xfd\x7b\xc4\xa8", "AArch64 epilogue"
            ),
            InstructionSpec(
                0x2000, "amoadd.d.aqrl", "a0, a1, (a2)", b"\x2f\x35\xb6\x06", "RV64 atomic"
            ),
            InstructionSpec(
                0x3000, "call", "sym.imp.__stack_chk_fail", b"\xe8\x00\x00\x00\x00", "long symbol"
            ),
        )
        cards = VGroup(*(InstructionView(spec, width=6.1, theme=self.theme) for spec in specs))
        cards.arrange_in_grid(rows=3, cols=2, buff=(0.22, 0.22))
        _fit_content(cards, heading)
        self.add(heading)
        self.play(LaggedStart(*(FadeIn(card) for card in cards), lag_ratio=0.08), run_time=1.1)
        self.wait(0.25)


class MultiArchitectureRegisterStress(RevScene):
    """Compare x86-64, AArch64, and RV64 register values without collisions."""

    def construct(self) -> None:
        heading = _heading("One state snapshot, three architectures", self)
        x86 = RegisterBank(
            {"rip": 0x40117D, "rsp": 0x7FFFFFFFE280, "rax": 0xDEADBEEFCAFEBABE, "r15": 0x1234},
            bits=64,
            width=4.1,
            title="x86-64",
            theme=self.theme,
        )
        arm = RegisterBank(
            {"pc": 0x40081C, "sp": 0x7FFFFFFFD9A0, "x0": 0x4141414141414141, "x30": 0x400710},
            bits=64,
            width=4.1,
            title="aarch64",
            theme=self.theme,
        )
        riscv = RegisterBank(
            {"pc": 0x105AC, "x2": 0x3FFFFFFE20, "x10": 0x1337, "x31": 0xFFFFFFFFFFFFFFFF},
            bits=64,
            width=4.1,
            title="rv64",
            theme=self.theme,
        )
        banks = VGroup(x86, arm, riscv).arrange(RIGHT, buff=0.3)
        flags = FlagRegister({"ZF": False, "CF": True, "SF": None, "OF": False}, theme=self.theme)
        content = VGroup(banks, flags).arrange(DOWN, buff=0.35)
        _fit_content(content, heading)
        self.play(FadeIn(heading), FadeIn(content), run_time=0.7)
        self.play(
            x86.animate_set("RAX", 0),
            arm.animate_set("X0", 0x41),
            riscv.animate_set("X10", 0x42),
            flags.animate_set("zf", True),
        )
        self.wait(0.25)


class FullWidthHexDumpStress(RevScene):
    """Keep a 64-byte dump readable while writes cross a row boundary."""

    def construct(self) -> None:
        heading = _heading("A cross-row patch in a 64-byte window", self)
        payload = bytes(range(0x20, 0x60))
        dump = HexDump(
            payload,
            base_address=0x7FFFFFFFDF80,
            bytes_per_row=16,
            title="stack window · 64 bytes",
            theme=self.theme,
        )
        _fit_content(dump, heading, width=13.4, height=5.8)
        self.play(FadeIn(heading), FadeIn(dump), run_time=0.65)
        self.play(dump.highlight(0x7FFFFFFFDF8E, 6, color=self.theme.warning))
        self.play(dump.animate_write(0x7FFFFFFFDF8E, b"REBOOT", color=self.theme.danger))
        self.wait(0.3)


class MemoryMapPermissionStress(RevScene):
    """Tour a realistic process map with long names and permission changes."""

    def construct(self) -> None:
        heading = _heading("Which region owns the faulting address?", self)
        memory_map = MemoryMap(
            (
                MemorySegmentSpec("linux-vdso.so.1", 0x7FFFF7FFD000, 0x7FFFF7FFF000, "r-x"),
                MemorySegmentSpec("thread stack + guard", 0x7FFFFFFDC000, 0x7FFFFFFFF000, "rw-"),
                MemorySegmentSpec("libc.so.6 · executable", 0x7FFFF7C00000, 0x7FFFF7DBF000, "r-x"),
                MemorySegmentSpec("heap arenas", 0x555555760000, 0x555555982000, "rw-"),
                MemorySegmentSpec(".data / .bss", 0x555555557000, 0x555555760000, "rw-"),
                MemorySegmentSpec("main executable", 0x555555554000, 0x555555557000, "r-x"),
                MemorySegmentSpec("unmapped null page", 0, 0x1000, "---"),
            ),
            width=8.2,
            segment_height=0.56,
            address_width=12,
            title="/proc/self/maps",
            theme=self.theme,
        )
        _fit_content(memory_map, heading, width=9.2, height=6.0)
        self.play(FadeIn(heading), FadeIn(memory_map), run_time=0.65)
        self.play(memory_map.highlight("thread stack + guard", color=self.theme.danger))
        self.play(memory_map.highlight(0x555555770000, color=self.theme.warning))
        self.wait(0.25)


class LongExecutionTraceStress(RevScene):
    """Page into a long trace and stop at a late write breakpoint."""

    def construct(self) -> None:
        heading = _heading("A readable viewport into a longer trace", self)
        frame_pointer = 0x7FFFFFFFE2B8
        overwrite_target = frame_pointer + 8
        decoded_pointer = 0x4141414141414141
        events = (
            TraceEvent(
                0x401150,
                "push rbp",
                {"rsp": frame_pointer},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401151,
                "mov rbp, rsp",
                {"rbp": frame_pointer, "rsp": frame_pointer},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401154,
                "sub rsp, 0x30",
                {"rbp": frame_pointer, "rsp": frame_pointer - 0x30},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401158,
                "lea rdi, [rbp - 0x20]",
                {"rdi": frame_pointer - 0x20, "rsp": frame_pointer - 0x30},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x40115C,
                "call decode_packet",
                {"rax": decoded_pointer, "rsp": frame_pointer - 0x30},
                note="decoder returned",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401161,
                "test eax, eax",
                {"rax": decoded_pointer, "zf": 0},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401163,
                "je cleanup",
                {"zf": 0},
                note="not taken",
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x401165,
                "mov qword ptr [rbp + 8], rax",
                {"rax": decoded_pointer, "rbp": frame_pointer},
                memory=MemoryAccess(
                    overwrite_target,
                    8,
                    AccessKind.WRITE,
                    decoded_pointer,
                ),
                note="late overwrite",
                phase=TracePhase.BEFORE,
            ),
            TraceEvent(
                0x401169,
                "leave",
                {"rbp": 0x7FFFFFFFE310, "rsp": overwrite_target},
                phase=TracePhase.AFTER,
            ),
            TraceEvent(
                0x40116A,
                "ret",
                {"rsp": overwrite_target},
                phase=TracePhase.BEFORE,
            ),
        )
        trace = ExecutionTrace.window(
            events,
            start=3,
            count=7,
            breakpoints=(events[7].address,),
            width=12.8,
            row_height=0.62,
            show_registers=True,
            title="recorded instruction trace",
            theme=self.theme,
        )
        _fit_content(trace, heading, width=13.2, height=6.0)
        self.play(FadeIn(heading), FadeIn(trace), run_time=0.7)
        self.play(trace.step_to(1))
        self.play(trace.run_to_breakpoint())
        self.play(trace.highlight_memory_access(4))
        self.wait(0.25)


class MultiAccessTraceStress(RevScene):
    """Show capture phase and both sides of a multi-access string operation."""

    def construct(self) -> None:
        heading = _heading("One instruction can touch more than one address", self)
        source = 0x604000
        destination = 0x7FFFFFFFE100
        trace = ExecutionTrace(
            (
                TraceEvent(
                    0x401200,
                    "movsb",
                    {"rsi": source + 1, "rdi": destination + 1},
                    note="copy one byte",
                    phase=TracePhase.AFTER,
                    memory_accesses=(
                        MemoryAccess(source, 1, AccessKind.READ, b"A"),
                        MemoryAccess(destination, 1, AccessKind.WRITE, b"A"),
                    ),
                ),
                TraceEvent(
                    0x401201,
                    "cmp byte ptr [rdi - 1], 0",
                    {"zf": 0, "rdi": destination + 1},
                    memory=MemoryAccess(destination, 1, AccessKind.READ, b"A"),
                    note="branch input",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x401205,
                    "jne accepted",
                    {"zf": 0},
                    note="taken",
                    phase=TracePhase.BEFORE,
                ),
            ),
            breakpoints=(0x401200,),
            width=12.4,
            row_height=0.72,
            memory_width=3.55,
            title="multi-access trace",
            theme=self.theme,
        )
        _fit_content(trace, heading, width=12.9, height=5.8)
        self.play(FadeIn(heading), FadeIn(trace), run_time=0.7)
        self.play(trace.run_to_breakpoint())
        self.play(trace.highlight_memory_access(0, occurrence=1))
        self.wait(0.25)


class OddPanelWorkbenchStress(RevScene):
    """Center an incomplete workbench row while preserving semantic focus."""

    def construct(self) -> None:
        heading = _heading("Three evidence views, without an empty visual cell", self)
        data_address = 0x401000
        code_address = 0x404000
        trace = ExecutionTrace(
            (
                TraceEvent(
                    code_address,
                    "cmp dword ptr [rdi], 0x464c457f",
                    {"rdi": data_address, "zf": 1},
                    memory=MemoryAccess(
                        data_address,
                        4,
                        AccessKind.READ,
                        b"\x7fELF",
                    ),
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    code_address + 6,
                    "jne reject",
                    {"zf": 1},
                    note="not taken",
                    phase=TracePhase.BEFORE,
                ),
            ),
            width=5.8,
            row_height=0.62,
            show_memory=False,
            title="trace",
            theme=self.theme,
        )
        dump = HexDump(
            b"\x7fELF\x02\x01\x01\x00",
            base_address=data_address,
            bytes_per_row=8,
            title="ELF header bytes",
            theme=self.theme,
        )
        memory_map = MemoryMap(
            (
                MemorySegmentSpec(".text", code_address, code_address + 0x1000, "r-x"),
                MemorySegmentSpec(".rodata", data_address, data_address + 0x800, "r--"),
            ),
            width=5.8,
            segment_height=0.56,
            title="mapping",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {"trace": trace, "bytes": dump, "mapping": memory_map},
            columns=2,
            horizontal_buff=0.42,
            vertical_buff=0.4,
            theme=self.theme,
        )
        _fit_content(workbench, heading, width=12.8, height=6.0)
        self.play(FadeIn(heading), FadeIn(workbench), run_time=0.7)
        self.play(workbench.focus(MemoryAddressRef(data_address), scale_factor=1.025))
        self.wait(0.25)


class PipelineCapacityStress(RevScene):
    """Fit eight overlapping instructions, stalls, and squashes into one pipeline."""

    def construct(self) -> None:
        heading = _heading("Pipeline pressure after a load and mispredict", self)
        rows = (
            PipelineInstruction("load rax, [rbx]", 0),
            PipelineInstruction("add rcx, rax", 1, stalled_cycles=(3, 4)),
            PipelineInstruction("cmp rcx, 0", 2, stalled_cycles=(3, 4)),
            PipelineInstruction("jz cold", 5),
            PipelineInstruction("mov r8, r9", 6, squashed_at_cycle=7),
            PipelineInstruction("xor r10, r10", 7, squashed_at_cycle=7),
            PipelineInstruction("call hot", 8),
            PipelineInstruction("store [rdi], rax", 9),
        )
        pipeline = PipelineDiagram(
            rows,
            stages=("IF", "ID", "EX", "MEM", "WB"),
            cell_width=0.58,
            cell_height=0.37,
            theme=self.theme,
        )
        _fit_content(pipeline, heading, width=13.3, height=6.0)
        self.play(FadeIn(heading), FadeIn(pipeline), run_time=0.7)
        self.play(pipeline.highlight_cycle(3))
        self.play(pipeline.highlight_cycle(7))
        self.wait(0.25)
