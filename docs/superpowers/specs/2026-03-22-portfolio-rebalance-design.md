# Phase 3C: 多基金轮动与再平衡 — 设计文档

**日期：** 2026-03-22
**版本：** v1.0
**目标：** 实现固定基金池的多基金轮动回测能力，形成 Momentum + Threshold Rebalance 的完整组合策略闭环。

---

## 一、背景与目标

### 1.1 当前状态

**Phase 3 已完成：**

- 3A：CompositeStrategy + SignalModifier + MAFilter（过滤型组合）
- 3B：策略解释面板（BlockedSignalTrace）

**现有基础设施：**

- `Strategy` 基类：单基金策略接口
- `BacktestEngine`：单基金回测引擎
- `RebalancePolicy` 接口：存根，未接入主流程
- `ThresholdRebalancePolicy`：存根，返回空列表

**当前缺失：**

1. 多基金组合回测能力
2. `PortfolioStrategy` 组合策略接口
3. `RebalancePolicy` 真实实现
4. 组合级信号模型

---

### 1.2 本阶段目标

- 实现固定基金池的多基金轮动回测
- 支持 Momentum 策略输出目标权重
- 支持 Threshold Rebalance 判断是否调仓
- 形成完整的组合策略能力闭环

---

### 1.3 本阶段不做

- 和虚拟账户打通
- 税费/滑点/最小交易单位
- 动态基金池
- 任意嵌套组合策略树
- 跨资产类别特殊处理（货币基金、QDII 时差、ETF 场内成交规则差异）
- 修改现有单基金 `MomentumStrategy`

---

## 二、核心硬规则

### 2.1 信号生成方式

`generate_portfolio_signals()` 采用**一次性批量生成**：

- 策略一次性生成整段回测期间的所有组合信号
- Engine 不循环调用策略，只调用一次
- **每个交易日最多一条 `PortfolioSignal`**，若策略输出同日多条信号，直接报错

### 2.2 权重归一化约束

`target_weights` 必须满足：

- key 可以包含基金代码和 `"CASH"`
- 所有权重满足 `0 <= w <= 1`
- 总和满足 `abs(sum(weights.values()) - 1.0) < 1e-6`
- 若策略输出不满足约束，视为无效信号并报错
- **必须在模型层 `__post_init__` 中校验**，而非仅在文档约束

### 2.3 Momentum 默认配仓规则

- 过去 `lookback_days` 收益率排序
- 选前 `top_n` 只基金
- 入选基金**等权分配**
- 未入选部分全部给 `CASH`
- 若有效基金不足 `top_n`，剩余权重给 `CASH`

示例（`top_n=2`，基金池 3 只）：

```python
{
    "fund_a": 0.5,
    "fund_b": 0.5,
    "CASH": 0.0,
}
```

### 2.4 执行顺序规则

1. `T` 日生成组合信号
2. `T+1` 日执行调仓
3. `T+1` 当日**先卖出，再买入**
4. 卖出和买入都按 `T+1` 同一日 NAV 成交
5. 最后一个交易日产生的信号，如无 `T+1` 数据，则丢弃不执行
6. **执行后不强制重置 cash，只基于真实交易结果保留剩余现金**

### 2.5 时间轴职责划分

- **Engine 负责**：时间轴对齐（取交集）、lookback 可用性裁剪
- **Strategy 负责**：在已对齐的有效时间轴上生成信号
- Strategy 接收的 `nav_histories` 已由 Engine 完成裁剪，无需再做对齐

### 2.6 策略隔离原则

- 新建 `PortfolioMomentumStrategy`，实现 `PortfolioStrategy`
- 不修改现有单基金 `MomentumStrategy`
- 保持 Phase 1/2/3A 已有功能和测试不变

---

## 三、数据模型

### 3.1 PortfolioSignal

**文件：** `domain/backtest/models.py`

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass
class PortfolioSignal:
    """组合级再平衡信号。"""
    date: date
    action: Literal["REBALANCE"]
    target_weights: dict[str, float]  # fund_code -> weight, includes "CASH"
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        """校验信号有效性。"""
        if self.action != "REBALANCE":
            raise ValueError(f"PortfolioSignal.action must be 'REBALANCE', got {self.action}")

        if "CASH" not in self.target_weights:
            raise ValueError("target_weights must include 'CASH'")

        total = sum(self.target_weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"target_weights must sum to 1.0, got {total:.6f}")

        for fund_code, weight in self.target_weights.items():
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"invalid weight for {fund_code}: {weight}")

        if not self.reason:
            raise ValueError("reason cannot be empty")
