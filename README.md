# Manim Rev

[![Project status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/SauceTaster/manim-rev#project-status)
[![CI](https://github.com/SauceTaster/manim-rev/actions/workflows/ci.yml/badge.svg)](https://github.com/SauceTaster/manim-rev/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://saucetaster.github.io/manim-rev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/SauceTaster/manim-rev/blob/main/LICENSE)

**Manim Rev** is a [Manim Community Edition](https://www.manim.community/)
plugin for explaining reverse engineering, program analysis, CPU behavior, and
software vulnerabilities in talks and videos.

It provides composable, addressable visual objects instead of one fixed slide
template. You supply the evidence and narrative; Manim Rev helps you turn them
into deterministic animations.

> **Project status:** `0.1.0` is an alpha release candidate. The source tree is
> usable and its complete example corpus has been tested, but it has **not yet
> been published to PyPI**. Expect public API changes before 1.0 and pin the
> commit or release used by a production talk.

[Website and gallery](https://saucetaster.github.io/manim-rev/) ·
[example catalog](https://github.com/SauceTaster/manim-rev/blob/main/docs/examples.md) ·
[component guide](https://github.com/SauceTaster/manim-rev/blob/main/docs/guide.md) ·
[visual QA record](https://github.com/SauceTaster/manim-rev/blob/main/docs/visual-qa.md) ·
[GitHub repository](https://github.com/SauceTaster/manim-rev)

![A contact sheet of Manim Rev's integrated example scenes](https://raw.githubusercontent.com/SauceTaster/manim-rev/main/docs/assets/visual-qa/core.png)

## What it covers

- control-flow graphs and basic blocks;
- disassembly, registers, flags, traces, and breakpoints;
- memory maps and addressable hex dumps;
- instruction encodings, CPU data paths, and pipeline hazards;
- fuzzing coverage, corpus growth, and crash triage;
- symbolic-execution trees, solver constraints, and angr-style stashes;
- source listings, cross-references, and source-to-assembly links; and
- stack overwrites, taint flow, and vulnerability callouts.

The core package renders caller-supplied snapshot models. Optional adapters
translate existing Capstone instructions, angr CFGs, Ghidra JSON exports, and
debugger trace records into those models.

Manim Rev is intentionally **not** a disassembler, decompiler, debugger,
emulator, symbolic-execution engine, exploit framework, or sandbox. It does
not run binaries, control analysis tools, collect live traces, or establish a
security boundary around untrusted input. Layouts are deterministic, but a
scene author still owns technical accuracy, narrative choices, and final
presentation-scale review.

## Installation

Manim Rev declares Python 3.11 or newer and Manim Community Edition
`>=0.20.1,<0.21`; CI targets Python 3.11–3.14. The release-candidate corpus is
qualified with the Cairo renderer. Manim's
[platform installation guide](https://docs.manim.community/en/stable/installation.html)
lists native Cairo and Pango prerequisites that some systems need.

### Install from source today

Clone the canonical repository and install the core package:

```bash
git clone https://github.com/SauceTaster/manim-rev.git
cd manim-rev
python -m pip install .
```

Install an optional adapter when you need it:

```bash
python -m pip install ".[analysis]"  # Capstone adapter
python -m pip install ".[angr]"      # angr adapter
```

For development and the bundled examples, use the locked environment:

```bash
uv sync --extra dev
uv run manim examples/showcase.py ReverseEngineeringShowcase -pql
```

### PyPI installation after the first release

Once a release is visible on [PyPI](https://pypi.org/project/manim-rev/), the
intended commands are:

```bash
python -m pip install manim-rev
python -m pip install "manim-rev[analysis]"
python -m pip install "manim-rev[angr]"
```

Do not assume those commands are available until the PyPI project shows a
published release. Manim discovers the installed plugin, but scene files
should still import the symbols they use explicitly.

## Five-minute example

```python
from manim import Create, Scene
from manim_rev import (
    BasicBlockSpec,
    CFGEdgeSpec,
    ControlFlowGraph,
    EdgeKind,
    InstructionSpec,
)


class BranchScene(Scene):
    def construct(self):
        blocks = [
            BasicBlockSpec(
                "check",
                0x401000,
                [
                    InstructionSpec(0x401000, "test", "eax, eax"),
                    InstructionSpec(0x401002, "je", "fail"),
                ],
            ),
            BasicBlockSpec("ok", 0x401004, ["call handle_ok"]),
            BasicBlockSpec("fail", 0x40100B, ["call reject"]),
        ]
        edges = [
            CFGEdgeSpec("check", "ok", EdgeKind.FALSE, "ZF = 0"),
            CFGEdgeSpec("check", "fail", EdgeKind.TRUE, "ZF = 1"),
        ]
        cfg = ControlFlowGraph(blocks, edges)
        self.play(Create(cfg))
        self.play(cfg.traverse(["check", "ok"]))
```

Save that scene as `branch_scene.py`, then render it with:

```bash
manim branch_scene.py BranchScene -pql
```

See [`examples/showcase.py`](https://github.com/SauceTaster/manim-rev/blob/main/examples/showcase.py)
for broader scenes and the
[component guide](https://github.com/SauceTaster/manim-rev/blob/main/docs/guide.md)
for the public building blocks.

## Examples and gallery

The repository includes 39 deterministic scenes spanning focused teaching
beats, integrated showcases, and crowded-layout stress cases. The
[complete catalog](https://github.com/SauceTaster/manim-rev/blob/main/docs/examples.md)
explains each scene's intent and gives
exact render commands. The [GitHub Pages site](https://saucetaster.github.io/manim-rev/)
is the easiest way to browse the public gallery.

Representative local commands:

```bash
# CFG, instructions, registers, flags, and a hex write
uv run manim examples/showcase.py ReverseEngineeringShowcase -pql

# CPU pipeline, fuzzing, symbolic execution, and vulnerability scenes
uv run manim examples/showcase.py PipelineShowcase -pql
uv run manim examples/showcase.py FuzzingShowcase -pql
uv run manim examples/showcase.py SymbolicExecutionShowcase -pql
uv run manim examples/showcase.py VulnerabilityShowcase -pql

# A breakpoint connected to the exact byte it writes
uv run manim examples/debugger_walkthrough.py DebuggerMemoryWalkthrough -pql

# Source lines connected to lowered instructions and outgoing xrefs
uv run manim examples/source_xrefs.py SourceXRefWalkthrough -pql
```

Discover and stress-render the complete catalog, then generate sampled-frame
contact sheets and readability heuristics:

```bash
uv run python scripts/render_examples.py --list
uv run python scripts/render_examples.py --jobs 2
uv run python scripts/qa_examples.py
```

The 0.1.0 release-candidate corpus passed a full 39-scene render and human
inspection of 117 early, middle, and final frames. See the
[visual QA record](https://github.com/SauceTaster/manim-rev/blob/main/docs/visual-qa.md)
for the scope and limitations of that
review. Automated heuristics are review prompts, not a substitute for checking
technical accuracy, intent, legibility, clipping, contrast, and continuity.

## Design principles

- **Presentation-first:** high contrast and legible at talk scale.
- **Deterministic:** internal layouts do not require Graphviz or random seeds.
- **Composable:** helpers return ordinary Manim animations and do not call
  `Scene.play()` for you.
- **Addressable:** views expose semantic references instead of fragile
  submobject indexes.
- **Portable:** no required LaTeX, Graphviz, angr, Capstone, or live debugger.

State-changing animation helpers update a component's logical state as soon as
the helper is called. Build and play dependent updates sequentially so each
animation starts from the state established by the previous one.

## Project status

| Area | Current state |
| --- | --- |
| Maturity | Alpha release candidate; public APIs can change before 1.0 |
| Distribution | Source install is available; no PyPI release is claimed yet |
| Python | Requires 3.11 or newer; CI targets 3.11–3.14 |
| Manim | Community Edition `>=0.20.1,<0.21` |
| Qualified renderer | Cairo; OpenGL has not been part of the release-candidate visual audit |
| Examples | 39 scenes rendered; 117 sampled frames reviewed |
| Integrations | Snapshot/import adapters, not live tool control |
| Stability approach | Changelog entries and migration notes for intentional API changes |

This is an animation library for educational material, not a security product.
Do not treat its diagrams, adapters, or examples as validation of a binary's
safety or as a substitute for reviewing original analysis evidence.

## Contributing and support

Contributions are welcome. Start with
[`CONTRIBUTING.md`](https://github.com/SauceTaster/manim-rev/blob/main/CONTRIBUTING.md)
and the
[`CODE_OF_CONDUCT.md`](https://github.com/SauceTaster/manim-rev/blob/main/CODE_OF_CONDUCT.md).
Public bug reports, feature
requests, and visual regressions belong in
[GitHub Issues](https://github.com/SauceTaster/manim-rev/issues); support is
best-effort while the project is alpha.

Do not disclose suspected vulnerabilities in a public issue. Follow
[`SECURITY.md`](https://github.com/SauceTaster/manim-rev/blob/main/SECURITY.md)
and use GitHub private vulnerability reporting when it is enabled. Citation
metadata for papers and teaching material is in
[`CITATION.cff`](https://github.com/SauceTaster/manim-rev/blob/main/CITATION.cff).

## License

[MIT](https://github.com/SauceTaster/manim-rev/blob/main/LICENSE) © Manim Rev contributors.
