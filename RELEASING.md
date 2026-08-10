# Releasing Manim Rev

This checklist is for project maintainers. The canonical repository is
<https://github.com/SauceTaster/manim-rev>, and its public documentation is at
<https://saucetaster.github.io/manim-rev/>. The release workflow is designed to
build artifacts once in GitHub Actions, publish them to PyPI with short-lived
OpenID Connect credentials, and attach the same artifacts to a GitHub release.

## One-time repository setup

Before the first release:

1. Confirm that the canonical repository is public and that the URLs in
   `pyproject.toml`, `CITATION.cff`, `README.md`, and `CHANGELOG.md` resolve.
2. Reserve or create the `manim-rev` project on PyPI.
3. Add a PyPI Trusted Publisher for the repository, workflow
   `.github/workflows/release.yml`, and environment `pypi`.
4. Create the GitHub `pypi` environment. Require maintainer approval and limit
   deployments to protected `v*` tags.
5. Protect the default branch and `v*` tags. Require the CI checks and review
   changes to `.github/workflows/release.yml` carefully.
6. Enable GitHub private vulnerability reporting so `SECURITY.md` has a fully
   confidential intake path.
7. Enable the repository's GitHub Pages deployment and confirm the published
   gallery at <https://saucetaster.github.io/manim-rev/>.

The release workflow intentionally contains no long-lived PyPI token.

## Prepare a release

1. Choose a Semantic Versioning number.
2. Update `project.version` in `pyproject.toml`, the source-tree fallback in
   `src/manim_rev/__init__.py`, and `version` in `CITATION.cff`.
3. Add `date-released` to `CITATION.cff` using the intended release date.
4. Move the relevant changelog entries from `Unreleased` to a dated version
   heading, add a link to the matching GitHub tag, and leave a new empty
   `Unreleased` section.
5. Update the README and Pages status/installation text so both describe the
   release being made; do not claim PyPI availability before publication
   succeeds. Run `uv run python scripts/check_site.py site` after changing the
   site copy.
6. Run `uv lock` if dependency metadata changed.
7. Run the complete verification suite:

   ```bash
   uv sync --frozen --extra dev
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy
   uv run pytest --cov=manim_rev --cov-report=term-missing
   uv run python scripts/render_examples.py --list
   uv run python scripts/render_examples.py --jobs 2
   uv run python scripts/qa_examples.py
   uv run python scripts/check_site.py site
   uv run python scripts/sync_visual_assets.py --check
   uv build
   uvx --from twine==6.2.0 twine check --strict dist/*
   ```

8. Review the generated QA report and contact sheets. Resolve warnings or
   record why each remaining warning is an acceptable false positive. After
   approval, run `uv run python scripts/sync_visual_assets.py`, then repeat it
   with `--check` to confirm the retained docs and Pages assets are current.
9. Merge the release preparation through the protected default branch.

## Publish

Create and push an annotated tag that exactly matches the package version:

```bash
git tag -a v0.1.0 -m "Manim Rev 0.1.0"
git push origin v0.1.0
```

`.github/workflows/release.yml` rejects a tag that does not match
`project.version`. After environment approval it publishes to PyPI and creates
the GitHub release with the exact wheel and source archive that were checked.

Afterward, verify installation in a clean environment, confirm the PyPI
provenance information, test `manim plugins -l`, check the GitHub Pages site,
and only then announce the release or change the README to say that PyPI is
available.
