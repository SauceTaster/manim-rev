# Example catalog

Manim Rev ships 39 deterministic scenes. Each scene is a short talk beat rather
than a feature dump: its class docstring states the intended audience takeaway,
and its animation focuses on the evidence that supports that takeaway.

All examples target Manim's default 16:9 frame, work with the Cairo renderer,
and require neither LaTeX nor Graphviz.

## Analysis and debugging

| Source | Scenes | Focus |
| --- | --- | --- |
| [`analysis/cfg_talks.py`](../examples/analysis/cfg_talks.py) | `LoopAndCallRecovery`, `DenseDispatchRecovery`, `TraceBackedBranchRecovery` | loops, calls, jump tables, merge points, and trace-backed CFG validation |
| [`analysis/debugger_traces.py`](../examples/analysis/debugger_traces.py) | `RunToBreakpointWalkthrough`, `ReadModifyWriteTrace`, `RepeatedLoopBreakpoint` | breakpoints, stopped state, repeated addresses, and memory accesses |
| [`analysis/memory_workbenches.py`](../examples/analysis/memory_workbenches.py) | `ProtocolHexFieldTour`, `ProcessMemoryMapTour`, `SemanticPatchWorkbench` | byte fields, cross-row highlights, mappings, permissions, and coordinated panes |
| [`analysis/source_analysis.py`](../examples/analysis/source_analysis.py) | `SourceLoweringWalkthrough`, `IncomingXRefPivot`, `RootCauseAcrossViews` | source-to-assembly links, incoming/outgoing xrefs, and evidence joined by address |
| [`debugger_walkthrough.py`](../examples/debugger_walkthrough.py) | `DebuggerMemoryWalkthrough` | one store followed from trace instruction to exact stack byte |
| [`source_xrefs.py`](../examples/source_xrefs.py) | `SourceXRefWalkthrough` | one C branch connected to basic blocks, calls, and code references |

The [analysis gallery guide](../examples/analysis/README.md) lists the audience
question and direct render command for each of its 12 scenes.

## CPU and security stories

| Source | Scenes | Focus |
| --- | --- | --- |
| [`security/cpu_walkthroughs.py`](../examples/security/cpu_walkthroughs.py) | `InstructionDecodeWalkthrough`, `RegisterFlagsBranchWalkthrough`, `CPUDataPathLoadWalkthrough` | byte decoding, effective addresses, flags, signed branches, and CPU data paths |
| [`security/pipeline_hazards.py`](../examples/security/pipeline_hazards.py) | `PipelineLoadUseHazard`, `PipelineBranchMispredictSquash` | bubbles, forwarding pressure, misprediction, and squashed work |
| [`security/fuzzing_campaigns.py`](../examples/security/fuzzing_campaigns.py) | `FuzzCoverageGrowthCampaign`, `FuzzCrashTriageWalkthrough` | corpus growth, new edges, crash reproduction, and deduplication |
| [`security/symbolic_execution.py`](../examples/security/symbolic_execution.py) | `SymbolicForkConstraintWalkthrough`, `SymbolicStashLifecycle` | symbolic forks, constraints, satisfiability, and angr-style state stashes |
| [`security/vulnerability_stories.py`](../examples/security/vulnerability_stories.py) | `StackOverwriteControlFlow`, `TaintToCommandSink`, `VulnerabilityTriageBoard` | stack boundaries, taint to a command sink, and evidence-driven triage |

The [security gallery guide](../examples/security/README.md) includes the direct
render commands and the design findings produced by its visual stress pass.

## Integrated showcases

[`showcase.py`](../examples/showcase.py) contains five compact scenes for a
first tour of the library:

- `ReverseEngineeringShowcase` combines a CFG, disassembly, registers, flags,
  and a stack-memory window.
- `PipelineShowcase` connects a load-use stall to a simplified CPU data path.
- `FuzzingShowcase` moves from coverage growth to a unique crash.
- `SymbolicExecutionShowcase` follows a fork, constraint, and stash summary.
- `VulnerabilityShowcase` joins a stack overwrite, taint path, and finding card.

## Layout stress scenes

[`stress/component_limits.py`](../examples/stress/component_limits.py) contains
eight regression scenes that intentionally pressure reusable components:

- mixed short and maximum-length instructions;
- x86-64, AArch64, and RV64 register sets;
- a 64-byte dump with writes crossing a row boundary;
- realistic process mappings with long labels and permission changes;
- a readable viewport into a longer instruction trace;
- a pre/post-state trace with one instruction performing both a read and write;
- an odd-count semantic workbench with a centered trailing view; and
- eight overlapping pipeline instructions with stalls and squashes.

These scenes are examples you can borrow from, but they also serve as a visual
regression corpus for scale-aware transforms and crowded projector layouts.

## Discover and render everything

From the repository root:

```bash
uv run python scripts/render_examples.py --list
uv run python scripts/render_examples.py --jobs 2
uv run python scripts/qa_examples.py
```

The renderer isolates every scene's Manim media cache, records failures and
timeouts in JSON, and supports substring filters with repeated `--match`
arguments. The QA command samples early, middle, and final frames, writes
per-category final-frame and timeline contact sheets, and reports likely
clipping, contrast, density, or blank-frame problems for human review.

The retained 0.1.0 release-candidate results are in the
[visual QA record](visual-qa.md): 39 of 39 scenes rendered, all 117 sampled
frames passed the automated heuristics, and the contact sheets received a
human content and readability review.

Use `-qh` with Manim directly for final presentation output after replacing
the examples' addresses, code, and evidence with material from your talk.
