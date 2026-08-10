# Manim Rev guide

Manim Rev is a set of presentation-oriented Manim mobjects. Build a model,
construct a view, add it to a scene, then compose the animation returned by the
view with any ordinary Manim animation.

State-changing animation helpers update a component's logical state when the
helper is called, before `Scene.play()` runs. Build and play dependent updates
in sequence; do not assume logical state changes are deferred until playback.

The package is intentionally not a live debugger or binary loader. Record the
facts you want to explain first, then render them deterministically.

## Component map

| Topic | Main components |
| --- | --- |
| Control flow | `BasicBlock`, `ControlFlowGraph` |
| Instructions and CPU | `InstructionView`, `InstructionEncoding`, `CPUBlockDiagram` |
| Registers and flags | `RegisterBank`, `FlagRegister` |
| Pipelining | `PipelineDiagram`, `PipelineInstruction` |
| Memory | `HexDump`, `MemoryMap` |
| Debug traces | `ExecutionTrace` |
| Source analysis | `SourceListing`, `CrossReferencePanel`, `SourceAssemblyMap` |
| Fuzzing | `CoverageBitmap`, `FuzzingDashboard`, `CrashCard` |
| Symbolic execution | `SymbolicExecutionTree`, `ConstraintPanel`, `StashPanel` |
| Vulnerabilities | `StackOverflowDiagram`, `TaintFlowDiagram`, `VulnerabilityCard` |
| Coordinated panes | `AnalysisWorkbench`, `ReferenceLink`, `focus_across` |

All core text uses Pango-backed `Text`; LaTeX is not required. CFG and symbolic
tree layouts are internal and deterministic; Graphviz is not required.

## Themes and scenes

`RevScene` sets a dark, high-contrast background and provides simple title-card
helpers. Every component accepts a `RevTheme`, so a scene can use a custom
palette without changing global Manim state.

The default palette stays close to Manim Community Edition's familiar visual
language: black, white, and gray for structure; blue (`#58C4DD`) for active
information; green (`#83C167`) for success and true branches; yellow
(`#F7D96F`) for warnings and loops; and red (`#FC6255`) for false branches,
failures, or dangerous state. Branch labels keep the meaning explicit without
relying on color alone.

```python
from manim_rev import DEFAULT_THEME, RevScene


class BrandedTalk(RevScene):
    theme = DEFAULT_THEME.derive(
        background="#101010",
        info="#29ABCA",
        warning="#F0AC5F",
    )

    def construct(self):
        title = self.show_title("From bytes to behavior", "a guided trace")
        self.wait()
```

`light_theme()` returns a light projector-friendly alternative. The retained
0.1.0 visual audit covers the default dark theme; review a light-theme scene on
the intended projector before using it in a talk.

## CFGs and basic blocks

Models are renderer-independent. An instruction can be a short string or an
`InstructionSpec` when the scene needs a real address, machine bytes, mnemonic,
and operands.

```python
from manim_rev import (
    BasicBlockSpec,
    CFGEdgeSpec,
    ControlFlowGraph,
    EdgeKind,
    InstructionSpec,
)

blocks = [
    BasicBlockSpec(
        "entry",
        0x401000,
        [
            InstructionSpec(0x401000, "cmp", "eax, 0", b"\x83\xf8\x00"),
            InstructionSpec(0x401003, "je", "0x401010", b"\x74\x0b"),
        ],
        label="validate",
    ),
    BasicBlockSpec("accept", 0x401005, ["call process", "ret"]),
    BasicBlockSpec("reject", 0x401010, ["xor eax, eax", "ret"]),
]
edges = [
    CFGEdgeSpec("entry", "accept", EdgeKind.FALSE, "ZF = 0"),
    CFGEdgeSpec("entry", "reject", EdgeKind.TRUE, "ZF = 1"),
]
cfg = ControlFlowGraph(
    blocks,
    edges,
    positions={
        "entry": (0, 2),
        "accept": (-2.7, -1),
        "reject": (2.7, -1),
    },
)

self.add(cfg)
self.play(cfg.traverse(["entry", "accept"]))
```

