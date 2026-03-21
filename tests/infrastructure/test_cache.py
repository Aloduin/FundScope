"""Tests for L1 memory cache.

Verifies cache hits return identical results and different arguments
produce different cache entries.
"""
import pytest
from infrastructure.datasource.cache import cached, clear_l1_cache, _l1_cache
from infrastructure.datasource.akshare_source import AkShareDataSource


@pytest.fixture(autouse=True)
def clear_cache_before_each_test():
    """Clear cache before each test to ensure isolation."""
    clear_l1_cache()
    yield
    clear_l1_cache()


class TestL1Cache:
    """Test L1 memory cache functionality."""

    def test_l1_cache_hits(self):
        """Verify cache hit returns identical result.

        When calling the same method with same arguments twice,
        the second call should return cached result.
        """
        datasource = AkShareDataSource(use_mock=True)

        # First call - cache miss
        result1 = datasource.get_fund_basic_info("000001")

        # Second call - cache hit
        result2 = datasource.get_fund_basic_info("000001")

        # Results should be identical
        assert result1 == result2
        assert result1 is result2  # Same object reference (cached)

    def test_l1_cache_different_args(self):
        """Verify different arguments produce different cache entries.

        Calls with different fund codes should return different results
        and be cached separately.
        """
        datasource = AkShareDataSource(use_mock=True)

        # Call with fund code 000001
        result1 = datasource.get_fund_basic_info("000001")

        # Call with fund code 000002
        result2 = datasource.get_fund_basic_info("000002")

        # Results should be different (different fund codes)
        assert result1["fund_code"] == "000001"
        assert result2["fund_code"] == "000002"
        assert result1 != result2

    def test_l1_cache_nav_history(self):
        """Test cache with NAV history method."""
        datasource = AkShareDataSource(use_mock=True)

        # First call - cache miss
        nav1 = datasource.get_fund_nav_history("000001")

        # Second call - cache hit
        nav2 = datasource.get_fund_nav_history("000001")

        # Should return same cached result
        assert nav1 == nav2
        assert nav1 is nav2

    def test_l1_cache_clear(self):
        """Test clear_l1_cache function."""
        datasource = AkShareDataSource(use_mock=True)

        # Populate cache
        datasource.get_fund_basic_info("000001")

        # Verify cache has entries
        assert len(_l1_cache) > 0

        # Clear cache
        clear_l1_cache()

        # Verify cache is empty
        assert len(_l1_cache) == 0

    def test_cache_key_format(self):
        """Test that cache keys are properly formatted."""
        from infrastructure.datasource.cache import _make_cache_key

        key = _make_cache_key(
            key_prefix="fund_info",
            method_name="get_fund_basic_info",
            args=("000001",),
            kwargs={}
        )

        assert key == "fund_info:get_fund_basic_info:000001"

    def test_cache_key_with_kwargs(self):
        """Test cache key generation with keyword arguments."""
        from infrastructure.datasource.cache import _make_cache_key
        from datetime import date

        key = _make_cache_key(
            key_prefix="nav_history",
            method_name="get_fund_nav_history",
            args=("000001",),
            kwargs={"start_date": date(2024, 1, 1), "end_date": date(2024, 12, 31)}
        )

        assert "start_date=2024-01-01" in key
        assert "end_date=2024-12-31" in key
        assert "fund_info" not in key  # Wrong prefix
        assert "nav_history" in key
