"""Small, renderer-independent data models used by the visual components."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

Address = int | str


def _validate_integer(value: object, *, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")


def _validate_address(address: Address, *, field: str) -> None:
    if isinstance(address, bool) or not isinstance(address, (int, str)):
        raise TypeError(f"{field} must be an integer or symbolic string")
    if isinstance(address, int) and address < 0:
        raise ValueError(f"{field} must be non-negative")
    if isinstance(address, str) and not address.strip():
        raise ValueError(f"{field} symbolic address cannot be empty")


class _FrozenRegisterMap(Mapping[str, int | str]):
    """A read-only mapping that remains safe under Manim's deep copies."""

    __slots__ = ("_data",)

    def __init__(self, values: Mapping[str, int | str]) -> None:
        self._data = MappingProxyType(dict(values))

    def __getitem__(self, key: str) -> int | str:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __deepcopy__(self, memo: dict[int, object]) -> _FrozenRegisterMap:
        return self

    def __reduce__(self):  # type: ignore[no-untyped-def]
        return (type(self), (dict(self._data),))

    def __repr__(self) -> str:
        return repr(dict(self._data))


def format_address(address: Address, *, width: int = 8) -> str:
    """Format integer addresses while preserving symbolic/string addresses."""

    _validate_integer(width, field="address width")
    if width < 1:
        raise ValueError("address width must be positive")
    _validate_address(address, field="address")
    if isinstance(address, int):
        digits = max(width, max(1, (address.bit_length() + 3) // 4))
        return f"0x{address:0{digits}X}"
    return str(address)


class EdgeKind(StrEnum):
    FALLTHROUGH = "fallthrough"
    TRUE = "true"
    FALSE = "false"
    CALL = "call"
    RETURN = "return"
    LOOP = "loop"
    UNCONDITIONAL = "unconditional"


class AccessKind(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


class StateStatus(StrEnum):
    ACTIVE = "active"
    FOUND = "found"
    AVOIDED = "avoided"
    DEADENDED = "deadended"
    UNSAT = "unsat"
    ERRORED = "errored"


class TracePhase(StrEnum):
    """Whether an event snapshot was captured before or after its instruction."""

    UNKNOWN = "unknown"
    BEFORE = "before"
    AFTER = "after"


@dataclass(frozen=True, slots=True)
class InstructionSpec:
    address: Address
    mnemonic: str
    operands: str = ""
    raw_bytes: bytes = b""
    comment: str = ""

    def __post_init__(self) -> None:
        _validate_address(self.address, field="instruction address")
        object.__setattr__(self, "raw_bytes", bytes(self.raw_bytes))

    @property
    def text(self) -> str:
        return f"{self.mnemonic} {self.operands}".rstrip()

    @property
    def bytes_text(self) -> str:
        return " ".join(f"{byte:02X}" for byte in self.raw_bytes)


@dataclass(frozen=True, slots=True)
class BasicBlockSpec:
    key: str
    address: Address
    instructions: Sequence[InstructionSpec | str]
    label: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("basic block key cannot be empty")
        if isinstance(self.instructions, (str, bytes)):
            raise TypeError("instructions must be a sequence, not a bare string")
        if any(not isinstance(item, (InstructionSpec, str)) for item in self.instructions):
            raise TypeError("instructions must contain only InstructionSpec or str values")
        _validate_address(self.address, field="basic block address")
        object.__setattr__(self, "instructions", tuple(self.instructions))


@dataclass(frozen=True, slots=True)
class CFGEdgeSpec:
    source: str
    target: str
    kind: EdgeKind = EdgeKind.FALLTHROUGH
    label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", EdgeKind(self.kind))


@dataclass(frozen=True, slots=True)
class MemoryAccess:
    """One exact-width access; byte values must contain every accessed byte."""

    address: Address
    size: int = 1
    kind: AccessKind = AccessKind.READ
    value: int | bytes | str | None = None

    def __post_init__(self) -> None:
        _validate_integer(self.size, field="memory access size")
        if self.size < 1:
            raise ValueError("memory access size must be positive")
        _validate_address(self.address, field="memory access address")
        object.__setattr__(self, "kind", AccessKind(self.kind))
        if isinstance(self.value, bytes) and len(self.value) != self.size:
            raise ValueError(
                "memory access byte value length must equal the access size "
                f"({len(self.value)} != {self.size})"
            )


@dataclass(frozen=True, slots=True)
class TraceEvent:
    address: Address
    instruction: str
    registers: Mapping[str, int | str] = field(default_factory=dict)
    memory: MemoryAccess | None = None
    note: str = ""
    phase: TracePhase = TracePhase.UNKNOWN
    memory_accesses: Sequence[MemoryAccess] = ()

    def __post_init__(self) -> None:
        _validate_address(self.address, field="trace event address")
        object.__setattr__(self, "registers", _FrozenRegisterMap(self.registers))
        object.__setattr__(self, "phase", TracePhase(self.phase))
        if isinstance(self.memory_accesses, (str, bytes)):
            raise TypeError("memory_accesses must be a sequence of MemoryAccess values")
        accesses = tuple(self.memory_accesses)
        if any(not isinstance(access, MemoryAccess) for access in accesses):
            raise TypeError("memory_accesses must contain only MemoryAccess values")
        if self.memory is not None and not isinstance(self.memory, MemoryAccess):
            raise TypeError("memory must be a MemoryAccess value or None")
        if self.memory is not None and accesses:
            raise ValueError("use either memory or memory_accesses, not both")
        if self.memory is not None:
            accesses = (self.memory,)
        elif accesses:
            object.__setattr__(self, "memory", accesses[0])
        object.__setattr__(self, "memory_accesses", accesses)


@dataclass(frozen=True, slots=True)
class MemorySegmentSpec:
    name: str
    start: int
    end: int
    permissions: str = "r--"
    color: str | None = None

    def __post_init__(self) -> None:
        _validate_integer(self.start, field="memory segment start")
        _validate_integer(self.end, field="memory segment end")
        if self.start < 0:
            raise ValueError("memory segment start must be non-negative")
        if self.end <= self.start:
            raise ValueError("memory segment end must be greater than start")


@dataclass(frozen=True, slots=True)
class PipelineInstruction:
    label: str
    start_cycle: int
    squashed: bool = False
    stalled_cycles: Sequence[int] = ()
    squashed_at_cycle: int | None = None

    def __post_init__(self) -> None:
        _validate_integer(self.start_cycle, field="start_cycle")
        if isinstance(self.stalled_cycles, (str, bytes)):
            raise TypeError("stalled_cycles must be a sequence of integers")
        stalled_cycles = tuple(self.stalled_cycles)
        for cycle in stalled_cycles:
            _validate_integer(cycle, field="stalled cycle")
        if self.squashed_at_cycle is not None:
            _validate_integer(self.squashed_at_cycle, field="squashed_at_cycle")
        if self.start_cycle < 0:
            raise ValueError("start_cycle must be non-negative")
        if any(cycle < 0 for cycle in stalled_cycles):
            raise ValueError("stalled cycles must be non-negative")
        if any(cycle < self.start_cycle for cycle in stalled_cycles):
            raise ValueError("stalled cycles cannot precede the instruction start")
        if self.squashed_at_cycle is not None and self.squashed_at_cycle < self.start_cycle:
            raise ValueError("squash cycle cannot precede the instruction start")
        if self.squashed and self.squashed_at_cycle is not None:
            raise ValueError("use either squashed or squashed_at_cycle, not both")
        object.__setattr__(self, "stalled_cycles", tuple(sorted(set(stalled_cycles))))


@dataclass(frozen=True, slots=True)
class SymbolicStateSpec:
    key: str
    address: Address
    constraints: Sequence[str] = ()
    status: StateStatus = StateStatus.ACTIVE
    label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.key, str):
            raise TypeError("symbolic state key must be a string")
        if not self.key.strip():
            raise ValueError("symbolic state key cannot be empty")
        if isinstance(self.constraints, (str, bytes)):
            raise TypeError("constraints must be a sequence, not a bare string")
        if any(not isinstance(constraint, str) for constraint in self.constraints):
            raise TypeError("constraints must contain only str values")
        _validate_address(self.address, field="symbolic state address")
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "status", StateStatus(self.status))


@dataclass(frozen=True, slots=True)
class SymbolicEdgeSpec:
    source: str
    target: str
    condition: str = ""


@dataclass(frozen=True, slots=True)
class XRefSpec:
    source: str
    target: str
    kind: str = "reference"
    label: str = ""
