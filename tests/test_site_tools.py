from __future__ import annotations

from pathlib import Path

from scripts.check_site import validate_site


def _write_minimal_site(root: Path) -> None:
    (root / "styles.css").write_text("body { color: #fff; }", encoding="utf-8")
    (root / "clip.mp4").write_bytes(b"video")
    (root / "image.png").write_bytes(b"image")
    (root / "examples.html").write_text(
        """<!doctype html>
<html lang="en"><head><meta name="viewport" content="width=device-width">
<title>Examples</title></head><body><h1 id="gallery">Gallery</h1></body></html>
""",
        encoding="utf-8",
    )
    (root / "index.html").write_text(
        """<!doctype html>
<html lang="en"><head><meta name="viewport" content="width=device-width">
<title>Home</title><link rel="stylesheet" href="styles.css"></head><body>
<a href="examples.html#gallery">Examples</a>
<img src="image.png" alt="Example frame">
<video controls poster="image.png"><source src="clip.mp4" type="video/mp4"></video>
</body></html>
""",
        encoding="utf-8",
    )


def test_validate_site_accepts_complete_relative_site(tmp_path: Path) -> None:
    _write_minimal_site(tmp_path)

    assert validate_site(tmp_path) == []


def test_validate_site_reports_missing_assets_and_fragments(tmp_path: Path) -> None:
    _write_minimal_site(tmp_path)
    (tmp_path / "index.html").write_text(
        (tmp_path / "index.html")
        .read_text(encoding="utf-8")
        .replace("image.png", "missing.png", 1)
        .replace("#gallery", "#absent"),
        encoding="utf-8",
    )

    errors = validate_site(tmp_path)

    assert any("missing local target 'missing.png'" in error for error in errors)
    assert any("missing fragment #absent" in error for error in errors)


def test_validate_site_rejects_project_root_links_and_inaccessible_media(
    tmp_path: Path,
) -> None:
    _write_minimal_site(tmp_path)
    (tmp_path / "index.html").write_text(
        (tmp_path / "index.html")
        .read_text(encoding="utf-8")
        .replace("examples.html#gallery", "/examples.html")
        .replace("<video controls", "<video"),
        encoding="utf-8",
    )

    errors = validate_site(tmp_path)

    assert any("root-relative links break" in error for error in errors)
    assert any("video must expose native controls" in error for error in errors)
