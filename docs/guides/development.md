# FundScope 开发指南

## 1. 开发环境设置

### 1.1 克隆仓库

```bash
git clone https://github.com/Aloduin/FundScope.git
cd FundScope
```

### 1.2 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e ".[dev]"
```

### 1.3 验证安装

```bash
# 运行测试
uv run pytest

# 启动应用
uv run streamlit run ui/app.py
```

---

## 2. 代码规范

### 2.1 类型注解

所有函数必须有类型注解：

```python
def calculate_score(metrics: FundMetrics, fund_type: str) -> FundScore:
    """Calculate fund comprehensive score."""
    ...
```

### 2.2 文档字符串

所有公共函数和类必须有文档字符串：

```python
@dataclass
class FundInfo:
    """Fund basic information.

    Attributes:
        fund_code: Fund code (e.g., '000001')
        fund_name: Fund name
        ...
    """
    ...
```

### 2.3 日志

使用统一日志模块，不使用 print：

```python
from shared.logger import get_logger

logger = get_logger(__name__)
logger.info(f"Processing fund: {fund_code}")
```

---

## 3. 测试规范

### 3.1 测试目录

```
tests/
├── infrastructure/
├── domain/
│   ├── fund/
│   ├── portfolio/
│   └── simulation/
└── service/
```

### 3.2 测试命名

```python
def test_<function>_<scenario>_<expected>()
```

示例：
```python
def test_buy_insufficient_cash_raises():
    """Test that buy with insufficient cash raises."""
    ...
```

### 3.3 测试结构

```python
class TestClassName:
    """Tests for ClassName."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = MyService()

    def test_scenario(self):
        """Test description."""
        # Arrange
        ...
        # Act
        ...
        # Assert
        ...
```

### 3.4 运行测试

```bash
# 全部测试
uv run pytest

# 特定模块
uv run pytest tests/domain/fund/ -v

# 特定文件
uv run pytest tests/domain/fund/test_scorer.py -v

# 特定测试
uv run pytest tests/domain/fund/test_scorer.py::TestCalculateScore::test_score_with_complete_metrics -v
```

---

## 4. 提交规范

### 4.1 Commit 格式

```
<type>: <subject>

[optional body]
```

### 4.2 Type 说明

| Type | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 bug |
| refactor | 重构 |
| docs | 文档 |
| test | 测试 |
| chore | 其他（配置、依赖等） |

### 4.3 示例

```bash
feat: 添加基金评分功能

- 实现多维度评分逻辑
- 支持动态权重
- 处理缺失维度

fix: 修复持仓权重计算错误

refactor: 重构数据源接口
```

---

## 5. 架构约束

### 5.1 依赖方向

严格单向依赖：

```
ui → service → domain → infrastructure
```

**禁止：**
- ❌ ui 直接调用 infrastructure
- ❌ domain 调用 sqlite / akshare
- ❌ infrastructure 调用 domain/service

### 5.2 Domain 层零 IO

`domain/` 层：
- 不调用 akshare
- 不读写文件/数据库
- 仅处理 dataclass / DataFrame

### 5.3 数据源可插拔

所有数据获取通过 `AbstractDataSource`：

```python
from infrastructure.datasource.abstract import AbstractDataSource

class AkShareDataSource(AbstractDataSource):
    ...
```

---

## 6. 开发流程

### 6.1 添加新功能

1. **创建分支**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **编写测试（TDD）**
   ```python
   # tests/domain/mydomain/test_new_feature.py
   def test_new_feature():
       ...
   ```

3. **实现功能**
   ```python
   # domain/mydomain/new_feature.py
   def new_feature():
       ...
   ```

4. **运行测试**
   ```bash
   uv run pytest tests/domain/mydomain/ -v
   ```

5. **提交**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

6. **推送并创建 PR**
   ```bash
   git push -u origin feature/new-feature
   ```

### 6.2 修复 Bug

1. **创建分支**
   ```bash
   git checkout -b fix/bug-description
   ```

2. **编写重现测试**
   ```python
   def test_bug_repro():
       ...
   ```

3. **修复 Bug**

4. **验证测试通过**

5. **提交**
   ```bash
   git add .
   git commit -m "fix: resolve bug description"
   ```

---

## 7. 调试技巧

### 7.1 日志调试

```python
logger.debug(f"Debug info: {data}")
logger.info(f"Processing: {item}")
logger.warning(f"Potential issue: {condition}")
logger.error(f"Error: {e}", exc_info=True)
```

### 7.2 Streamlit 调试

```python
import streamlit as st

st.write("Variable value:", variable)
st.json(data_dict)
st.code(function_output)
```

### 7.3 查看数据库

```bash
# 使用 SQLite 客户端
sqlite3 data/sqlite/fundscope.db

# 查询表
SELECT * FROM fund_info LIMIT 10;
```

---

## 8. 常见问题

### Q1: 如何修改配置？

编辑 `shared/config.py`，修改后重启应用。

### Q2: 如何清空缓存？

删除 `data/cache/` 和 `data/parquet/` 目录。

### Q3: 如何重置数据库？

删除 `data/sqlite/fundscope.db`，重启应用自动重建。

### Q4: 如何查看日志？

日志文件在 `logs/` 目录。

---

## 9. 参考资源

- [快速开始](quickstart.md)
- [架构说明](architecture.md)
- [设计文档](../superpowers/specs/2026-03-21-fundscope-design.md)
- [实施计划](../superpowers/plans/)
