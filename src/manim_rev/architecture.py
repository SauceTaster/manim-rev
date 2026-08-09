"""Portable architecture descriptions for register and CPU visuals."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Endianness(StrEnum):
    LITTLE = "little"
    BIG = "big"


@dataclass(frozen=True, slots=True)
class RegisterSpec:
    name: str
    bits: int
    role: str = "general"
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("register name cannot be empty")
        if self.bits <= 0:
            raise ValueError("register width must be positive")


@dataclass(frozen=True, slots=True)
class FlagSpec:
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("flag name cannot be empty")


@dataclass(frozen=True, slots=True)
class ArchitectureSpec:
    name: str
    bits: int
    endianness: Endianness
    program_counter: str
    stack_pointer: str
    registers: tuple[RegisterSpec, ...]
    flags: tuple[FlagSpec, ...] = ()

    def __post_init__(self) -> None:
        if self.bits <= 0:
            raise ValueError("architecture width must be positive")
        names: set[str] = set()
        identifiers: dict[str, str] = {}
        for register in self.registers:
            canonical = register.name.casefold()
            names.add(canonical)
            for identifier in (register.name, *register.aliases):
                normalized = identifier.casefold()
                if normalized in identifiers:
                    raise ValueError(
                        f"register name or alias {identifier!r} collides with "
                        f"{identifiers[normalized]!r}"
                    )
                identifiers[normalized] = register.name
        flag_names = [flag.name.casefold() for flag in self.flags]
        if len(flag_names) != len(set(flag_names)):
            raise ValueError("architecture flag names must be unique")
        if self.program_counter.casefold() not in names:
            raise ValueError("program counter must be included in registers")
        if self.stack_pointer.casefold() not in names:
            raise ValueError("stack pointer must be included in registers")

    def register(self, name_or_alias: str) -> RegisterSpec:
        needle = name_or_alias.casefold()
        for register in self.registers:
            if needle == register.name.casefold() or needle in {
                alias.casefold() for alias in register.aliases
            }:
                return register
        raise KeyError(f"unknown {self.name} register: {name_or_alias}")


X86_64 = ArchitectureSpec(
    name="x86-64",
    bits=64,
    endianness=Endianness.LITTLE,
    program_counter="rip",
    stack_pointer="rsp",
    registers=(
        RegisterSpec("rax", 64, aliases=("eax", "ax", "al")),
        RegisterSpec("rbx", 64, aliases=("ebx", "bx", "bl")),
        RegisterSpec("rcx", 64, aliases=("ecx", "cx", "cl")),
        RegisterSpec("rdx", 64, aliases=("edx", "dx", "dl")),
        RegisterSpec("rsi", 64, aliases=("esi", "si", "sil")),
        RegisterSpec("rdi", 64, aliases=("edi", "di", "dil")),
        RegisterSpec("rbp", 64, role="frame pointer", aliases=("ebp", "bp")),
        RegisterSpec("rsp", 64, role="stack pointer", aliases=("esp", "sp")),
        *(
            RegisterSpec(
                f"r{index}",
                64,
                aliases=(f"r{index}d", f"r{index}w", f"r{index}b"),
            )
            for index in range(8, 16)
        ),
        RegisterSpec("rip", 64, role="program counter", aliases=("eip", "ip")),
    ),
    flags=(
        FlagSpec("CF", "carry"),
        FlagSpec("PF", "parity"),
        FlagSpec("AF", "auxiliary carry"),
        FlagSpec("ZF", "zero"),
        FlagSpec("SF", "sign"),
        FlagSpec("OF", "overflow"),
    ),
)


AARCH64 = ArchitectureSpec(
    name="AArch64",
    bits=64,
    endianness=Endianness.LITTLE,
    program_counter="pc",
    stack_pointer="sp",
    registers=(
        *(RegisterSpec(f"x{index}", 64, aliases=(f"w{index}",)) for index in range(29)),
        RegisterSpec("x29", 64, role="frame pointer", aliases=("w29", "fp")),
        RegisterSpec("x30", 64, role="link register", aliases=("w30", "lr")),
        RegisterSpec("xzr", 64, role="constant zero", aliases=("wzr",)),
        RegisterSpec("sp", 64, role="stack pointer", aliases=("wsp",)),
        RegisterSpec("pc", 64, role="program counter"),
    ),
    flags=(
        FlagSpec("N", "negative"),
        FlagSpec("Z", "zero"),
        FlagSpec("C", "carry"),
        FlagSpec("V", "overflow"),
    ),
)


RV64 = ArchitectureSpec(
    name="RISC-V RV64",
    bits=64,
    endianness=Endianness.LITTLE,
    program_counter="pc",
    stack_pointer="x2",
    registers=(
        RegisterSpec("x0", 64, role="constant zero", aliases=("zero",)),
        RegisterSpec("x1", 64, role="return address", aliases=("ra",)),
        RegisterSpec("x2", 64, role="stack pointer", aliases=("sp",)),
        RegisterSpec("x3", 64, aliases=("gp",)),
        RegisterSpec("x4", 64, aliases=("tp",)),
        *(RegisterSpec(f"x{index}", 64, aliases=(f"t{index - 5}",)) for index in range(5, 8)),
        RegisterSpec("x8", 64, role="frame pointer", aliases=("s0", "fp")),
        RegisterSpec("x9", 64, aliases=("s1",)),
        *(RegisterSpec(f"x{index}", 64, aliases=(f"a{index - 10}",)) for index in range(10, 18)),
        *(RegisterSpec(f"x{index}", 64, aliases=(f"s{index - 16}",)) for index in range(18, 28)),
        *(RegisterSpec(f"x{index}", 64, aliases=(f"t{index - 25}",)) for index in range(28, 32)),
        RegisterSpec("pc", 64, role="program counter"),
    ),
)
