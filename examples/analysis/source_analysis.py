"""Source lowering and cross-reference examples for analysis talks.

Render every scene in this file with::

    manim -ql --renderer cairo examples/analysis/source_analysis.py \
        SourceLoweringWalkthrough IncomingXRefPivot RootCauseAcrossViews

All source text is Pango-backed; these scenes need neither LaTeX nor Graphviz.
"""

from __future__ import annotations

from manim import DOWN, RIGHT, UP, Create, FadeIn, VGroup

from manim_rev import (
    AddressRef,
    AnalysisWorkbench,
    BasicBlock,
    BasicBlockSpec,
    CrossReferencePanel,
    ExecutionTrace,
    InstructionSpec,
    RevScene,
    SourceAssemblyLinkSpec,
    SourceAssemblyMap,
    SourceListing,
    SourceRef,
    TraceEvent,
    TracePhase,
    XRefSpec,
    focus_across,
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


class SourceLoweringWalkthrough(RevScene):
    """Show one source condition lowering to several machine instructions."""

    def construct(self) -> None:
        title = _title(
            self,
            "One Source Line, Three Instructions",
            "a bounds check becomes compare, constant load, and conditional move",
        )
        initialize_zero = 0x404000
        compare_low = 0x404002
        select_nonnegative = 0x404004
        compare_high = 0x404007
        load_maximum = 0x40400C
        select_maximum = 0x404011
        source = SourceListing(
            (
                "int clamp_byte(int value) {",
                "    if (value < 0)",
                "        return 0;",
                "    if (value > 255)",
                "        return 255;",
                "    return value;",
                "}",
            ),
            filename="codec.c",
            width=5.25,
            row_height=0.36,
            address_map={
                2: (compare_low, select_nonnegative),
                3: initialize_zero,
                4: (compare_high, load_maximum, select_maximum),
                5: (load_maximum, select_maximum),
                6: select_nonnegative,
            },
            highlighted_lines={4: self.theme.warning},
            theme=self.theme,
        )
        assembly = BasicBlock(
            BasicBlockSpec(
                "clamp",
                0x404000,
                (
                    InstructionSpec(initialize_zero, "xor", "eax, eax", b"\x31\xc0"),
                    InstructionSpec(compare_low, "test", "edi, edi", b"\x85\xff"),
                    InstructionSpec(select_nonnegative, "cmovns", "eax, edi", b"\x0f\x49\xc7"),
                    InstructionSpec(compare_high, "cmp", "eax, 0xff", b"\x3d\xff\x00\x00\x00"),
                    InstructionSpec(load_maximum, "mov", "edx, 0xff", b"\xba\xff\x00\x00\x00"),
                    InstructionSpec(select_maximum, "cmovg", "eax, edx", b"\x0f\x4f\xc2"),
                    InstructionSpec(0x404014, "ret", raw_bytes=b"\xc3"),
                ),
                label="compiler output",
            ),
            width=6.05,
            row_height=0.35,
            show_bytes=True,
            theme=self.theme,
        )
        content = VGroup(source, assembly).arrange(RIGHT, buff=1.1, aligned_edge=UP)
        _under_title(content, title, max_width=12.8, max_height=5.75)
        links = SourceAssemblyMap(
            source,
            assembly,
            (
                SourceAssemblyLinkSpec(2, compare_low, "signed lower bound"),
                SourceAssemblyLinkSpec(2, select_nonnegative),
                SourceAssemblyLinkSpec(4, compare_high, "upper bound"),
                SourceAssemblyLinkSpec(4, load_maximum),
                SourceAssemblyLinkSpec(4, select_maximum),
            ),
            color=self.theme.info,
            theme=self.theme,
        )
        footer = _footer(self, "line 4 owns the CMP, constant MOV, and CMOVG at machine-code level")

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(content, shift=UP * 0.08), run_time=0.45)
        self.play(Create(links), run_time=0.5)
        self.play(
            focus_across(SourceRef(4, "codec.c"), source, links, color=self.theme.warning),
            run_time=0.45,
        )
        self.play(links.follow(4, compare_high), run_time=0.55)
        self.play(links.follow(4, select_maximum), run_time=0.55)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class IncomingXRefPivot(RevScene):
    """Pivot from a dangerous source line to its callers and global data."""

    def construct(self) -> None:
        title = _title(
            self,
            "Pivot on a Cross-Reference",
            "one unchecked copy connects callers, global state, and a logging sink",
        )
        source = SourceListing(
            (
                "void decode(Packet *packet) {",
                "    char name[16];",
                "    memcpy(name, packet->data, packet->len);",
                "    last_packet = packet;",
                "    audit(name);",
                "}",
            ),
            filename="packet.c",
            width=5.5,
            row_height=0.4,
            highlighted_lines={3: self.theme.danger},
            theme=self.theme,
        )
        xrefs = CrossReferencePanel(
            (
                XRefSpec("net.c:88", "packet.c:1", "call", "decode from socket loop"),
                XRefSpec("tests.c:41", "packet.c:1", "call", "fuzz harness entry"),
                XRefSpec("packet.c:3", "0x00402120", "call", "memcpy@plt"),
                XRefSpec("packet.c:3", "packet->len", "read", "attacker-controlled length"),
                XRefSpec("packet.c:4", "last_packet", "write", "global pointer"),
                XRefSpec("packet.c:5", "0x00401890", "call", "audit"),
                XRefSpec("last_packet", "admin.c:72", "read", "later privileged read"),
            ),
            width=6.6,
            row_height=0.43,
            title="incoming + outgoing xrefs",
            theme=self.theme,
        )
        content = VGroup(source, xrefs).arrange(RIGHT, buff=0.55, aligned_edge=UP)
        _under_title(content, title, max_width=12.8, max_height=5.85)
        footer = _footer(
            self, "the vulnerable line is reachable from both production and fuzz entry points"
        )

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(content, shift=UP * 0.08), run_time=0.45)
        line = SourceRef(3, "packet.c")
        self.play(focus_across(line, source, xrefs, color=self.theme.danger), run_time=0.5)
        self.play(xrefs.follow(2, color=self.theme.call), run_time=0.55)
        self.play(xrefs.follow(3, color=self.theme.info), run_time=0.55)
        self.play(xrefs.follow(6, color=self.theme.warning), run_time=0.55)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)


