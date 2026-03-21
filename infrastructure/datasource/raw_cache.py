"""L2 raw response cache with file system storage.

Provides TTL-based file system cache for akshare API responses.
Cache files are stored in data/cache/ directory with 7-day TTL.
"""
from datetime import date, datetime
from pathlib import Path
import json
from typing import Any

from shared.logger import get_logger

logger = get_logger(__name__)

# Cache directory
CACHE_DIR = Path("data/cache")
# TTL: 7 days
CACHE_TTL_DAYS = 7


def _json_default(obj: Any) -> Any:
    """JSON serializer for objects not supported by default.

    Handles:
    - date/datetime -> ISO format string (YYYY-MM-DD)
    - Path -> string representation
    - numpy types -> Python native types

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation

    Raises:
        TypeError: If object type is not supported
    """
    # Handle date and datetime
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, date):
        return obj.strftime("%Y-%m-%d")

    # Handle Path objects
    if isinstance(obj, Path):
        return str(obj)

    # Handle numpy types (common in data processing)
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()

    # Fallback: try string conversion
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def get_cache_path(fund_code: str, data_type: str, date_suffix: str) -> Path:
    """Build cache file path.

    Format: data/cache/{fund_code}_{data_type}_{YYYYMMDD}.json

    Args:
        fund_code: Fund code (e.g., "000001")
        data_type: Data type (e.g., "fund_info", "nav_history")
        date_suffix: Date suffix in YYYYMMDD format

    Returns:
        Path to cache file
    """
    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{fund_code}_{data_type}_{date_suffix}.json"
    return CACHE_DIR / filename


def load_cached_response(fund_code: str, data_type: str) -> Any | None:
    """Load cached response from file system.

    Checks TTL (7 days) and returns None if cache is expired.

    Args:
        fund_code: Fund code (e.g., "000001")
        data_type: Data type (e.g., "fund_info", "nav_history")

    Returns:
        Cached data if valid, None if cache miss or expired
    """
    # Find existing cache files for this fund_code and data_type
    if not CACHE_DIR.exists():
        return None

    pattern = f"{fund_code}_{data_type}_*.json"
    cache_files = list(CACHE_DIR.glob(pattern))

    if not cache_files:
        logger.debug(f"L2 cache miss: {fund_code}/{data_type}")
        return None

    # Use the most recent cache file
    cache_file = max(cache_files, key=lambda p: p.stat().st_mtime)

    # Check TTL based on file modification time
    file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    age = datetime.now() - file_mtime

    if age.days >= CACHE_TTL_DAYS:
        logger.debug(f"L2 cache expired: {cache_file.name} (age: {age.days} days)")
        # Remove expired cache
        cache_file.unlink()
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"L2 cache hit: {cache_file.name} (age: {age.days} days)")
        return data

    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"L2 cache read error: {cache_file.name} - {e}")
        # Remove corrupted cache
        try:
            cache_file.unlink()
        except IOError:
            pass
        return None


def save_cached_response(fund_code: str, data_type: str, data: Any) -> Path:
    """Save response to file system cache.

    Creates a new cache file with current date suffix.

    Args:
        fund_code: Fund code (e.g., "000001")
        data_type: Data type (e.g., "fund_info", "nav_history")
        data: Data to cache (must be JSON-serializable)

    Returns:
        Path to created cache file
    """
    # Generate date suffix
    date_suffix = date.today().strftime("%Y%m%d")
    cache_file = get_cache_path(fund_code, data_type, date_suffix)

    # Clean up old cache files for the same fund_code and data_type
    if CACHE_DIR.exists():
        pattern = f"{fund_code}_{data_type}_*.json"
        old_files = [f for f in CACHE_DIR.glob(pattern) if f != cache_file]
        for old_file in old_files:
            try:
                old_file.unlink()
                logger.debug(f"Removed old cache: {old_file.name}")
            except IOError as e:
                logger.warning(f"Failed to remove old cache {old_file.name}: {e}")

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, default=_json_default, ensure_ascii=False, indent=2)

        logger.info(f"L2 cache saved: {cache_file.name}")
        return cache_file

    except IOError as e:
        logger.error(f"L2 cache write error: {cache_file} - {e}")
        raise