```

---

### 3.2 PortfolioBacktestResult

**文件：** `domain/backtest/models.py`

```python
@dataclass
class PortfolioBacktestResult:
    """组合回测结果。"""
    strategy_name: str
    fund_codes: list[str]
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    equity_curve: list[tuple[date, float]]
    rebalance_signals: list[PortfolioSignal]
    executed_trades: list[ExecutedTrade]
    portfolio_weights_history: list[tuple[date, dict[str, float]]]
```

**字段说明：**

- `portfolio_weights_history`：每个交易日的组合权重快照，包含 `"CASH"` 权重

---

### 3.3 ExecutedTrade 扩展

**文件：** `domain/backtest/models.py`

现有 `ExecutedTrade` 字段：`date, fund_code, action, amount, nav, shares, reason`

新增可选字段：

```python
@dataclass
class ExecutedTrade:
    date: date
    fund_code: str
    action: Literal["BUY", "SELL"]
    amount: float
    nav: float
    shares: float
    reason: str
    rebalance_id: str | None = None  # 可追溯到某次组合调仓信号
```

**用途：** 支持后续解释面板展示"某次调仓包含哪些买卖"

---

## 四、策略层设计

### 4.1 PortfolioStrategy 基类

**文件：** `domain/backtest/strategies/portfolio_base.py`

```python
from abc import ABC, abstractmethod
from datetime import date
from domain.backtest.models import PortfolioSignal

class PortfolioStrategy(ABC):
    """组合策略基类。"""

    @abstractmethod
    def name(self) -> str:
        """策略名称。"""
        raise NotImplementedError

    @abstractmethod
    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date]
    ) -> list[PortfolioSignal]:
        """一次性生成整段期间的所有组合信号。

        Args:
            nav_histories: fund_code -> [{"date": date, "nav": float, ...}, ...]
                           已由 Engine 完成时间轴对齐和 lookback 裁剪
            aligned_dates: 已对齐的有效交易日列表

        Returns:
            按时间排序的 PortfolioSignal 列表

        约束:
            - 每个交易日最多返回一条信号
            - 若同日返回多条信号，将触发运行时错误
        """
        raise NotImplementedError
```

---

### 4.2 PortfolioMomentumStrategy

**文件：** `domain/backtest/strategies/portfolio_momentum.py`

```python
from dataclasses import dataclass
from datetime import date, timedelta
from domain.backtest.models import PortfolioSignal
from domain.backtest.strategies.portfolio_base import PortfolioStrategy

@dataclass
class MomentumConfig:
    """Momentum 策略配置。"""
    lookback_days: int = 60        # 收益率回顾窗口
    top_n: int = 2                  # 选前 N 只基金
    signal_interval_days: int = 20  # 信号生成间隔


