# Analysis talk examples

This gallery contains twelve short, deterministic scenes for code-analysis and
debugging talks.  Every scene targets Manim's default 16:9 frame, uses Cairo,
and avoids LaTeX and Graphviz.

## Scene catalog

| File | Scene | Talk beat / stress case |
| --- | --- | --- |
| `cfg_talks.py` | `LoopAndCallRecovery` | Recover a loop across CALL and RETURN edges, then traverse the back edge. |
| `cfg_talks.py` | `DenseDispatchRecovery` | Keep a five-way jump-table dispatch and its shared epilogue readable. |
| `cfg_talks.py` | `TraceBackedBranchRecovery` | Validate a static branch with a recorded dynamic path. |
| `source_analysis.py` | `SourceLoweringWalkthrough` | Map one source condition to multiple lowered instructions. |
| `source_analysis.py` | `IncomingXRefPivot` | Pivot among incoming calls, reads, writes, and outgoing calls. |
| `source_analysis.py` | `RootCauseAcrossViews` | Join source, trace, and xref evidence by instruction address. |
| `debugger_traces.py` | `RunToBreakpointWalkthrough` | Arm a breakpoint and inspect the stopped call target. |
| `debugger_traces.py` | `ReadModifyWriteTrace` | Follow a little-endian read-modify-write into a hex dump. |
| `debugger_traces.py` | `RepeatedLoopBreakpoint` | Preserve duplicate trace addresses and visit three breakpoint occurrences. |
| `memory_workbenches.py` | `ProtocolHexFieldTour` | Highlight fields across a row boundary and patch a length value. |
| `memory_workbenches.py` | `ProcessMemoryMapTour` | Resolve execute, read, heap-write, and stack-write addresses to mappings. |
| `memory_workbenches.py` | `SemanticPatchWorkbench` | Coordinate source, breakpoint, bytes, and process mapping in one workbench. |

## Render the gallery

From the repository root:

```bash
uv run manim -ql --renderer cairo examples/analysis/cfg_talks.py \
  LoopAndCallRecovery DenseDispatchRecovery TraceBackedBranchRecovery

uv run manim -ql --renderer cairo examples/analysis/source_analysis.py \
  SourceLoweringWalkthrough IncomingXRefPivot RootCauseAcrossViews

uv run manim -ql --renderer cairo examples/analysis/debugger_traces.py \
  RunToBreakpointWalkthrough ReadModifyWriteTrace RepeatedLoopBreakpoint

uv run manim -ql --renderer cairo examples/analysis/memory_workbenches.py \
  ProtocolHexFieldTour ProcessMemoryMapTour SemanticPatchWorkbench
```

Use `-qh` for a final talk render.  The low-quality commands above are useful
as a quick regression pass because they expose text that becomes too small at
projector-like resolutions.

## Presentation conventions

- Each scene has one claim in its title, one evidence-focused animation, and a
  concise takeaway along the bottom edge.
- Visible traces and byte windows are intentionally small; the audience should
  be able to follow the active row or address without pausing the talk.
- Address-based semantic references connect panes instead of depending on
  brittle `submobjects` indexes.
- Read, write, execute, true/false, call/return, and loop states use both text
  labels and color, so meaning does not depend on color alone.
