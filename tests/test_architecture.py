from __future__ import annotations

import pytest

from manim_rev.architecture import (
    AARCH64,
    RV64,
    X86_64,
    ArchitectureSpec,
    Endianness,
    RegisterSpec,
)


def test_builtin_architectures_expose_roles_and_aliases() -> None:
    assert X86_64.register("eax").name == "rax"
    assert X86_64.register(X86_64.program_counter).role == "program counter"
    assert AARCH64.register("x30").bits == 64
    assert AARCH64.register("lr").name == "x30"
    assert AARCH64.register("w7").name == "x7"
    assert RV64.register("sp").name == "x2"
    assert RV64.register("a7").name == "x17"
    assert RV64.register("t6").name == "x31"
    assert X86_64.register("r12d").name == "r12"


def test_architecture_requires_pc_and_sp_in_register_file() -> None:
    with pytest.raises(ValueError, match="program counter"):
        ArchitectureSpec("bad", 32, Endianness.LITTLE, "pc", "sp", ())


def test_unknown_register_has_contextual_error() -> None:
    with pytest.raises(KeyError, match="x86-64"):
        X86_64.register("not_a_register")


def test_architecture_rejects_alias_collisions() -> None:
    with pytest.raises(ValueError, match="collides"):
        ArchitectureSpec(
            "ambiguous",
            64,
            Endianness.LITTLE,
            "pc",
            "sp",
            (
                RegisterSpec("pc", 64, aliases=("ip",)),
                RegisterSpec("sp", 64, aliases=("IP",)),
            ),
        )