class PortfolioMomentumStrategy(PortfolioStrategy):
    """多基金动量轮动策略。

    假设输入的 nav_histories 已由 Engine 完成时间轴对齐和 lookback 可用性裁剪，
    仅负责在给定有效时间轴上生成组合信号。
    """

    def __init__(self, config: MomentumConfig | None = None):
        self.config = config or MomentumConfig()

    def name(self) -> str:
        return f"PortfolioMomentum({self.config.lookback_days}, top{self.config.top_n})"

    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date]
    ) -> list[PortfolioSignal]:
        """生成组合信号。

        Args:
            nav_histories: 已对齐的净值历史
            aligned_dates: 有效交易日列表（已保证每个日期有足够 lookback 数据）

        Returns:
            组合信号列表
        """
        signals = []
        signal_dates = set()  # 用于检测同日多信号

        # 构建日期 -> NAV 索引
        nav_by_date = self._index_nav_by_date(nav_histories)

        # 按间隔生成信号
        last_signal_date = None
        for current_date in aligned_dates:
            if last_signal_date is None or \
               (current_date - last_signal_date).days >= self.config.signal_interval_days:

                # 计算各基金收益率（基于精确的 lookback 日期）
                returns = self._calculate_returns_exact(
                    nav_by_date, current_date, self.config.lookback_days
                )

                if not returns:
                    # 所有基金数据不足，跳过该日
                    continue

                # 选前 top_n
                sorted_funds = sorted(returns.items(), key=lambda x: x[1], reverse=True)
                top_funds = [f[0] for f in sorted_funds[:self.config.top_n]]

                # 构造目标权重（等权 + CASH）
                target_weights = self._build_target_weights(top_funds)

                # 生成信号
                signal = PortfolioSignal(
                    date=current_date,
                    action="REBALANCE",
                    target_weights=target_weights,
                    confidence=1.0,
                    reason=f"动量轮动：{', '.join(top_funds)}"
                )

                # 检测同日多信号
                if current_date in signal_dates:
                    raise ValueError(f"Multiple signals on {current_date}")
                signal_dates.add(current_date)

                signals.append(signal)
                last_signal_date = current_date

        return signals

    def _index_nav_by_date(self, nav_histories: dict[str, list[dict]]) -> dict[date, dict[str, float]]:
        """构造日期 -> {fund_code: nav} 索引。"""
        index = {}
        for fund_code, nav_list in nav_histories.items():
            for item in nav_list:
                d = item["date"]
                if d not in index:
                    index[d] = {}
                index[d][fund_code] = item["nav"]
        return index

    def _calculate_returns_exact(
        self,
        nav_by_date: dict[date, dict[str, float]],
        as_of_date: date,
        lookback_days: int
    ) -> dict[str, float]:
        """计算各基金在精确 lookback 窗口内的收益率。

        使用 as_of_date 和 as_of_date - lookback_days 两个精确日期的 NAV 计算，
        而非自然日窗口。这要求 Engine 已确保所有基金在这两个日期都有数据。
        """
        returns = {}
        cutoff = as_of_date - timedelta(days=lookback_days)

        end_navs = nav_by_date.get(as_of_date, {})
        start_navs = nav_by_date.get(cutoff, {})

        for fund_code in end_navs:
            if fund_code not in start_navs:
                continue  # 起始日无数据

            start_nav = start_navs[fund_code]
            end_nav = end_navs[fund_code]

            if start_nav <= 0:
                continue  # 无效净值

            returns[fund_code] = (end_nav - start_nav) / start_nav

        return returns

    def _build_target_weights(self, top_funds: list[str]) -> dict[str, float]:
        """构造目标权重字典。"""
        weights = {}

        if top_funds:
            per_fund = 1.0 / len(top_funds)
            for fund in top_funds:
                weights[fund] = per_fund

        # 补 CASH
        cash_weight = 1.0 - sum(weights.values())
        weights["CASH"] = cash_weight

        return weights
```

---

## 五、再平衡层设计

### 5.1 RebalancePolicy 接口修订

**文件：** `domain/backtest/strategies/rebalance/policy.py`

```python
from abc import ABC, abstractmethod
from domain.backtest.models import PortfolioSignal, SignalContext

class RebalancePolicy(ABC):
    """再平衡策略接口。

    Phase 3C：作为组合级 Signal Modifier，决定信号是否执行。
    """

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        """判断是否执行再平衡信号。

        Args:
            signal: 组合级再平衡信号
            current_positions: 当前持仓 [{"fund_code": str, "weight": float}, ...]
            context: 信号上下文

        Returns:
            - 放行：返回 signal（可能修改）
            - 拦截：返回 None
        """
        raise NotImplementedError
```

---

### 5.2 ThresholdRebalancePolicy 完整实现

**文件：** `domain/backtest/strategies/rebalance/threshold.py`

```python
from domain.backtest.models import PortfolioSignal, SignalContext
from domain.backtest.strategies.rebalance.policy import RebalancePolicy

class ThresholdRebalancePolicy(RebalancePolicy):
    """阈值触发型再平衡策略。

    仅当目标权重与当前权重的偏差超过阈值时，才执行调仓。
    """

    def __init__(self, threshold: float = 0.05):
        """
        Args:
            threshold: 触发调仓的最小权重偏差（如 0.05 表示 5%）
        """
        self.threshold = threshold

    def name(self) -> str:
        return f"ThresholdRebalance({self.threshold:.0%})"

    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        # 1. 构造当前权重字典
        current_weights = {}
        for pos in current_positions:
            current_weights[pos["fund_code"]] = pos["weight"]

        # 2. 确保 CASH 在当前权重中
        if "CASH" not in current_weights:
            current_weights["CASH"] = 0.0

        # 3. 计算最大偏差
        target_weights = signal.target_weights
        all_keys = set(current_weights.keys()) | set(target_weights.keys())

        max_deviation = 0.0
        for key in all_keys:
            current_w = current_weights.get(key, 0.0)
            target_w = target_weights.get(key, 0.0)
            deviation = abs(current_w - target_w)
            max_deviation = max(max_deviation, deviation)

        # 4. 判断是否放行
        if max_deviation >= self.threshold:
            return signal  # 放行
        else:
            return None   # 拦截
