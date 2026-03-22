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

### 2.2 权重归一化约束

`target_weights` 必须满足：

- key 可以包含基金代码和 `"CASH"`
- 所有权重满足 `0 <= w <= 1`
- 总和满足 `abs(sum(weights.values()) - 1.0) < 1e-6`
- 若策略输出不满足约束，视为无效信号并报错

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

### 2.5 策略隔离原则

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
```

**约束：**

- `target_weights` 必须包含 `"CASH"` 键
- 所有权重总和必须等于 1.0

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

```python
@dataclass
class ExecutedTrade:
    # ... 现有字段 ...
    rebalance_id: str | None = None  # 可追溯到某次组合调仓信号
```

**用途：** 支持后续解释面板展示"某次调仓包含哪些买卖"

---

## 四、策略层设计

### 4.1 PortfolioStrategy 基类

**文件：** `domain/backtest/strategies/portfolio_base.py`

```python
from abc import ABC, abstractmethod
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
        nav_histories: dict[str, list[dict]]
    ) -> list[PortfolioSignal]:
        """一次性生成整段期间的所有组合信号。

        Args:
            nav_histories: fund_code -> [{"date": date, "nav": float, ...}, ...]

        Returns:
            按时间排序的 PortfolioSignal 列表
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
    """多基金动量轮动策略。"""

    def __init__(self, config: MomentumConfig | None = None):
        self.config = config or MomentumConfig()

    def name(self) -> str:
        return f"PortfolioMomentum({self.config.lookback_days}, top{self.config.top_n})"

    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]]
    ) -> list[PortfolioSignal]:
        signals = []

        # 1. 对齐时间轴
        aligned_dates = self._align_dates(nav_histories)

        # 2. 按间隔生成信号
        last_signal_date = None
        for current_date in aligned_dates:
            if last_signal_date is None or \
               (current_date - last_signal_date).days >= self.config.signal_interval_days:

                # 3. 计算各基金收益率
                returns = self._calculate_returns(
                    nav_histories, current_date, self.config.lookback_days
                )

                # 4. 选前 top_n
                sorted_funds = sorted(returns.items(), key=lambda x: x[1], reverse=True)
                top_funds = [f[0] for f in sorted_funds[:self.config.top_n]]

                # 5. 构造目标权重（等权 + CASH）
                target_weights = self._build_target_weights(top_funds)

                # 6. 生成信号
                signal = PortfolioSignal(
                    date=current_date,
                    action="REBALANCE",
                    target_weights=target_weights,
                    confidence=1.0,
                    reason=f"动量轮动：{', '.join(top_funds)}"
                )
                signals.append(signal)
                last_signal_date = current_date

        return signals

    def _align_dates(self, nav_histories: dict[str, list[dict]]) -> list[date]:
        """取所有基金净值日期的交集。"""
        date_sets = []
        for nav_list in nav_histories.values():
            dates = {d["date"] for d in nav_list}
            date_sets.append(dates)
        common_dates = sorted(set.intersection(*date_sets))
        return common_dates

    def _calculate_returns(
        self,
        nav_histories: dict[str, list[dict]],
        as_of_date: date,
        lookback_days: int
    ) -> dict[str, float]:
        """计算各基金在 lookback 窗口内的收益率。"""
        returns = {}
        cutoff = as_of_date - timedelta(days=lookback_days)

        for fund_code, nav_list in nav_histories.items():
            # 筛选窗口内数据
            window = [d for d in nav_list if cutoff <= d["date"] <= as_of_date]
            if len(window) < 2:
                continue  # 数据不足，跳过

            start_nav = window[0]["nav"]
            end_nav = window[-1]["nav"]
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
    """组合回测引擎。"""

    def __init__(self, initial_cash: float = 100000):
        self.initial_cash = initial_cash

    def run(
        self,
        strategy: PortfolioStrategy,
        fund_codes: list[str],
        nav_histories: dict[str, list[dict]],
        rebalance_policy: RebalancePolicy | None = None,
    ) -> PortfolioBacktestResult:
        """运行组合回测。

        Args:
            strategy: 组合策略
            fund_codes: 基金池
            nav_histories: fund_code -> nav history
            rebalance_policy: 再平衡策略（可选）

        Returns:
            组合回测结果
        """
        # 1. 对齐时间轴
        aligned_dates = self._align_dates(nav_histories)
        start_date = aligned_dates[0]
        end_date = aligned_dates[-1]

        # 2. 初始化组合状态
        state = PortfolioState(
            cash=self.initial_cash,
            holdings={},
            weights={"CASH": 1.0}
        )

        # 3. 生成所有信号（一次性）
        signals = strategy.generate_portfolio_signals(nav_histories)
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

            # 4.5 T+1 执行（如果当天有要执行的信号）
            # 注意：信号在 T 日产生，我们在 T 日记录它，在下一次循环（T+1）执行
            # 这里简化处理：信号在 T 日产生，我们在 T 日就执行（用 T 日 NAV）
            # 实际应该用 T+1 NAV

            if signal_to_execute and i + 1 < len(aligned_dates):
                # 获取 T+1 的 NAV
                next_date = aligned_dates[i + 1]
                next_navs = nav_by_date.get(next_date, {})

                # 4.6 应用 RebalancePolicy
                if rebalance_policy:
                    context = self._build_context(current_date, current_navs)
                    current_positions = self._get_current_positions(state)
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

    def _align_dates(self, nav_histories: dict[str, list[dict]]) -> list[date]:
        """取所有基金净值日期的交集。"""
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

    def _get_current_positions(self, state: PortfolioState) -> list[dict]:
        """获取当前持仓列表。"""
        total_value = state.cash + sum(state.holdings.values())  # 简化，实际需要 NAV
        positions = []

        for fund_code, shares in state.holdings.items():
            positions.append({
                "fund_code": fund_code,
                "shares": shares,
                "weight": 0.0  # 实际计算需要 NAV
            })

        return positions

    def _build_context(self, current_date: date, current_navs: dict[str, float]) -> SignalContext:
        """构造信号上下文。"""
        return SignalContext(
            date=current_date,
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
                    shares=shares,
                    price=nav,
                    amount=amount,
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
                    shares=shares_to_buy,
                    price=nav,
                    amount=delta,
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
                    shares=shares_to_sell,
                    price=nav,
                    amount=-delta,
                    rebalance_id=rebalance_id,
                ))

        # 4. 更新现金
        state.cash = target_amounts.get("CASH", state.cash)

        # 5. 更新权重
        total_value_after = self._calculate_portfolio_value(state, next_navs)
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
            "sharpe_ratio": 0.0,  # TODO: 实现
        }
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
from infrastructure.data_source import AkshareDataSource

class PortfolioBacktestService:
    """组合回测服务。"""

    def __init__(self, datasource: AkshareDataSource | None = None):
        self.datasource = datasource or AkshareDataSource()
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
        """运行组合回测。"""
        # 1. 获取 NAV 数据
        nav_histories = {}
        for fund_code in fund_codes:
            nav_histories[fund_code] = self.datasource.get_fund_nav_history(fund_code)

        # 2. 创建策略
        strategy = self._create_strategy(strategy_name, strategy_params)

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
| `domain/backtest/engine.py` | 新增 `PortfolioBacktestEngine` |
| `service/portfolio_backtest_service.py` | 新增 |
| `ui/pages/3_strategy_lab.py` | 新增组合回测区块 |

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