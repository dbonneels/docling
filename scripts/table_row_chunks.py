#!/usr/bin/env python
"""Extract row-level table chunks from a PDF and optionally search them.

Examples
--------
Extract every table row to ``output/<pdf-stem>_rows.csv`` and ``.jsonl``::

    uv run python scripts/table_row_chunks.py \
        data/raw/IPCC_AR6_WGI_SPM-25-29.pdf

Filter the extracted rows with a keyword query::

    uv run python scripts/table_row_chunks.py \
        data/raw/IPCC_AR6_WGI_SPM-25-29.pdf \
        --query "1.5"

Choose an explicit output base path::

    uv run python scripts/table_row_chunks.py report.pdf --out output/my_rows --format csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from docling_test.table_rows import (
    document_to_row_chunks,
    search_rows,
    write_row_chunks,
)

#: Output format used when --format is disabled.
DEFAULT_FORMAT = "jsonl"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a PDF with Docling and emit one retrievable chunk per "
            "table body row (headers travel with the values)."
        )
    )
    parser.add_argument("pdf", type=Path, help="Path to the input PDF.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output base path (extension optional). Defaults to "
            "'output/<pdf-stem>_rows'."
        ),
    )
    # parser.add_argument(
    #     "--format",
    #     choices=("csv", "jsonl", "both"),
    #     default="both",
    #     help="Output format(s). Default: both.",
    # )
    parser.add_argument(
        "--query",
        default=None,
        help="Optional keyword query to run against 'row_serialized'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of query hits to display.",
    )
    parser.add_argument(
        "--no-caption",
        action="store_true",
        help="Do not copy table captions into the row chunks.",
    )
    return parser.parse_args(argv)


def _formats(value: str) -> tuple[str, ...]:
    """Kept for when the --format option is re-enabled."""
    return ("csv", "jsonl") if value == "both" else (value,)


def _print_hits(hits: pd.DataFrame) -> None:
    if hits.empty:
        print("No matching row.")
        return

    print(f"\n{len(hits)} matching row(s):\n")
    for _, row in hits.iterrows():
        print(
            f"[{row['table_id']} page {row['page_num']} "
            f"row {row['row_index']}/{row['n_rows']}]"
        )
        print(f"  {row['row_serialized']}")
        if row.get("caption"):
            print(f"  caption: {row['caption']}")
        print()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.pdf.is_file():
        print(f"Input PDF not found: {args.pdf}", file=sys.stderr)
        return 2

    # Lazy import : Docling n'est importé que lorsque la conversion est réellement demandée.
    from docling.document_converter import DocumentConverter

    print(f"Converting {args.pdf} with Docling ...", file=sys.stderr)
    result = DocumentConverter().convert(str(args.pdf))
    document = result.document

    """La fonction document_to_row_chunks() :
        1. Parcourt les tableaux du document Docling.
        2. Exporte chaque tableau en DataFrame.
        3. Récupère les en-têtes des colonnes.
        4. Parcourt les lignes du tableau.
        5. Crée un chunk pour chaque ligne.
        6. Retourne un DataFrame Pandas contenant tous les chunks."""

    row_df = document_to_row_chunks(
        document,
        include_caption=not args.no_caption,  # les légendes sont inclues
    )

    n_tables = len(
        getattr(document, "tables", [])
    )  # Récupère l'attribut tables de document. Si cet attribut n'existe pas, retourne une liste vide [].
    print(
        f"Extracted {len(row_df)} row chunk(s) from {n_tables} table(s).",
        file=sys.stderr,
    )

    print(row_df.shape)
    print(row_df.columns.tolist())

    print(
        row_df[["table_id", "page_num", "row_index", "row_serialized"]]
        .head(10)
        .to_string(index=False)
    )

    # base_path = args.out or Path("output") / f"{args.pdf.stem}_rows"
    base_path = Path("output") / f"{args.pdf.stem}_rows"
    written = write_row_chunks(
        row_df,
        base_path,
        formats=_formats(DEFAULT_FORMAT),
    )
    for path in written:
        print(f"Wrote {path}")

    # if args.query:
    #     hits = search_rows(row_df, args.query, limit=args.limit)
    #     _print_hits(hits)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