```

---

## 六、引擎层设计

### 6.1 PortfolioBacktestEngine

**文件：** `domain/backtest/engine.py`（新增类）

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from domain.backtest.models import (
    PortfolioSignal,
    PortfolioBacktestResult,
    ExecutedTrade,
    SignalContext,
)
from domain.backtest.strategies.portfolio_base import PortfolioStrategy
from domain.backtest.strategies.rebalance.policy import RebalancePolicy

@dataclass
class PortfolioState:
    """组合状态快照。"""
    cash: float
    holdings: dict[str, float]  # fund_code -> shares
    weights: dict[str, float]   # fund_code -> weight (includes CASH)


class PortfolioBacktestEngine:
    """组合回测引擎。

    职责：
    - 时间轴对齐（取所有基金净值日期交集）
    - Lookback 可用性裁剪（确保每个日期都有足够历史数据）
    - 信号执行（T+1 规则）
    - 组合状态管理
    """

    def __init__(self, initial_cash: float = 100000):
        self.initial_cash = initial_cash

    def run(
        self,
        strategy: PortfolioStrategy,
        fund_codes: list[str],
        nav_histories: dict[str, list[dict]],
        rebalance_policy: RebalancePolicy | None = None,
        lookback_days: int = 60,
    ) -> PortfolioBacktestResult:
        """运行组合回测。

        Args:
            strategy: 组合策略
            fund_codes: 基金池
            nav_histories: fund_code -> nav history
            rebalance_policy: 再平衡策略（可选）
            lookback_days: 策略所需的最小历史数据天数（用于裁剪时间轴）

        Returns:
            组合回测结果
        """
        # 1. 对齐时间轴并裁剪 lookback 不足的日期
        aligned_dates = self._prepare_aligned_dates(nav_histories, lookback_days)
        if not aligned_dates:
            raise ValueError("No valid trading dates after alignment and lookback filtering")

        start_date = aligned_dates[0]
        end_date = aligned_dates[-1]

        # 2. 初始化组合状态
        state = PortfolioState(
            cash=self.initial_cash,
            holdings={},
            weights={"CASH": 1.0}
        )

        # 3. 生成所有信号（一次性）
        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        # 3.1 校验：每个交易日最多一条信号
        signal_dates = [s.date for s in signals]
        if len(signal_dates) != len(set(signal_dates)):
            duplicate_dates = [d for d in signal_dates if signal_dates.count(d) > 1]
            raise ValueError(f"Multiple signals on same date: {set(duplicate_dates)}")

        signal_index = 0

        # 4. 按时间轴遍历执行
        equity_curve = []
        executed_trades = []
        weights_history = []

        nav_by_date = self._index_nav_by_date(nav_histories)

        for i, current_date in enumerate(aligned_dates):
            # 4.1 更新净值
            current_navs = nav_by_date.get(current_date, {})

            # 4.2 记录权重快照
            weights_history.append((current_date, state.weights.copy()))

            # 4.3 计算组合净值
            portfolio_value = self._calculate_portfolio_value(state, current_navs)
            equity_curve.append((current_date, portfolio_value))

            # 4.4 检查是否有信号待执行
            while signal_index < len(signals):
                signal = signals[signal_index]

                # 信号日期 = T，执行日期 = T+1
                if signal.date == current_date:
                    # T 日收到信号，准备 T+1 执行
                    signal_to_execute = signal
                    signal_index += 1
                    break
                elif signal.date < current_date:
                    # 信号已过，跳过（可能是对齐问题）
                    signal_index += 1
                    continue
                else:
                    # 还没到信号日期
                    signal_to_execute = None
                    break
            else:
                signal_to_execute = None

            # 4.5 T+1 执行逻辑
            # 信号在 T 日（current_date）产生，策略使用 T 日收盘后数据计算
            # 实际执行在 T+1 日（next_date），使用 T+1 的 NAV 成交
            # 这符合实际投资中"T 日信号，T+1 执行"的规则

            if signal_to_execute and i + 1 < len(aligned_dates):
                # 获取 T+1 的 NAV
                next_date = aligned_dates[i + 1]
                next_navs = nav_by_date.get(next_date, {})

                # 4.6 应用 RebalancePolicy
                if rebalance_policy:
                    context = self._build_context(current_date, current_navs)
                    current_positions = self._get_current_positions(state, current_navs)
                    signal_to_execute = rebalance_policy.apply(
                        signal_to_execute, current_positions, context
                    )

                # 4.7 执行调仓
                if signal_to_execute:
                    trades = self._execute_rebalance(
                        signal_to_execute,
                        state,
                        next_navs,
                        next_date
                    )
                    executed_trades.extend(trades)

        # 5. 计算绩效指标
        metrics = self._calculate_metrics(equity_curve)

        return PortfolioBacktestResult(
            strategy_name=strategy.name(),
            fund_codes=fund_codes,
            start_date=start_date,
            end_date=end_date,
            total_return=metrics["total_return"],
            annualized_return=metrics["annualized_return"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            equity_curve=equity_curve,
            rebalance_signals=signals,
            executed_trades=executed_trades,
            portfolio_weights_history=weights_history,
        )

    def _prepare_aligned_dates(
        self,
        nav_histories: dict[str, list[dict]],
        lookback_days: int
    ) -> list[date]:
        """准备对齐的时间轴，并裁剪 lookback 不足的日期。

        规则：
        1. 取所有基金净值日期的交集
        2. 过滤掉所有不足 lookback_days 的日期
        3. 确保每个有效日期都有对应的历史数据

        Args:
            nav_histories: 各基金的净值历史
            lookback_days: 策略所需的最小历史天数

        Returns:
            有效交易日列表
        """
        # 1. 取日期交集
        date_sets = []
        for nav_list in nav_histories.values():
            dates = {d["date"] for d in nav_list}
            date_sets.append(dates)

        if not date_sets:
            return []

        common_dates = sorted(set.intersection(*date_sets))

        if not common_dates:
            return []

        # 2. 找到所有基金都有足够 lookback 数据的最早日期
        # 对于每个候选日期，检查 lookback 天前是否有数据
        min_start_date = None

        # 获取所有日期集合（用于快速查找）
        all_dates = set(common_dates)
        sorted_all_dates = sorted(all_dates)

        for candidate_date in common_dates:
            cutoff = candidate_date - timedelta(days=lookback_days)

            # 检查 cutoff 是否在数据范围内
            # 由于交易日可能不连续，我们需要找到 >= cutoff 的最早日期
            # 并确保这个日期与 candidate_date 之间有足够的数据点

            # 简化处理：直接检查 cutoff 是否在数据中
            # 如果不在，找到第一个 >= cutoff 的日期
            dates_before = [d for d in sorted_all_dates if d <= candidate_date]

            # 需要至少 lookback_days 个交易日
            # 这里简化为：找到第一个有足够历史数据的日期
            if len(dates_before) >= lookback_days:
                min_start_date = candidate_date
                break

        if min_start_date is None:
            return []

        # 3. 返回从 min_start_date 开始的所有日期
        valid_dates = [d for d in common_dates if d >= min_start_date]
        return valid_dates

    def _align_dates(self, nav_histories: dict[str, list[dict]]) -> list[date]:
        """取所有基金净值日期的交集（不含 lookback 裁剪）。

        此方法保留供内部使用，但主要入口是 _prepare_aligned_dates。
        """
        date_sets = []
        for nav_list in nav_histories.values():
            dates = {d["date"] for d in nav_list}
            date_sets.append(dates)
        common_dates = sorted(set.intersection(*date_sets))
        return common_dates

    def _index_nav_by_date(self, nav_histories: dict[str, list[dict]]) -> dict[date, dict[str, float]]:
        """构造 date -> {fund_code: nav} 索引。"""
        index = {}
        for fund_code, nav_list in nav_histories.items():
            for item in nav_list:
                d = item["date"]
                if d not in index:
                    index[d] = {}
                index[d][fund_code] = item["nav"]
        return index

    def _calculate_portfolio_value(
        self,
        state: PortfolioState,
        current_navs: dict[str, float]
    ) -> float:
        """计算组合总价值。"""
        value = state.cash
        for fund_code, shares in state.holdings.items():
            nav = current_navs.get(fund_code, 0)
            value += shares * nav
        return value

    def _get_current_positions(
        self,
        state: PortfolioState,
        current_navs: dict[str, float]
    ) -> list[dict]:
        """获取当前持仓列表（含权重）。"""
        total_value = self._calculate_portfolio_value(state, current_navs)
        positions = []

        for fund_code, shares in state.holdings.items():
            nav = current_navs.get(fund_code, 0)
            value = shares * nav
            positions.append({
                "fund_code": fund_code,
                "shares": shares,
                "value": value,
                "weight": value / total_value if total_value > 0 else 0.0
            })

        # 补充 CASH 持仓
        if state.cash > 0:
            positions.append({
                "fund_code": "CASH",
                "shares": state.cash,
                "value": state.cash,
                "weight": state.cash / total_value if total_value > 0 else 0.0
            })

        return positions

    def _build_context(self, current_date: date, current_navs: dict[str, float]) -> SignalContext:
        """构造信号上下文。

        注意：组合级上下文中 current_nav 使用 0.0 作为占位符，
        因为多基金场景没有单一"当前净值"概念。
        实际净值信息通过 indicators 字段传递。
        """
        return SignalContext(
            date=current_date,
            current_nav=0.0,  # 组合级占位符
            indicators=current_navs
        )

    def _execute_rebalance(
        self,
        signal: PortfolioSignal,
        state: PortfolioState,
        next_navs: dict[str, float],
        execution_date: date,
    ) -> list[ExecutedTrade]:
        """执行再平衡。

        规则：先卖后买，同一日 NAV 成交。
        """
        trades = []
        rebalance_id = f"rebalance_{execution_date.isoformat()}"

        # 1. 计算目标金额
        total_value = self._calculate_portfolio_value(state, next_navs)
        target_amounts = {}
        for key, weight in signal.target_weights.items():
            if key == "CASH":
                target_amounts["CASH"] = total_value * weight
            else:
                target_amounts[key] = total_value * weight

        # 2. 先卖出
        for fund_code in list(state.holdings.keys()):
            if fund_code not in target_amounts:
                # 完全卖出
                shares = state.holdings[fund_code]
                nav = next_navs.get(fund_code, 0)
                amount = shares * nav
                state.cash += amount
                del state.holdings[fund_code]

                trades.append(ExecutedTrade(
                    date=execution_date,
                    fund_code=fund_code,
                    action="SELL",
                    amount=amount,
                    nav=nav,
                    shares=shares,
                    reason=f"再平衡调出: {rebalance_id}",
                    rebalance_id=rebalance_id,
                ))

        # 3. 再买入
        for fund_code, target_amount in target_amounts.items():
            if fund_code == "CASH":
                continue

            nav = next_navs.get(fund_code, 0)
            if nav <= 0:
                continue

            current_shares = state.holdings.get(fund_code, 0)
            current_value = current_shares * nav
            delta = target_amount - current_value

            if delta > 0:
                # 买入
                shares_to_buy = delta / nav
                state.cash -= delta
                state.holdings[fund_code] = current_shares + shares_to_buy

                trades.append(ExecutedTrade(
                    date=execution_date,
                    fund_code=fund_code,
                    action="BUY",
                    amount=delta,
                    nav=nav,
                    shares=shares_to_buy,
                    reason=f"再平衡调入: {rebalance_id}",
                    rebalance_id=rebalance_id,
                ))
            elif delta < 0:
                # 卖出
                shares_to_sell = -delta / nav
                state.cash -= delta  # 负负得正，cash 增加
                state.holdings[fund_code] = current_shares - shares_to_sell

                trades.append(ExecutedTrade(
                    date=execution_date,
                    fund_code=fund_code,
                    action="SELL",
                    amount=-delta,
                    nav=nav,
                    shares=shares_to_sell,
                    reason=f"再平衡减仓: {rebalance_id}",
                    rebalance_id=rebalance_id,
                ))

        # 4. 更新权重（注意：不强制重置 cash，只基于真实交易结果）
        # state.cash 已通过买卖操作自然更新

        # 5. 更新权重
        total_value_after = self._calculate_portfolio_value(state, next_navs)
        if total_value_after <= 0:
            return trades  # 无有效持仓

        state.weights = {}
        for fund_code, shares in state.holdings.items():
            nav = next_navs.get(fund_code, 0)
            state.weights[fund_code] = (shares * nav) / total_value_after
        state.weights["CASH"] = state.cash / total_value_after

        return trades

    def _calculate_metrics(self, equity_curve: list[tuple[date, float]]) -> dict:
        """计算绩效指标。"""
        if not equity_curve:
            return {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
            }

        values = [v for _, v in equity_curve]
        total_return = (values[-1] - values[0]) / values[0]

        # 简化计算
        days = (equity_curve[-1][0] - equity_curve[0][0]).days
        annualized_return = (1 + total_return) ** (365 / max(days, 1)) - 1

        # 最大回撤
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_dd,
            "sharpe_ratio": self._calculate_sharpe_ratio(equity_curve, annualized_return),
        }

    def _calculate_sharpe_ratio(
        self,
        equity_curve: list[tuple[date, float]],
        annualized_return: float
    ) -> float:
        """计算夏普比率。

        简化假设：无风险利率 = 0。
        """
        if len(equity_curve) < 2:
            return 0.0

        # 计算日收益率
        values = [v for _, v in equity_curve]
        daily_returns = []
        for i in range(1, len(values)):
            daily_return = (values[i] - values[i-1]) / values[i-1]
            daily_returns.append(daily_return)

        if not daily_returns:
            return 0.0

        # 计算日收益率标准差
        import statistics
        std_dev = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0

        if std_dev == 0:
            return 0.0

        # 年化标准差
        annualized_std = std_dev * (252 ** 0.5)

        # 夏普比率 = (年化收益 - 无风险利率) / 年化标准差
        # 简化：无风险利率 = 0
        return annualized_return / annualized_std
```

