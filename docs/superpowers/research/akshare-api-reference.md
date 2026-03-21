# akshare API 参考文档

> 本文档基于 akshare v1.18.42 版本实测编写，记录基金相关 API 的真实可用调用方式。
>
> **在线文档：** https://akshare.akfamily.xyz/

---

## 目录

1. [基金列表接口](#1-基金列表接口)
2. [基金历史净值接口](#2-基金历史净值接口)
3. [ETF/LOF 接口](#3-etflof 接口)
4. [基金详细信息接口](#4-基金详细信息接口)
5. [错误处理与注意事项](#5-错误处理与注意事项)

---

## 1. 基金列表接口

### 1.1 开放式基金列表

```python
import akshare as ak

# 获取所有开放式基金历史数据（默认）
df = ak.fund_open_fund_info_em()

# 指定基金代码获取单只基金数据
df = ak.fund_open_fund_info_em(symbol="710001")
```

**函数签名：**
```python
fund_open_fund_info_em(
    symbol: str = '710001',
    indicator: str = '单位净值',
    period: str = '成立以来'
) -> pd.DataFrame
```

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 净值日期 | datetime | 净值发布日期 |
| 单位净值 | float | 每份基金份额的净值 |
| 累计净值 | float | 单位净值 + 累计分红 |

**参数说明：**
- `symbol`: 基金代码，可通过 `fund_open_fund_daily_em()` 获取所有可用代码
- `indicator`: 选择指标类型，可选 `"单位净值"` 等
- `period`: 时间范围，可选 `"1 年"`, `"3 年"`, `"6 年"`, `"1 年"`, `"3 年"`, `"5 年"`, "`成立以来`", "`今年以来`"

**实测返回示例：**
```
         净值日期    单位净值  累计净值
0  2011-09-21  1.0000  0.00
1  2011-09-23  1.0000  0.00
2  2011-09-30  1.0001  0.01
```

### 1.2 获取基金代码列表

```python
# 获取当日开放式基金数据（包含所有基金代码）
df = ak.fund_open_fund_daily_em()
```

---

## 2. 基金历史净值接口

### 2.1 ETF/场内基金历史净值

```python
import akshare as ak

# 获取 ETF 或 LOF 基金历史净值
df = ak.fund_etf_fund_info_em(fund="510300")

# 指定时间范围
df = ak.fund_etf_fund_info_em(
    fund="510300",
    start_date="20200101",
    end_date="20251231"
)
```

**函数签名：**
```python
fund_etf_fund_info_em(
    fund: str = '511280',
    start_date: str = '20000101',
    end_date: str = '20500101'
) -> pd.DataFrame
```

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 净值日期 | datetime | 净值发布日期 |
| 单位净值 | float | 每份基金份额的净值 |
| 累计净值 | float | 单位净值 + 累计分红 |
| 涨跌幅 | float | 日涨跌幅 (%) |
| 申购状态 | string | 申购状态（开放/暂停） |
| 赎回状态 | string | 赎回状态（开放/暂停） |

**实测返回示例：**
```
         净值日期  单位净值  累计净值  涨跌幅  申购状态  赎回状态
0  2012-05-04   1.007   1.007   NaN  暂停申购  暂停赎回
1  2012-05-11   2.637   0.978 -2.86  暂停申购  暂停赎回
2  2012-05-18   2.574   0.955 -2.39  暂停申购  暂停赎回
```

**适用基金类型：**
- ETF（交易型开放式指数基金）
- LOF（上市型开放式基金）
- 场内基金

**测试通过的基金代码：**
| 代码 | 名称 | 类型 |
|------|------|------|
| 510300 | 沪深 300ETF | ETF |
| 159915 | 创业板 ETF | ETF |
| 518880 | 黄金 ETF | ETF |
| 000001 | 华夏成长混合 | 开放式基金 |
| 110022 | 易方达消费行业 | 开放式基金 |

---

## 3. ETF/LOF 接口

### 3.1 ETF 实时行情

```python
# 获取 ETF 实时行情（可能因网络问题失败）
df = ak.fund_etf_spot_em()
```

**函数签名：**
```python
fund_etf_spot_em() -> pd.DataFrame
```

**用途：** 获取交易所 ETF 基金的实时行情数据

**注意事项：**
- 该接口对网络稳定性要求较高
- 实测中可能返回 `ConnectionError`
- 建议在代码中添加重试机制

### 3.2 ETF 历史行情（Sina 数据源）

```python
# 获取 ETF 历史 K 线数据
df = ak.fund_etf_hist_sina(symbol="sh510300")
```

**函数签名：**
```python
fund_etf_hist_sina(symbol: str = 'sh510050') -> pd.DataFrame
```

**参数说明：**
- `symbol`: 基金代码，需要添加市场前缀
  - `sh` + 6 位代码：上海证券交易所
  - `sz` + 6 位代码：深圳证券交易所

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| date | datetime | 交易日期 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | int | 成交量（股） |
| amount | int | 成交额（元） |

**实测返回示例：**
```
        date   open   high    low  close      volume      amount
0 2012-05-28  2.551  2.607  2.544  2.604  1277518720  3285755392
1 2012-05-29  2.602  2.661  2.602  2.644   714948992  1875593344
2 2012-05-30  2.642  2.647  2.633  2.636   265887200   701725760
```

### 3.3 ETF 分类列表

```python
# 获取 ETF 分类列表
df = ak.fund_etf_category_sina(symbol="ETF 基金")

# 可选项：
# - "债券型基金"
# - "ETF 基金"
# - "LOF 基金"
```

**函数签名：**
```python
fund_etf_category_sina(symbol: str = 'LOF 基金') -> pd.DataFrame
```

**参数说明：**
- `symbol`: 基金类别，可选：
  - `"债券型基金"`
  - `"ETF 基金"`
  - `"LOF 基金"`

---

## 4. 基金详细信息接口

### 4.1 基金基本信息

```python
# 获取基金名称
df = ak.fund_name_em()

# 获取基金经理信息
df = ak.fund_manager_em()
```

### 4.2 基金费率

```python
# 获取基金费率信息
df = ak.fund_fee_em(symbol="000001")
```

### 4.3 基金分红信息

```python
# 获取基金分红信息
df = ak.fund_fh_em(symbol="000001")

# 获取基金分红排行
df = ak.fund_fh_rank_em()
```

### 4.4 基金持仓

```python
# 获取基金股票持仓
df = ak.fund_portfolio_hold_em(symbol="000001")

# 获取基金债券持仓
df = ak.fund_portfolio_bond_hold_em(symbol="000001")

# 获取基金行业配置
df = ak.fund_portfolio_industry_allocation_em(symbol="000001")
```

### 4.5 基金规模

```python
# 获取基金规模信息
df = ak.fund_scale_change_em(symbol="000001")

# 获取 ETF 规模（上交所）
df = ak.fund_etf_scale_sse()

# 获取 ETF 规模（深交所）
df = ak.fund_etf_scale_szse()
```

### 4.6 基金评级

```python
# 获取晨星评级
df = ak.fund_rating_ja()

# 获取招商评级
df = ak.fund_rating_zs()

# 获取上海评级
df = ak.fund_rating_sh()
```

### 4.7 基金公告

```python
# 获取基金分红公告
df = ak.fund_announcement_dividend_em(symbol="000001")

# 获取基金人事变动公告
df = ak.fund_announcement_personnel_em(symbol="000001")

# 获取基金定期报告
df = ak.fund_announcement_report_em(symbol="000001")
```

---

## 5. 错误处理与注意事项

### 5.1 常见错误类型

#### 网络连接错误
```python
# 错误示例：RemoteDisconnected
ConnectionError: ('Connection aborted.',
                  RemoteDisconnected('Remote end closed connection without response'))
```

**处理方式：**
```python
import time
from requests.exceptions import ConnectionError

def fetch_with_retry(func, max_retries=3, delay=1):
    for i in range(max_retries):
        try:
            return func()
        except ConnectionError:
            if i < max_retries - 1:
                time.sleep(delay * (i + 1))  # 递增延迟
            else:
                raise
```

#### 空数据返回
```python
# 某些基金代码可能返回空 DataFrame
df = ak.fund_etf_hist_sina(symbol="invalid_symbol")
# 返回：Empty DataFrame
# Columns: []
# Index: []
```

**处理方式：**
```python
if df.empty:
    print("未找到该基金数据")
    return None
```

#### 日期解析警告
```python
UserWarning: Could not infer format, so each element will be parsed individually
```

**处理方式：**
```python
# 在获取数据后手动处理日期列
df['净值日期'] = pd.to_datetime(df['净值日期'], errors='coerce')
```

### 5.2 接口限制

| 接口 | 限制 | 建议 |
|------|------|------|
| fund_etf_spot_em | 网络不稳定 | 添加重试机制 |
| fund_etf_hist_sina | 需要市场前缀 | 自动添加 sh/sz 前缀 |
| fund_open_fund_info_em | 数据量大时较慢 | 指定时间范围 |

### 5.3 数据更新频率

- **净值数据**：每个交易日更新（T 日 20:00 后）
- **实时行情**：交易时间内实时更新
- **持仓数据**：季度更新（季报披露后）
- **规模数据**：季度更新

### 5.4 最佳实践

```python
import akshare as ak
import pandas as pd
from datetime import datetime

class FundDataFetcher:
    """基金数据获取器"""

    def __init__(self):
        self.cache = {}

    def get_fund_nav(self, code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取基金历史净值

        Args:
            code: 基金代码
            start_date: 开始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD

        Returns:
            DataFrame with columns: 净值日期，单位净值，累计净值，涨跌幅，申购状态，赎回状态
        """
        # 日期默认值
        if not start_date:
            start_date = "20000101"
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            df = ak.fund_etf_fund_info_em(
                fund=code,
                start_date=start_date,
                end_date=end_date
            )

            # 数据验证
            if df.empty:
                print(f"基金 {code} 未找到数据")
                return pd.DataFrame()

            # 日期列处理
            if '净值日期' in df.columns:
                df['净值日期'] = pd.to_datetime(df['净值日期'], errors='coerce')

            return df

        except Exception as e:
            print(f"获取基金 {code} 数据失败：{e}")
            return pd.DataFrame()

    def get_etf_history(self, code: str) -> pd.DataFrame:
        """
        获取 ETF 历史行情

        Args:
            code: 基金代码（6 位数字）

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        # 自动添加市场前缀
        if code.startswith('5'):  # 上交所 ETF
            symbol = f"sh{code}"
        elif code.startswith('1'):  # 深交所 ETF
            symbol = f"sz{code}"
        else:
            symbol = f"sh{code}"  # 默认上交所

        try:
            df = ak.fund_etf_hist_sina(symbol=symbol)

            if df.empty:
                print(f"ETF {code} 未找到数据")
                return pd.DataFrame()

            # 日期列处理
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')

            return df

        except Exception as e:
            print(f"获取 ETF {code} 数据失败：{e}")
            return pd.DataFrame()


# 使用示例
if __name__ == "__main__":
    fetcher = FundDataFetcher()

    # 获取沪深 300ETF 历史净值
    nav_df = fetcher.get_fund_nav("510300")
    print(nav_df.head())

    # 获取 ETF 历史行情
    hist_df = fetcher.get_etf_history("510300")
    print(hist_df.head())
```

---

## 附录：完整 API 列表

共发现 101 个基金相关 API，以下是主要 API：

### 基础数据
- `fund_open_fund_info_em` - 开放式基金净值
- `fund_open_fund_daily_em` - 开放式基金当日数据
- `fund_etf_fund_info_em` - ETF/场内基金净值
- `fund_etf_spot_em` - ETF 实时行情
- `fund_etf_hist_sina` - ETF 历史行情

### 基金信息
- `fund_name_em` - 基金名称列表
- `fund_manager_em` - 基金经理信息
- `fund_fee_em` - 基金费率
- `fund_scale_change_em` - 基金规模变动

### 持仓分析
- `fund_portfolio_hold_em` - 股票持仓
- `fund_portfolio_bond_hold_em` - 债券持仓
- `fund_portfolio_industry_allocation_em` - 行业配置

### 评级与分红
- `fund_rating_ja` - 晨星评级
- `fund_rating_zs` - 招商评级
- `fund_rating_sh` - 上海评级
- `fund_fh_em` - 基金分红
- `fund_fh_rank_em` - 分红排行

### 公告信息
- `fund_announcement_dividend_em` - 分红公告
- `fund_announcement_personnel_em` - 人事变动公告
- `fund_announcement_report_em` - 定期报告

---

## 版本信息

- **akshare 版本**: 1.18.42
- **文档更新日期**: 2026-03-21
- **数据源**: 东方财富、新浪财经

## 注意事项

1. 本文档所有接口均需联网使用
2. 部分接口可能有访问频率限制
3. 数据仅供参考，请以官方公告为准
4. 建议在代码中添加适当的错误处理和重试机制