`ControlFlowGraph.block(key)`, `edge(source, target)`, and address lookup methods
avoid fragile indexes into `submobjects`. Pass `positions={key: (x, y)}` (or
three-dimensional `(x, y, z)` coordinates) when matching a diagram from
another tool. A partial mapping overrides only the named blocks; omitted blocks
retain their repeatable built-in layered positions.

The built-in layout ranks blocks by their longest forward path, so a merge is
placed below all of its incoming branches. Explicit loop and detected back edges
are excluded from ranking and routed outside the graph bounds. Ordinary edges
use distributed block ports; true and false labels remain explicit rather than
relying on color alone.

Instruction rows preserve full integer and symbolic addresses by default. For a
deliberately compact talk diagram, pass `compact_addresses=True` to
`BasicBlock` or `ControlFlowGraph`; integers then use an explicit ellipsis such
as `0x…ABCD`, while symbolic addresses remain intact. Blocks narrower than the
supported column minimum raise an error instead of silently overflowing. The
minimum basic-block width is `2.25`, or `3.10` when `show_bytes=True`; automatic
CFG layout gaps must be at least `0.25` so edge ports and labels have real
clearance.

## Disassembly, registers, flags, and CPU details

`InstructionView` is a single decoded-instruction card. `RegisterBank` and
`FlagRegister` expose stable named cells and animate updates without calling
`Scene.play()` themselves.

```python
from manim_rev import FlagRegister, RegisterBank

registers = RegisterBank(
    {"rip": 0x401000, "rax": 0, "rbx": 0x7FFFFFFFE120},
    bits=64,
    columns=1,
)
flags = FlagRegister({"ZF": False, "CF": False, "SF": None, "OF": False})

self.add(registers, flags)
self.play(registers.animate_set("rip", 0x401003))
self.play(flags.animate_set("ZF", True))
```

Built-in `ArchitectureSpec` snapshots are available as `X86_64`, `AARCH64`,
and `RV64`. They normalize common register aliases and describe PC/SP roles.
They do not emulate instructions.

Use `RegisterBank.from_architecture(X86_64, values)` or
`FlagRegister.from_architecture(AARCH64, flags)` to normalize aliases and use
the architecture's native width and labels.

`InstructionEncoding` creates proportional named bit fields. `CPUBlockDiagram`
explains movement through fetch/decode/register/execute/memory/writeback blocks.

## Pipeline talks

Pipeline rows can be strings for a regular staggered schedule or explicit
`PipelineInstruction` values with stalls and squashed instructions.

```python
from manim_rev import PipelineDiagram, PipelineInstruction

pipeline = PipelineDiagram(
    [
        PipelineInstruction("load rax, [rbx]", 0),
        PipelineInstruction("add rcx, rax", 1, stalled_cycles=(3,)),
        PipelineInstruction("wrong-path load", 2, squashed_at_cycle=3),
    ],
    stages=("IF", "ID", "EX", "MEM", "WB"),
)

self.add(pipeline)
self.play(pipeline.highlight_cycle(3))
```

Stalls are labeled. Set `squashed_at_cycle` to stop a wrong-path instruction at
the cycle where it is flushed; that slot uses both an `X` and color so the state
does not depend on color perception alone. The legacy `squashed=True` form marks
an entire row when cycle-level timing is intentionally unspecified.

## Hex dumps and memory maps

`HexDump` windows a byte sequence at a base address and keeps direct handles to
address, byte, and ASCII cells. Use `bytes_at(address, length)` to coordinate a
memory access with another view. Use `MemoryMap` for address-space segments and
permissions.

Keep the visible byte window small. A talk rarely benefits from constructing a
`Text` object for an entire memory image.

## Traces, breakpoints, and coordinated panes

`ExecutionTrace` renders a recorded sequence of `TraceEvent` objects. Each event
can contain its instruction, register snapshot, note, and one or more memory
accesses. Set `phase=TracePhase.BEFORE` or `TracePhase.AFTER` when the capture
point is known; the row labels it as pre- or post-state. Leave it unknown only
when the producer cannot establish timing. The trace exposes stable
event/address lookups, `current_index`, `current_event`, `current_row`, an
active-row cursor, stepping animations, and breakpoint markers.

For a long recording, keep the projected text readable with a numbered window:

```python
trace_view = ExecutionTrace.window(
    events,
    start=120,
    count=7,
    breakpoints=recorded_breakpoints,
)
```

