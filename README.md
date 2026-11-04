# docling-test

[![Status](https://img.shields.io/badge/Status-Live-brightgreen)](https://github.com/dbonneels/docling)

Row-level table chunks for RAG, built on top of [Docling](https://github.com/docling-project/docling).

Instead of indexing a whole table as one chunk, each **body row** becomes its
own retrievable chunk, with the column headers copied into the text:

```text
Global Warming Between 1850-1900 and 2010-2019 (°C).1.07 (0.8-1.3; likely range).Approximate global warming relative to 1850-1900 until temperature limit (°C): 1.5 | Global Warming Between 1850-1900 and 2010-2019 (°C).1.07 (0.8-1.3; likely range).a Additional global warming relative 2010-2019 until perature limit (°C): 0.43 | Historical Cumulative CO2 Emissions from 1850 to 2019 (GtCO2).2390 (± 240; likely range).to tem- Estimated from the Likelihood to temperature 17%: 900 | Historical Cumulative CO2 Emissions from 1850 to 2019 (GtCO2).2390 (± 240; likely range).remaining beginning of 2020 of limiting global limit b 33%: 650 | Historical Cumulative CO2 Emissions from 1850 to 2019 (GtCO2).2390 (± 240; likely range).budgets (GtCO2) warming 50%: 500 | Historical Cumulative CO2 Emissions from 1850 to 2019 (GtCO2).2390 (± 240; likely range).67%: 400 | Historical Cumulative CO2 Emissions from 1850 to 2019 (GtCO2).2390 (± 240; likely range).83%: 300 | Historical Cumulative CO2 Emissions from 1850 to 2019 (GtCO2).Variations in reductions in non-CO2 emissions c.Variations in reductions in non-CO2 emissions c: Higher or lower reductions in accompanying non-CO2 emissions can increase or decrease the values on the left by 220 GtCO2 or more
```

That way a targeted question retrieves the one row that answers it, not the entire table.

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
