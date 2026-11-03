# docling-test

Row-level table chunks for RAG, built on top of [Docling](https://github.com/docling-project/docling).

Instead of indexing a whole table as one chunk, each **body row** becomes its
own retrievable chunk, with the column headers copied into the text:

```text
Layer Type: Self-Attention | Complexity per Layer: O(n^2)
```

That way a targeted question ("what is the complexity of self-attention?")
retrieves the one row that answers it, not the entire table.

This is an implementation of the approach described in
[Retrieve One Row from a Table, Not the Whole Table](https://towardsdatascience.com/retrieve-one-row-from-a-table-not-the-whole-table-row-level-chunks-for-rag/).

## Usage

```bash
# Extract every table body row to output/<pdf-stem>_rows.jsonl
uv run python scripts/table_row_chunks.py data/raw/IPCC_AR6_WGI_SPM-25-29.pdf

# Keyword search over the extracted rows
uv run python scripts/table_row_chunks.py \
    data/raw/IPCC_AR6_WGI_SPM-25-29.pdf \
    --query "1.5"

# Explicit output base path
uv run python scripts/table_row_chunks.py report.pdf \
    --out output/report_rows
```

The script writes JSONL by default. The `--format` option is currently
commented out in `scripts/table_row_chunks.py`; re-enable it there to export
CSV or both formats.

Options:

| Option | Description |
| --- | --- |
| `--out PATH` | Output base path (`.jsonl` appended). Default: `output/<pdf-stem>_rows`. |
| `--query TEXT` | Run a literal keyword search on `row_serialized` and print hits. |
| `--limit N` | Maximum number of query hits to print. |
| `--no-caption` | Do not copy table captions into the chunks. |

## Output columns

| Column | Content |
| --- | --- |
| `table_id` | Table identifier within the document (`t1`, `t2`, ...). |
| `page_num` | Page number of the table (1-based). |
| `row_index` | Body-row index within the table (1-based). |
| `line_num` | Kept for schema compatibility; always empty. |
| `n_rows` | Number of body rows in the table. |
| `n_cols` | Number of columns. |
| `column_headers` | List of column labels. |
| `row_cells` | List of cell values for this row. |
| `row_serialized` | `Header: value \| Header: value \| ...`, the retrieval text. |
| `caption` | Table caption when Docling detects one. |

## Python API

```python
from docling.document_converter import DocumentConverter
from docling_test.table_rows import document_to_row_chunks, search_rows

result = DocumentConverter().convert("data/raw/IPCC_AR6_WGI_SPM-25-29.pdf")
rows = document_to_row_chunks(result.document)

hits = search_rows(rows, "1.5")
print(hits[["page_num", "row_index", "row_serialized"]])
```

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
