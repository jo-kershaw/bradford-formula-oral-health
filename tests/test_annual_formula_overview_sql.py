"""Check the structure of overview SQL without contacting the Bradford database."""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sql_backend import load_source_yearly_overview


class FakeEngine:
    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_annual_prescribing_overview_only_counts_formula_names(monkeypatch):
    sql = []

    def fake_read_sql(query, conn):
        statement = str(query)
        sql.append(statement)
        if "dbo.cb_Master_GA" in statement:
            return pd.DataFrame({"ga_year": [2020], "n_ga": [4]})
        return pd.DataFrame({"year": [2020], "n_prescriptions": [5], "n_children": [3]})

    monkeypatch.setattr(pd, "read_sql", fake_read_sql)
    tables = load_source_yearly_overview(FakeEngine())
    assert len(sql) == 2
    medication_sql = next(q for q in sql if "dbo.tbl_SRPrimaryCareMedication" in q)
    assert "dbo.medication_names_and_dmd_codes" in medication_sql
    assert "JOIN formula_names" in medication_sql
    assert "SELECT DISTINCT person_id, prescription_date" in medication_sql
    assert "COUNT(DISTINCT person_id) AS n_children" in medication_sql
    assert list(tables["formula_prescriptions_by_year"].columns) == ["year", "n_prescriptions"]
    assert list(tables["children_prescribed_formula_by_year"].columns) == ["year", "n_children"]
