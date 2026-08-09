"""Hex dump, memory map, and coordinated-workbench talk examples.

Render every scene in this file with::

    manim -ql --renderer cairo examples/analysis/memory_workbenches.py \
        ProtocolHexFieldTour ProcessMemoryMapTour SemanticPatchWorkbench

These scenes use compact memory windows suitable for a 16:9 presentation.
"""

from __future__ import annotations

from manim import DOWN, UP, FadeIn, Transform, VGroup

from manim_rev import (
    AccessKind,
    AddressRef,
    AnalysisWorkbench,
    ExecutionTrace,
    HexDump,
    MemoryAccess,
    MemoryMap,
    MemorySegmentSpec,
    RevScene,
    SourceListing,
    TraceEvent,
    TracePhase,
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


class ProtocolHexFieldTour(RevScene):
    """Decode fields and patch a length in a compact protocol hex dump."""

    def construct(self) -> None:
        title = _title(
            self,
            "Read Structure from Raw Bytes",
            "field highlights turn a packet dump into a parser hypothesis",
        )
        base = 0x608000
        packet = bytes.fromhex(
            "52 45 56 31 12 00 03 01 34 12 00 00 00 00 41 42 "
            "43 44 45 46 00 FF 10 20 30 40 50 60 70 80 90 A0"
        )
        dump = HexDump(
            packet,
            base_address=base,
            bytes_per_row=16,
            title="captured packet",
            theme=self.theme,
        )
        _under_title(dump, title, max_width=12.4, max_height=5.55)
        status = _footer(self, "start with the four-byte magic")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(dump, shift=UP * 0.08), FadeIn(status), run_time=0.45)
        self.play(dump.highlight_range(base, 4, color=self.theme.info), run_time=0.45)
        length_note = _footer(self, "offset +0x04: 12 00 -> payload length 0x0012 (little endian)")
        self.play(Transform(status, length_note), run_time=0.25)
        self.play(dump.highlight_range(base + 4, 2, color=self.theme.warning), run_time=0.45)
        payload_note = _footer(self, "payload begins at +0x0E and crosses the 16-byte row boundary")
        self.play(Transform(status, payload_note), run_time=0.25)
        self.play(dump.highlight_range(base + 14, 8, color=self.theme.success), run_time=0.55)
        patch_note = _footer(self, "patch the advertised length from 0x0012 to 0x0008")
        self.play(Transform(status, patch_note), run_time=0.25)
        self.play(
            dump.animate_write(base + 4, b"\x08\x00", color=self.theme.danger),
            run_time=0.55,
        )
        self.wait(0.2)


