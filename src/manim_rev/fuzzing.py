"""Coverage, fuzzing-progress, and crash visualizations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Animation,
    AnimationGroup,
    Circumscribe,
    FadeIn,
    Indicate,
    Mobject,
    RoundedRectangle,
    Succession,
    Transform,
    VGroup,
)

from .models import Address, format_address
from .primitives import KeyValueRow, Panel, label_text, mono_text
from .refs import AddressRangeRef, AddressRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme

__all__ = ["CoverageBitmap", "CoverageMap", "CrashCard", "FuzzingDashboard", "HitValues"]

HitValues = Sequence[int | bool] | Mapping[int, int | bool]


def _match_width(target: Mobject, current: Mobject) -> Mobject:
    target.scale_to_fit_width(current.width)
    return target.move_to(current)


def _match_text(target: Mobject, current: Mobject, *, align_right: bool = False) -> Mobject:
    if target.height > 0 and current.height > 0:
        target.scale_to_fit_height(current.height)
    if align_right:
        return target.move_to(current, aligned_edge=RIGHT)
    return target.move_to(current)


def _normalize_hits(values: HitValues, *, size: int | None = None) -> list[int]:
    if isinstance(values, Mapping):
        if not values and size is None:
            raise ValueError("a coverage bitmap requires at least one cell")
        for index in values:
            if not isinstance(index, int) or index < 0:
                raise ValueError("coverage-map indices must be non-negative integers")
        inferred_size = max(values, default=-1) + 1
        target_size = inferred_size if size is None else size
        if inferred_size > target_size:
            raise ValueError("coverage update is larger than the existing bitmap")
        normalized = [0] * target_size
        for index, value in values.items():
            normalized[index] = int(value)
    else:
        normalized = [int(value) for value in values]
        if size is not None and len(normalized) != size:
            raise ValueError("coverage updates must preserve the bitmap size")

    if not normalized:
        raise ValueError("a coverage bitmap requires at least one cell")
    if any(value < 0 for value in normalized):
        raise ValueError("coverage hit counts cannot be negative")
    return normalized


class CoverageBitmap(Panel):
    """A fixed-size edge/block coverage bitmap with addressable cells."""

    def __init__(
        self,
        hits: HitValues,
        *,
        columns: int = 16,
        cell_size: float = 0.27,
        show_counts: bool = False,
        base_address: int | None = None,
        addresses: Sequence[int] | None = None,
        title: str = "coverage bitmap",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if columns < 1:
            raise ValueError("coverage bitmap columns must be positive")
        if cell_size <= 0:
            raise ValueError("coverage bitmap cell size must be positive")
        self._hits = _normalize_hits(hits)
        if base_address is not None and addresses is not None:
            raise ValueError("use either base_address or explicit addresses, not both")
        if base_address is not None and base_address < 0:
            raise ValueError("coverage base_address must be non-negative")
        if addresses is not None:
            normalized_addresses = tuple(addresses)
            if len(normalized_addresses) != len(self._hits):
                raise ValueError("explicit coverage addresses must match the bitmap size")
            if any(address < 0 for address in normalized_addresses):
                raise ValueError("explicit coverage addresses must be non-negative")
            if len(normalized_addresses) != len(set(normalized_addresses)):
                raise ValueError("explicit coverage addresses must be unique")
        elif base_address is not None:
            normalized_addresses = tuple(base_address + index for index in range(len(self._hits)))
        else:
            normalized_addresses = ()
        self.columns = columns
        self.cell_size = cell_size
        self.show_counts = show_counts
        self.base_address = base_address
        self.addresses = normalized_addresses
        rows = (len(self._hits) + columns - 1) // columns
        displayed_columns = min(columns, len(self._hits))
        width = max(2.5, 0.48 + displayed_columns * cell_size + (displayed_columns - 1) * 0.035)
        height = 1.07 + rows * cell_size + (rows - 1) * 0.035
        super().__init__(width=width, height=height, title=title, theme=theme)

        self.cells: dict[int, VGroup] = {}
        self.cells_group = VGroup()
        for index, count in enumerate(self._hits):
            cell = self._make_cell(index, count)
            self.cells[index] = cell
            self.cells_group.add(cell)
        self.cells_by_address = {
            address: self.cells[index] for index, address in enumerate(self.addresses)
        }
        self.cells_group.arrange_in_grid(
            rows=rows,
            cols=columns,
            buff=0.035,
            flow_order="rd",
        )
        self.coverage_label = self._make_coverage_label()
        content = VGroup(self.cells_group, self.coverage_label).arrange(DOWN, buff=0.13)
        content.move_to(self.background).shift(DOWN * 0.14)
        self.add(content)

    @property
    def hits(self) -> tuple[int, ...]:
        return tuple(self._hits)

    @property
    def covered_count(self) -> int:
        return sum(count > 0 for count in self._hits)

    @property
    def coverage_ratio(self) -> float:
        return self.covered_count / len(self._hits)

    def _cell_style(self, count: int) -> tuple[str, float, str]:
        if count == 0:
            return self.theme.panel_alt, 0.5, self.theme.border
        if count >= 64:
            return self.theme.warning, 0.88, self.theme.warning
        if count >= 8:
            return self.theme.success, 0.76, self.theme.success
        return self.theme.info, 0.62, self.theme.info

    def _make_cell(self, index: int, count: int) -> VGroup:
        fill, opacity, stroke = self._cell_style(count)
        box = RoundedRectangle(
            width=self.cell_size,
            height=self.cell_size,
            corner_radius=min(0.045, self.cell_size / 5),
            stroke_color=stroke,
            stroke_width=0.8,
            fill_color=fill,
            fill_opacity=opacity,
        )
        cell = VGroup(box)
        if self.show_counts:
            value = mono_text(
                count,
                font_size=max(8, self.cell_size * 37),
                color=self.theme.text if count else self.theme.muted,
                theme=self.theme,
            ).move_to(box)
            cell.add(value)
        return cell

    def _make_coverage_label(self):  # type: ignore[no-untyped-def]
        return mono_text(
            f"{self.covered_count}/{len(self._hits)}  {self.coverage_ratio:.1%}",
            font_size=15,
            color=self.theme.success,
            theme=self.theme,
        )

    def cell(self, index: int) -> VGroup:
        """Return a coverage cell by zero-based bitmap index."""

        try:
            return self.cells[index]
        except KeyError as error:
            raise IndexError(f"coverage cell {index} is outside the bitmap") from error

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if not self.addresses:
            return ()
        if isinstance(ref, AddressRef) and isinstance(ref.address, int):
            cell = self.cells_by_address.get(ref.address)
            return (cell,) if cell is not None else ()
        if isinstance(ref, AddressRangeRef):
            range_end = ref.start + ref.length
            return tuple(
                self.cells[index]
                for index, address in enumerate(self.addresses)
                if ref.start <= address < range_end
            )
        return ()

    def set_hit(self, index: int, count: int = 1) -> CoverageBitmap:
        """Replace one hit count immediately and return ``self``."""

        if count < 0:
            raise ValueError("coverage hit counts cannot be negative")
        cell = self.cell(index)
        target = _match_width(self._make_cell(index, count), cell)
        cell.become(target)
        self._hits[index] = count
        self.coverage_label.become(_match_text(self._make_coverage_label(), self.coverage_label))
        return self

    def animate_hit(self, index: int, count: int | None = None) -> Animation:
        """Build an animation that records and emphasizes a newly covered cell."""

        cell = self.cell(index)
        new_count = self._hits[index] + 1 if count is None else count
        if new_count < 0:
            raise ValueError("coverage hit counts cannot be negative")
        self._hits[index] = new_count
        target = _match_width(self._make_cell(index, new_count), cell)
        target_label = _match_text(self._make_coverage_label(), self.coverage_label)
        return AnimationGroup(
            Transform(cell, target),
            Transform(self.coverage_label, target_label),
            Circumscribe(cell, color=self.theme.warning, buff=0.025),
        )

    def animate_update(self, hits: HitValues) -> Animation:
        """Build an animation that replaces the complete bitmap state."""

        normalized = _normalize_hits(hits, size=len(self._hits))
        self._hits[:] = normalized
        animations: list[Animation] = []
        for index, count in enumerate(normalized):
            cell = self.cell(index)
            animations.append(Transform(cell, _match_width(self._make_cell(index, count), cell)))
        animations.append(
            Transform(
                self.coverage_label,
                _match_text(self._make_coverage_label(), self.coverage_label),
            )
        )
        return AnimationGroup(*animations, lag_ratio=0.015)

    def focus(self, target: int | VisualRef) -> Animation:
        """Emphasize one index or an address reference resolved by the bitmap."""

        targets = (self.cell(target),) if isinstance(target, int) else self.resolve(target)
        if not targets:
            raise LookupError(f"coverage bitmap cannot resolve {target!r}")
        return AnimationGroup(
            *(Indicate(cell, color=self.theme.warning, scale_factor=1.15) for cell in targets)
        )


# A shorter, presentation-oriented spelling retained as an equal public API.
CoverageMap = CoverageBitmap


class FuzzingDashboard(Panel):
    """A compact dashboard for the headline statistics of a fuzzing run."""

    _ORDER = ("executions", "execs_per_second", "coverage", "crashes", "corpus_size")

    def __init__(
        self,
        *,
        executions: int = 0,
        execs_per_second: int | float = 0,
        coverage: int | float | str = 0.0,
        crashes: int = 0,
        corpus_size: int = 0,
        title: str = "fuzzing",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        values: dict[str, int | float | str] = {
            "executions": executions,
            "execs_per_second": execs_per_second,
            "coverage": coverage,
            "crashes": crashes,
            "corpus_size": corpus_size,
        }
        for key in ("executions", "execs_per_second", "crashes", "corpus_size"):
            metric_value = values[key]
            if not isinstance(metric_value, (int, float)) or metric_value < 0:
                raise ValueError(f"dashboard metric {key!r} must be non-negative")
        if isinstance(coverage, (int, float)) and coverage < 0:
            raise ValueError("dashboard metric 'coverage' must be non-negative")
        self.metrics = values
        super().__init__(width=4.2, height=2.85, title=title, theme=theme)
        self.rows: dict[str, KeyValueRow] = {}
        rows = VGroup()
        for key in self._ORDER:
            row = KeyValueRow(
                self._metric_label(key),
                self._format_metric(key, values[key]),
                width=3.55,
                font_size=18,
                value_color=self._metric_color(key),
                theme=theme,
            )
            self.rows[key] = row
            rows.add(row)
        rows.arrange(DOWN, buff=0.13, aligned_edge=LEFT)
        rows.move_to(self.background).shift(DOWN * 0.18)
        self.add(rows)

    @staticmethod
    def _metric_label(name: str) -> str:
        return {
            "executions": "EXECS",
            "execs_per_second": "SPEED",
            "coverage": "COVERAGE",
            "crashes": "CRASHES",
            "corpus_size": "CORPUS",
        }[name]

    def _metric_color(self, name: str) -> str:
        return {
            "executions": self.theme.text,
            "execs_per_second": self.theme.info,
            "coverage": self.theme.success,
            "crashes": self.theme.danger,
            "corpus_size": self.theme.opcode,
        }[name]

    @staticmethod
    def _format_metric(name: str, value: int | float | str) -> str:
        if name == "coverage" and isinstance(value, float) and 0 <= value <= 1:
            return f"{value:.1%}"
        if name == "execs_per_second" and isinstance(value, (int, float)):
            return f"{value:,.0f}/s"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    def metric(self, name: str) -> KeyValueRow:
        """Return a metric row by its stable snake-case name."""

        try:
            return self.rows[name]
        except KeyError as error:
            raise KeyError(f"unknown fuzzing metric {name!r}") from error

    def set_metric(self, name: str, value: int | float | str) -> FuzzingDashboard:
        """Replace one metric immediately and return ``self``."""

        row = self.metric(name)
        if isinstance(value, (int, float)) and value < 0:
            raise ValueError(f"dashboard metric {name!r} must be non-negative")
        target = mono_text(
            self._format_metric(name, value),
            font_size=row.font_size,
            color=self._metric_color(name),
            theme=self.theme,
        )
        _match_text(target, row.value, align_right=True)
        row.value.become(target)
        self.metrics[name] = value
        return self

    def animate_update(self, **metrics: int | float | str) -> Animation:
        """Build animations for one or more named metric updates."""

        if not metrics:
            raise ValueError("at least one dashboard metric must be updated")
        for name, value in metrics.items():
            self.metric(name)
            if isinstance(value, (int, float)) and value < 0:
                raise ValueError(f"dashboard metric {name!r} must be non-negative")
        animations: list[Animation] = []
        for name, value in metrics.items():
            row = self.metric(name)
            target = mono_text(
                self._format_metric(name, value),
                font_size=row.font_size,
                color=self._metric_color(name),
                theme=self.theme,
            )
            _match_text(target, row.value, align_right=True)
            self.metrics[name] = value
            animations.extend(
                (
                    Transform(row.value, target),
                    Circumscribe(row, color=self._metric_color(name), buff=0.045),
                )
            )
        return AnimationGroup(*animations, lag_ratio=0.04)

    def animate_crash(self, count: int | None = None) -> Animation:
        """Increment or replace the crash count with a danger emphasis."""

        current = int(self.metrics["crashes"])
        return self.animate_update(crashes=current + 1 if count is None else count)


class CrashCard(Panel):
    """A reproducible crash summary suitable for a fuzzing-results slide."""

    def __init__(
        self,
        signal: str,
        address: Address,
        input_data: bytes | str,
        *,
        reason: str = "",
        reproducible: bool = True,
        address_width: int = 8,
        max_input_bytes: int = 24,
        title: str = "crash found",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if max_input_bytes < 1:
            raise ValueError("max_input_bytes must be positive")
        self.signal = signal
        self.address_value = address
        self.input_data = input_data
        self.reason = reason
        self.reproducible = reproducible
        self.address_width = address_width
        height = 2.55 if reason else 2.15
        super().__init__(
            width=5.8,
            height=height,
            title=title,
            theme=theme,
            fill_color=theme.panel,
        )
        self.background.set_stroke(theme.danger, width=2)
        self.rows: dict[str, KeyValueRow] = {}
        values = (
            ("signal", signal, theme.danger),
            ("address", format_address(address, width=address_width), theme.address),
            ("input", self._input_preview(input_data, max_input_bytes), theme.taint),
            (
                "repro",
                "yes" if reproducible else "no",
                theme.success if reproducible else theme.warning,
            ),
        )
        rows = VGroup()
        for key, value, color in values:
            row = KeyValueRow(
                key.upper(),
                value,
                width=5.2,
                font_size=17,
                value_color=color,
                theme=theme,
            )
            if row.value.width > 3.7:
                row.value.scale_to_fit_width(3.7)
            self.rows[key] = row
            rows.add(row)
        rows.arrange(DOWN, buff=0.11, aligned_edge=LEFT)
        content = VGroup(rows)
        self.reason_mobject = None
        if reason:
            wrapped = "\n".join(reason[index : index + 58] for index in range(0, len(reason), 58))
            self.reason_mobject = label_text(
                wrapped,
                font_size=15,
                color=theme.muted,
                theme=theme,
                line_spacing=0.8,
            )
            if self.reason_mobject.width > 5.15:
                self.reason_mobject.scale_to_fit_width(5.15)
            content.add(self.reason_mobject)
        content.arrange(DOWN, buff=0.12, aligned_edge=LEFT)
        content.move_to(self.background).shift(DOWN * 0.17)
        self.add(content)
        self.address = self.rows["address"]

    @staticmethod
    def _input_preview(data: bytes | str, limit: int) -> str:
        if isinstance(data, bytes):
            shown = data[:limit]
            preview = " ".join(f"{byte:02X}" for byte in shown)
            return preview + (" …" if len(data) > limit else "")
        escaped = data.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return escaped[:limit] + ("…" if len(escaped) > limit else "")

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, AddressRef):
            return (self.address,) if ref.address == self.address_value else ()
        if (
            isinstance(ref, AddressRangeRef)
            and isinstance(self.address_value, int)
            and ref.start <= self.address_value < ref.start + ref.length
        ):
            return (self.address,)
        return ()

    def focus_fault(self) -> Animation:
        """Emphasize the signal and fault address."""

        return AnimationGroup(
            Indicate(self.rows["signal"], color=self.theme.danger, scale_factor=1.05),
            Indicate(self.address, color=self.theme.warning, scale_factor=1.05),
        )

    def animate_reveal(self) -> Animation:
        """Build a concise crash-card entrance without playing it."""

        return Succession(
            FadeIn(self, shift=UP * 0.12),
            self.focus_fault(),
        )
