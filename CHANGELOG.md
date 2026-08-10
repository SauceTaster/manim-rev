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

### Changed

- Reworked basic blocks as flat, square-edged instruction diagrams with shared
  columns, fitted headers, and non-destructive outline focus animations.
- Replaced shortest-path CFG layering with deterministic longest-forward-path
  ranks so merge blocks remain below every incoming branch.
- Added distributed edge ports, side-to-side manual routes, outside loop lanes,
  backed labels, and neutral fallthrough/unconditional edges for clearer dense
  graphs.
- Preserved complete instruction addresses by default and added opt-in,
  ellipsis-marked compact numeric addresses for deliberately small talk blocks.
- Rejected block widths below `2.25` (`3.10` with instruction bytes) and CFG
  layout gaps below `0.25` instead of accepting geometry that can overflow or
  collapse an edge.
- Aligned the default themes, scene titles, examples, contact sheets, and GitHub
  Pages site with Manim Community's black/white/gray visual language and core
  blue, green, yellow, and red accents.

[Unreleased]: https://github.com/SauceTaster/manim-rev/commits/main
