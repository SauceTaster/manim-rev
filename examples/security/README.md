# Security talk gallery

This directory is a stress-oriented gallery for the CPU, pipeline, fuzzing,
symbolic-execution, and vulnerability APIs in Manim Rev. Each scene is one
short talk beat with recorded facts and an explicit takeaway. The layouts are
designed for Manim's default 16:9 frame.

The examples use Pango-backed text only. They require neither LaTeX nor
Graphviz.

## Scene index

| File | Scene | Audience question |
| --- | --- | --- |
| `cpu_walkthroughs.py` | `InstructionDecodeWalkthrough` | How do five x86-64 byte groups encode one load? |
| `cpu_walkthroughs.py` | `RegisterFlagsBranchWalkthrough` | Which flags make signed `jl` take the branch? |
| `cpu_walkthroughs.py` | `CPUDataPathLoadWalkthrough` | Where does a load travel before writeback? |
| `pipeline_hazards.py` | `PipelineLoadUseHazard` | Why does a dependent ALU operation need a bubble? |
| `pipeline_hazards.py` | `PipelineBranchMispredictSquash` | Which wrong-path instructions are discarded? |
| `fuzzing_campaigns.py` | `FuzzCoverageGrowthCampaign` | Which retained mutation opened new coverage? |
| `fuzzing_campaigns.py` | `FuzzCrashTriageWalkthrough` | How does a crash counter become a useful report? |
| `symbolic_execution.py` | `SymbolicForkConstraintWalkthrough` | Which satisfiable constraints reach a hidden parser? |
| `symbolic_execution.py` | `SymbolicStashLifecycle` | How do states move between angr-style stashes? |
| `vulnerability_stories.py` | `StackOverwriteControlFlow` | Which payload bytes cross each stack boundary? |
| `vulnerability_stories.py` | `TaintToCommandSink` | Why does a length check fail to remove command taint? |
| `vulnerability_stories.py` | `VulnerabilityTriageBoard` | Which evidence makes one finding more urgent? |

## Render the gallery

Run these commands from the repository root:

```bash
uv run manim -ql --renderer=cairo examples/security/cpu_walkthroughs.py \
  InstructionDecodeWalkthrough RegisterFlagsBranchWalkthrough \
  CPUDataPathLoadWalkthrough

uv run manim -ql --renderer=cairo examples/security/pipeline_hazards.py \
  PipelineLoadUseHazard PipelineBranchMispredictSquash

uv run manim -ql --renderer=cairo examples/security/fuzzing_campaigns.py \
  FuzzCoverageGrowthCampaign FuzzCrashTriageWalkthrough

uv run manim -ql --renderer=cairo examples/security/symbolic_execution.py \
  SymbolicForkConstraintWalkthrough SymbolicStashLifecycle

uv run manim -ql --renderer=cairo examples/security/vulnerability_stories.py \
  StackOverwriteControlFlow TaintToCommandSink VulnerabilityTriageBoard
```

Use `-qh` for a final talk render after changing platform-specific text,
addresses, or evidence strings.

## Visual QA record

The full gallery was rendered with Manim Community 0.20.1, Cairo, and the
854x480 low-quality preset. Beginning, intermediate, and final frames were
sampled from every scene and checked for clipping, overlap, contrast,
chronology, and whether the final frame communicates the stated audience
question. All 12 scenes passed after the example-level adjustments below:

- Keep crash previews short with `max_input_bytes`; long hexadecimal previews
  are intentionally shrunk by `CrashCard` and become hard to read at 480p.
- Animate `FadeIn(view)` and `Indicate(view)` sequentially when they target the
  same mobject. Running them simultaneously can leave the view transparent.
- `VulnerabilityTriageBoard` deliberately combines long finding titles with
  4.15-unit cards. It is a regression example for title fitting beside the
  severity badge.
- `TaintToCommandSink` deliberately mixes addressed and unaddressed stages at
  a tight gap. It is a regression example for horizontal connector routing
  across unequal node heights.

The final two cases exposed component layout defects during this stress pass;
the current implementations were changed and these scenes now guard the
intended output. Re-render any scene after changing its copy or geometry.
