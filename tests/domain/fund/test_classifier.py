"""Tests for fund sector classification."""
from domain.fund.classifier import classify_sector


class TestClassifySector:
    """Tests for classify_sector function."""

    def test_single_sector_match(self):
        """Test classification with single sector match."""
        primary, sectors, source = classify_sector("某某红利低波基金")

        assert primary == "红利低波"
        assert "红利低波" in sectors
        assert source == "auto"

    def test_multi_sector_match(self):
        """Test classification with multiple sector matches."""
        # Fund name that matches multiple sectors
        primary, sectors, source = classify_sector("某某半导体芯片基金")

        assert primary == "半导体"
        assert len(sectors) >= 1
        assert source == "auto" or source == "auto_ambiguous"

    def test_no_sector_match(self):
        """Test classification when no sector matches."""
        primary, sectors, source = classify_sector("某某稳健增长基金")

        assert primary == "未分类"
        assert sectors == []
        assert source == "auto_unknown"

    def test_empty_fund_name(self):
        """Test classification with empty fund name."""
        primary, sectors, source = classify_sector("")

        assert primary == "未分类"
        assert sectors == []
        assert source == "auto_unknown"

    def test_case_insensitive_matching(self):
        """Test that matching is case insensitive."""
        primary, sectors, source = classify_sector("某某 DIVIDEND 基金")

        assert "红利低波" in sectors or primary == "红利低波"

    def test_specific_sector_keywords(self):
        """Test specific sector keyword matching."""
        # 半导体
        primary, sectors, source = classify_sector("某某半导体混合")
        assert "半导体" in sectors

        # 医疗
        primary, sectors, source = classify_sector("某某医疗健康基金")
        assert "医疗" in sectors

        # 消费
        primary, sectors, source = classify_sector("某某消费白酒基金")
        assert "消费" in sectors

        # 新能源
        primary, sectors, source = classify_sector("某某光伏储能基金")
        assert "新能源" in sectors

        # 债券
        primary, sectors, source = classify_sector("某某纯债债券")
        assert "债券" in sectors

        # 宽基指数
        primary, sectors, source = classify_sector("某某沪深 300 指数")
        assert "宽基指数" in sectors

    def test_first_match_is_primary(self):
        """Test that first matched sector becomes primary."""
        # SECTOR_KEYWORDS order determines primary
        primary, sectors, source = classify_sector("某某消费红利基金")

        assert primary == sectors[0]
        assert len(sectors) >= 1