---

## 七、多基金时间轴对齐规则

### 7.1 核心规则

1. 组合时间轴取**所有基金净值日期的交集**
2. 只有在交集日期上才允许生成组合信号与执行调仓
3. 某基金在某日无 NAV，则该日不可调仓到该基金
4. 起始日取所有基金都已有足够 lookback 数据后的最晚日期

### 7.2 边界处理

- 最后一个交易日的信号若无 T+1 数据，则丢弃不执行
- 某基金数据缺失时，不参与当日收益计算

---

## 八、Service 层变更

### 8.1 PortfolioBacktestService

**文件：** `service/portfolio_backtest_service.py`（新建）

```python
from datetime import date
from domain.backtest.engine import PortfolioBacktestEngine
from domain.backtest.strategies.portfolio_momentum import (
    PortfolioMomentumStrategy,
    MomentumConfig,
)
from domain.backtest.strategies.rebalance.threshold import ThresholdRebalancePolicy
from infrastructure.datasource.akshare_source import AkShareDataSource

class PortfolioBacktestService:
    """组合回测服务。"""

    def __init__(self, datasource: AkShareDataSource | None = None):
        self.datasource = datasource or AkShareDataSource()
        self.engine = PortfolioBacktestEngine()

    def run_portfolio_backtest(
        self,
        fund_codes: list[str],
        strategy_name: str,
        strategy_params: dict,
        start_date: date,
        end_date: date,
        initial_cash: float = 100000,
        rebalance_policy_name: str | None = None,
        rebalance_params: dict | None = None,
    ) -> dict:
        """运行组合回测。

        Args:
            fund_codes: 基金池代码列表
            strategy_name: 策略名称
            strategy_params: 策略参数
            start_date: 回测起始日期
            end_date: 回测结束日期
            initial_cash: 初始资金
            rebalance_policy_name: 再平衡策略名称
            rebalance_params: 再平衡策略参数

        Returns:
            组合回测结果
        """
        # 1. 创建策略（先创建以获取 lookback_days）
        strategy = self._create_strategy(strategy_name, strategy_params)
        lookback_days = strategy_params.get("lookback_days", 60)

        # 2. 获取 NAV 数据（使用日期范围过滤）
        nav_histories = {}
        for fund_code in fund_codes:
            full_history = self.datasource.get_fund_nav_history(fund_code)
            # 过滤到指定日期范围
            filtered = [
                d for d in full_history
                if start_date <= d["date"] <= end_date
            ]
            nav_histories[fund_code] = filtered

        # 3. 创建 RebalancePolicy
        rebalance_policy = None
        if rebalance_policy_name:
            rebalance_policy = self._create_rebalance_policy(
                rebalance_policy_name, rebalance_params or {}
            )

        # 4. 运行回测
        result = self.engine.run(
            strategy=strategy,
            fund_codes=fund_codes,
            nav_histories=nav_histories,
            rebalance_policy=rebalance_policy,
            lookback_days=lookback_days,
        )

        return result

    def _create_strategy(self, name: str, params: dict) -> PortfolioStrategy:
        if name == "PortfolioMomentum":
            config = MomentumConfig(
                lookback_days=params.get("lookback_days", 60),
                top_n=params.get("top_n", 2),
                signal_interval_days=params.get("signal_interval_days", 20),
            )
            return PortfolioMomentumStrategy(config)
        else:
            raise ValueError(f"Unknown portfolio strategy: {name}")

    def _create_rebalance_policy(self, name: str, params: dict) -> RebalancePolicy:
        if name == "Threshold":
            return ThresholdRebalancePolicy(
                threshold=params.get("threshold", 0.05)
            )
        else:
            raise ValueError(f"Unknown rebalance policy: {name}")
```

