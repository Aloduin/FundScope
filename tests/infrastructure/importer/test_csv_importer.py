"""Tests for infrastructure/importer/csv_importer.py"""
from __future__ import annotations

import csv
import io

import pytest

from infrastructure.importer.csv_importer import CsvImportResult, parse_csv


# ---------------------------------------------------------------------------
# Helpers to build CSV bytes
# ---------------------------------------------------------------------------

def _make_csv(
    rows: list[dict],
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8",
) -> bytes:
    """Serialise a list of dicts to CSV bytes."""
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode(encoding)


# ---------------------------------------------------------------------------
# Source-type detection
# ---------------------------------------------------------------------------

class TestSourceTypeDetection:
    """parse_csv correctly identifies the CSV format."""

    def test_standard_english_columns(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "TestFund", "amount": "1000"},
        ])
        result = parse_csv(data)
        assert result.source_type == "standard"

    def test_alipay_format(self):
        data = _make_csv([
            {"基金代码": "000001", "基金名称": "测试基金", "市值(元)": "2000"},
        ])
        result = parse_csv(data)
        assert result.source_type == "alipay"

    def test_tiantian_format(self):
        data = _make_csv([
            {"基金代码": "000001", "基金名称": "测试基金", "最新市值": "3000"},
        ])
        result = parse_csv(data)
        assert result.source_type == "tiantian"

    def test_unknown_format(self):
        data = _make_csv([
            {"代码": "000001", "金额": "1000"},
        ])
        result = parse_csv(data)
        assert result.source_type == "unknown"


# ---------------------------------------------------------------------------
# Column normalisation
# ---------------------------------------------------------------------------

class TestColumnNormalisation:
    """Column synonyms are mapped to canonical names."""

    def test_chinese_columns_normalised(self):
        data = _make_csv([
            {"基金代码": "000001", "基金名称": "测试基金", "持有金额": "500"},
        ])
        result = parse_csv(data)
        assert len(result.valid_rows) == 1
        row = result.valid_rows[0]
        assert row["fund_code"] == "000001"
        assert row["fund_name"] == "测试基金"
        assert row["amount"] == pytest.approx(500.0)

    def test_detected_columns_are_original(self):
        """detected_columns must keep the original (un-normalised) header."""
        data = _make_csv([
            {"基金代码": "000001", "基金名称": "测试基金", "市值(元)": "1000"},
        ])
        result = parse_csv(data)
        assert "基金代码" in result.detected_columns
        assert "market_value" not in result.detected_columns

    def test_normalized_columns_mapping(self):
        """normalized_columns maps original → target."""
        data = _make_csv([
            {"基金代码": "000001", "基金名称": "测试基金", "市值(元)": "1000"},
        ])
        result = parse_csv(data)
        assert result.normalized_columns.get("基金代码") == "fund_code"
        assert result.normalized_columns.get("基金名称") == "fund_name"


# ---------------------------------------------------------------------------
# Amount cleaning
# ---------------------------------------------------------------------------

class TestAmountCleaning:
    """Various raw amount representations are cleaned correctly."""

    def _single_amount_row(self, amount_str: str) -> bytes:
        return _make_csv([
            {"fund_code": "000001", "fund_name": "F", "amount": amount_str},
        ])

    def test_plain_integer(self):
        result = parse_csv(self._single_amount_row("1000"))
        assert result.valid_rows[0]["amount"] == pytest.approx(1000.0)

    def test_decimal(self):
        result = parse_csv(self._single_amount_row("1234.56"))
        assert result.valid_rows[0]["amount"] == pytest.approx(1234.56)

    def test_thousands_separator(self):
        result = parse_csv(self._single_amount_row("1,234.56"))
        assert result.valid_rows[0]["amount"] == pytest.approx(1234.56)

    def test_currency_symbol_rmb(self):
        result = parse_csv(self._single_amount_row("￥1000"))
        assert result.valid_rows[0]["amount"] == pytest.approx(1000.0)

    def test_currency_symbol_dollar(self):
        result = parse_csv(self._single_amount_row("$500.00"))
        assert result.valid_rows[0]["amount"] == pytest.approx(500.0)

    def test_empty_amount_is_skipped(self):
        result = parse_csv(self._single_amount_row(""))
        assert len(result.valid_rows) == 0
        assert len(result.skipped_rows) == 1
        assert "amount" in result.skipped_rows[0]["reason"]

    def test_placeholder_dash_is_skipped(self):
        result = parse_csv(self._single_amount_row("--"))
        assert len(result.valid_rows) == 0
        assert len(result.skipped_rows) == 1

    def test_non_numeric_is_skipped(self):
        result = parse_csv(self._single_amount_row("N/A"))
        assert len(result.valid_rows) == 0
        assert len(result.skipped_rows) == 1

    def test_zero_amount_is_skipped(self):
        result = parse_csv(self._single_amount_row("0"))
        assert len(result.valid_rows) == 0
        assert len(result.skipped_rows) == 1

    def test_negative_amount_is_skipped(self):
        result = parse_csv(self._single_amount_row("-100"))
        assert len(result.valid_rows) == 0
        assert len(result.skipped_rows) == 1