Rows retain their indexes from the complete recording. Event lookup and
stepping use local indexes inside the visible window, and breakpoints outside
that window are omitted.

`AnalysisWorkbench` arranges any named views and resolves semantic references
across them. This is the most direct way to explain “this breakpoint caused
that write.”

```python
from manim_rev import AnalysisWorkbench

workbench = AnalysisWorkbench(
    {"trace": trace_view, "registers": registers, "memory": hex_dump},
    columns=2,
)
self.add(workbench)

link = workbench.breakpoint_to_memory(
    breakpoint_panel="trace",
    instruction_address=0x40102A,
    memory_panel="memory",
    memory_address=0x7FFFFFFFE128,
    length=8,
    label="8-byte write",
)
self.play(link.animate_flow())
```

## Source, assembly, and cross-references

`SourceListing` owns its line mobjects rather than depending on private fields
inside Manim's `Code` class. `CrossReferencePanel` presents calls, reads, writes,
and other references. `SourceAssemblyMap` draws and animates stable connections
from source lines to one or more instruction addresses.

Use these views for source-level root cause, compiler lowering, and following a
call or data reference through a program.

## Fuzzing

`CoverageBitmap` is an addressable bitmap/grid for newly discovered edges or
blocks. `FuzzingDashboard` shows the small set of live numbers an audience can
follow—executions, coverage, corpus, and crashes. `CrashCard` turns a unique
crash into a legible triage summary.

Prefer recorded snapshots at meaningful points over animating every fuzz input.
Typical beats are corpus seed, new path, coverage plateau, first crash, and
deduplicated crash.

## Symbolic execution and angr-style states

`SymbolicExecutionTree` visualizes forks and pruned paths from
`SymbolicStateSpec` and `SymbolicEdgeSpec`. `ConstraintPanel` makes solver input
explicit, while `StashPanel` shows active/found/avoided/deadended/errored counts.

These are angr-like visuals, not a live angr dependency. The optional adapter
can snapshot an angr CFG; symbolic states can be modeled directly so renders
remain reproducible.

## Vulnerability showcases

Use `StackOverflowDiagram` to reveal buffer bytes crossing into the saved frame
pointer and return address. `TaintFlowDiagram` shows untrusted data traveling
through transforms or sanitizers to a sensitive sink. `VulnerabilityCard`
anchors the demo with CWE, severity, impact, and root cause.

The components visualize a scenario; they do not generate payloads or execute
untrusted code.

## Semantic references

References let independent panels agree about what an item means:

- `AddressRef` and `AddressRangeRef`
- `ExecutedAddressRef`, `MemoryAddressRef`, and `MemoryRangeRef` when a dynamic
  trace must distinguish the instruction pointer from touched storage
- `BlockRef`
- `RegisterRef` and `FlagRef`
- `SourceRef`
- `PipelineSlotRef`
- `SymbolicStateRef`

Views implement `resolve(ref)`. Use `focus_across(ref, view_a, view_b, ...)` for
a synchronized indication, or `AnalysisWorkbench.focus(ref)` across every pane.
For repeated events, `AnalysisWorkbench.link()` accepts `source_occurrence` and
`target_occurrence`; pass `path_arc` when a curved manual route avoids dense
content.

## Optional adapters

`manim_rev.adapters` uses duck typing and imports no heavy analysis framework.

- `instruction_from_capstone()` converts a Capstone instruction.
- `cfg_from_angr()` snapshots an angr/NetworkX-like CFG.
- `cfg_from_ghidra_json()` consumes a small exported JSON shape.
- `trace_events_from_records()` accepts JSON/GDB/LLDB-style dictionaries.

For a source checkout today, install the relevant extra with
`python -m pip install ".[analysis]"` for Capstone or
`python -m pip install ".[angr]"` for angr. After a release is visible on PyPI,
the corresponding distribution commands will be
`python -m pip install "manim-rev[analysis]"` and
`python -m pip install "manim-rev[angr]"`. Live analysis should happen before
rendering.

## Rendering and testing

```bash
uv run pytest
uv run ruff check .
uv run manim examples/showcase.py ReverseEngineeringShowcase -ql
```

Cairo is the baseline renderer. Keep a smoke render for each scene used in a
talk, especially if its layout is tightly packed or uses long platform-specific
symbol names.
