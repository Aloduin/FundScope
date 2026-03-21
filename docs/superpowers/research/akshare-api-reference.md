# akshare API 参考文档

> 本文档基于 akshare v1.18.42 版本实测编写，记录基金相关 API 的真实可用调用方式。
>
> **在线文档：** https://akshare.akfamily.xyz/
> **官方文档路径：** D:\Projects\akshare\docs\data\fund\fund_public.md

---

## 目录

1. [核心接口（MVP 必备）](#1-核心接口 mvp 必备)
2. [基金列表接口](#2-基金列表接口)
3. [基金历史净值接口](#3-基金历史净值接口)
4. [ETF/LOF 接口](#4-etflof 接口)
5. [基金详细信息接口](#5-基金详细信息接口)
6. [错误处理与注意事项](#6-错误处理与注意事项)

---

## 1. 核心接口（MVP 必备）

### MVP 数据获取方案

FundScope MVP 阶段推荐使用以下两个核心接口：

```python
import akshare as ak

# 1. 获取所有开放式基金列表（用于获取基金代码）
fund_list_df = ak.fund_open_fund_daily_em()

# 2. 获取单只开放式基金历史净值
nav_df = ak.fund_open_fund_info_em(symbol="000001", indicator="单位净值走势")
```

### 接口对比

| 接口 | 用途 | 返回数据 | 适用场景 |
|------|------|----------|----------|
| `fund_open_fund_daily_em()` | 获取所有开放式基金当日快照 | 所有基金的最新净值、增长率等 | 基金筛选、列表展示 |
| `fund_open_fund_info_em(symbol, indicator)` | 获取单只基金历史数据 | 指定基金的历史净值走势 | 回测、指标计算 |
| `fund_etf_fund_info_em(fund, start_date, end_date)` | 获取 ETF/场内基金历史净值 | ETF/LOF 的历史净值 | ETF/LOF 回测 |

---

## 2. 基金列表接口

### 2.1 开放式基金列表（当日快照）

```python
import akshare as ak

# 获取当日所有开放式基金数据
df = ak.fund_open_fund_daily_em()
```

**函数签名：**
```python
fund_open_fund_daily_em() -> pd.DataFrame
```

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 基金代码 | str | 基金唯一标识 |
| 基金简称 | str | 基金名称缩写 |
| 单位净值 | float | 当前交易日单位净值 |
| 累计净值 | float | 当前交易日累计净值 |
| 前交易日 - 单位净值 | float | 上一交易日单位净值 |
| 前交易日 - 累计净值 | float | 上一交易日累计净值 |
| 日增长值 | float | 日增长额 |
| 日增长率 | float | 日增长率 (%) |
| 申购状态 | str | 申购状态（开放申购/限大额/封闭期） |
| 赎回状态 | str | 赎回状态（开放赎回/封闭期） |
| 手续费 | str | 申购费率 (%) |

**实测返回示例：**
```
      基金代码             基金简称 2020-12-28-单位净值  ...  申购状态  赎回状态    手续费
0      010407        安信中债 1-3 年政策性金融债 C          1.0906  ...  开放申购  开放赎回  0.00%
1      161725             招商中证白酒指数分级          1.3869  ...   限大额  开放赎回  0.10%
2      160632                  鹏华酒分级          1.0360  ...  开放申购  开放赎回  0.12%
```

**数据更新时间：** 每个交易日 16:00-23:00 更新当日数据

**用途：**
- 获取所有可用基金代码
- 基金筛选和排行
- 实时行情监控

---

### 2.2 基金名称列表

```python
import akshare as ak

# 获取所有基金名称列表
df = ak.fund_name_em()
```

**函数签名：**
```python
fund_name_em() -> pd.DataFrame
```

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 基金代码 | object | 基金代码 |
| 拼音缩写 | object | 拼音首字母缩写 |
| 基金简称 | object | 基金简称 |
| 基金类型 | object | 混合型/股票型/债券型等 |
| 拼音全称 | object | 完整拼音 |

**实测返回示例：**
```
       基金代码      拼音缩写  ...  基金类型                              拼音全称
0      000001        HXCZHH  ...   混合型                  HUAXIACHENGZHANGHUNHE
1      000002        HXCZHH  ...   混合型                  HUAXIACHENGZHANGHUNHE
2      000003      ZHKZZZQA  ...   债券型           ZHONGHAIKEZHUANZHAIZHAIQUANA
```

---

## 3. 基金历史净值接口

### 3.1 开放式基金历史净值（核心接口）

```python
import akshare as ak

# 获取单只开放式基金历史净值
df = ak.fund_open_fund_info_em(symbol="000001", indicator="单位净值走势")

# 获取累计净值走势
df = ak.fund_open_fund_info_em(symbol="000001", indicator="累计净值走势")

# 获取累计收益率走势（支持时间范围选择）
df = ak.fund_open_fund_info_em(
    symbol="000001",
    indicator="累计收益率走势",
    period="3 年"  # 可选：1 月/3 月/6 月/1 年/3 年/5 年/今年来/成立来
)
```

**函数签名：**
```python
fund_open_fund_info_em(
    symbol: str = '710001',
    indicator: str = '单位净值走势',
    period: str = '成立来'
) -> pd.DataFrame
```

**参数说明：**
- `symbol`: 基金代码（6 位数字），通过 `fund_open_fund_daily_em()` 获取
- `indicator`: 指标类型，可选值：
  - `单位净值走势` - 返回单位净值历史
  - `累计净值走势` - 返回累计净值历史
  - `累计收益率走势` - 返回累计收益率（需配合 period 参数）
  - `同类排名走势` - 返回同类排名
  - `同类排名百分比` - 返回同类排名百分比
  - `分红送配详情` - 返回分红信息
  - `拆分详情` - 返回拆分信息
- `period`: 时间范围（仅对 `累计收益率走势` 有效），可选：
  - `1 月`、`3 月 `、`6 月`
  - `1 年 `、`3 年`、`5 年`
  - `今年来 `、` 成立来`

**返回字段（单位净值走势）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 净值日期 | object | 净值发布日期 |
| 单位净值 | float64 | 每份基金份额的净值 |
| 日增长率 | float64 | 日增长率 (%) |

**返回字段（累计净值走势）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 净值日期 | object | 净值发布日期 |
| 累计净值 | float64 | 单位净值 + 累计分红 |

**返回字段（累计收益率走势）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 日期 | object | 日期 |
| 累计收益率 | float64 | 累计收益率 (%) |

**实测返回示例（单位净值走势）：**
```
       净值日期    单位净值  日增长率
0     2011-09-21  1.0000  0.00
1     2011-09-23  1.0000  0.00
2     2011-09-30  1.0001  0.01
3     2011-10-14  1.0005  0.04
```

**实测返回示例（累计净值走势）：**
```
       净值日期    累计净值
0     2011-09-21  1.0000
1     2011-09-23  1.0000
2     2011-09-30  1.0001
```

**注意事项：**
- 该接口返回的数据可能存在非连续日期（跳过非交易日）
- 部分老基金数据可能从成立日开始
- 建议在获取数据后手动处理日期列：
  ```python
  df['净值日期'] = pd.to_datetime(df['净值日期'], errors='coerce')
  ```

---

### 3.2 ETF/场内基金历史净值

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

**参数说明：**
- `fund`: 基金代码（6 位数字）
- `start_date`: 开始日期，格式 YYYYMMDD
- `end_date`: 结束日期，格式 YYYYMMDD

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

---

## 4. ETF/LOF 接口

### 4.1 ETF 实时行情

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

---

### 4.2 ETF 历史行情（东方财富）

```python
import akshare as ak

# 获取 ETF 历史行情（日频率）
df = ak.fund_etf_hist_em(
    symbol="510300",
    period="daily",
    start_date="20200101",
    end_date="20251231",
    adjust=""  # 不复权
)

# 前复权
df = ak.fund_etf_hist_em(symbol="510300", adjust="qfq")

# 后复权（推荐用于量化回测）
df = ak.fund_etf_hist_em(symbol="510300", adjust="hfq")
```

**函数签名：**
```python
fund_etf_hist_em(
    symbol: str = '513500',
    period: str = 'daily',  # 'daily', 'weekly', 'monthly'
    start_date: str = '20000101',
    end_date: str = '20230104',
    adjust: str = ''  # '': 不复权，'qfq': 前复权，'hfq': 后复权
) -> pd.DataFrame
```

**参数说明：**
- `symbol`: ETF 代码（6 位数字）
- `period`: 周期，可选 `daily`、`weekly`、`monthly`
- `start_date`: 开始日期，格式 YYYYMMDD
- `end_date`: 结束日期，格式 YYYYMMDD
- `adjust`: 复权类型，可选：
  - `''`: 不复权
  - `'qfq'`: 前复权
  - `'hfq'`: 后复权（推荐用于量化回测）

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| 日期 | object | 交易日期 |
| 开盘 | float64 | 开盘价 |
| 收盘 | float64 | 收盘价 |
| 最高 | float64 | 最高价 |
| 最低 | float64 | 最低价 |
| 成交量 | int64 | 成交量（股） |
| 成交额 | float64 | 成交额（元） |
| 振幅 | float64 | 振幅 (%) |
| 涨跌幅 | float64 | 涨跌幅 (%) |
| 涨跌额 | float64 | 涨跌额 |
| 换手率 | float64 | 换手率 (%) |

**数据复权说明：**

1. **为何要复权**：由于股票存在配股、分拆、合并和发放股息等事件，会导致股价出现较大的缺口。若使用不复权的价格处理数据、计算各种指标，将会导致它们失去连续性，且使用不复权价格计算收益也会出现错误。

2. **前复权**：保持当前价格不变，将历史价格进行增减，从而使股价连续。
   - 优点：能一眼看出股价的历史走势，叠加各种技术指标也比较顺畅
   - 缺点：历史价格是时变的，在不同时点看到的历史前复权价可能出现差异

3. **后复权**：保证历史价格不变，在每次股票权益事件发生后，调整当前的股票价格。
   - 优点：可以被看作投资者的长期财富增长曲线，反映投资者的真实收益率情况
   - **推荐用于量化投资研究**

**实测返回示例（不复权）：**
```
       日期     开盘     收盘     最高  ...    振幅   涨跌幅    涨跌额   换手率
0     2014-01-15  0.994  0.986  0.996  ...  0.00  0.00  0.000  1.88
1     2014-01-16  0.988  0.991  0.994  ...  0.61  0.51  0.005  0.56
```

---

### 4.3 LOF 历史行情（东方财富）

```python
import akshare as ak

# 获取 LOF 历史行情
df = ak.fund_lof_hist_em(
    symbol="166009",
    period="daily",
    start_date="20200101",
    end_date="20251231",
    adjust="hfq"  # 后复权
)
```

**函数签名：**
```python
fund_lof_hist_em(
    symbol: str = '166009',
    period: str = 'daily',
    start_date: str = '20000101',
    end_date: str = '20230104',
    adjust: str = ''
) -> pd.DataFrame
```

**返回字段：** 与 `fund_etf_hist_em` 相同

---

### 4.4 ETF 历史行情（新浪财经）

```python
import akshare as ak

# 获取 ETF 历史行情（Sina 数据源）
df = ak.fund_etf_hist_sina(symbol="sh510050")
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
| date | object | 交易日期 |
| open | float64 | 开盘价 |
| high | float64 | 最高价 |
| low | float64 | 最低价 |
| close | float64 | 收盘价 |
| volume | int64 | 成交量（手） |

**实测返回示例：**
```
            date   open   high    low  close      volume
0     2005-02-23  0.881  0.882  0.866  0.876  1269742542
1     2005-02-24  0.876  0.876  0.868  0.876   451614223
```

---

## 5. 基金详细信息接口

### 5.1 基金基本信息（雪球）

```python
import akshare as ak

# 获取单只基金基本信息
df = ak.fund_individual_basic_info_xq(symbol="000001")
```

**函数签名：**
```python
fund_individual_basic_info_xq(
    symbol: str = '000001',
    timeout: float = None
) -> pd.DataFrame
```

**返回字段：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| item | object | 指标名称 |
| value | object | 指标值 |

**返回内容包括：**
- 基金代码、基金名称、基金全称
- 成立时间
- 最新规模
- 基金公司
- 基金经理
- 托管银行
- 基金类型
- 评级机构、基金评级
- 投资策略、投资目标
- 业绩比较基准

**实测返回示例：**
```
      item                                              value
0     基金代码                                             000001
1     基金名称                                             华夏成长混合
2     基金全称                                            华夏成长前收费
3     成立时间                                         2001-12-18
4     最新规模                                             27.30 亿
5     基金公司                                         华夏基金管理有限公司
6     基金经理                                            王泽实 万方方
7     托管银行                                       中国建设银行股份有限公司
8     基金类型                                             混合型 - 偏股
9     评级机构                                               晨星评级
10    基金评级                                               一星基金
```

---

### 5.2 基金费率

```python
import akshare as ak

# 获取基金费率信息
df = ak.fund_fee_em(symbol="000001")
```

---

### 5.3 基金规模

```python
import akshare as ak

# 获取基金规模信息
df = ak.fund_scale_change_em(symbol="000001")

# 获取 ETF 规模（上交所）
df = ak.fund_etf_scale_sse()

# 获取 ETF 规模（深交所）
df = ak.fund_etf_scale_szse()
```

---

### 5.4 基金持仓

```python
import akshare as ak

# 获取基金股票持仓
df = ak.fund_portfolio_hold_em(symbol="000001")

# 获取基金债券持仓
df = ak.fund_portfolio_bond_hold_em(symbol="000001")

# 获取基金行业配置
df = ak.fund_portfolio_industry_allocation_em(symbol="000001")
```

---

### 5.5 基金评级

```python
import akshare as ak

# 获取晨星评级
df = ak.fund_rating_ja()

# 获取招商评级
df = ak.fund_rating_zs()

# 获取上海评级
df = ak.fund_rating_sh()
```

---

### 5.6 基金分红

```python
import akshare as ak

# 获取基金分红信息
df = ak.fund_fh_em(symbol="000001")

# 获取基金分红排行
df = ak.fund_fh_rank_em()
```

---

## 6. 错误处理与注意事项

### 6.1 常见错误类型

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

### 6.2 接口限制

| 接口 | 限制 | 建议 |
|------|------|------|
| fund_etf_spot_em | 网络不稳定 | 添加重试机制 |
| fund_etf_hist_sina | 需要市场前缀 | 自动添加 sh/sz 前缀 |
| fund_open_fund_info_em | 数据量大时较慢 | 指定时间范围 |

### 6.3 数据更新频率

- **净值数据**：每个交易日更新（T 日 20:00 后）
- **实时行情**：交易时间内实时更新
- **持仓数据**：季度更新（季报披露后）
- **规模数据**：季度更新

### 6.4 最佳实践

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
            DataFrame with columns: 净值日期，单位净值，累计净值，日增长率
        """
        # 日期默认值
        if not start_date:
            start_date = "20000101"
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            df = ak.fund_open_fund_info_em(
                symbol=code,
                indicator="单位净值走势"
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

    def get_etf_history(self, code: str, adjust: str = "hfq") -> pd.DataFrame:
        """
        获取 ETF 历史行情

        Args:
            code: 基金代码（6 位数字）
            adjust: 复权类型，默认后复权

        Returns:
            DataFrame with columns: 日期，开盘，收盘，最高，最低，成交量，成交额，振幅，涨跌幅，涨跌额，换手率
        """
        try:
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date="20000101",
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust=adjust
            )

            if df.empty:
                print(f"ETF {code} 未找到数据")
                return pd.DataFrame()

            # 日期列处理
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')

            return df

        except Exception as e:
            print(f"获取 ETF {code} 数据失败：{e}")
            return pd.DataFrame()


# 使用示例
if __name__ == "__main__":
    fetcher = FundDataFetcher()

    # 获取开放式基金历史净值
    nav_df = fetcher.get_fund_nav("000001")
    print(nav_df.head())

    # 获取 ETF 历史行情（后复权）
    hist_df = fetcher.get_etf_history("510300", adjust="hfq")
    print(hist_df.head())
```

---

## 附录：完整 API 列表

### 基础数据
- `fund_name_em` - 基金名称列表
- `fund_open_fund_daily_em` - 开放式基金当日数据
- `fund_open_fund_info_em` - 开放式基金历史净值
- `fund_etf_fund_info_em` - ETF/场内基金净值
- `fund_etf_spot_em` - ETF 实时行情
- `fund_etf_hist_em` - ETF 历史行情（东方财富）
- `fund_etf_hist_sina` - ETF 历史行情（新浪财经）
- `fund_lof_hist_em` - LOF 历史行情

### 基金信息
- `fund_individual_basic_info_xq` - 基金基本信息（雪球）
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

---

## 版本信息

- **akshare 版本**: 1.18.42
- **文档更新日期**: 2026-03-21
- **数据源**: 东方财富、新浪财经、雪球

## 注意事项

1. 本文档所有接口均需联网使用
2. 部分接口可能有访问频率限制
3. 数据仅供参考，请以官方公告为准
4. 建议在代码中添加适当的错误处理和重试机制
