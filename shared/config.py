"""FundScope 统一配置模块"""
from pathlib import Path
from datetime import date

# Data source configuration
USE_REAL_DATA = True  # True = 使用真实 akshare API, False = 使用 mock 数据

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PARQUET_DIR = DATA_DIR / "parquet"
SQLITE_DB_PATH = DATA_DIR / "sqlite" / "fundscope.db"
CACHE_DIR = DATA_DIR / "cache"

PARQUET_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Data version for tracking data snapshots
DATA_VERSION = date.today().strftime("%Y%m%d")

FUND_TYPE_MAPPING = {
    "股票型": "equity",
    "混合型": "mixed",
    "债券型": "bond",
    "指数型": "index",
}
DEFAULT_FUND_TYPE = "mixed"

SCORE_WEIGHTS_BY_TYPE: dict[str, dict[str, float]] = {
    "equity": {
        "return": 0.35,
        "risk": 0.25,
        "stability": 0.20,
        "cost": 0.10,
        "size": 0.05,
        "manager": 0.05,
    },
    "bond": {
        "return": 0.20,
        "risk": 0.35,
        "stability": 0.25,
        "cost": 0.10,
        "size": 0.05,
        "manager": 0.05,
    },
    "index": {
        "return": 0.35,
        "risk": 0.25,
        "stability": 0.15,
        "cost": 0.15,
        "size": 0.05,
        "manager": 0.05,
    },
    "mixed": {
        "return": 0.30,
        "risk": 0.25,
        "stability": 0.20,
        "cost": 0.10,
        "size": 0.08,
        "manager": 0.07,
    },
}

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "红利低波": ["红利", "低波", "高股息", "dividend"],
    "半导体": ["半导体", "芯片", "集成电路", "科创芯片"],
    "医疗": ["医疗", "医药", "生物", "健康", "医健"],
    "AI": ["人工智能", "AI", "数字经济", "科技创新"],
    "消费": ["消费", "白酒", "食品", "零售"],
    "新能源": ["新能源", "光伏", "储能", "电池", "碳中和"],
    "债券": ["债券", "纯债", "信用债", "利率债"],
    "宽基指数": ["沪深 300", "中证 500", "中证 1000", "全 A"],
}

L1_CACHE_TTL_SECONDS = 30 * 60
L2A_CACHE_TTL_DAYS = 7

BACKTEST_DEFAULT_INITIAL_CASH = 100000.0
