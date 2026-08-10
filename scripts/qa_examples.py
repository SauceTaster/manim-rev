#!/usr/bin/env python3
"""Extract representative frames and run visual heuristics over example renders.

The heuristics deliberately do not claim to replace human review. They flag
blank frames, clipping, weak contrast, extreme density, and missing intent so a
contact-sheet review can focus on likely failures.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


@dataclass(frozen=True, slots=True)
class FrameMetrics:
    label: str
    path: str
    width: int
    height: int
    background: tuple[int, int, int]
    active_fraction: float
    min_margin_px: int
    edge_fraction: float
    contrast_p20: float
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SceneQA:
    file: str
    scene: str
    intent: str
    output: str
    frames: tuple[FrameMetrics, ...]
    warnings: tuple[str, ...]


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr}"
        )
    return completed.stdout.strip()


def _duration(path: Path) -> float:
    output = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(output)


def _extract_video_frames(video: Path, destination: Path, scene: str) -> dict[str, Path]:
    duration = _duration(video)
    points = {
        "early": min(max(duration * 0.18, 0.05), max(0.05, duration - 0.05)),
        "middle": min(max(duration * 0.55, 0.05), max(0.05, duration - 0.05)),
        "final": max(0.0, duration - 0.08),
    }
    frames: dict[str, Path] = {}
    for label, seconds in points.items():
        output = destination / f"{scene}__{label}.png"
        _run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-ss",
                f"{seconds:.4f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-y",
                str(output),
            ]
        )
        frames[label] = output
    return frames


def _background_color(rgb: np.ndarray) -> np.ndarray:
    height, width, _ = rgb.shape
    patch = max(4, min(width, height) // 40)
    corners = np.concatenate(
        (
            rgb[:patch, :patch].reshape(-1, 3),
            rgb[:patch, -patch:].reshape(-1, 3),
            rgb[-patch:, :patch].reshape(-1, 3),
            rgb[-patch:, -patch:].reshape(-1, 3),
        )
    )
    return np.median(corners, axis=0)


def analyze_frame(path: Path, label: str, project_root: Path) -> FrameMetrics:
    image = Image.open(path).convert("RGB")
    rgb = np.asarray(image, dtype=np.float32)
    height, width, _ = rgb.shape
    background = _background_color(rgb)
    distance = np.linalg.norm(rgb - background, axis=2)
    active = distance >= 18
    active_count = int(active.sum())
    active_fraction = active_count / (width * height)
    warnings: list[str] = []
    if active_count == 0:
        min_margin = min(width, height)
        edge_fraction = 0.0
        contrast_p20 = 0.0
        warnings.append("blank frame")
    else:
        ys, xs = np.nonzero(active)
        min_margin = int(min(xs.min(), ys.min(), width - 1 - xs.max(), height - 1 - ys.max()))
        border = max(2, round(min(width, height) * 0.01))
        edge_mask = np.zeros_like(active)
        edge_mask[:border, :] = True
        edge_mask[-border:, :] = True
        edge_mask[:, :border] = True
        edge_mask[:, -border:] = True
        edge_fraction = float((active & edge_mask).sum() / active_count)
        luminance = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
        background_luminance = float(
            background[0] * 0.2126 + background[1] * 0.7152 + background[2] * 0.0722
        )
        # Panel fills are intentionally close to the background and should not
        # be mistaken for low-contrast text. Measure the more salient pixels.
        salient = distance >= 35
        contrast_p20 = (
            float(np.percentile(np.abs(luminance[salient] - background_luminance), 20))
            if salient.any()
            else 0.0
        )
        if min_margin <= 2 or edge_fraction > 0.002:
            warnings.append("content touches the frame edge")
        if contrast_p20 < 16:
            warnings.append("salient foreground contrast is weak")
        # Filled panels are active pixels too, so only flag layouts that occupy
        # nearly the entire frame. Human review still judges text density.
        if active_fraction > 0.68:
            warnings.append("frame is visually dense")
        if active_fraction < 0.008:
            warnings.append("frame may be too sparse")
    relative_path = path.relative_to(project_root) if path.is_relative_to(project_root) else path
    return FrameMetrics(
        label=label,
        path=str(relative_path),
        width=width,
        height=height,
        background=tuple(round(value) for value in background),
        active_fraction=round(active_fraction, 4),
        min_margin_px=min_margin,
        edge_fraction=round(edge_fraction, 5),
        contrast_p20=round(contrast_p20, 2),
        warnings=tuple(warnings),
    )


def _category(file: str) -> str:
    path = Path(file)
    if len(path.parts) >= 3 and path.parts[0] == "examples":
        return path.parts[1]
    return "core"


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def make_contact_sheets(
    scenes: list[SceneQA],
    *,
    project_root: Path,
    output_dir: Path,
    columns: int = 3,
) -> list[Path]:
    grouped: defaultdict[str, list[SceneQA]] = defaultdict(list)
    for scene in scenes:
        grouped[_category(scene.file)].append(scene)
    output_paths: list[Path] = []
    thumb_size = (427, 240)
    caption_height = 38
    gutter = 12
    for category, items in sorted(grouped.items()):
        items.sort(key=lambda item: (item.file, item.scene))
        rows = math.ceil(len(items) / columns)
        sheet = Image.new(
            "RGB",
            (
                gutter + columns * (thumb_size[0] + gutter),
                gutter + rows * (thumb_size[1] + caption_height + gutter),
            ),
            "#000000",
        )
        draw = ImageDraw.Draw(sheet)
        for index, scene in enumerate(items):
            row, column = divmod(index, columns)
            x = gutter + column * (thumb_size[0] + gutter)
            y = gutter + row * (thumb_size[1] + caption_height + gutter)
            final = next(frame for frame in scene.frames if frame.label == "final")
            frame = Image.open(project_root / final.path).convert("RGB")
            thumbnail = ImageOps.fit(frame, thumb_size, method=Image.Resampling.LANCZOS)
            sheet.paste(thumbnail, (x, y))
            caption = scene.scene
            if scene.warnings:
                caption += "  [review]"
            draw.text((x + 3, y + thumb_size[1] + 7), caption, fill="#FFFFFF", font=_font(15))
        output = output_dir / f"{category}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output)
        output_paths.append(output)
    return output_paths


def make_timeline_sheets(
    scenes: list[SceneQA],
    *,
    project_root: Path,
    output_dir: Path,
) -> list[Path]:
    """Create early/middle/final strips for reviewing animation continuity."""

    grouped: defaultdict[str, list[SceneQA]] = defaultdict(list)
    for scene in scenes:
        grouped[_category(scene.file)].append(scene)
    output_paths: list[Path] = []
    thumb_size = (320, 180)
    caption_height = 34
    gutter = 10
    labels = ("early", "middle", "final")
    for category, items in sorted(grouped.items()):
        items.sort(key=lambda item: (item.file, item.scene))
        sheet = Image.new(
            "RGB",
            (
                gutter + len(labels) * (thumb_size[0] + gutter),
                gutter + len(items) * (thumb_size[1] + caption_height + gutter),
            ),
            "#000000",
        )
        draw = ImageDraw.Draw(sheet)
        for row, scene in enumerate(items):
            y = gutter + row * (thumb_size[1] + caption_height + gutter)
            by_label = {frame.label: frame for frame in scene.frames}
            for column, label in enumerate(labels):
                frame_metrics = by_label.get(label) or by_label["final"]
                x = gutter + column * (thumb_size[0] + gutter)
                frame = Image.open(project_root / frame_metrics.path).convert("RGB")
                thumbnail = ImageOps.fit(frame, thumb_size, method=Image.Resampling.LANCZOS)
                sheet.paste(thumbnail, (x, y))
                draw.text((x + 5, y + 5), label, fill="#FFFFFF", font=_font(12))
            caption = scene.scene
            if scene.warnings:
                caption += "  [review]"
            draw.text(
                (gutter + 3, y + thumb_size[1] + 6),
                caption,
                fill="#FFFFFF",
                font=_font(14),
            )
        output = output_dir / f"{category}-timeline.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output)
        output_paths.append(output)
    return output_paths


def _write_markdown(
    scenes: list[SceneQA],
    sheets: list[Path],
    *,
    project_root: Path,
    output: Path,
) -> None:
    warning_count = sum(bool(scene.warnings) for scene in scenes)
    lines = [
        "# Example render QA",
        "",
        f"- Scenes reviewed: **{len(scenes)}**",
        f"- Scenes with heuristic warnings: **{warning_count}**",
        "- Frames sampled per video: **early, middle, final**; still renders use **final**",
        "",
        "Heuristic warnings are review prompts, not automatic failures. Human review must confirm",
        "content accuracy, legibility, narrative intent, and animation continuity.",
        "",
        "## Contact sheets",
        "",
    ]
    for sheet in sheets:
        relative = sheet.relative_to(project_root) if sheet.is_relative_to(project_root) else sheet
        lines.append(f"- `{relative}`")
    lines.extend(
        [
            "",
            "## Scene results",
            "",
            "| Scene | Intent | Active area (final) | Margin | Contrast p20 | Review |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for scene in scenes:
        final = next(frame for frame in scene.frames if frame.label == "final")
        review = "; ".join(scene.warnings) if scene.warnings else "pass"
        intent = scene.intent.replace("|", "\\|") or "**missing**"
        lines.append(
            f"| `{scene.scene}` | {intent} | {final.active_fraction:.1%} | "
            f"{final.min_margin_px}px | {final.contrast_p20:.1f} | {review} |"
        )
    lines.extend(
        [
            "",
            "## Human review checklist",
            "",
            "- [ ] The scene communicates the intent in its class docstring.",
            "- [ ] Addresses, instructions, flags, constraints, and vulnerability facts are coherent.",
            "- [ ] Text is readable at 480p and remains readable when projected at 1080p.",
            "- [ ] No panel, label, arrow, or animated target clips or overlaps unexpectedly.",
            "- [ ] Early and middle frames preserve narrative continuity, not only the final frame.",
            "- [ ] Color is reinforced with labels, symbols, or shape; meaning is not color-only.",
            "- [ ] Animation endpoints retain updated values after transforms finish.",
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-report", type=Path, default=Path("build/qa/render-report.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/qa"))
    parser.add_argument("--strict", action="store_true", help="fail on heuristic warnings")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[1]
    report_path = (project_root / args.render_report).resolve()
    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    output_dir = (project_root / args.output_dir).resolve()
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    scenes: list[SceneQA] = []
    for result in payload["results"]:
        if result["status"] not in {"passed", "skipped"} or not result["output"]:
            continue
        source = Path(result["output"])
        source = source if source.is_absolute() else project_root / source
        scene_frame_dir = frame_dir / f"{_category(result['file'])}__{result['scene']}"
        scene_frame_dir.mkdir(parents=True, exist_ok=True)
        if source.suffix.casefold() == ".png":
            target = scene_frame_dir / f"{result['scene']}__final.png"
            Image.open(source).save(target)
            extracted = {"final": target}
        else:
            extracted = _extract_video_frames(source, scene_frame_dir, result["scene"])
        frames = tuple(
            analyze_frame(path, label, project_root) for label, path in extracted.items()
        )
        warnings = sorted(
            {warning for frame in frames for warning in frame.warnings}
            | ({"missing narrative intent docstring"} if not result["intent"] else set())
        )
        scenes.append(
            SceneQA(
                file=result["file"],
                scene=result["scene"],
                intent=result["intent"],
                output=result["output"],
                frames=frames,
                warnings=tuple(warnings),
            )
        )
    scenes.sort(key=lambda item: (item.file, item.scene))
    sheets = make_contact_sheets(
        scenes,
        project_root=project_root,
        output_dir=output_dir / "contact-sheets",
    )
    sheets.extend(
        make_timeline_sheets(
            scenes,
            project_root=project_root,
            output_dir=output_dir / "contact-sheets",
        )
    )
    qa_json = output_dir / "qa-report.json"
    qa_json.write_text(
        json.dumps(
            {
                "scene_count": len(scenes),
                "warning_count": sum(bool(scene.warnings) for scene in scenes),
                "scenes": [asdict(scene) for scene in scenes],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_markdown(
        scenes,
        sheets,
        project_root=project_root,
        output=output_dir / "qa-report.md",
    )
    warning_count = sum(bool(scene.warnings) for scene in scenes)
    print(f"Analyzed {len(scenes)} scenes; {warning_count} have heuristic review prompts")
    for sheet in sheets:
        print(f"Contact sheet: {sheet.relative_to(project_root)}")
    print(f"Report: {qa_json.relative_to(project_root)}")
    return 1 if args.strict and warning_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
