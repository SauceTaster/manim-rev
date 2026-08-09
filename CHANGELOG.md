# Changelog

All notable changes to Manim Rev are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The source tree currently identifies itself as `0.1.0` for release-candidate
validation. No `0.1.0` tag or PyPI release is claimed yet.

### Added

- Initial Manim Community Edition plugin and typed public API.
- Control-flow graphs, basic blocks, instructions, traces, breakpoints,
  registers, flags, memory maps, and hex dumps.
- Optional explicit two- or three-dimensional control-flow graph positions.
- Number-preserving `ExecutionTrace.window()` views for long recordings.
- Pre/post trace phases, multi-access events, and execution-vs-memory references.
- Architecture-normalized register and flag banks and cycle-specific pipeline squashes.
- CPU diagrams, instruction encodings, pipeline hazards, fuzzing views,
  symbolic execution, vulnerability diagrams, source listings, and xrefs.
- Optional adapters for Capstone, angr, Ghidra exports, and
  debugger trace records.
- Example catalog, stress-render tooling, visual heuristics, and contact-sheet
  generation for presentation-scale QA.
- Dependency-free GitHub Pages site with playable examples, reviewed galleries,
  accessibility accommodations, and pre-deployment link validation.
- Contributor, security, citation, CI, and trusted-release infrastructure.

[Unreleased]: https://github.com/SauceTaster/manim-rev/commits/main
