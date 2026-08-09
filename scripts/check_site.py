"""Validate the dependency-free GitHub Pages site before deployment."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
_EXTERNAL_SCHEMES = {"data", "http", "https", "mailto", "tel"}


@dataclass(slots=True)
class Reference:
    source: Path
    line: int
    tag: str
    attribute: str
    value: str


@dataclass(slots=True)
class Document:
    path: Path
    ids: set[str] = field(default_factory=set)
    references: list[Reference] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    has_title: bool = False
    has_viewport: bool = False
    language: str | None = None


class _SiteHTMLParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.document = Document(path)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        line, _ = self.getpos()

        identifier = attributes.get("id")
        if identifier:
            if identifier in self.document.ids:
                self.document.errors.append(
                    f"{self.document.path}:{line}: duplicate id {identifier!r}"
                )
            self.document.ids.add(identifier)

        if tag == "html":
            self.document.language = attributes.get("lang")
        elif tag == "title":
            self.document.has_title = True
        elif tag == "meta" and attributes.get("name", "").casefold() == "viewport":
            self.document.has_viewport = bool(attributes.get("content"))
        elif tag == "img" and "alt" not in attributes:
            self.document.errors.append(f"{self.document.path}:{line}: img must provide alt text")
        elif tag == "video" and "controls" not in attributes:
            self.document.errors.append(
                f"{self.document.path}:{line}: video must expose native controls"
            )

        for attribute in ("href", "src", "poster"):
            value = attributes.get(attribute)
            if value:
                self.document.references.append(
                    Reference(self.document.path, line, tag, attribute, value)
                )


def _parse_document(path: Path) -> Document:
    parser = _SiteHTMLParser(path)
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    document = parser.document
    if not document.language:
        document.errors.append(f"{path}: html element must declare a language")
    if not document.has_title:
        document.errors.append(f"{path}: document must include a title")
    if not document.has_viewport:
        document.errors.append(f"{path}: document must include a viewport meta tag")
    return document


def _resolve_local_target(root: Path, reference: Reference) -> tuple[Path, str] | None:
    value = reference.value.strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    if scheme:
        if scheme not in _EXTERNAL_SCHEMES:
            raise ValueError(f"unsupported URL scheme {parsed.scheme!r}")
        if scheme == "http":
            raise ValueError("external links must use HTTPS")
        return None
    if parsed.netloc:
        raise ValueError("protocol-relative URLs are not allowed")
    if parsed.path.startswith("/"):
        raise ValueError("root-relative links break on the /manim-rev/ Pages path")

    source_directory = reference.source.parent
    target = source_directory / unquote(parsed.path) if parsed.path else reference.source
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError("local target escapes the site directory") from error
    if target.is_dir():
        target = target / "index.html"
    return target, unquote(parsed.fragment)


def validate_site(root: Path) -> list[str]:
    """Return deterministic validation errors for a static-site directory."""

    root = root.resolve()
    errors: list[str] = []
    if not root.is_dir():
        return [f"site directory does not exist: {root}"]

    for required in ("index.html", "examples.html", "styles.css"):
        if not (root / required).is_file():
            errors.append(f"missing required site file: {required}")

    documents = {
        path.resolve(): _parse_document(path)
        for path in sorted(root.rglob("*.html"))
        if path.is_file()
    }
    for document in documents.values():
        errors.extend(document.errors)

    references = [reference for document in documents.values() for reference in document.references]
    for stylesheet in sorted(root.rglob("*.css")):
        for match in _CSS_URL.finditer(stylesheet.read_text(encoding="utf-8")):
            references.append(
                Reference(
                    stylesheet.resolve(),
                    stylesheet.read_text(encoding="utf-8").count("\n", 0, match.start()) + 1,
                    "css",
                    "url",
                    match.group(2),
                )
            )

    for reference in references:
        try:
            resolved = _resolve_local_target(root, reference)
        except ValueError as error:
            errors.append(
                f"{reference.source}:{reference.line}: {reference.attribute}="
                f"{reference.value!r}: {error}"
            )
            continue
        if resolved is None:
            continue
        target, fragment = resolved
        if not target.is_file():
            errors.append(
                f"{reference.source}:{reference.line}: missing local target {reference.value!r}"
            )
            continue
        if target.suffix.casefold() == ".mp4" and target.stat().st_size == 0:
            errors.append(f"{target}: video asset is empty")
        if fragment:
            target_document = documents.get(target)
            if target_document is None or fragment not in target_document.ids:
                errors.append(
                    f"{reference.source}:{reference.line}: missing fragment "
                    f"#{fragment} in {target.relative_to(root)}"
                )

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, nargs="?", default=Path("site"))
    args = parser.parse_args()
    errors = validate_site(args.site)
    if errors:
        print("Static-site validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    html_count = sum(1 for _ in args.site.rglob("*.html"))
    print(f"Static-site validation passed for {html_count} HTML documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
