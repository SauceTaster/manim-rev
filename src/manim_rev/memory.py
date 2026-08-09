"""Hex-dump and process-memory-map visualizations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    Animation,
    AnimationGroup,
    Indicate,
    Mobject,
    Rectangle,
    RoundedRectangle,
    Transform,
    VGroup,
)

from .models import MemorySegmentSpec, format_address
from .primitives import Panel, mono_text
from .refs import AddressRangeRef, AddressRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme

__all__ = [
    "HexAddressCell",
    "HexAsciiCell",
    "HexByteCell",
    "HexDump",
    "HexDumpRow",
    "MemoryMap",
    "MemorySegment",
]


def _fit_width(mobject: Mobject, width: float) -> Mobject:
    if mobject.width > width:
        mobject.scale_to_fit_width(width)
    return mobject


def _coerce_byte(value: int) -> int:
    if not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ValueError("a byte value must be an integer between 0 and 255")
    return value


def _coerce_bytes(values: int | bytes | bytearray | memoryview | Iterable[int]) -> bytes:
    if isinstance(values, int):
        return bytes((_coerce_byte(values),))
    if isinstance(values, str):
        raise TypeError("hex-dump data must be bytes or an iterable of integers")
    try:
        return bytes(values)
    except (TypeError, ValueError) as error:
        raise ValueError("hex-dump values must contain integers between 0 and 255") from error


def _ascii(values: Iterable[int]) -> str:
    return "".join(chr(value) if 0x20 <= value <= 0x7E else "." for value in values)


class _HexCell(VGroup):
    """Shared fixed-size cell behavior."""

    def __init__(
        self,
        text: str,
        *,
        width: float,
        height: float,
        font_size: float,
        text_color: str,
        theme: RevTheme,
    ) -> None:
        super().__init__()
        self.theme = theme
        self.cell_width = width
        self.cell_height = height
        self.font_size = font_size
        self.text_color = text_color
        self.background = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=min(0.06, height / 5),
            stroke_color=theme.border,
            stroke_width=1,
            fill_color=theme.panel_alt,
            fill_opacity=1,
        )
        self.background.set_z_index(-1)
        self.text = self._make_text(text)
        self.add(self.background, self.text)

    def _make_text(self, value: str):  # type: ignore[no-untyped-def]
        text = mono_text(
            value,
            font_size=self.font_size,
            color=self.text_color,
            theme=self.theme,
        )
        visual_scale = self.background.width / self.cell_width
        max_width = self.background.width - 0.1 * visual_scale
        max_height = self.background.height - 0.08 * visual_scale
        if text.width > max_width:
            text.scale_to_fit_width(max_width)
        if text.height > max_height:
            text.scale_to_fit_height(max_height)
        return text.move_to(self.background)

    def highlight(
        self,
        *,
        color: str | None = None,
        scale_factor: float = 1.08,
        run_time: float = 0.35,
    ) -> Animation:
        """Return a short emphasis animation for this cell."""

        return Indicate(
            self,
            color=color or self.theme.warning,
            scale_factor=scale_factor,
            run_time=run_time,
        )


class HexAddressCell(_HexCell):
    """Address label at the beginning of a :class:`HexDumpRow`."""

    def __init__(
        self,
        address: int,
        *,
        address_width: int = 8,
        width: float = 1.48,
        height: float = 0.38,
        font_size: float = 15,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        self.address = address
        self.address_width = address_width
        self.display = format_address(address, width=address_width)
        super().__init__(
            self.display,
            width=width,
            height=height,
            font_size=font_size,
            text_color=theme.address,
            theme=theme,
        )


class HexByteCell(_HexCell):
    """One addressable byte with stable value and animation handles."""

    def __init__(
        self,
        address: int,
        value: int,
        *,
        offset: int = 0,
        width: float = 0.38,
        height: float = 0.38,
        font_size: float = 15,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        self.address = address
        self.offset = offset
        self.value = _coerce_byte(value)
        super().__init__(
            f"{self.value:02X}",
            width=width,
            height=height,
            font_size=font_size,
            text_color=theme.text,
            theme=theme,
        )

    @property
    def display(self) -> str:
        return f"{self.value:02X}"

    def set_value(self, value: int) -> HexByteCell:
        """Replace the displayed value immediately and return ``self``."""

        self.value = _coerce_byte(value)
        self.text.become(self._make_text(self.display))
        return self

    def animate_write(
        self,
        value: int,
        *,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        """Build an animation that writes and emphasizes a new byte value."""

        self.value = _coerce_byte(value)
        target = self._make_text(self.display)
        return AnimationGroup(
            Transform(self.text, target),
            Indicate(
                self.background,
                color=color or self.theme.danger,
                scale_factor=1.06,
            ),
            lag_ratio=0,
            run_time=run_time,
        )

    def write(
        self,
        value: int,
        *,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        """Alias for :meth:`animate_write` for talk-friendly scene code."""

        return self.animate_write(value, color=color, run_time=run_time)


class HexAsciiCell(_HexCell):
    """Printable-ASCII interpretation of one row of bytes."""

    def __init__(
        self,
        address: int,
        values: bytes | bytearray | memoryview | Iterable[int],
        *,
        capacity: int,
        width: float | None = None,
        height: float = 0.38,
        font_size: float = 15,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        self.address = address
        if capacity < 1:
            raise ValueError("ASCII cell capacity must be positive")
        self.capacity = capacity
        self.values = _coerce_bytes(values)
        if len(self.values) > capacity:
            raise ValueError("ASCII cell data exceeds its row capacity")
        super().__init__(
            _ascii(self.values),
            width=width or max(0.72, capacity * 0.2 + 0.22),
            height=height,
            font_size=font_size,
            text_color=theme.success,
            theme=theme,
        )

    @property
    def display(self) -> str:
        return _ascii(self.values)

    def set_values(self, values: bytes | bytearray | memoryview | Iterable[int]) -> HexAsciiCell:
        """Replace the ASCII interpretation immediately."""

        raw = _coerce_bytes(values)
        if len(raw) > self.capacity:
            raise ValueError("ASCII cell data exceeds its row capacity")
        self.values = raw
        self.text.become(self._make_text(self.display))
        return self

    def animate_write(
        self,
        values: bytes | bytearray | memoryview | Iterable[int],
        *,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        """Build an animation that refreshes the printable interpretation."""

        raw = _coerce_bytes(values)
        if len(raw) > self.capacity:
            raise ValueError("ASCII cell data exceeds its row capacity")
        self.values = raw
        target = self._make_text(self.display)
        return AnimationGroup(
            Transform(self.text, target),
            Indicate(
                self.background,
                color=color or self.theme.success,
                scale_factor=1.03,
            ),
            lag_ratio=0,
            run_time=run_time,
        )


class HexDumpRow(VGroup):
    """One aligned address, byte, and ASCII row in a hex dump."""

    def __init__(
        self,
        address: int,
        values: bytes | bytearray | memoryview | Iterable[int],
        *,
        offset: int = 0,
        bytes_per_row: int = 16,
        address_width: int = 8,
        show_ascii: bool = True,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        raw = _coerce_bytes(values)
        if bytes_per_row < 1:
            raise ValueError("bytes_per_row must be positive")
        if len(raw) > bytes_per_row:
            raise ValueError("row data exceeds bytes_per_row")
        self.address = address
        self.offset = offset
        self.bytes_per_row = bytes_per_row
        self.theme = theme
        self.address_cell = HexAddressCell(
            address,
            address_width=address_width,
            theme=theme,
        )
        cells = tuple(
            HexByteCell(address + index, value, offset=offset + index, theme=theme)
            for index, value in enumerate(raw)
        )
        self.byte_cells = cells
        self.cells_by_address = {cell.address: cell for cell in cells}
        self.byte_group = VGroup(*cells)
        if cells:
            self.byte_group.arrange(RIGHT, buff=0.045)

        self.address_cell.move_to([0, 0, 0], aligned_edge=LEFT)
        byte_x = self.address_cell.get_right()[0] + 0.15
        if cells:
            self.byte_group.move_to([byte_x, 0, 0], aligned_edge=LEFT)

        self.ascii_cell: HexAsciiCell | None = None
        if show_ascii:
            self.ascii_cell = HexAsciiCell(
                address,
                raw,
                capacity=bytes_per_row,
                theme=theme,
            )
            byte_width = 0.38
            byte_gap = 0.045
            byte_area_right = byte_x + bytes_per_row * byte_width
            byte_area_right += max(0, bytes_per_row - 1) * byte_gap
            self.ascii_cell.move_to([byte_area_right + 0.16, 0, 0], aligned_edge=LEFT)

        self.add(self.address_cell, self.byte_group)
        if self.ascii_cell is not None:
            self.add(self.ascii_cell)

    @property
    def data(self) -> bytes:
        return bytes(cell.value for cell in self.byte_cells)

    def contains(self, address: int) -> bool:
        return address in self.cells_by_address

    def byte_cell(self, address: int) -> HexByteCell:
        try:
            return self.cells_by_address[address]
        except KeyError as error:
            raise KeyError(f"address {format_address(address)} is not in this row") from error

    def resolve(self, ref: VisualRef) -> tuple[HexByteCell, ...]:
        if isinstance(ref, AddressRef) and isinstance(ref.address, int):
            cell = self.cells_by_address.get(ref.address)
            return (cell,) if cell is not None else ()
        if isinstance(ref, AddressRangeRef):
            end = ref.start + ref.length
            return tuple(
                cell
                for address, cell in self.cells_by_address.items()
                if ref.start <= address < end
            )
        return ()


class HexDump(Panel):
    """A stable, addressable hex dump for memory and packet demonstrations.

    Mutation methods update the component's logical state immediately and return
    animations for a scene to play.  This mirrors Manim's ``animate_*`` idiom and
    makes subsequent calls deterministic while animations are being assembled.
    """

    def __init__(
        self,
        data: bytes | bytearray | memoryview | Iterable[int],
        *,
        base_address: int = 0,
        bytes_per_row: int = 16,
        address_width: int = 8,
        show_ascii: bool = True,
        title: str = "hex dump",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if base_address < 0:
            raise ValueError("base_address must be non-negative")
        if bytes_per_row < 1:
            raise ValueError("bytes_per_row must be positive")
        if address_width < 1:
            raise ValueError("address_width must be positive")
        raw = _coerce_bytes(data)
        self.base_address = base_address
        self.bytes_per_row = bytes_per_row
        self.address_width = address_width
        self.show_ascii = show_ascii
        self._data = bytearray(raw)

        row_items = tuple(
            HexDumpRow(
                base_address + offset,
                raw[offset : offset + bytes_per_row],
                offset=offset,
                bytes_per_row=bytes_per_row,
                address_width=address_width,
                show_ascii=show_ascii,
                theme=theme,
            )
            for offset in range(0, len(raw), bytes_per_row)
        )
        self.rows = row_items
        self.row_group = VGroup(*row_items)
        if row_items:
            self.row_group.arrange(DOWN, buff=0.065, aligned_edge=LEFT)
            content_width = self.row_group.width
            content_height = self.row_group.height
        else:
            self.empty_label = mono_text("<empty>", font_size=15, color=theme.muted, theme=theme)
            content_width = self.empty_label.width
            content_height = max(0.38, self.empty_label.height)

        panel_width = max(2.2, content_width + 0.36)
        panel_height = content_height + (0.76 if title else 0.36)
        super().__init__(
            width=panel_width,
            height=panel_height,
            title=title or None,
            theme=theme,
        )

        self.byte_cells: dict[int, HexByteCell] = {
            cell.address: cell for row in row_items for cell in row.byte_cells
        }
        self.address_cells: dict[int, HexAddressCell] = {
            row.address: row.address_cell for row in row_items
        }
        self.ascii_cells: dict[int, HexAsciiCell] = {
            row.address: row.ascii_cell for row in row_items if row.ascii_cell is not None
        }
        if row_items:
            self.row_group.move_to(self.background).shift(DOWN * (0.18 if title else 0))
            self.add(self.row_group)
        else:
            self.empty_label.move_to(self.background).shift(DOWN * (0.16 if title else 0))
            self.add(self.empty_label)

    @property
    def data(self) -> bytes:
        """Return an immutable snapshot of the displayed bytes."""

        return bytes(self._data)

    @property
    def end_address(self) -> int:
        """Return the exclusive end address."""

        return self.base_address + len(self._data)

    def __getitem__(self, address: int) -> HexByteCell:
        return self.byte_cell(address)

    def _slice(self, address: int, length: int, *, allow_empty: bool = False) -> slice:
        if length < 0 or (length == 0 and not allow_empty):
            qualifier = "non-negative" if allow_empty else "positive"
            raise ValueError(f"length must be {qualifier}")
        offset = address - self.base_address
        if offset < 0 or offset + length > len(self._data):
            raise IndexError(
                f"range {format_address(address)}..{format_address(address + length)} "
                "falls outside the hex dump"
            )
        return slice(offset, offset + length)

    def byte_cell(self, address: int) -> HexByteCell:
        """Return the byte cell at an absolute address."""

        try:
            return self.byte_cells[address]
        except KeyError as error:
            raise KeyError(f"address {format_address(address)} is not in this hex dump") from error

    def row_for_address(self, address: int) -> HexDumpRow:
        """Return the row containing an absolute byte address."""

        self.byte_cell(address)
        index = (address - self.base_address) // self.bytes_per_row
        return self.rows[index]

    def bytes_at(self, address: int, length: int = 1) -> bytes:
        """Return bytes beginning at an absolute address."""

        data_slice = self._slice(address, length, allow_empty=True)
        return bytes(self._data[data_slice])

    def set_bytes(
        self,
        address: int,
        values: int | bytes | bytearray | memoryview | Iterable[int],
    ) -> HexDump:
        """Write bytes immediately, refreshing byte and ASCII cells."""

        raw = _coerce_bytes(values)
        if not raw:
            raise ValueError("at least one byte is required")
        data_slice = self._slice(address, len(raw))
        self._data[data_slice] = raw
        for index, value in enumerate(raw):
            self.byte_cell(address + index).set_value(value)
        for row in {self.row_for_address(address + index) for index in range(len(raw))}:
            start = row.offset
            row_data = self._data[start : start + len(row.byte_cells)]
            if row.ascii_cell is not None:
                row.ascii_cell.set_values(row_data)
        return self

    def highlight(
        self,
        address: int,
        length: int = 1,
        *,
        color: str | None = None,
        lag_ratio: float = 0.05,
        run_time: float = 0.4,
    ) -> Animation:
        """Build an animation emphasizing an absolute address range."""

        data_slice = self._slice(address, length)
        targets = [
            self.byte_cells[self.base_address + offset]
            for offset in range(data_slice.start, data_slice.stop)
        ]
        return AnimationGroup(
            *(cell.highlight(color=color, run_time=run_time) for cell in targets),
            lag_ratio=lag_ratio,
            run_time=run_time,
        )

    def highlight_range(
        self,
        address: int,
        length: int = 1,
        *,
        color: str | None = None,
        lag_ratio: float = 0.05,
        run_time: float = 0.4,
    ) -> Animation:
        """Named alias for :meth:`highlight`."""

        return self.highlight(
            address,
            length,
            color=color,
            lag_ratio=lag_ratio,
            run_time=run_time,
        )

    def animate_write(
        self,
        address: int,
        values: int | bytes | bytearray | memoryview | Iterable[int],
        *,
        color: str | None = None,
        lag_ratio: float = 0.06,
        run_time: float = 0.5,
    ) -> Animation:
        """Build an animation that writes one or more bytes."""

        raw = _coerce_bytes(values)
        if not raw:
            raise ValueError("at least one byte is required")
        data_slice = self._slice(address, len(raw))
        self._data[data_slice] = raw
        animations: list[Animation] = [
            self.byte_cell(address + index).animate_write(value, color=color)
            for index, value in enumerate(raw)
        ]
        touched_rows = {self.row_for_address(address + index) for index in range(len(raw))}
        for row in sorted(touched_rows, key=lambda item: item.offset):
            if row.ascii_cell is None:
                continue
            start = row.offset
            row_data = self._data[start : start + len(row.byte_cells)]
            animations.append(
                row.ascii_cell.animate_write(row_data, color=color or self.theme.success)
            )
        return AnimationGroup(
            *animations,
            lag_ratio=lag_ratio,
            run_time=run_time,
        )

    def write(
        self,
        address: int,
        values: int | bytes | bytearray | memoryview | Iterable[int],
        *,
        color: str | None = None,
        lag_ratio: float = 0.06,
        run_time: float = 0.5,
    ) -> Animation:
        """Alias for :meth:`animate_write` for compact scene code."""

        return self.animate_write(
            address,
            values,
            color=color,
            lag_ratio=lag_ratio,
            run_time=run_time,
        )

    def resolve(self, ref: VisualRef) -> tuple[HexByteCell, ...]:
        if isinstance(ref, AddressRef) and isinstance(ref.address, int):
            cell = self.byte_cells.get(ref.address)
            return (cell,) if cell is not None else ()
        if isinstance(ref, AddressRangeRef):
            end = ref.start + ref.length
            return tuple(
                cell for address, cell in self.byte_cells.items() if ref.start <= address < end
            )
        return ()


class MemorySegment(VGroup):
    """Rendered view of one :class:`~manim_rev.models.MemorySegmentSpec`."""

    def __init__(
        self,
        spec: MemorySegmentSpec,
        *,
        width: float = 4.2,
        height: float = 0.7,
        address_width: int = 8,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.spec = spec
        self.theme = theme
        color = spec.color or self._permission_color(spec.permissions)
        self.background = Rectangle(
            width=width,
            height=height,
            stroke_color=color,
            stroke_width=1.5,
            fill_color=color,
            fill_opacity=0.13,
        )
        self.name = mono_text(
            spec.name,
            font_size=17,
            color=theme.text,
            theme=theme,
            weight="BOLD",
        )
        self.permissions = mono_text(
            spec.permissions,
            font_size=15,
            color=color,
            theme=theme,
        )
        self.address_range = mono_text(
            f"{format_address(spec.start, width=address_width)} - "
            f"{format_address(spec.end, width=address_width)}",
            font_size=12,
            color=theme.muted,
            theme=theme,
        )
        inner_width = max(0.2, width - 0.3)
        _fit_width(self.permissions, max(0.35, min(0.9, inner_width * 0.24)))
        permission_height = max(0.04, height * 0.32)
        if self.permissions.height > permission_height:
            self.permissions.scale_to_fit_height(permission_height)
        name_width = max(0.2, inner_width - self.permissions.width - 0.16)
        _fit_width(self.name, name_width)
        _fit_width(self.address_range, inner_width)
        self.label_stack = VGroup(self.name, self.address_range).arrange(
            DOWN,
            buff=max(0.015, min(0.06, height * 0.08)),
            aligned_edge=LEFT,
        )
        content_height = max(0.08, height - 0.12)
        if self.label_stack.height > content_height:
            self.label_stack.scale_to_fit_height(content_height)
        self.label_stack.move_to(self.background)
        self.label_stack.align_to(self.background, LEFT).shift(RIGHT * 0.15)
        self.permissions.move_to(
            [self.background.get_right()[0] - 0.15, self.name.get_center()[1], 0],
            aligned_edge=RIGHT,
        )
        self.add(self.background, self.name, self.permissions, self.address_range)

    def _permission_color(self, permissions: str) -> str:
        if "x" in permissions.casefold():
            return self.theme.opcode
        if "w" in permissions.casefold():
            return self.theme.warning
        return self.theme.info

    def contains(self, address: int) -> bool:
        return self.spec.start <= address < self.spec.end

    def intersects(self, start: int, end: int) -> bool:
        return self.spec.start < end and start < self.spec.end

    def highlight(
        self,
        *,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        return Indicate(
            self,
            color=color or self.spec.color or self.theme.warning,
            scale_factor=1.035,
            run_time=run_time,
        )


class MemoryMap(Panel):
    """A high-to-low process memory map with semantic address lookup."""

    def __init__(
        self,
        segments: Sequence[MemorySegmentSpec],
        *,
        width: float = 4.7,
        segment_height: float = 0.7,
        address_width: int = 8,
        high_addresses_on_top: bool = True,
        title: str = "memory map",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width <= 0.7:
            raise ValueError("width must be greater than 0.7")
        if segment_height <= 0:
            raise ValueError("segment_height must be positive")
        specs = tuple(segments)
        names = [spec.name for spec in specs]
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("memory segment names must be unique ignoring case")
        self.segment_specs = specs
        ordered_specs = sorted(
            specs,
            key=lambda spec: spec.start,
            reverse=high_addresses_on_top,
        )
        block_items = tuple(
            MemorySegment(
                spec,
                width=width - 0.36,
                height=segment_height,
                address_width=address_width,
                theme=theme,
            )
            for spec in ordered_specs
        )
        self.segment_blocks = block_items
        self.segments = {block.spec.name: block for block in block_items}
        self.segment_group = VGroup(*block_items)
        if block_items:
            self.segment_group.arrange(DOWN, buff=0.06)
            content_height = self.segment_group.height
        else:
            self.empty_label = mono_text(
                "<no mappings>", font_size=15, color=theme.muted, theme=theme
            )
            content_height = max(segment_height, self.empty_label.height)
        panel_height = content_height + (0.76 if title else 0.36)
        super().__init__(
            width=width,
            height=panel_height,
            title=title or None,
            theme=theme,
        )
        if block_items:
            self.segment_group.move_to(self.background).shift(DOWN * (0.18 if title else 0))
            self.add(self.segment_group)
        else:
            self.empty_label.move_to(self.background).shift(DOWN * (0.16 if title else 0))
            self.add(self.empty_label)

    def segment(self, name: str) -> MemorySegment:
        """Return a segment by name, accepting case-insensitive lookups."""

        if name in self.segments:
            return self.segments[name]
        folded = name.casefold()
        for segment_name, block in self.segments.items():
            if segment_name.casefold() == folded:
                return block
        raise KeyError(f"unknown memory segment {name!r}")

    def segments_at(self, address: int) -> tuple[MemorySegment, ...]:
        """Return every mapping containing ``address``."""

        return tuple(block for block in self.segment_blocks if block.contains(address))

    def segment_for_address(self, address: int) -> MemorySegment:
        """Return the first mapping containing ``address``."""

        matches = self.segments_at(address)
        if not matches:
            raise KeyError(f"address {format_address(address)} is not mapped")
        return matches[0]

    def highlight(
        self,
        segment: str | int,
        *,
        color: str | None = None,
        run_time: float = 0.4,
    ) -> Animation:
        """Emphasize a named segment or every segment containing an address."""

        targets = (
            (self.segment(segment),) if isinstance(segment, str) else self.segments_at(segment)
        )
        if not targets:
            raise KeyError(f"address {format_address(segment)} is not mapped")
        return AnimationGroup(
            *(target.highlight(color=color, run_time=run_time) for target in targets),
            lag_ratio=0,
            run_time=run_time,
        )

    def resolve(self, ref: VisualRef) -> tuple[MemorySegment, ...]:
        if isinstance(ref, AddressRef) and isinstance(ref.address, int):
            return self.segments_at(ref.address)
        if isinstance(ref, AddressRangeRef):
            end = ref.start + ref.length
            return tuple(block for block in self.segment_blocks if block.intersects(ref.start, end))
        return ()
