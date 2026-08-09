from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from manim import tempconfig


@pytest.fixture(scope="session", autouse=True)
def isolated_manim_media(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Keep Manim text-cache files isolated across concurrent test processes."""

    media_dir: Path = tmp_path_factory.mktemp("manim_media")
    with tempconfig({"media_dir": str(media_dir)}):
        yield
