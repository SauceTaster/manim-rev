#!/usr/bin/env python3
"""Discover and render every example Scene with isolated Manim media caches.

The isolation is important: Manim's text cache uses temporary SVG filenames,
so independent media directories make parallel stress renders deterministic.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

SCENE_BASES = {"Scene", "RevScene", "MovingCameraScene", "ThreeDScene", "ZoomedScene"}


@dataclass(frozen=True, slots=True)
class SceneSpec:
    file: str
    scene: str
    intent: str
    line: int


@dataclass(frozen=True, slots=True)
class RenderResult:
    file: str
    scene: str
    intent: str
    status: str
    seconds: float
    output: str | None
    log: str


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def discover_scenes(examples_dir: Path) -> list[SceneSpec]:
    """Return direct Manim Scene subclasses found below ``examples_dir``."""

    scenes: list[SceneSpec] = []
    for path in sorted(examples_dir.rglob("*.py")):
        if "__pycache__" in path.parts or path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(_base_name(base) in SCENE_BASES for base in node.bases):
                continue
            docstring = ast.get_docstring(node, clean=True) or ""
            intent = docstring.splitlines()[0].strip() if docstring else ""
            scenes.append(
                SceneSpec(
                    file=str(path),
                    scene=node.name,
                    intent=intent,
                    line=node.lineno,
                )
            )
    return scenes


def _safe_slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")


def _find_output(media_dir: Path, scene: str, extension: str) -> Path | None:
    candidates = list(media_dir.rglob(f"*{scene}*.{extension}"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _render_one(
    spec: SceneSpec,
    *,
    project_root: Path,
    media_root: Path,
    log_root: Path,
    quality: str,
    save_last_frame: bool,
    timeout: int,
    skip_existing: bool,
) -> RenderResult:
    relative = Path(spec.file).resolve().relative_to(project_root)
    task_slug = f"{_safe_slug(str(relative.with_suffix('')))}__{spec.scene}"
    media_dir = media_root / task_slug
    extension = "png" if save_last_frame else "mp4"
    existing = _find_output(media_dir, spec.scene, extension)
    if skip_existing and existing is not None:
        return RenderResult(
            file=str(relative),
            scene=spec.scene,
            intent=spec.intent,
            status="skipped",
            seconds=0,
            output=str(existing.relative_to(project_root))
            if existing.is_relative_to(project_root)
            else str(existing),
            log="",
        )

    media_dir.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"{task_slug}.log"
    executable = shutil.which("manim")
    command = [executable] if executable else [sys.executable, "-m", "manim"]
    command.extend(
        [
            "render",
            f"-q{quality}",
            "--disable_caching",
            "--progress_bar",
            "none",
            "--verbosity",
            "warning",
            "--media_dir",
            str(media_dir),
        ]
    )
    if save_last_frame:
        command.append("--save_last_frame")
    command.extend([str(relative), spec.scene])

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        log_path.write_text(completed.stdout, encoding="utf-8")
        output = _find_output(media_dir, spec.scene, extension)
        status = "passed" if completed.returncode == 0 and output is not None else "failed"
    except subprocess.TimeoutExpired as error:
        captured = error.stdout or ""
        if isinstance(captured, bytes):
            captured = captured.decode(errors="replace")
        log_path.write_text(f"TIMEOUT after {timeout}s\n{captured}", encoding="utf-8")
        output = None
        status = "timeout"
    elapsed = time.monotonic() - started
    return RenderResult(
        file=str(relative),
        scene=spec.scene,
        intent=spec.intent,
        status=status,
        seconds=round(elapsed, 3),
        output=(
            str(output.relative_to(project_root))
            if output is not None and output.is_relative_to(project_root)
            else str(output)
            if output is not None
            else None
        ),
        log=str(log_path.relative_to(project_root)),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples-dir", type=Path, default=Path("examples"))
    parser.add_argument("--media-dir", type=Path, default=Path("build/example-renders"))
    parser.add_argument("--report", type=Path, default=Path("build/qa/render-report.json"))
    parser.add_argument("--logs", type=Path, default=Path("build/qa/logs"))
    parser.add_argument("--quality", choices=("l", "m", "h", "p", "k"), default="l")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--match", action="append", default=[], help="substring filter")
    parser.add_argument("--save-last-frame", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--list", action="store_true", help="list scenes without rendering")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[1]
    examples_dir = (project_root / args.examples_dir).resolve()
    scenes = discover_scenes(examples_dir)
    if args.match:
        needles = [value.casefold() for value in args.match]
        scenes = [
            scene
            for scene in scenes
            if any(
                needle in f"{scene.file}::{scene.scene} {scene.intent}".casefold()
                for needle in needles
            )
        ]
    if not scenes:
        print("No matching scenes found.", file=sys.stderr)
        return 2
    missing_intent = [scene for scene in scenes if not scene.intent]
    for scene in scenes:
        marker = " ! missing class docstring" if not scene.intent else ""
        print(f"{Path(scene.file).relative_to(project_root)}::{scene.scene}{marker}")
    if args.list:
        return 1 if missing_intent else 0
    if args.jobs < 1:
        print("--jobs must be at least 1", file=sys.stderr)
        return 2

    kwargs = {
        "project_root": project_root,
        "media_root": (project_root / args.media_dir).resolve(),
        "log_root": (project_root / args.logs).resolve(),
        "quality": args.quality,
        "save_last_frame": args.save_last_frame,
        "timeout": args.timeout,
        "skip_existing": args.skip_existing,
    }
    results: list[RenderResult] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(_render_one, scene, **kwargs): scene for scene in scenes}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"[{result.status:7}] {result.scene:38} {result.seconds:7.2f}s")
    results.sort(key=lambda result: (result.file, result.scene))
    report_path = (project_root / args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "generated_at_epoch": int(time.time()),
                "quality": args.quality,
                "save_last_frame": args.save_last_frame,
                "scene_count": len(results),
                "results": [asdict(result) for result in results],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    failures = [result for result in results if result.status not in {"passed", "skipped"}]
    print(f"\n{len(results) - len(failures)}/{len(results)} scenes rendered successfully")
    print(f"Report: {report_path.relative_to(project_root)}")
    return 1 if failures or missing_intent else 0


if __name__ == "__main__":
    raise SystemExit(main())