---

## 九、UI 变更

### 9.1 新增组合回测区块

**文件：** `ui/pages/3_strategy_lab.py`

在现有单基金回测区块之后，新增组合回测区块：

```python
# 组合回测区块
st.divider()
st.subheader("组合策略回测")

# 基金池输入
fund_codes_input = st.text_input(
    "基金池（逗号分隔）",
    placeholder="000001,000002,000003",
    key="portfolio_fund_codes"
)

if fund_codes_input:
    fund_codes = [c.strip() for c in fund_codes_input.split(",") if c.strip()]

    # 策略选择
    col1, col2 = st.columns(2)
    with col1:
        portfolio_strategy = st.selectbox(
            "组合策略",
            options=["PortfolioMomentum"],
            key="portfolio_strategy"
        )
    with col2:
        rebalance_policy = st.selectbox(
            "再平衡策略",
            options=["无", "Threshold"],
            key="rebalance_policy"
        )

    # 参数输入
    col1, col2, col3 = st.columns(3)
    with col1:
        lookback_days = st.number_input("动量窗口 (天)", min_value=10, value=60, key="lookback")
    with col2:
        top_n = st.number_input("持仓数量", min_value=1, max_value=10, value=2, key="top_n")
    with col3:
        signal_interval = st.number_input("调仓间隔 (天)", min_value=5, value=20, key="interval")

    if rebalance_policy == "Threshold":
        threshold = st.number_input("调仓阈值", min_value=0.01, max_value=0.20, value=0.05, step=0.01, key="threshold")

    # 运行按钮
    if st.button("运行组合回测", type="primary", key="run_portfolio"):
        # ... 调用 service
        pass
```

