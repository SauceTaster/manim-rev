"""Instruction, register, flag, and CPU data-path talk examples.

Render all scenes in this file with:

    manim -ql examples/security/cpu_walkthroughs.py
"""

from __future__ import annotations

from _common import callout, legend, place_content, scene_heading
from manim import DOWN, RIGHT, AnimationGroup, FadeIn, Indicate, Succession, VGroup

from manim_rev import (
    CPUBlockDiagram,
    FlagRegister,
    InstructionEncoding,
    InstructionField,
    InstructionSpec,
    InstructionView,
    RegisterBank,
    RevScene,
)


class InstructionDecodeWalkthrough(RevScene):
    """Explain how five x86-64 byte groups become one effective-address load."""

    def construct(self) -> None:
        heading = scene_heading("Five byte groups, one memory operand", "instruction decoding")
        instruction = InstructionView(
            InstructionSpec(
                0x401080,
                "mov",
                "rax, [rsp + 0x20]",
                bytes.fromhex("48 8B 44 24 20"),
                "load caller-local value",
            ),
            width=10.9,
            height=1.2,
        )
        encoding = InstructionEncoding(
            (
                InstructionField("REX.W", 8, "48"),
                InstructionField("opcode", 8, "8B"),
                InstructionField("ModR/M", 8, "44"),
                InstructionField("SIB", 8, "24"),
                InstructionField("disp8", 8, "20"),
            ),
            width=10.9,
            height=0.92,
        )
        field_legend = legend(
            (
                ("operand size", self.theme.opcode),
                ("register selection", self.theme.register),
                ("addressing", self.theme.immediate),
            )
        )
        notes = VGroup(
            callout("REX.W", "Select a 64-bit destination: RAX.", width=3.45),
            callout("SIB + disp8", "Use RSP as the base, then add 0x20.", width=3.45),
            callout("result", "Read eight bytes from the effective address.", width=3.45),
        ).arrange(RIGHT, buff=0.28)
        content = VGroup(instruction, encoding, field_legend, notes).arrange(DOWN, buff=0.3)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(instruction), run_time=0.45)
        self.play(FadeIn(encoding), FadeIn(field_legend), run_time=0.4)
        self.play(
            Succession(
                *(
                    Indicate(encoding.field_mobjects[name], color=self.theme.warning)
                    for name in ("REX.W", "opcode", "ModR/M", "SIB", "disp8")
                )
            ),
            run_time=1.2,
        )
        self.play(FadeIn(notes, shift=DOWN * 0.08), run_time=0.4)
        self.wait(0.2)


class RegisterFlagsBranchWalkthrough(RevScene):
    """Connect a signed comparison to the exact flag relation consumed by ``jl``."""

    def construct(self) -> None:
        heading = scene_heading("Why JL takes the branch for -1 < 1", "registers and flags")
        registers = RegisterBank(
            {"eax": 0xFFFFFFFF, "ecx": 0x00000001, "eip": 0x00401120},
            bits=32,
            width=4.45,
            title="before CMP",
        )
        compare = InstructionView(
            InstructionSpec(0x401120, "cmp", "eax, ecx", bytes.fromhex("39 C8")),
            width=7.6,
        )
        branch = InstructionView(
            InstructionSpec(
                0x401122,
                "jl",
                "0x401138",
                bytes.fromhex("7C 14"),
                "signed less-than",
            ),
            width=7.6,
        )
        flags = FlagRegister({"ZF": None, "SF": None, "OF": None, "CF": None})
        outcome = callout(
            "branch taken",
            "JL tests SF != OF. Here 1 != 0, so execution jumps to 0x401138.",
            width=7.6,
            color=self.theme.success,
        )
        right = VGroup(compare, branch, flags, outcome).arrange(DOWN, aligned_edge=RIGHT, buff=0.22)
        content = VGroup(registers, right).arrange(RIGHT, buff=0.52)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(registers), FadeIn(compare), run_time=0.45)
        self.play(Indicate(compare, color=self.theme.opcode), run_time=0.38)
        self.play(
            AnimationGroup(
                flags.animate_set("ZF", False),
                flags.animate_set("SF", True),
                flags.animate_set("OF", False),
                flags.animate_set("CF", False),
                lag_ratio=0.08,
            ),
            run_time=0.65,
        )
        self.play(FadeIn(branch), run_time=0.28)
        self.play(Indicate(branch, color=self.theme.success), run_time=0.38)
        self.play(FadeIn(outcome, shift=DOWN * 0.08), run_time=0.35)
        self.wait(0.2)


class CPUDataPathLoadWalkthrough(RevScene):
    """Follow a load through fetch, decode, address generation, memory, and writeback."""

    def construct(self) -> None:
        heading = scene_heading("Follow one load across the CPU", "data path")
        instruction = InstructionView(
            InstructionSpec(
                0x401080,
                "mov",
                "rax, [rbx + 0x20]",
                bytes.fromhex("48 8B 43 20"),
            ),
            width=8.7,
        )
        datapath = CPUBlockDiagram()
        registers = RegisterBank(
            {"rbx": 0x7FFFFFFFE000, "rax": 0},
            bits=64,
            columns=2,
            width=6.0,
            title="architectural state",
        )
        facts = VGroup(
            callout(
                "execute",
                "Effective address = RBX + 0x20 = 0x7FFFFFFFE020.",
                width=3.2,
                color=self.theme.warning,
            ),
            callout(
                "memory",
                "The eight-byte little-endian value is 0x1122334455667788.",
                width=3.2,
                color=self.theme.success,
            ),
        ).arrange(RIGHT, buff=0.22)
        lower = VGroup(registers, facts).arrange(RIGHT, buff=0.35)
        content = VGroup(instruction, datapath, lower).arrange(DOWN, buff=0.42)
        place_content(content, heading)

        self.play(FadeIn(heading), FadeIn(instruction), run_time=0.4)
        self.play(FadeIn(datapath), FadeIn(lower), run_time=0.45)
        self.play(
            datapath.pulse(("Fetch", "Decode", "Registers", "Execute", "Memory", "Writeback")),
            run_time=1.3,
        )
        self.play(
            registers.animate_set("rax", 0x1122334455667788, color=self.theme.success),
            run_time=0.45,
        )
        self.wait(0.2)
