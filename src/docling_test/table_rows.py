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
"""Cette liste définit les dix colonnes du DataFrame final.
table_id	Identifiant du tableau
page_num	Numéro de page PDF
row_index	Numéro de la ligne dans le tableau
line_num	Numéro de ligne source, ici non disponible
n_rows	Nombre de lignes de données du tableau
n_cols	Nombre de colonnes
column_headers	En-têtes des colonnes
row_cells	Valeurs des cellules
row_serialized	Ligne convertie en texte
caption	Légende du tableau"""

#: Columns holding Python lists; JSON-encoded when exporting to CSV.
LIST_COLUMNS = ("column_headers", "row_cells")

_WHITESPACE_RE = re.compile(
    r"\s+"
)  # outil de recherche qui reconnaît toutes les suites de caractères blancs.


def normalize_headers(
    headers: Sequence[str],  # noms des colonnes.
    n_cols: int | None = None,  # nombre de colonnes attendu, facultatif.
) -> list[str]:
    """Clean, de-duplicate and pad/truncate headers to ``n_cols`` columns."""
    cleaned: list[str] = []  # contiendra les en-têtes nettoyés
    seen: dict[str, int] = {}  # mémorisera le nombre d'occurrences de chaque nom

    for index, header in enumerate(headers):
        name = _WHITESPACE_RE.sub(" ", str(header).replace("\n", " ")).strip()
        if not name:  # Si un en-tête est vide, on lui attribue un nom automatique.
            name = f"col_{index + 1}"
        count = (
            seen.get(name, 0) + 1
        )  # .get() récupère la valeur associée à une clé. Si la clé n'existe pas, il retourne 0.
        seen[name] = count
        if count > 1:
            unique = f"{name}_{count}"
            while unique in seen:
                count += 1
                unique = f"{name}_{count}"
            seen[unique] = 1
            name = unique
        cleaned.append(name)

    if (
        n_cols is not None
    ):  # S'il manque des en-têtes, on ajoute des noms artificiels. S'il y en a trop, on les supprime.
        if len(cleaned) < n_cols:
            cleaned.extend(f"col_{i + 1}" for i in range(len(cleaned), n_cols))
        cleaned = cleaned[:n_cols]
    return cleaned


def _clean_cell(
    value: Any,
) -> str:  # Cette fonction nettoie une cellule d'un DataFrame.
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
        f"{header}: {cell}"
        for header, cell in zip(
            headers, cells, strict=False
        )  # zip() associe les éléments de deux séquences position par position.
    )


# Pour chaque paire, on construit une chaîne de caractères, puis on assemble les chaînes avec | comme séparateur.
# strict=False autorise des séquences de longueurs différentes : l'itération s'arrête à la séquence la plus courte.


def _make_chunk(
    *,  # impose d'utiliser des arguments nommés
    table_id: str,
    page_num: int | None,
    row_index: int,
    line_num: int | None,
    n_rows: int,
    headers: Sequence[str],
    cells: Sequence[str],
    caption: str = "",
) -> dict[str, Any]:
    n_cols = len(headers)  # Si on a trois en-têtes, on a trois colonnes
    padded = list(cells[:n_cols]) + [""] * max(
        0, n_cols - len(cells)
    )  # garantit que le nombre de cellules correspond au nombre de colonnes
    return {  # Chaque chunk est un dictionnaire Python
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


def _table_caption(
    table: Any, doc: Any
) -> str:  # Cette fonction récupère la légende du tableau. La légende peut améliorer la compréhension d'un chunk lorsqu'il est récupéré indépendamment du tableau original.
    if (
        doc is None or not hasattr(table, "caption_text")
    ):  # vérifie que le document existe et que l'objet table possède une méthode caption_text
        return ""
    try:
        return _clean_cell(table.caption_text(doc))
    except Exception:
        return ""  # Si une erreur survient, retourne une chaîne vide


def _table_page(table: Any) -> int | None:
    provenance = (
        getattr(table, "prov", None) or []
    )  # getattr() récupère l'attribut prov ; s'il n'existe pas, il retourne None. Remplace une valeur absente ou vide par une liste vide.
    if not provenance:
        return None
    return getattr(provenance[0], "page_no", None)


# La provenance permet de conserver la page PDF d'où provient le tableau.


def table_to_row_chunks(
    table: Any,
    doc: Any = None,
    table_id: str = "t1",
    *,
    include_caption: bool = True,
) -> list[dict[str, Any]]:
    """Turn one Docling ``TableItem`` into one chunk per body row. Cette fonction transforme un seul tableau Docling en plusieurs chunks."""
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
