"""PPTX ingestion — extract text, tables, speaker notes, and slide images.

Exports:
  ParsedDeck  — structured representation of the deck
  parse_pptx  — parse a .pptx file into ParsedDeck
  render_slides_to_png — convert slides to PNG via LibreOffice + pdftoppm
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TableCell:
    text: str
    row: int
    col: int


@dataclass
class SlideTable:
    headers: list[str]
    rows: list[list[str]]


@dataclass
class ParsedSlide:
    index: int  # 1-based
    title: str
    body_paragraphs: list[str]
    speaker_notes: str
    tables: list[SlideTable]
    image_path: Path | None = None  # set after render_slides_to_png


@dataclass
class ParsedDeck:
    title: str
    slides: list[ParsedSlide]
    source_path: Path

    @property
    def full_text(self) -> str:
        """All text in the deck concatenated for LLM context."""
        parts: list[str] = [f"# Deck: {self.title}\n"]
        for s in self.slides:
            parts.append(f"\n## Slide {s.index}: {s.title}")
            for p in s.body_paragraphs:
                if p.strip():
                    parts.append(f"  {p}")
            for t in s.tables:
                parts.append("  [TABLE]")
                if t.headers:
                    parts.append("  | " + " | ".join(t.headers) + " |")
                for row in t.rows:
                    parts.append("  | " + " | ".join(row) + " |")
            if s.speaker_notes:
                parts.append(f"\n  [Notes] {s.speaker_notes}")
        return "\n".join(parts)

    @property
    def cache_key(self) -> str:
        """SHA-256 of the raw pptx bytes — used to skip re-parse."""
        data = self.source_path.read_bytes()
        return hashlib.sha256(data).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _extract_table(table_shape: object) -> SlideTable:  # type: ignore[type-arg]
    """Extract headers and rows from a pptx table shape."""
    from pptx.shapes.table import Table  # type: ignore[import-untyped]

    tbl: Table = table_shape.table  # type: ignore[attr-defined]
    rows: list[list[str]] = []
    for i, row in enumerate(tbl.rows):
        cells = [cell.text.strip() for cell in row.cells]
        rows.append(cells)

    headers: list[str] = []
    data_rows = rows
    if rows:
        # Treat first row as header if it looks like one (short uppercase or bold)
        headers = rows[0]
        data_rows = rows[1:]

    return SlideTable(headers=headers, rows=data_rows)


def parse_pptx(path: Path) -> ParsedDeck:
    """Parse a .pptx file into a ParsedDeck.

    Args:
        path: Absolute path to the .pptx file.

    Returns:
        ParsedDeck with all text, tables, and notes extracted.
    """
    logger.info("Parsing PPTX: %s", path)
    prs = Presentation(str(path))

    deck_title = path.stem
    slides: list[ParsedSlide] = []

    for idx, slide in enumerate(prs.slides, start=1):
        title = ""
        body_paragraphs: list[str] = []
        tables: list[SlideTable] = []

        for shape in slide.shapes:
            # Title placeholder
            if shape.has_text_frame:
                if hasattr(shape, "placeholder_format") and shape.placeholder_format:
                    ph_type = shape.placeholder_format.type
                    # 1 = TITLE, 13 = CENTER_TITLE, 15 = SUBTITLE
                    if ph_type in (1, 13):
                        title = shape.text_frame.text.strip()
                        continue

                # Body / other text
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        body_paragraphs.append(text)

            # Tables
            if shape.has_table:
                tables.append(_extract_table(shape))

        # Use first non-empty body paragraph as title if title placeholder absent
        if not title and body_paragraphs:
            title = body_paragraphs[0]
            body_paragraphs = body_paragraphs[1:]

        # Speaker notes
        notes_text = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()

        slides.append(
            ParsedSlide(
                index=idx,
                title=title,
                body_paragraphs=body_paragraphs,
                speaker_notes=notes_text,
                tables=tables,
            )
        )
        logger.debug("  Slide %d: %s (%d paragraphs)", idx, title, len(body_paragraphs))

    # Try to get deck title from core properties
    if hasattr(prs, "core_properties") and prs.core_properties.title:
        deck_title = prs.core_properties.title

    logger.info("Parsed %d slides from '%s'", len(slides), deck_title)
    return ParsedDeck(title=deck_title, slides=slides, source_path=path)


# ---------------------------------------------------------------------------
# Slide → PNG rendering
# ---------------------------------------------------------------------------


def render_slides_to_png(deck: ParsedDeck, output_dir: Path) -> list[Path]:
    """Convert PPTX slides to PNG images using LibreOffice + pdftoppm.

    Requires: libreoffice, pdftoppm (poppler-utils)

    Args:
        deck: ParsedDeck with source_path set.
        output_dir: Directory to write PNG files into.

    Returns:
        List of PNG paths, one per slide.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = deck.source_path

    logger.info("Rendering %d slides to PNG in %s", len(deck.slides), output_dir)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Step 1: PPTX → PDF via LibreOffice
        pdf_dir = tmp / "pdf"
        pdf_dir.mkdir()
        _run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_dir),
                str(pptx_path),
            ],
            check=True,
            capture_output=True,
        )

        pdf_files = list(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            raise RuntimeError(
                f"LibreOffice did not produce a PDF from {pptx_path}. "
                "Check that LibreOffice is installed and the PPTX is not corrupted."
            )
        pdf_path = pdf_files[0]

        # Step 2: PDF → PNG via pdftoppm (300 DPI → downscale to 1920px wide)
        png_prefix = tmp / "slide"
        _run(
            [
                "pdftoppm",
                "-r",
                "150",
                "-png",
                str(pdf_path),
                str(png_prefix),
            ],
            check=True,
            capture_output=True,
        )

        # pdftoppm names: slide-1.png, slide-2.png, ... or slide-01.png etc.
        raw_pngs = sorted(tmp.glob("slide-*.png"), key=lambda p: _slide_num(p.name))
        if not raw_pngs:
            raise RuntimeError("pdftoppm produced no PNGs. Check poppler installation.")

        # Copy to output_dir with consistent naming
        png_paths: list[Path] = []
        for i, src in enumerate(raw_pngs, start=1):
            dst = output_dir / f"slide_{i:03d}.png"
            shutil.copy2(src, dst)
            png_paths.append(dst)
            if i <= len(deck.slides):
                deck.slides[i - 1].image_path = dst

        logger.info("Rendered %d slide PNGs", len(png_paths))
        return png_paths


def _slide_num(name: str) -> int:
    """Extract slide number from pdftoppm output filename."""
    stem = Path(name).stem  # e.g. 'slide-001'
    parts = stem.rsplit("-", 1)
    try:
        return int(parts[-1])
    except ValueError:
        return 0


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, **kwargs)  # type: ignore[call-overload]
    return result
