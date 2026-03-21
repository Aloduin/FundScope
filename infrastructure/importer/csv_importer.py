"""CSV importer for fund portfolio data.

Supports multiple CSV formats (Alipay, Tiantian, standard English, unknown).
Handles encoding detection, column normalization, amount cleaning, and row merging.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pandas as pd


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CsvImportResult:
    valid_rows: list[dict]         # cleaned valid rows
    merged_rows: list[dict]        # merged by fund_code (for final import preview)
    skipped_rows: list[dict]       # skipped rows with reason and raw_row
    warnings: list[str]            # non-fatal warnings (e.g. name mismatch)
    detected_columns: list[str]    # original CSV column names
    normalized_columns: dict       # column name mapping {original: target}
    source_type: str               # "alipay" | "tiantian" | "standard" | "unknown"


# ---------------------------------------------------------------------------
# Column synonym table
# ---------------------------------------------------------------------------

# Maps each *target* field name to the set of recognised synonym strings
# (after normalisation is already applied to the CSV header).
_COLUMN_SYNONYMS: dict[str, list[str]] = {
    "fund_code": [
        "基金代码",
        "fund_code",
    ],
    "fund_name": [
        "基金名称",
        "基金简称",
        "fund_name",
    ],
    "amount": [
        "市值(元)",
        "市值（元）",
        "持有金额",
        "最新市值",
        "当前金额",
        "amount",
    ],
}

# source_type detection — checked against *normalised* column names
_ALIPAY_MARKERS = {"市值(元)", "持有金额"}
_TIANTIAN_MARKERS = {"最新市值", "当前金额"}
_STANDARD_COLS = {"fund_code", "fund_name", "amount"}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_FULLWIDTH_MAP = str.maketrans(
    # full-width digits 0-9
    "０１２３４５６７８９"
    # full-width upper A-Z
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    # full-width lower a-z
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    # full-width left / right parentheses
    "（）",
    # half-width equivalents
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "()",
)


def _normalize_col(name: str) -> str:
    """Apply all column normalisation rules to a single header string."""
    # 1. Strip leading/trailing whitespace
    name = name.strip()
    # 2. Remove newlines
    name = name.replace("\n", "").replace("\r", "")
    # 3. Normalize full-width to half-width
    name = name.translate(_FULLWIDTH_MAP)
    return name


def _build_col_mapping(raw_columns: list[str]) -> dict[str, str]:
    """Return {original_col: target_field} for columns that match a synonym."""
    mapping: dict[str, str] = {}
    for raw in raw_columns:
        normalised = _normalize_col(raw)
        for target, synonyms in _COLUMN_SYNONYMS.items():
            if normalised in synonyms:
                mapping[raw] = target
                break
    return mapping


# ---------------------------------------------------------------------------
# Amount cleaning
# ---------------------------------------------------------------------------

_CURRENCY_RE = re.compile(r"[￥¥$]")


def _clean_amount(raw: object) -> tuple[float | None, str | None]:
    """Return (float_value, error_reason) for a raw amount cell.

    Returns (None, reason) when the value should cause the row to be skipped.
    """
    if raw is None:
        return None, "amount is empty"

    text = str(raw).strip()

    # Handle placeholder / empty values
    if text in ("", "--", "-", "nan", "NaN"):
        return None, "amount is empty or placeholder"

    # Remove currency symbols
    text = _CURRENCY_RE.sub("", text)

    # Remove thousands-separator commas (only when surrounded by digits)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)

    try:
        value = float(text)
    except ValueError:
        return None, f"amount cannot be parsed: '{raw}'"

    if value <= 0:
        return None, "amount <= 0"

    return value, None


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------

def _decode(file_content: bytes) -> str:
    """Try UTF-8 then GBK; raise ValueError if both fail."""
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return file_content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(
        "Cannot decode file content: tried UTF-8 and GBK but both failed."
    )


# ---------------------------------------------------------------------------
# Source type detection
# ---------------------------------------------------------------------------

def _detect_source_type(normalised_cols: set[str]) -> str:
    """Detect the CSV format based on normalised column names."""
    if normalised_cols & _ALIPAY_MARKERS:
        return "alipay"
    if normalised_cols & _TIANTIAN_MARKERS:
        return "tiantian"
    if _STANDARD_COLS <= normalised_cols:
        return "standard"
    return "unknown"


# ---------------------------------------------------------------------------
# Main parsing function
# ---------------------------------------------------------------------------

def parse_csv(file_content: bytes) -> CsvImportResult:
    """Parse a fund portfolio CSV file and return a structured result.

    Args:
        file_content: Raw bytes of the CSV file.

    Returns:
        CsvImportResult with valid rows, merged rows, skipped rows, warnings,
        and metadata about the detected format.

    Raises:
        ValueError: If the file cannot be decoded.
    """
    text = _decode(file_content)

    df_raw = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)

    # --- detected columns (original) ---
    detected_columns: list[str] = list(df_raw.columns)

    # --- build normalised column mapping ---
    normalized_columns: dict[str, str] = _build_col_mapping(detected_columns)

    # --- rename columns to target names ---
    df = df_raw.rename(columns=normalized_columns)

    # --- detect source type (use normalised column names) ---
    normalised_col_set: set[str] = {
        _normalize_col(c) for c in detected_columns
    }
    source_type = _detect_source_type(normalised_col_set)

    # --- process rows ---
    valid_rows: list[dict] = []
    skipped_rows: list[dict] = []
    warnings: list[str] = []

    for i, row in df.iterrows():
        row_num = int(i) + 2  # 1-based, +1 for header row
        raw_row = dict(df_raw.iloc[int(i)])  # original column names

        fund_code_val = row.get("fund_code", "") if "fund_code" in df.columns else ""
        fund_name_val = row.get("fund_name", "") if "fund_name" in df.columns else ""
        amount_raw = row.get("amount", "") if "amount" in df.columns else ""

        fund_code = str(fund_code_val).strip() if fund_code_val is not None else ""
        fund_name = str(fund_name_val).strip() if fund_name_val is not None else ""

        # Missing fund_code
        if not fund_code or fund_code in ("", "nan"):
            skipped_rows.append({
                "row_num": row_num,
                "reason": "missing fund_code",
                "raw_row": raw_row,
            })
            continue

        # Clean amount
        amount_value, amount_error = _clean_amount(amount_raw)
        if amount_error is not None:
            skipped_rows.append({
                "row_num": row_num,
                "reason": amount_error,
                "raw_row": raw_row,
            })
            continue

        valid_rows.append({
            "row_num": row_num,
            "fund_code": fund_code,
            "fund_name": fund_name,
            "raw_amount": str(amount_raw).strip(),
            "amount": amount_value,
        })

    # --- merge valid rows by fund_code ---
    merged_rows = _merge_by_fund_code(valid_rows, warnings)

    return CsvImportResult(
        valid_rows=valid_rows,
        merged_rows=merged_rows,
        skipped_rows=skipped_rows,
        warnings=warnings,
        detected_columns=detected_columns,
        normalized_columns=normalized_columns,
        source_type=source_type,
    )


# ---------------------------------------------------------------------------
# Public class interface
# ---------------------------------------------------------------------------


class CsvImporter:
    """Thin wrapper around parse_csv for class-based call sites."""

    @staticmethod
    def from_bytes(file_content: bytes) -> CsvImportResult:
        return parse_csv(file_content)


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------

def _merge_by_fund_code(
    valid_rows: list[dict],
    warnings: list[str],
) -> list[dict]:
    """Merge valid rows by fund_code, summing amounts.

    Keeps the fund_name from the first occurrence.  Appends to *warnings* if
    the same fund_code appears with different fund_name values.
    """
    merged: dict[str, dict] = {}  # fund_code -> merged row

    for row in valid_rows:
        code = row["fund_code"]
        name = row["fund_name"]
        amount = row["amount"]

        if code not in merged:
            merged[code] = {
                "fund_code": code,
                "fund_name": name,
                "amount": amount,
            }
        else:
            existing_name = merged[code]["fund_name"]
            if name and existing_name and name != existing_name:
                warnings.append(
                    f"基金代码 {code} 出现名称不一致，已按首行名称保留"
                )
            merged[code]["amount"] += amount

    return list(merged.values())