---

## 十、文件变更清单

| 文件 | 动作 |
|------|------|
| `domain/backtest/models.py` | 新增 `PortfolioSignal`、`PortfolioBacktestResult`；扩展 `ExecutedTrade` |
| `domain/backtest/strategies/portfolio_base.py` | 新增 `PortfolioStrategy` 基类 |
| `domain/backtest/strategies/portfolio_momentum.py` | 新增 `PortfolioMomentumStrategy` |
| `domain/backtest/strategies/rebalance/policy.py` | 修订接口为 `apply()` |
| `domain/backtest/strategies/rebalance/threshold.py` | 完整实现 `ThresholdRebalancePolicy` |
| `domain/backtest/strategies/__init__.py` | 导出 `PortfolioStrategy` |
| `domain/backtest/engine.py` | 新增 `PortfolioBacktestEngine` |
| `service/portfolio_backtest_service.py` | 新增 |
| `ui/pages/3_strategy_lab.py` | 新增组合回测区块 |

### 10.1 接口变更迁移说明

**RebalancePolicy 接口变更：**

原有接口（Phase 3A 存根）：
```python
def rebalance(
    self,
    current_positions: list[dict],
    target_weights: dict[str, float],
    context: SignalContext
) -> list[Signal]
```

新接口（Phase 3C）：
```python
def apply(
    self,
    signal: PortfolioSignal,
    current_positions: list[dict],
    context: SignalContext,
) -> PortfolioSignal | None
```

