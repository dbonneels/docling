"""Row-level table chunks for RAG.

This module implements the idea described in "Retrieve One Row from a Table,
Not the Whole Table: Row-Level Chunks for RAG": each body row of a table
becomes its own retrievable chunk, and the column headers travel with the
values so a match reads like a self-contained sentence::

    Layer Type: Self-Attention | Complexity per Layer: O(n^2)

The entry point is :func:`document_to_row_chunks`: it walks a Docling
``DoclingDocument``, exports every ``TableItem`` to a pandas DataFrame and
emits one chunk per body row. Docling already reconstructs the table grid
(including multi-row headers), so this path is more robust than parsing
Markdown pipe lines.
"""

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

#: Canonical column order of the row-level DataFrame.
ROW_CHUNK_COLUMNS = [
    "table_id",
    "page_num",
    "row_index",
    "line_num",
    "n_rows",
    "n_cols",
    "column_headers",
    "row_cells",
    "row_serialized",
    "caption",
]

#: Columns holding Python lists; JSON-encoded when exporting to CSV.
LIST_COLUMNS = ("column_headers", "row_cells")

_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def normalize_headers(
    headers: Sequence[str],
    n_cols: int | None = None,
) -> list[str]:
    """Clean, de-duplicate and pad/truncate headers to ``n_cols`` columns."""
    cleaned: list[str] = []
    seen: dict[str, int] = {}

    for index, header in enumerate(headers):
        name = _WHITESPACE_RE.sub(" ", str(header).replace("\n", " ")).strip()
        if not name:
            name = f"col_{index + 1}"
        count = seen.get(name, 0) + 1
        seen[name] = count
        if count > 1:
            unique = f"{name}_{count}"
            while unique in seen:
                count += 1
                unique = f"{name}_{count}"
            seen[unique] = 1
            name = unique
        cleaned.append(name)

    if n_cols is not None:
        if len(cleaned) < n_cols:
            cleaned.extend(f"col_{i + 1}" for i in range(len(cleaned), n_cols))
        cleaned = cleaned[:n_cols]
    return cleaned


def _clean_cell(value: Any) -> str:
    """Turn a DataFrame cell into a compact, stripped string."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def _serialize_pairs(headers: Sequence[str], cells: Sequence[str]) -> str:
    """Serialize one row as ``Header: value | Header: value``."""
    return " | ".join(
        f"{header}: {cell}" for header, cell in zip(headers, cells, strict=False)
    )


def _make_chunk(
    *,
    table_id: str,
    page_num: int | None,
    row_index: int,
    line_num: int | None,
    n_rows: int,
    headers: Sequence[str],
    cells: Sequence[str],
    caption: str = "",
) -> dict[str, Any]:
    n_cols = len(headers)
    padded = list(cells[:n_cols]) + [""] * max(0, n_cols - len(cells))
    return {
        "table_id": table_id,
        "page_num": page_num,
        "row_index": row_index,
        "line_num": line_num,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "column_headers": list(headers),
        "row_cells": padded,
        "row_serialized": _serialize_pairs(headers, padded),
        "caption": caption,
    }


# ---------------------------------------------------------------------------
# Docling native tables
# ---------------------------------------------------------------------------


def _table_caption(table: Any, doc: Any) -> str:
    if doc is None or not hasattr(table, "caption_text"):
        return ""
    try:
        return _clean_cell(table.caption_text(doc))
    except Exception:
        return ""


def _table_page(table: Any) -> int | None:
    provenance = getattr(table, "prov", None) or []
    if not provenance:
        return None
    return getattr(provenance[0], "page_no", None)


def table_to_row_chunks(
    table: Any,
    doc: Any = None,
    table_id: str = "t1",
    *,
    include_caption: bool = True,
) -> list[dict[str, Any]]:
    """Turn one Docling ``TableItem`` into one chunk per body row."""
    frame = table.export_to_dataframe(doc=doc)
    if frame is None or frame.empty:
        return []

    headers = [_clean_cell(column) for column in frame.columns]
    body_cells = [
        [_clean_cell(value) for value in row]
        for row in frame.itertuples(index=False, name=None)
    ]

    # Docling already folds multi-row headers when it exports the grid, so we
    # must not apply the article's pipe-line heuristic here: it could mistake a
    # genuine all-text first data row for a sub-header and silently drop it.
    headers = normalize_headers(headers, len(headers))

    page_num = _table_page(table)
    caption = _table_caption(table, doc) if include_caption else ""
    n_rows = len(body_cells)

    return [
        _make_chunk(
            table_id=table_id,
            page_num=page_num,
            row_index=row_index,
            line_num=None,
            n_rows=n_rows,
            headers=headers,
            cells=cells,
            caption=caption,
        )
        for row_index, cells in enumerate(body_cells, start=1)
    ]


def document_to_row_chunks(
    doc: Any,
    *,
    include_caption: bool = True,
) -> pd.DataFrame:
    """Extract row-level chunks from every table of a Docling document."""
    chunks: list[dict[str, Any]] = []
    for table_index, table in enumerate(getattr(doc, "tables", []), start=1):
        chunks.extend(
            table_to_row_chunks(
                table,
                doc,
                table_id=f"t{table_index}",
                include_caption=include_caption,
            )
        )
    return pd.DataFrame(chunks, columns=ROW_CHUNK_COLUMNS)


# ---------------------------------------------------------------------------
# Retrieval demo and export helpers
# ---------------------------------------------------------------------------


def search_rows(
    row_df: pd.DataFrame,
    query: str,
    *,
    case_sensitive: bool = False,
    limit: int | None = None,
) -> pd.DataFrame:
    """Keyword-match a query against ``row_serialized``.

    This is deliberately a plain substring match: it illustrates the article's
    targeted-lookup case, it is not a full retrieval stack.
    """
    if row_df.empty or not query.strip():
        return row_df.head(0)

    mask = (
        row_df["row_serialized"]
        .astype(str)
        .str.contains(query, case=case_sensitive, regex=False, na=False)
    )
    hits = row_df.loc[mask]
    return hits.head(limit) if limit is not None else hits


def to_csv_ready(row_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with list-valued columns JSON-encoded for CSV output."""
    frame = row_df.copy()
    for column in LIST_COLUMNS:
        if column in frame.columns:
            frame[column] = frame[column].map(
                lambda value: json.dumps(
                    list(value) if isinstance(value, (list, tuple)) else value,
                    ensure_ascii=False,
                )
            )
    return frame


def write_row_chunks(
    row_df: pd.DataFrame,
    base_path: str | Path,
    *,
    formats: Sequence[str] = ("csv", "jsonl"),
) -> list[Path]:
    """Write row chunks to ``base_path`` with the requested formats."""
    base = Path(base_path)
    if base.suffix.lower() in {".csv", ".jsonl"}:
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for fmt in formats:
        if fmt == "csv":
            path = base.with_suffix(".csv")
            to_csv_ready(row_df).to_csv(path, index=False, encoding="utf-8")
        elif fmt == "jsonl":
            path = base.with_suffix(".jsonl")
            row_df.to_json(
                path,
                orient="records",
                lines=True,
                force_ascii=False,
            )
        else:
            raise ValueError(f"Unsupported output format: {fmt}")
        written.append(path)
    return written
