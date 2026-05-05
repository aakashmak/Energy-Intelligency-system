"""
Tests for data collection layer.
DB tests mock psycopg2 directly — no supabase-py SDK involved.
Run: pytest src/tests/ -v
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from src.data.validate import validate_production, check_coverage


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def prod_df():
    """Valid production DataFrame (value col — matches DB schema)."""
    return pd.DataFrame({
        "region":    ["Permian", "Permian", "Bakken", "Bakken"],
        "commodity": ["oil",     "oil",     "gas",    "gas"],
        "period":    pd.to_datetime(["2023-01-01", "2023-02-01",
                                     "2023-01-01", "2023-02-01"]),
        "value":     [600.0, 620.0, 150.0, 160.0],
        "source":    ["EIA_basin"] * 4,
    })


@pytest.fixture
def validate_df():
    """80-row production DF using 'production' col (validate_production expects this)."""
    return pd.DataFrame({
        "region":     ["Permian"] * 80,
        "commodity":  ["oil"] * 80,
        "period":     pd.date_range("2017-01-01", periods=80, freq="MS"),
        "production": [500.0 + i for i in range(80)],
        "source":     ["EIA_basin"] * 80,
    })


# ── validate_production ────────────────────────────────────────────────────────

class TestValidateProduction:

    def test_passes_clean_data(self, validate_df):
        assert len(validate_production(validate_df)) == 80

    def test_removes_null_production(self):
        df = pd.DataFrame({
            "region":     ["Permian", "Permian"],
            "commodity":  ["oil", "oil"],
            "period":     pd.to_datetime(["2023-01-01", "2023-02-01"]),
            "production": [500.0, None],
            "source":     ["EIA_basin", "EIA_basin"],
        })
        assert len(validate_production(df)) == 1

    def test_removes_negative_production(self):
        df = pd.DataFrame({
            "region":     ["Permian"],
            "commodity":  ["oil"],
            "period":     pd.to_datetime(["2023-01-01"]),
            "production": [-10.0],
            "source":     ["EIA_basin"],
        })
        assert len(validate_production(df)) == 0

    def test_raises_on_missing_columns(self):
        with pytest.raises(ValueError, match="missing required columns"):
            validate_production(pd.DataFrame({"region": ["Permian"]}))

    def test_raises_on_empty_dataframe(self):
        with pytest.raises(ValueError, match="empty"):
            validate_production(
                pd.DataFrame(columns=["region", "commodity", "period", "production"])
            )

    def test_coerces_string_period(self):
        df = pd.DataFrame({
            "region":     ["Bakken"],
            "commodity":  ["oil"],
            "period":     ["2022-06-01"],
            "production": [300.0],
            "source":     ["EIA_basin"],
        })
        assert len(validate_production(df)) == 1


# ── check_coverage ─────────────────────────────────────────────────────────────

class TestCheckCoverage:

    def _full_df(self):
        rows = []
        for r in ["Permian", "Bakken", "Eagle Ford", "Appalachia", "Gulf Coast"]:
            for c in ["oil", "gas"]:
                rows.append({"region": r, "commodity": c,
                             "period": pd.Timestamp("2023-01-01"), "production": 100.0})
        return pd.DataFrame(rows)

    def test_full_coverage_no_missing(self):
        cov = check_coverage(self._full_df())
        assert cov["missing_series"] == []
        assert cov["regions_covered"] == 5

    def test_detects_missing_series(self):
        df = pd.DataFrame({
            "region": ["Permian"], "commodity": ["oil"],
            "period": [pd.Timestamp("2023-01-01")], "production": [500.0],
        })
        assert len(check_coverage(df)["missing_series"]) == 9

    def test_date_range_correct(self):
        df = pd.DataFrame({
            "region": ["Permian", "Permian"], "commodity": ["oil", "oil"],
            "period": pd.to_datetime(["2020-01-01", "2023-12-01"]),
            "production": [400.0, 500.0],
        })
        cov = check_coverage(df)
        assert cov["date_range"]["min"] == "2020-01-01"
        assert cov["date_range"]["max"] == "2023-12-01"


# ── DB — upsert_production (mocked psycopg2) ──────────────────────────────────

class TestUpsertProduction:

    def _make_mock_conn(self):
        """Build a mock psycopg2 connection with cursor context manager."""
        mock_cur  = MagicMock()
        mock_ctx  = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_ctx
        return mock_conn, mock_cur

    @patch("src.data.db.get_connection")
    def test_upsert_returns_row_count(self, mock_get_conn, prod_df):
        mock_conn, _ = self._make_mock_conn()
        mock_get_conn.return_value = mock_conn
        from src.data.db import upsert_production
        assert upsert_production(prod_df) == 4

    @patch("src.data.db.get_connection")
    def test_upsert_empty_skips_db(self, mock_get_conn):
        from src.data.db import upsert_production
        assert upsert_production(pd.DataFrame()) == 0
        mock_get_conn.assert_not_called()

    def test_upsert_missing_cols_raises(self):
        from src.data.db import upsert_production
        with pytest.raises(ValueError, match="missing columns"):
            upsert_production(pd.DataFrame({"region": ["Permian"]}))

    @patch("src.data.db.get_connection")
    def test_upsert_rollback_on_error(self, mock_get_conn, prod_df):
        mock_conn, mock_cur = self._make_mock_conn()
        mock_cur.side_effect = Exception("DB error")
        mock_get_conn.return_value = mock_conn
        from src.data.db import upsert_production
        with pytest.raises(Exception, match="DB error"):
            upsert_production(prod_df)
        mock_conn.rollback.assert_called_once()


# ── DB — read_production (mocked pd.read_sql_query) ───────────────────────────

class TestReadProduction:

    @patch("src.data.db.get_connection")
    @patch("src.data.db.pd.read_sql_query")
    def test_read_all_returns_dataframe(self, mock_read, mock_conn):
        mock_read.return_value = pd.DataFrame({
            "region": ["Permian"], "commodity": ["oil"],
            "period": ["2023-01-01"], "value": [600.0], "source": ["EIA_basin"],
        })
        from src.data.db import read_production
        df = read_production()
        assert len(df) == 1
        assert list(df.columns) == ["region", "commodity", "period", "value", "source"]

    @patch("src.data.db.get_connection")
    @patch("src.data.db.pd.read_sql_query")
    def test_read_with_filters(self, mock_read, mock_conn):
        mock_read.return_value = pd.DataFrame({
            "region": ["Bakken"], "commodity": ["gas"],
            "period": ["2023-06-01"], "value": [140.0], "source": ["EIA_basin"],
        })
        from src.data.db import read_production
        df = read_production(region="Bakken", commodity="gas")
        assert df.iloc[0]["region"] == "Bakken"


# ── EIA fetcher (mocked HTTP) ──────────────────────────────────────────────────

class TestEIAFetcher:

    def _mock_eia_response(self, values):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "response": {
                "data": [
                    {"period": f"2023-{str(i+1).zfill(2)}", "value": str(v)}
                    for i, v in enumerate(values)
                ]
            }
        }
        return mock

    @patch("src.data.eia_fetcher.requests.get")
    def test_fetch_series_returns_dataframe(self, mock_get):
        mock_get.return_value = self._mock_eia_response([500, 510, 520])
        from src.data import eia_fetcher
        eia_fetcher.API_KEY = "test_key"
        df = eia_fetcher.fetch_series("PET.TEST.M")
        assert len(df) == 3
        assert set(df.columns) == {"period", "production"}

    @patch("src.data.eia_fetcher.requests.get")
    def test_fetch_series_empty_response(self, mock_get):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {"response": {"data": []}}
        mock_get.return_value = mock
        from src.data import eia_fetcher
        eia_fetcher.API_KEY = "test_key"
        assert eia_fetcher.fetch_series("PET.EMPTY.M").empty

    def test_fetch_series_raises_without_key(self):
        from src.data import eia_fetcher
        eia_fetcher.API_KEY = ""
        with pytest.raises(ValueError, match="EIA_API_KEY"):
            eia_fetcher.fetch_series("PET.TEST.M")
