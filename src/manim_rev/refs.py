"""Semantic references and cross-view focus helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable

from manim import Animation, AnimationGroup, Indicate, Mobject

from .models import Address
from .theme import DEFAULT_THEME


@dataclass(frozen=True, slots=True)
class AddressRef:
    """Compatibility reference for any visual associated with an address.

    Some views attach only one meaning to an address. Dynamic traces can attach
    both an executed instruction and a memory access to the same row, so new code
    can use :class:`ExecutedAddressRef` or :class:`MemoryAddressRef` when that
    distinction matters.
    """

    address: Address

    def __post_init__(self) -> None:
        if isinstance(self.address, bool) or not isinstance(self.address, (int, str)):
            raise TypeError("address reference must be an integer or symbolic string")
        if isinstance(self.address, int) and self.address < 0:
            raise ValueError("address reference must be non-negative")
        if isinstance(self.address, str) and not self.address.strip():
            raise ValueError("symbolic address reference cannot be empty")


@dataclass(frozen=True, slots=True)
class ExecutedAddressRef(AddressRef):
    """Address of an instruction executed by a dynamic trace."""


@dataclass(frozen=True, slots=True)
class MemoryAddressRef(AddressRef):
    """Address touched by a dynamic memory access."""


@dataclass(frozen=True, slots=True)
class AddressRangeRef:
    """Compatibility reference for visuals intersecting an address range."""

    start: int
    length: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("address range start must be non-negative")
        if self.length < 1:
            raise ValueError("address range length must be positive")


@dataclass(frozen=True, slots=True)
class MemoryRangeRef(AddressRangeRef):
    """Address range touched by a dynamic memory access."""


@dataclass(frozen=True, slots=True)
class BlockRef:
    key: str

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("block reference key cannot be empty")


@dataclass(frozen=True, slots=True)
class RegisterRef:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("register reference name cannot be empty")


@dataclass(frozen=True, slots=True)
class FlagRef:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("flag reference name cannot be empty")


@dataclass(frozen=True, slots=True)
class SourceRef:
    line: int
    file: str | None = None

    def __post_init__(self) -> None:
        if self.line < 1:
            raise ValueError("source reference line must be positive")


@dataclass(frozen=True, slots=True)
class SymbolicStateRef:
    key: str

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("symbolic state reference key cannot be empty")


@dataclass(frozen=True, slots=True)
class PipelineSlotRef:
    instruction: int
    cycle: int

    def __post_init__(self) -> None:
        if self.instruction < 0 or self.cycle < 0:
            raise ValueError("pipeline slot indexes must be non-negative")


VisualRef: TypeAlias = (
    AddressRef
    | AddressRangeRef
    | ExecutedAddressRef
    | MemoryAddressRef
    | MemoryRangeRef
    | BlockRef
    | RegisterRef
    | FlagRef
    | SourceRef
    | SymbolicStateRef
    | PipelineSlotRef
)


@runtime_checkable
class RefResolver(Protocol):
    """Implemented by views that expose semantic references."""

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]: ...


def focus_across(
    ref: VisualRef,
    *views: RefResolver,
    color: str = DEFAULT_THEME.warning,
    scale_factor: float = 1.06,
    lag_ratio: float = 0,
) -> Animation:
    """Indicate every mobject that resolves to ``ref`` across multiple views."""

    targets: list[Mobject] = []
    seen: set[int] = set()
    for view in views:
        for target in view.resolve(ref):
            identity = id(target)
            if identity not in seen:
                targets.append(target)
                seen.add(identity)
    if not targets:
        raise LookupError(f"no view resolved {ref!r}")
    return AnimationGroup(
        *(Indicate(target, color=color, scale_factor=scale_factor) for target in targets),
        lag_ratio=lag_ratio,
    )