class RootCauseAcrossViews(RevScene):
    """Coordinate source, runtime trace, and xrefs around one call address."""

    def construct(self) -> None:
        title = _title(
            self,
            "Root Cause Across Three Views",
            "the same call site appears in source, a crash trace, and the xref table",
        )
        call_site = 0x40510A
        source = SourceListing(
            (
                "size = read_length(cursor);",
                "cursor += 2;",
                "copy_field(dst, cursor, size);",
                "return cursor + size;",
            ),
            filename="tlv.c",
            start_line=61,
            width=4.75,
            row_height=0.4,
            address_map={61: 0x405100, 62: 0x405106, 63: call_site, 64: 0x405110},
            highlighted_lines={63: self.theme.danger},
            theme=self.theme,
        )
        trace = ExecutionTrace(
            (
                TraceEvent(
                    0x405100,
                    "call read_length",
                    {"eax": 0x180},
                    note="size = 384",
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    0x405106,
                    "add rsi, 2",
                    {"rsi": 0x607202},
                    phase=TracePhase.AFTER,
                ),
                TraceEvent(
                    call_site,
                    "call copy_field",
                    {"rdx": 0x180},
                    note="crash site",
                    phase=TracePhase.BEFORE,
                ),
            ),
            breakpoints=(call_site,),
            width=7.1,
            row_height=0.58,
            title="crashing trace",
            theme=self.theme,
        )
        xrefs = CrossReferencePanel(
            (
                XRefSpec("tlv.c:63", "0x0040510A", "call", "copy_field"),
                XRefSpec("0x0040510A", "copy_field", "code", "direct call"),
                XRefSpec("copy_field", "memcpy", "call", "unchecked length"),
            ),
            width=4.75,
            row_height=0.4,
            title="xref chain",
            theme=self.theme,
        )
        workbench = AnalysisWorkbench(
            {"source": source, "trace": trace, "xrefs": xrefs},
            columns=2,
            horizontal_buff=0.45,
            vertical_buff=0.3,
            theme=self.theme,
        )
        _under_title(workbench, title, max_width=12.8, max_height=5.65)
        footer = _footer(
            self, "0x0040510A is the join key: source line 63 -> trace row 02 -> xref chain"
        )

        self.play(FadeIn(title, shift=UP * 0.08), run_time=0.3)
        self.play(FadeIn(workbench, shift=UP * 0.08), run_time=0.45)
        self.play(trace.run_to_breakpoint(), run_time=0.55)
        self.play(workbench.focus(AddressRef(call_site), color=self.theme.danger), run_time=0.5)
        link = workbench.link(
            "source",
            AddressRef(call_site),
            "trace",
            AddressRef(call_site),
            label="same site",
            color=self.theme.warning,
        )
        self.play(link.animate_flow(), run_time=0.65)
        self.play(xrefs.follow(0, color=self.theme.call), run_time=0.5)
        self.play(FadeIn(footer, shift=UP * 0.05), run_time=0.25)
        self.wait(0.2)
