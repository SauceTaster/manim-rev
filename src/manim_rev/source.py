"""Source listings, cross references, and source-to-assembly links."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    Animation,
    AnimationGroup,
    Arrow,
    Indicate,
    Mobject,
    RoundedRectangle,
    ShowPassingFlash,
    VGroup,
)

from .models import Address, InstructionSpec, XRefSpec, format_address
from .primitives import Panel, mono_text
from .refs import AddressRangeRef, AddressRef, BlockRef, SourceRef, VisualRef
from .theme import DEFAULT_THEME, RevTheme


def _fit_width(mobject: Mobject, width: float) -> Mobject:
    if mobject.width > width:
        mobject.scale_to_fit_width(width)
    return mobject


def _address_tuple(value: Address | Sequence[Address]) -> tuple[Address, ...]:
    if isinstance(value, (int, str)):
        return (value,)
    return tuple(value)


class SourceListing(Panel):
    """A line-addressable source code panel without a LaTeX dependency."""

    def __init__(
        self,
        source: str | Sequence[str],
        *,
        filename: str = "source",
        start_line: int = 1,
        width: float = 6.4,
        row_height: float = 0.34,
        address_map: Mapping[int, Address | Sequence[Address]] | None = None,
        highlighted_lines: Mapping[int, str] | None = None,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if start_line < 1:
            raise ValueError("source line numbers must start at 1 or greater")
        if width <= 1:
            raise ValueError("source-listing width must be greater than 1")
        if row_height <= 0:
            raise ValueError("source row height must be positive")

        lines = source.splitlines() or [""] if isinstance(source, str) else list(source) or [""]
        self.source_lines = tuple(str(line) for line in lines)
        self.filename = filename
        self.start_line = start_line
        self.end_line = start_line + len(self.source_lines) - 1
        self.address_map = {
            line: _address_tuple(addresses) for line, addresses in (address_map or {}).items()
        }
        unknown_lines = sorted(
            line for line in self.address_map if not self.start_line <= line <= self.end_line
        )
        if unknown_lines:
            raise KeyError(f"address map references unknown source line(s): {unknown_lines}")

        highlight_map = dict(highlighted_lines or {})
        unknown_highlights = sorted(
            line for line in highlight_map if not self.start_line <= line <= self.end_line
        )
        if unknown_highlights:
            raise KeyError(f"highlight map references unknown source line(s): {unknown_highlights}")

        height = 0.7 + len(self.source_lines) * (row_height + 0.025)
        super().__init__(
            width=width,
            height=height,
            title=filename,
            theme=theme,
            title_font_size=16,
        )
        self.line_mobjects: dict[int, VGroup] = {}
        self._line_text: dict[int, str] = {}
        rows = VGroup()
        last_line_digits = len(str(self.end_line))
        for offset, source_line in enumerate(self.source_lines):
            line_number = start_line + offset
            row = self._make_line(
                line_number,
                source_line,
                offset,
                width - 0.25,
                row_height,
                last_line_digits,
                highlight_map.get(line_number),
            )
            self.line_mobjects[line_number] = row
            self._line_text[line_number] = source_line
            rows.add(row)
        rows.arrange(DOWN, buff=0.025, aligned_edge=LEFT)
        rows.move_to(self.background).shift(DOWN * 0.16)
        self.rows = rows
        self.add(rows)

    def _make_line(
        self,
        line_number: int,
        source: str,
        index: int,
        width: float,
        height: float,
        number_digits: int,
        highlight: str | None,
    ) -> VGroup:
        background = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.035,
            stroke_color=highlight or self.theme.border,
            stroke_width=1.1 if highlight else 0,
            fill_color=highlight or self.theme.panel_alt,
            fill_opacity=0.17 if highlight else (0.42 if index % 2 == 0 else 0.2),
        )
        number = mono_text(
            f"{line_number:>{number_digits}}",
            font_size=13,
            color=self.theme.muted,
            theme=self.theme,
        )
        code = mono_text(
            source if source else " ",
            font_size=15,
            color=self.theme.text,
            theme=self.theme,
            disable_ligatures=True,
        )
        number.align_to(background, LEFT).shift(RIGHT * 0.09)
        code.next_to(number, RIGHT, buff=0.2)
        _fit_width(code, max(0.2, background.get_right()[0] - code.get_left()[0] - 0.1))
        return VGroup(background, number, code)

    def line(self, number: int) -> VGroup:
        """Return a source row by its one-based displayed line number."""

        try:
            return self.line_mobjects[number]
        except KeyError as error:
            raise KeyError(
                f"line {number} is outside {self.filename!r} ({self.start_line}-{self.end_line})"
            ) from error

    def text_at(self, number: int) -> str:
        self.line(number)
        return self._line_text[number]

    def addresses_for_line(self, number: int) -> tuple[Address, ...]:
        self.line(number)
        return self.address_map.get(number, ())

    def lines_for_address(self, address: Address) -> tuple[int, ...]:
        return tuple(line for line, addresses in self.address_map.items() if address in addresses)

    def _matches_file(self, file: str | None) -> bool:
        if file is None:
            return True
        return file == self.filename or PurePath(file).name == PurePath(self.filename).name

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, SourceRef):
            if not self._matches_file(ref.file):
                return ()
            row = self.line_mobjects.get(ref.line)
            return (row,) if row is not None else ()
        if isinstance(ref, AddressRef):
            return tuple(self.line(line) for line in self.lines_for_address(ref.address))
        if isinstance(ref, AddressRangeRef):
            range_end = ref.start + ref.length
            lines: list[Mobject] = []
            for line, addresses in self.address_map.items():
                if any(
                    isinstance(address, int) and ref.start <= address < range_end
                    for address in addresses
                ):
                    lines.append(self.line(line))
            return tuple(lines)
        return ()

    def focus(
        self,
        line_or_ref: int | VisualRef,
        *,
        color: str | None = None,
        scale_factor: float = 1.025,
    ) -> Animation:
        """Emphasize a line number or semantic reference."""

        targets = (
            (self.line(line_or_ref),) if isinstance(line_or_ref, int) else self.resolve(line_or_ref)
        )
        if not targets:
            raise LookupError(f"source listing cannot resolve {line_or_ref!r}")
        return AnimationGroup(
            *(
                Indicate(
                    target,
                    color=color or self.theme.warning,
                    scale_factor=scale_factor,
                )
                for target in targets
            )
        )

    def link_to(
        self,
        assembly: Mobject,
        links: Mapping[int, Address | Sequence[Address]]
        | Sequence[SourceAssemblyLinkSpec]
        | None = None,
        *,
        theme: RevTheme | None = None,
    ) -> SourceAssemblyMap:
        """Create connectors after this listing and the assembly view are positioned."""

        return SourceAssemblyMap(self, assembly, links, theme=theme or self.theme)


def _xref_color(kind: str, theme: RevTheme) -> str:
    normalized = kind.casefold()
    if normalized in {"call", "code", "execute"}:
        return theme.call
    if normalized in {"write", "store"}:
        return theme.warning
    if normalized in {"read", "load"}:
        return theme.info
    if normalized in {"taint", "data"}:
        return theme.taint
    return theme.fallthrough


class _XRefRow(VGroup):
    def __init__(
        self,
        spec: XRefSpec,
        *,
        width: float,
        height: float,
        index: int,
        theme: RevTheme,
    ) -> None:
        super().__init__()
        self.spec = spec
        color = _xref_color(spec.kind, theme)
        background = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.045,
            stroke_width=0,
            fill_color=theme.panel_alt,
            fill_opacity=0.42 if index % 2 == 0 else 0.22,
        )
        self.kind = mono_text(spec.kind.upper(), font_size=10, color=color, theme=theme)
        self.source = mono_text(spec.source, font_size=14, color=theme.address, theme=theme)
        self.target = mono_text(spec.target, font_size=14, color=theme.text, theme=theme)
        if spec.label:
            target_value = VGroup(
                self.target,
                mono_text(f"[{spec.label}]", font_size=10, color=theme.muted, theme=theme),
            ).arrange(DOWN, buff=0.01, aligned_edge=LEFT)
        else:
            target_value = VGroup(self.target)

        left = background.get_left()[0]
        right = background.get_right()[0]
        self.kind.move_to([left + 0.37, 0, 0])
        self.source.move_to([left + width * 0.36, 0, 0])
        target_value.move_to([left + width * 0.77, 0, 0])
        _fit_width(self.source, width * 0.25)
        _fit_width(target_value, width * 0.28)
        self.arrow = Arrow(
            [left + width * 0.49, 0, 0],
            [left + width * 0.59, 0, 0],
            buff=0,
            color=color,
            stroke_width=1.8,
            max_tip_length_to_length_ratio=0.28,
        )
        self.add(background, self.kind, self.source, self.arrow, target_value)
        self.move_to([(left + right) / 2, 0, 0])


class CrossReferencePanel(Panel):
    """A compact, addressable list of source/code/data cross references."""

    def __init__(
        self,
        references: Sequence[XRefSpec],
        *,
        width: float = 5.4,
        row_height: float = 0.42,
        title: str = "cross references",
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        if width <= 1:
            raise ValueError("cross-reference panel width must be greater than 1")
        if row_height <= 0:
            raise ValueError("cross-reference row height must be positive")
        self.references = tuple(references)
        height = 0.7 + max(1, len(self.references)) * (row_height + 0.035)
        super().__init__(
            width=width,
            height=height,
            title=title,
            theme=theme,
            title_font_size=16,
        )
        self.row_mobjects: list[_XRefRow] = []
        rows = VGroup()
        for index, reference in enumerate(self.references):
            row = _XRefRow(
                reference,
                width=width - 0.25,
                height=row_height,
                index=index,
                theme=theme,
            )
            self.row_mobjects.append(row)
            rows.add(row)
        if not self.references:
            rows.add(mono_text("no references", font_size=14, color=theme.muted, theme=theme))
        rows.arrange(DOWN, buff=0.035, aligned_edge=LEFT)
        rows.move_to(self.background).shift(DOWN * 0.16)
        self.rows = rows
        self.add(rows)

    def row(self, index: int) -> VGroup:
        try:
            return self.row_mobjects[index]
        except IndexError as error:
            raise IndexError(f"cross-reference row {index} does not exist") from error

    def reference(
        self,
        source: str,
        target: str,
        *,
        kind: str | None = None,
        occurrence: int = 0,
    ) -> VGroup:
        """Return a stable reference row by endpoints and optional kind."""

        matches = [
            row
            for row in self.row_mobjects
            if row.spec.source == source
            and row.spec.target == target
            and (kind is None or row.spec.kind == kind)
        ]
        try:
            return matches[occurrence]
        except IndexError as error:
            raise KeyError(
                f"cross reference {source!r} -> {target!r} occurrence {occurrence} does not exist"
            ) from error

    def references_from(self, source: str) -> tuple[VGroup, ...]:
        return tuple(row for row in self.row_mobjects if row.spec.source == source)

    def references_to(self, target: str) -> tuple[VGroup, ...]:
        return tuple(row for row in self.row_mobjects if row.spec.target == target)

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, BlockRef):
            return tuple(
                row for row in self.row_mobjects if ref.key in {row.spec.source, row.spec.target}
            )
        if isinstance(ref, AddressRef):
            return tuple(
                row
                for row in self.row_mobjects
                if _endpoint_matches_address(row.spec.source, ref.address)
                or _endpoint_matches_address(row.spec.target, ref.address)
            )
        if isinstance(ref, AddressRangeRef):
            end = ref.start + ref.length
            return tuple(
                row
                for row in self.row_mobjects
                if any(
                    address is not None and ref.start <= address < end
                    for address in (
                        _parse_address(row.spec.source),
                        _parse_address(row.spec.target),
                    )
                )
            )
        if isinstance(ref, SourceRef):
            return tuple(
                row
                for row in self.row_mobjects
                if _endpoint_matches_source(row.spec.source, ref)
                or _endpoint_matches_source(row.spec.target, ref)
            )
        return ()

    def focus(
        self,
        index_or_ref: int | VisualRef,
        *,
        color: str | None = None,
        scale_factor: float = 1.035,
    ) -> Animation:
        targets = (
            (self.row(index_or_ref),)
            if isinstance(index_or_ref, int)
            else self.resolve(index_or_ref)
        )
        if not targets:
            raise LookupError(f"cross-reference panel cannot resolve {index_or_ref!r}")
        return AnimationGroup(
            *(
                Indicate(
                    target,
                    color=color or self.theme.warning,
                    scale_factor=scale_factor,
                )
                for target in targets
            )
        )

    def follow(self, index: int, *, color: str | None = None) -> Animation:
        """Animate one cross reference from its source endpoint to its target."""

        row = self.row(index)
        follow_color = color or self.theme.warning
        return AnimationGroup(
            Indicate(row.source, color=follow_color, scale_factor=1.05),  # type: ignore[attr-defined]
            ShowPassingFlash(
                row.arrow.copy().set_color(follow_color),  # type: ignore[attr-defined]
                time_width=0.6,
            ),
            Indicate(row.target, color=follow_color, scale_factor=1.05),  # type: ignore[attr-defined]
            lag_ratio=0.25,
        )


def _parse_address(value: str) -> int | None:
    try:
        return int(value.strip(), 0)
    except ValueError:
        return None


def _endpoint_matches_address(endpoint: str, address: Address) -> bool:
    if endpoint == str(address) or endpoint == format_address(address):
        return True
    return isinstance(address, int) and _parse_address(endpoint) == address


def _endpoint_matches_source(endpoint: str, ref: SourceRef) -> bool:
    file_part, separator, line_part = endpoint.rpartition(":")
    if not separator or not line_part.isdigit() or int(line_part) != ref.line:
        return False
    if ref.file is None:
        return True
    return file_part == ref.file or PurePath(file_part).name == PurePath(ref.file).name


@dataclass(frozen=True, slots=True)
class SourceAssemblyLinkSpec:
    """One source-line to instruction-address connection."""

    line: int
    address: Address
    label: str = ""


class _SourceAssemblyConnection(VGroup):
    def __init__(
        self,
        spec: SourceAssemblyLinkSpec,
        source: Mobject,
        target: Mobject,
        *,
        color: str,
        path_arc: float,
        theme: RevTheme,
    ) -> None:
        super().__init__()
        self.spec = spec
        self.source = source
        self.target = target
        self.arrow = Arrow(
            source,
            target,
            buff=0.06,
            path_arc=path_arc,
            color=color,
            stroke_width=1.7,
            max_tip_length_to_length_ratio=0.12,
        )
        self.add(self.arrow)
        self.label = None
        if spec.label:
            self.label = mono_text(spec.label, font_size=11, color=color, theme=theme)
            self.label.move_to(self.arrow.point_from_proportion(0.5) + DOWN * 0.09)
            self.add(self.label)


class SourceAssemblyMap(VGroup):
    """Connect source lines to addressable assembly/CFG mobjects.

    Position the source and assembly views before constructing this object so
    the connectors use their final endpoints.
    """

    def __init__(
        self,
        source: SourceListing,
        assembly: Mobject,
        links: Mapping[int, Address | Sequence[Address]]
        | Sequence[SourceAssemblyLinkSpec]
        | None = None,
        *,
        color: str | None = None,
        theme: RevTheme = DEFAULT_THEME,
    ) -> None:
        super().__init__()
        self.source = source
        self.assembly = assembly
        self.theme = theme
        self.link_specs = self._normalize_links(source, links)
        self.connections: defaultdict[tuple[int, Address], list[_SourceAssemblyConnection]] = (
            defaultdict(list)
        )
        per_line: defaultdict[int, int] = defaultdict(int)
        for spec in self.link_specs:
            source_row = source.line(spec.line)
            targets = _resolve_assembly(assembly, spec.address)
            if not targets:
                raise LookupError(
                    f"assembly view cannot resolve address {spec.address!r} for source line {spec.line}"
                )
            for target in targets:
                offset = per_line[spec.line]
                per_line[spec.line] += 1
                path_arc = (offset - (len(targets) - 1) / 2) * 0.08
                connection = _SourceAssemblyConnection(
                    spec,
                    source_row,
                    target,
                    color=color or theme.info,
                    path_arc=path_arc,
                    theme=theme,
                )
                self.connections[(spec.line, spec.address)].append(connection)
                self.add(connection)

    @staticmethod
    def _normalize_links(
        source: SourceListing,
        links: Mapping[int, Address | Sequence[Address]] | Sequence[SourceAssemblyLinkSpec] | None,
    ) -> tuple[SourceAssemblyLinkSpec, ...]:
        if links is None:
            links = source.address_map
        if isinstance(links, Mapping):
            return tuple(
                SourceAssemblyLinkSpec(line, address)
                for line, addresses in links.items()
                for address in _address_tuple(addresses)
            )
        return tuple(links)

    def connection(self, line: int, address: Address) -> VGroup:
        """Return all visual connectors for a source/address pair."""

        connections = self.connections.get((line, address))
        if not connections:
            raise KeyError(f"no source-to-assembly link for line {line}, address {address!r}")
        return VGroup(*connections)

    def resolve(self, ref: VisualRef) -> tuple[Mobject, ...]:
        if isinstance(ref, SourceRef):
            if not self.source._matches_file(ref.file):
                return ()
            return tuple(
                connection
                for (line, _), connections in self.connections.items()
                if line == ref.line
                for connection in connections
            )
        if isinstance(ref, AddressRef):
            return tuple(
                connection
                for (_, address), connections in self.connections.items()
                if address == ref.address
                for connection in connections
            )
        if isinstance(ref, AddressRangeRef):
            end = ref.start + ref.length
            return tuple(
                connection
                for (_, address), connections in self.connections.items()
                if isinstance(address, int) and ref.start <= address < end
                for connection in connections
            )
        return ()

    def follow(
        self,
        line: int,
        address: Address,
        *,
        color: str | None = None,
    ) -> Animation:
        """Animate one or more source-to-assembly connections."""

        connections = tuple(self.connection(line, address))
        if not connections:
            raise KeyError(f"no source-to-assembly link for line {line}, address {address!r}")
        follow_color = color or self.theme.warning
        targets = {connection.target for connection in connections}  # type: ignore[attr-defined]
        return AnimationGroup(
            Indicate(self.source.line(line), color=follow_color, scale_factor=1.025),
            *(
                ShowPassingFlash(
                    connection.arrow.copy().set_color(follow_color),  # type: ignore[attr-defined]
                    time_width=0.55,
                )
                for connection in connections
            ),
            *(Indicate(target, color=follow_color, scale_factor=1.04) for target in targets),
            lag_ratio=0.15,
        )


def _resolve_assembly(assembly: Mobject, address: Address) -> tuple[Mobject, ...]:
    resolver = getattr(assembly, "resolve", None)
    if callable(resolver):
        targets = tuple(resolver(AddressRef(address)))
        if targets:
            return targets

    instruction_lookup = getattr(assembly, "instruction", None)
    if callable(instruction_lookup):
        try:
            return (instruction_lookup(address),)
        except (KeyError, LookupError):
            pass
    if isinstance(instruction_lookup, InstructionSpec) and instruction_lookup.address == address:
        return (assembly,)

    descendant_targets: list[Mobject] = []
    for descendant in assembly.get_family():
        instruction = getattr(descendant, "instruction", None)
        if isinstance(instruction, InstructionSpec) and instruction.address == address:
            descendant_targets.append(descendant)
    return tuple(descendant_targets)
