"""Tests for Moving Average (MA) timing strategy."""
from datetime import date, timedelta
from domain.backtest.strategies.ma import MAStrategy


def generate_golden_cross_nav(start_date: date, periods: int = 100) -> list[dict]:
    """Generate NAV history with golden cross (falling then rising)."""
    nav_history = []
    nav = 1.0

    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        if i < periods // 2:
            nav = nav * 0.995
        else:
            nav = nav * 1.008
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })

    return nav_history


def generate_death_cross_nav(start_date: date, periods: int = 100) -> list[dict]:
    """Generate NAV history with death cross (rising then falling)."""
    nav_history = []
    nav = 1.0

    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        if i < periods // 2:
            nav = nav * 1.005
        else:
            nav = nav * 0.992
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })

    return nav_history


class TestMAStrategy:
    """Tests for MA timing strategy."""

    def test_ma_strategy_name(self):
        strategy = MAStrategy(short_window=5, long_window=20)
        assert strategy.name() == "MA Timing"

    def test_ma_generates_buy_on_golden_cross(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_golden_cross_nav(start_date, periods=100)

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) >= 1

    def test_ma_generates_sell_on_death_cross(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_death_cross_nav(start_date, periods=100)

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) >= 1

    def test_ma_signals_have_explanation(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_golden_cross_nav(start_date, periods=100)

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert signal.reason != ""
            assert "均线" in signal.reason or "上穿" in signal.reason or "下穿" in signal.reason

    def test_ma_confidence_varies_by_signal_strength(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_golden_cross_nav(start_date, periods=100)

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert 0.6 <= signal.confidence <= 0.8