# ---------------------------------------------------------------------------
# Row merging
# ---------------------------------------------------------------------------

class TestRowMerging:
    """Duplicate fund_code rows are merged by summing amounts."""

    def test_duplicate_codes_merged(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "FundA", "amount": "1000"},
            {"fund_code": "000001", "fund_name": "FundA", "amount": "500"},
        ])
        result = parse_csv(data)
        assert len(result.valid_rows) == 2         # raw rows preserved
        assert len(result.merged_rows) == 1        # merged to one
        assert result.merged_rows[0]["amount"] == pytest.approx(1500.0)

    def test_different_codes_not_merged(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "FundA", "amount": "1000"},
            {"fund_code": "000002", "fund_name": "FundB", "amount": "2000"},
        ])
        result = parse_csv(data)
        assert len(result.merged_rows) == 2

    def test_name_mismatch_produces_warning(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "FundA", "amount": "1000"},
            {"fund_code": "000001", "fund_name": "FundA_RENAMED", "amount": "500"},
        ])
        result = parse_csv(data)
        assert any("000001" in w for w in result.warnings)

    def test_merged_keeps_first_name(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "Original", "amount": "1000"},
            {"fund_code": "000001", "fund_name": "Updated", "amount": "500"},
        ])
        result = parse_csv(data)
        assert result.merged_rows[0]["fund_name"] == "Original"


# ---------------------------------------------------------------------------
# Skipped rows
# ---------------------------------------------------------------------------

class TestSkippedRows:
    """Rows with missing or invalid fields are recorded in skipped_rows."""

    def test_missing_fund_code_is_skipped(self):
        data = _make_csv([
            {"fund_code": "", "fund_name": "FundA", "amount": "1000"},
        ])
        result = parse_csv(data)
        assert len(result.skipped_rows) == 1
        assert "fund_code" in result.skipped_rows[0]["reason"]

    def test_skipped_row_contains_raw_row(self):
        data = _make_csv([
            {"fund_code": "", "fund_name": "FundA", "amount": "1000"},
        ])
        result = parse_csv(data)
        assert "raw_row" in result.skipped_rows[0]
        assert isinstance(result.skipped_rows[0]["raw_row"], dict)

    def test_skipped_row_contains_row_num(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "FundA", "amount": "1000"},
            {"fund_code": "", "fund_name": "FundB", "amount": "500"},
        ])
        result = parse_csv(data)
        # Second data row → row_num 3 (1 header + 1 valid + 1 skipped)
        assert result.skipped_rows[0]["row_num"] == 3

    def test_mixed_valid_and_invalid_rows(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "FundA", "amount": "1000"},
            {"fund_code": "", "fund_name": "FundB", "amount": "500"},
            {"fund_code": "000003", "fund_name": "FundC", "amount": "--"},
            {"fund_code": "000004", "fund_name": "FundD", "amount": "2000"},
        ])
        result = parse_csv(data)
        assert len(result.valid_rows) == 2
        assert len(result.skipped_rows) == 2


# ---------------------------------------------------------------------------
# Encoding handling
# ---------------------------------------------------------------------------

class TestEncoding:
    """Files encoded in UTF-8 and GBK are handled transparently."""

    def test_utf8_encoding(self):
        data = _make_csv(
            [{"fund_code": "000001", "fund_name": "华夏基金", "amount": "1000"}],
            encoding="utf-8",
        )
        result = parse_csv(data)
        assert result.valid_rows[0]["fund_name"] == "华夏基金"

    def test_gbk_encoding(self):
        data = _make_csv(
            [{"基金代码": "000001", "基金名称": "华夏基金", "市值(元)": "1000"}],
            encoding="gbk",
        )
        result = parse_csv(data)
        assert result.valid_rows[0]["fund_name"] == "华夏基金"

    def test_invalid_encoding_raises(self):
        with pytest.raises(ValueError, match="Cannot decode"):
            # Craft bytes that are invalid in both UTF-8 and GBK
            parse_csv(b"\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f")


# ---------------------------------------------------------------------------
# CsvImportResult structure
# ---------------------------------------------------------------------------

class TestCsvImportResult:
    """The returned dataclass has the expected fields."""

    def test_result_fields_present(self):
        data = _make_csv([
            {"fund_code": "000001", "fund_name": "FundA", "amount": "1000"},
        ])
        result = parse_csv(data)
        assert isinstance(result, CsvImportResult)
        assert hasattr(result, "valid_rows")
        assert hasattr(result, "merged_rows")
        assert hasattr(result, "skipped_rows")
        assert hasattr(result, "warnings")
        assert hasattr(result, "detected_columns")
        assert hasattr(result, "normalized_columns")
        assert hasattr(result, "source_type")

    def test_empty_csv_produces_empty_result(self):
        data = _make_csv([], fieldnames=["fund_code", "fund_name", "amount"])
        result = parse_csv(data)
        assert result.valid_rows == []
        assert result.merged_rows == []
        assert result.skipped_rows == []
