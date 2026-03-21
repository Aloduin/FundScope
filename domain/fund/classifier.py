"""Fund sector classification.

Uses keyword matching for automatic classification with multi-label support.
Phase 2: Add manual override table support.
"""
from shared.config import SECTOR_KEYWORDS
from shared.logger import get_logger

logger = get_logger(__name__)

# Default sector for unclassified funds
UNKNOWN_SECTOR = "未分类"


def classify_sector(fund_name: str, fund_code: str = "") -> tuple[str, list[str], str]:
    """Classify fund sector based on fund name keywords.

    Args:
        fund_name: Fund name (e.g., "某某红利低波基金")
        fund_code: Fund code (for logging, optional)

    Returns:
        Tuple of (primary_sector, sectors, source):
        - primary_sector: First matched sector (or "未分类")
        - sectors: All matched sectors (multi-label)
        - source: Classification source
          - "auto": Single sector matched
          - "auto_ambiguous": Multiple sectors matched
          - "auto_unknown": No sectors matched

    Keyword matching rules:
    - Iterate through SECTOR_KEYWORDS in dictionary order
    - First match becomes primary_sector
    - All matches added to sectors list
    """
    if not fund_name:
        logger.warning(f"Empty fund name for classification: {fund_code}")
        return UNKNOWN_SECTOR, [], "auto_unknown"

    matched_sectors = []

    for sector, keywords in SECTOR_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in fund_name.lower():
                if sector not in matched_sectors:
                    matched_sectors.append(sector)
                break  # Move to next sector after first keyword match

    if len(matched_sectors) == 0:
        logger.info(f"No sector matched for {fund_code}: {fund_name}")
        return UNKNOWN_SECTOR, [], "auto_unknown"

    primary_sector = matched_sectors[0]
    source = "auto" if len(matched_sectors) == 1 else "auto_ambiguous"

    if len(matched_sectors) > 1:
        logger.info(f"Multi-sector matched for {fund_code}: {matched_sectors}")

    return primary_sector, matched_sectors, source
