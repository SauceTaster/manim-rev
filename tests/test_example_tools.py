from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from scripts.qa_examples import analyze_frame
from scripts.render_examples import discover_scenes

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_every_example_scene_has_an_intent_docstring() -> None:
    scenes = discover_scenes(PROJECT_ROOT / "examples")
    assert len(scenes) >= 30
    assert all(scene.intent for scene in scenes)
    assert len({(scene.file, scene.scene) for scene in scenes}) == len(scenes)


def test_frame_qa_detects_content_and_blank_frames(tmp_path: Path) -> None:
    content_path = tmp_path / "content.png"
    content = Image.new("RGB", (160, 90), "#090D16")
    ImageDraw.Draw(content).rectangle((30, 20, 129, 69), fill="#ECF3FF")
    content.save(content_path)
    metrics = analyze_frame(content_path, "final", PROJECT_ROOT)
    assert metrics.min_margin_px == 20
    assert metrics.contrast_p20 > 100
    assert "blank frame" not in metrics.warnings

    blank_path = tmp_path / "blank.png"
    Image.new("RGB", (160, 90), "#090D16").save(blank_path)
    blank = analyze_frame(blank_path, "final", PROJECT_ROOT)
    assert "blank frame" in blank.warnings
