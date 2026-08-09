from __future__ import annotations

import pytest
from manim import Animation

from manim_rev.architecture import AARCH64, X86_64
from manim_rev.cpu import (
    CPUBlockDiagram,
    FlagRegister,
    InstructionEncoding,
    InstructionField,
    InstructionView,
    PipelineDiagram,
    RegisterBank,
)
from manim_rev.models import InstructionSpec, PipelineInstruction
from manim_rev.refs import AddressRangeRef, AddressRef, FlagRef, PipelineSlotRef, RegisterRef


def test_instruction_view_exposes_semantic_address() -> None:
    view = InstructionView(InstructionSpec(0x401000, "mov", "rax, rbx", b"\x48\x89\xd8"))
    assert view.instruction.bytes_text == "48 89 D8"
    assert view.resolve(AddressRef(0x401000)) == (view,)
    assert not view.resolve(AddressRef(0x401001))
    assert view.resolve(AddressRangeRef(0x401001, 1)) == (view,)


def test_instruction_view_fits_long_machine_code_inside_panel() -> None:
    view = InstructionView(
        InstructionSpec(
            0x401000,
            "vperm2f128",
            "ymm0, ymm1, ymm2, 0x31",
            bytes(range(15)),
            "long decoded instruction",
        )
    )
    assert view.width <= 5.8 + 1e-6


def test_register_bank_updates_and_resolves_case_insensitively() -> None:
    bank = RegisterBank({"rax": 1, "rbx": 2}, columns=2)
    assert bank.resolve(RegisterRef("RAX")) == (bank.rows["rax"],)
    assert isinstance(bank.animate_set("rax", 0xFEED), Animation)
    assert bank._values["rax"] == 0xFEED
    assert bank.set_value("RBX", 3) is bank

    architecture_bank = RegisterBank.from_architecture(X86_64, {"eax": 1, "RSP": 2})
    assert tuple(architecture_bank.rows) == ("rax", "rsp")
    with pytest.raises(ValueError, match="multiple values"):
        RegisterBank.from_architecture(X86_64, {"rax": 1, "eax": 2})


def test_flags_and_instruction_encoding() -> None:
    flags = FlagRegister({"ZF": False, "CF": True, "OF": None})
    assert flags.resolve(FlagRef("zf")) == (flags.cells["ZF"],)
    assert isinstance(flags.animate_set("ZF", True), Animation)

    encoding = InstructionEncoding(
        [InstructionField("opcode", 7, "0110011"), InstructionField("rd", 5, "00001")]
    )
    assert set(encoding.field_mobjects) == {"opcode", "rd"}
    with pytest.raises(ValueError, match="positive"):
        InstructionEncoding([InstructionField("bad", 0, "")])
    with pytest.raises(ValueError, match="unique"):
        InstructionEncoding([InstructionField("op", 4, "1"), InstructionField("OP", 4, "2")])

    architecture_flags = FlagRegister.from_architecture(AARCH64, {"z": True, "V": False})
    assert tuple(architecture_flags.cells) == ("Z", "V")


def test_pipeline_places_stalls_and_resolves_slots() -> None:
    pipeline = PipelineDiagram(
        [
            PipelineInstruction("load", 0),
            PipelineInstruction("add", 1, stalled_cycles=(3,)),
        ]
    )
    assert pipeline.schedule[1][3] == "STALL"
    assert pipeline.schedule[1][4] == "EX"
    assert pipeline.resolve(PipelineSlotRef(1, 3)) == (pipeline.cells[(1, 3)],)
    assert isinstance(pipeline.highlight_cycle(3), Animation)
    with pytest.raises(IndexError):
        pipeline.highlight_cycle(99)
    with pytest.raises(TypeError, match="bare string"):
        PipelineDiagram("load")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bare string"):
        PipelineDiagram(b"load")  # type: ignore[arg-type]


def test_pipeline_squash_cycle_truncates_wrong_path_work() -> None:
    pipeline = PipelineDiagram(
        [
            PipelineInstruction("branch", 1),
            PipelineInstruction("wrong path", 2, squashed_at_cycle=3),
        ]
    )

    assert pipeline.schedule[1] == {2: "IF", 3: "ID"}
    assert pipeline.squashed_slots == frozenset({(1, 3)})
    assert pipeline.cells[(1, 3)][1].text == "X"
    with pytest.raises(ValueError, match="unique"):
        PipelineDiagram(["nop"], stages=("IF", "if"))


def test_cpu_block_path_validation() -> None:
    cpu = CPUBlockDiagram()
    assert isinstance(cpu.pulse(["Fetch", "Decode", "Execute"]), Animation)
    with pytest.raises(KeyError, match="unknown CPU"):
        cpu.pulse(["warp drive"])
    with pytest.raises(ValueError, match="cannot be empty"):
        cpu.pulse([])
    with pytest.raises(ValueError, match="unique"):
        CPUBlockDiagram(blocks=("Decode", "decode"))
