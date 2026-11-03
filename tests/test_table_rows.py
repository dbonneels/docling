"""Unit tests for row-level table chunks."""

import unittest
from types import SimpleNamespace

import pandas as pd

from docling_test.table_rows import (
    document_to_row_chunks,
    normalize_headers,
    search_rows,
    to_csv_ready,
)


class HeaderTests(unittest.TestCase):
    def test_normalize_deduplicates_and_pads(self) -> None:
        self.assertEqual(
            normalize_headers(["A", "A", "", "B"], 5),
            ["A", "A_2", "col_3", "B", "col_5"],
        )


class DoclingPathTests(unittest.TestCase):
    def test_table_to_row_chunks_with_fake_docling_table(self) -> None:
        class FakeTable:
            prov = [SimpleNamespace(page_no=5)]

            def export_to_dataframe(self, doc=None):
                return pd.DataFrame({"Event": ["Theft"], "Cap": ["25,000 EUR"]})

            def caption_text(self, doc=None):
                return "Guarantees"

        class FakeDoc:
            tables = [FakeTable()]

        chunks = document_to_row_chunks(FakeDoc())

        self.assertEqual(len(chunks), 1)
        row = chunks.iloc[0]
        self.assertEqual(row["table_id"], "t1")
        self.assertEqual(row["page_num"], 5)
        self.assertEqual(row["row_serialized"], "Event: Theft | Cap: 25,000 EUR")
        self.assertEqual(row["caption"], "Guarantees")


class SearchAndExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            [
                {
                    "table_id": "t1",
                    "page_num": 1,
                    "row_index": 1,
                    "line_num": None,
                    "n_rows": 2,
                    "n_cols": 2,
                    "column_headers": ["Event", "Cap"],
                    "row_cells": ["Theft", "25,000 EUR"],
                    "row_serialized": "Event: Theft | Cap: 25,000 EUR",
                    "caption": "",
                },
                {
                    "table_id": "t1",
                    "page_num": 1,
                    "row_index": 2,
                    "line_num": None,
                    "n_rows": 2,
                    "n_cols": 2,
                    "column_headers": ["Event", "Cap"],
                    "row_cells": ["Fire", "10,000 EUR"],
                    "row_serialized": "Event: Fire | Cap: 10,000 EUR",
                    "caption": "",
                },
            ]
        )

    def test_search_returns_one_row(self) -> None:
        hits = search_rows(self.frame, "theft")
        self.assertEqual(len(hits), 1)
        self.assertIn("Theft", hits.iloc[0]["row_serialized"])

    def test_search_respects_limit(self) -> None:
        hits = search_rows(self.frame, "Event", limit=1)
        self.assertEqual(len(hits), 1)

    def test_csv_ready_json_encodes_lists(self) -> None:
        ready = to_csv_ready(self.frame)
        self.assertEqual(ready.loc[0, "column_headers"], '["Event", "Cap"]')
        self.assertEqual(ready.loc[0, "row_cells"], '["Theft", "25,000 EUR"]')


if __name__ == "__main__":
    unittest.main()
