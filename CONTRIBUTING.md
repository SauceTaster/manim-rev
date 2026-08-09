# Contributing to Manim Rev

Thank you for helping make reverse-engineering visuals clearer and more
accurate. Contributions can include components, adapters, tests, examples,
documentation, accessibility improvements, and visual QA reports.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Report suspected vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not through a public issue.

## Development setup

Manim Rev requires Python 3.11 or newer, and CI targets Python 3.11–3.14.
Install [uv](https://docs.astral.sh/uv/), then create the locked development
environment:

```bash
uv sync --extra dev
```

On Linux, Manim may need a compiler, Python headers, `pkg-config`, Pango, and
Cairo development headers. Follow the current
[Manim installation guide](https://docs.manim.community/en/stable/installation/linux.html)
for your platform.

Run the fast checks before making changes:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Making a change

- Keep public objects composable Manim mobjects or ordinary animation helpers.
- Preserve deterministic layouts and avoid new required external tools when a
  Python or Manim implementation is practical.
- Expose semantic lookups instead of relying on submobject indexes.
- Validate malformed public input with an actionable exception.
- Add or update tests for behavior changes and regressions.
- Document public API changes and add an entry under `Unreleased` in
  `CHANGELOG.md`.
- Keep optional integrations behind their corresponding extras. Core imports
  must continue to work without angr or Capstone installed.

The package is alpha, but compatibility still matters. If a change must break
an existing public API, explain the reason and migration path in the pull
request and changelog.

## Examples and visual QA

Examples are both documentation and stress tests. A new public component or a
meaningful visual behavior should normally have a focused scene. Use synthetic
or redistributable data; do not commit proprietary binaries, credentials,
personal data, or unexplained weaponized exploit material.

Every example scene must have a class docstring whose first line states its
teaching intent. Confirm the catalog is discoverable:

```bash
uv run python scripts/render_examples.py --list
```

For a focused iteration, render a matching scene to an isolated output folder:

```bash
uv run python scripts/render_examples.py \
  --match Pipeline \
  --save-last-frame
```

For a full review, render the catalog and create the QA report and contact
sheets:

```bash
uv run python scripts/render_examples.py --jobs 2
uv run python scripts/qa_examples.py
```

Automated heuristics only flag likely problems. Review representative early,
middle, and final frames and verify:

- the scene teaches what its docstring claims;
- addresses, opcodes, flags, control-flow edges, and labels are technically
  consistent;
- text is legible at the target resolution and does not overlap or clip;
- colors have sufficient contrast and are not the only carrier of meaning;
- highlights and camera movement preserve the viewer's context;
- the animation ends on a useful frame and does not leave temporary artifacts;
- common 16:9 presentation output remains inside the safe area.

Attach representative frames or a short render to pull requests that change
layout, color, animation, or example content. State which scenes and render
quality you reviewed.

## Tests and packaging

Run the relevant focused tests while iterating, then the complete suite:

```bash
uv run pytest tests/test_memory.py
uv run pytest --cov=manim_rev --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
uvx --from twine==6.2.0 twine check --strict dist/*
```

Do not hand-edit `uv.lock`. When dependency metadata changes, run `uv lock` and
include the resulting lockfile update.

## Pull requests

Keep a pull request focused enough to review. In its description, explain the
user-visible outcome, the reason for the design, verification performed, and
any compatibility impact. Draft pull requests are welcome for early design
feedback.

Maintainers may ask for changes when a visual is accurate in code but unclear
at presentation scale. That is part of the acceptance criteria for this
project, not merely cosmetic polish.

## Licensing contributions

By submitting a contribution, you agree that it is licensed under this
repository's [MIT License](LICENSE). You must have the right to submit every
included code, image, recording, dataset, and other asset. Do not contribute
material whose license or provenance is unclear.

Maintainer release steps are documented in [RELEASING.md](RELEASING.md).
