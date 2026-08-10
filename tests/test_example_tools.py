from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw
from scripts.qa_examples import analyze_frame
from scripts.render_examples import discover_scenes
from scripts.sync_visual_assets import CATEGORIES, DEMO_SCENES, sync_visual_assets

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_every_example_scene_has_an_intent_docstring() -> None:
    scenes = discover_scenes(PROJECT_ROOT / "examples")
    assert len(scenes) >= 30
    assert all(scene.intent for scene in scenes)
    assert len({(scene.file, scene.scene) for scene in scenes}) == len(scenes)


def test_frame_qa_detects_content_and_blank_frames(tmp_path: Path) -> None:
    content_path = tmp_path / "content.png"
    content = Image.new("RGB", (160, 90), "#000000")
    ImageDraw.Draw(content).rectangle((30, 20, 129, 69), fill="#FFFFFF")
    content.save(content_path)
    metrics = analyze_frame(content_path, "final", PROJECT_ROOT)
    assert metrics.min_margin_px == 20
    assert metrics.contrast_p20 > 100
    assert "blank frame" not in metrics.warnings

    blank_path = tmp_path / "blank.png"
    Image.new("RGB", (160, 90), "#000000").save(blank_path)
    blank = analyze_frame(blank_path, "final", PROJECT_ROOT)
    assert "blank frame" in blank.warnings


def test_visual_asset_sync_copies_and_checks_reviewed_outputs(tmp_path: Path) -> None:
    sheet_dir = tmp_path / "build/qa/contact-sheets"
    sheet_dir.mkdir(parents=True)
    for category in CATEGORIES:
        for suffix in ("", "-timeline"):
            (sheet_dir / f"{category}{suffix}.png").write_bytes(f"{category}{suffix}".encode())

    results = []
    for scene in DEMO_SCENES:
        output = Path("build/example-renders") / f"{scene}.mp4"
        rendered = tmp_path / output
        rendered.parent.mkdir(parents=True, exist_ok=True)
        rendered.write_bytes(scene.encode())
        results.append(
            {
                "scene": scene,
                "status": "passed",
                "output": str(output),
            }
        )
    (tmp_path / "build/qa/render-report.json").write_text(
        json.dumps({"results": results}),
        encoding="utf-8",
    )

    changed = sync_visual_assets(tmp_path)

    assert len(changed) == 22
    assert sync_visual_assets(tmp_path, check=True) == ()
    stale = tmp_path / "site/assets/core.png"
    stale.write_bytes(b"stale")
    assert sync_visual_assets(tmp_path, check=True) == (stale,)