**影响范围：**
- `domain/backtest/strategies/rebalance/threshold.py`：需完整重写
- `tests/domain/backtest/strategies/rebalance/`：需更新测试

**注意：** 现有 `CompositeStrategy` 中有 guard code 拒绝 `RebalancePolicy` 实例，Phase 3C 不会修改此逻辑。再平衡型组合使用独立的 `PortfolioBacktestEngine`，不通过 `CompositeStrategy`。

---

## 十一、测试覆盖

### 11.1 数据模型测试

- `PortfolioSignal` 构造与权重约束验证
- `PortfolioBacktestResult` 默认值

### 11.2 策略测试

- `PortfolioMomentumStrategy.generate_portfolio_signals()` 返回有效信号
- 时间轴对齐正确
- 配仓规则正确（前 N 等权 + CASH）

### 11.3 RebalancePolicy 测试

- `ThresholdRebalancePolicy.apply()` 偏差超过阈值时放行
- `ThresholdRebalancePolicy.apply()` 偏差低于阈值时拦截

### 11.4 Engine 测试

- 单基金池回测
- 多基金池回测
- 有/无 RebalancePolicy
- T+1 执行规则
- 先卖后买顺序

### 11.5 Service 测试

- 策略创建正确
- 端到端回测返回结果

---

## 十二、实现顺序建议

1. 数据模型（`PortfolioSignal`、`PortfolioBacktestResult`）
2. `PortfolioStrategy` 基类
3. `PortfolioMomentumStrategy`
4. `RebalancePolicy` 接口修订
5. `ThresholdRebalancePolicy` 实现
6. `PortfolioBacktestEngine`
7. `PortfolioBacktestService`
8. UI 区块
9. 全量测试

---

## 十三、后续扩展

| Phase | 内容 |
|-------|------|
| Phase 3C | 多基金轮动与再平衡（本设计） |
| Phase 3D | 回测统计精细化 |
| 后续 | 与虚拟账户打通、税费/滑点、动态基金池 |