class ProcessMemoryMapTour(RevScene):
    """Relate execute, read, and write trace events to process mappings."""

    def construct(self) -> None:
        title = _title(
            self,
            "Where Did That Address Land?",
            "permissions distinguish instruction fetches, constants, heap state, and stack writes",
        )
        heap_target = 0x611120
        stack_target = 0x7FFFFFFFDE80
        memory_map = MemoryMap(
            (
                MemorySegmentSpec(".text", 0x400000, 0x403000, "r-x"),
                MemorySegmentSpec(".rodata", 0x403000, 0x404000, "r--"),
                MemorySegmentSpec("heap", 0x610000, 0x618000, "rw-"),
                MemorySegmentSpec("guard page", 0x7FFFFFFDC000, 0x7FFFFFFDD000, "---"),
                MemorySegmentSpec("stack", 0x7FFFFFFDD000, 0x7FFFFFFFF000, "rw-"),
            ),
            width=5.35,
            segment_height=0.78,
            title="process mappings",
            theme=self.theme,
        )
        trace = ExecutionTrace(
            (
                TraceEvent(
                    0x401050,
                    "call decode",
                    memory=MemoryAccess(0x401050, 5, AccessKind.EXECUTE),
                    note=".text",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x401080,
                    "mov rax, [rip + table]",
                    memory=MemoryAccess(0x403120, 8, AccessKind.READ),
                    note=".rodata",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x401088,
                    "mov [rbx + 0x120], eax",
                    memory=MemoryAccess(heap_target, 4, AccessKind.WRITE, 0x2A),
                    note="heap",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x401090,
                    "push rax",
                    memory=MemoryAccess(stack_target, 8, AccessKind.WRITE, 0x2A),
                    note="stack",
                    phase=TracePhase.AFTER,
                ),
            ),
            width=7.15,
            row_height=0.57,
            title="address-bearing trace",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {"memory map": memory_map, "trace": trace},
            columns=2,
            horizontal_buff=0.4,
            theme=self.theme,
        )
        _under_title(workbench, title, max_width=12.8, max_height=5.8)
        footer = _footer(
            self, "0x00611120 resolves to heap (rw-); 0x7FFFFFFFDE80 resolves to stack (rw-)"
        )

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(workbench, shift=UP * 0.08), run_time=0.45)
        self.play(trace.step_to(1), workbench.focus(AddressRef(0x403120)), run_time=0.55)
        self.play(trace.step_to(2), workbench.focus(AddressRef(heap_target)), run_time=0.55)
        link = workbench.link(
            "trace",
            AddressRef(heap_target),
            "memory map",
            AddressRef(heap_target),
            label="mapped rw-",
            color=self.theme.warning,
        )
        self.play(link.animate_flow(), run_time=0.65)
        self.play(trace.step_to(3), workbench.focus(AddressRef(stack_target)), run_time=0.55)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class SemanticPatchWorkbench(RevScene):
    """Link a source line and breakpoint to the stack bytes it overwrites."""

    def construct(self) -> None:
        title = _title(
            self,
            "Triangulate a Suspicious Stack Patch",
            "source, trace, byte window, and mapping agree through semantic addresses",
        )
        store_instruction = 0x40712A
        stack_base = 0x7FFFFFFFDF00
        target = stack_base + 8
        source = SourceListing(
            (
                'char role[8] = "user";',
                "memcpy(role, packet->role, 4);",
                "authorize(role);",
                "return 0;",
            ),
            filename="session.c",
            start_line=118,
            width=4.65,
            row_height=0.36,
            address_map={118: 0x407110, 119: store_instruction, 120: 0x407134, 121: 0x407139},
            highlighted_lines={119: self.theme.danger},
            theme=self.theme,
        )
        trace = ExecutionTrace(
            (
                TraceEvent(
                    0x407120,
                    "mov eax, [rsi]",
                    {"eax": "ROOT"},
                    note="packet bytes",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    store_instruction,
                    "mov [rbp - 0x18], eax",
                    {"rbp": stack_base + 0x20},
                    MemoryAccess(target, 4, AccessKind.WRITE, b"ROOT"),
                    note="breakpoint",
                    phase=TracePhase.BEFORE,
                ),
                TraceEvent(
                    0x407134,
                    "call authorize",
                    {"rdi": target},
                    note="role consumed",
                    phase=TracePhase.BEFORE,
                ),
            ),
            breakpoints=(store_instruction,),
            width=7.1,
            row_height=0.56,
            title="stopped trace",
            theme=self.theme,
        )
        memory = HexDump(
            b"SESSION\x00user\x00\x00\x00\x00",
            base_address=stack_base,
            bytes_per_row=8,
            title="stack window",
            theme=self.theme,
        )
        memory_map = MemoryMap(
            (
                MemorySegmentSpec(".text", 0x400000, 0x409000, "r-x"),
                MemorySegmentSpec("stack", 0x7FFFFFFDD000, 0x7FFFFFFFF000, "rw-"),
            ),
            width=4.65,
            segment_height=0.82,
            title="relevant mappings",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {
                "source": source,
                "trace": trace,
                "bytes": memory,
                "map": memory_map,
            },
            columns=2,
            horizontal_buff=0.4,
            vertical_buff=0.28,
            theme=self.theme,
        )
        _under_title(workbench, title, max_width=12.8, max_height=5.65)
        footer = _footer(
            self, "instruction 0x0040712A writes ROOT to stack bytes at 0x7FFFFFFFDF08"
        )

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(workbench, shift=UP * 0.08), run_time=0.45)
        self.play(trace.run_to_breakpoint(), run_time=0.55)
        self.play(
            workbench.focus(AddressRef(store_instruction), color=self.theme.danger), run_time=0.45
        )
        source_link = workbench.link(
            "source",
            AddressRef(store_instruction),
            "trace",
            AddressRef(store_instruction),
            label="lowered store",
            color=self.theme.info,
        )
        self.play(source_link.animate_flow(), run_time=0.55)
        memory_link = workbench.breakpoint_to_memory(
            breakpoint_panel="trace",
            instruction_address=store_instruction,
            memory_panel="bytes",
            memory_address=target,
            length=4,
            label="writes ROOT",
        )
        self.play(memory_link.animate_flow(), run_time=0.6)
        self.play(
            memory.animate_write(target, b"ROOT", color=self.theme.danger),
            workbench.focus(AddressRef(target), color=self.theme.warning),
            run_time=0.65,
        )
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)
