#!/usr/bin/env python3
"""Sync reviewed QA sheets and demo renders into the public documentation."""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
from pathlib import Path
from typing import Any

CATEGORIES = ("analysis", "core", "security", "stress")
DEMO_SCENES = {
    "ReverseEngineeringShowcase": "reverse-engineering.mp4",
    "DebuggerMemoryWalkthrough": "debugger-memory.mp4",
    "PipelineBranchMispredictSquash": "pipeline-mispredict.mp4",
    "FuzzCoverageGrowthCampaign": "fuzzing-campaign.mp4",
    "SymbolicForkConstraintWalkthrough": "symbolic-fork.mp4",
    "StackOverwriteControlFlow": "stack-overflow.mp4",
}


def _render_outputs(project_root: Path, report: Path) -> dict[str, Path]:
    payload: dict[str, Any] = json.loads(report.read_text(encoding="utf-8"))
    outputs: dict[str, Path] = {}
    for result in payload.get("results", []):
        scene = result.get("scene")
        output = result.get("output")
        if scene not in DEMO_SCENES or result.get("status") not in {"passed", "skipped"}:
            continue
        if not isinstance(output, str) or not output:
            continue
        if scene in outputs:
            raise ValueError(f"render report contains duplicate scene {scene!r}")
        path = Path(output)
        outputs[scene] = path if path.is_absolute() else project_root / path
    missing = set(DEMO_SCENES).difference(outputs)
    if missing:
        formatted = ", ".join(sorted(missing))
        raise ValueError(f"render report is missing public demo scene(s): {formatted}")
    return outputs


def asset_pairs(project_root: Path) -> tuple[tuple[Path, Path], ...]:
    """Return every generated source and retained public destination pair."""

    sheet_dir = project_root / "build/qa/contact-sheets"
    pairs: list[tuple[Path, Path]] = []
    for category in CATEGORIES:
        for suffix in ("", "-timeline"):
            source = sheet_dir / f"{category}{suffix}.png"
            pairs.extend(
                (
                    (source, project_root / f"docs/assets/visual-qa/{source.name}"),
                    (source, project_root / f"site/assets/{source.name}"),
                )
            )

    report = project_root / "build/qa/render-report.json"
    for scene, output in _render_outputs(project_root, report).items():
        pairs.append((output, project_root / f"site/assets/demos/{DEMO_SCENES[scene]}"))
    return tuple(pairs)


def sync_visual_assets(project_root: Path, *, check: bool = False) -> tuple[Path, ...]:
    """Copy generated assets, or report destinations that are not synchronized."""

    changed: list[Path] = []
    for source, destination in asset_pairs(project_root):
        if not source.is_file():
            raise FileNotFoundError(f"generated visual asset does not exist: {source}")
        matches = destination.is_file() and filecmp.cmp(source, destination, shallow=False)
        if matches:
            continue
        changed.append(destination)
        if not check:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    return tuple(changed)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if retained assets differ instead of updating them",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[1]
    changed = sync_visual_assets(project_root, check=args.check)
    if args.check and changed:
        for path in changed:
            print(f"out of date: {path.relative_to(project_root)}")
        return 1
    action = "updated" if changed else "already current"
    print(f"Visual assets {action}: {len(changed)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
