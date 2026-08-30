# 发财（Stock Quant）

A 股量化策略研究与回测项目：定时更新行情数据、策略回测、每日选股，并提供 Web 前端可视化。

---

## 目录结构

```text
strategy/                量化策略
  predict.py             回测/预测入口（Predictor 类 + 命令行）
  daily_predict.py       每日批量预测任务（多策略并发 + 结果推送）
  load_stock.py          行情加载与按日期截取
  strategy_hub/          策略实现（每个文件一个策略）
update/                  数据更新
  update_market.py       单只股票更新入口
  update_market_patch.py 全市场并发更新入口
  fetch_market.py        行情拉取、指标计算与落盘（MarketAnalyzer）
  fetch_stock_info.py    个股信息（市值/股本）抓取
  check.py               数据完整性检查（对齐交易日历）
  sources/               数据源（可插拔）
    base.py              数据源统一接口 DailySource
    __init__.py          数据源注册表 create_source()
    adata_source.py      adata/akshare 远程数据源（remote）
    ths_source.py        同花顺 API 数据源（ths）
    local_source.py      本地全市场快照数据源（local）
    ths_api.py           同花顺 API 客户端
filter/                  选股筛选脚本（predict 前置）
utils/                   工具库
  config.py              路径与全局配置
  load_data.py           行情读取
  indicator.py           指标计算（MA/KDJ）
  parse.py               调参字符串解析
web/                     Streamlit 前端
data/                    本地数据（CSV）
note/                    研究笔记
```

---

## 环境准备

Python 3.11+ （开发环境 3.13）。

```bash
pip install -r requirements.txt
```

环境变量：

| 变量 | 说明 |
|---|---|
| `STOCK_WORK_DIR` | 数据根目录，默认当前目录 `.`，`data/` 在其下 |
| `THS_TOKEN` | 同花顺行情 API 的 `X-api-key`，使用 `ths` 数据源时必须设置 |
| `STOCK_NOTIFY_URL` | 每日预测任务的推送地址（可选） |

---

## 使用示例

```bash
# 拉取股票历史行情数据，000001：平安银行
python -m update.update_market -c 000001 -f remote
# 对 000001 平安银行，使用 “鱼盆模型” 进行回测
python -m strategy.predict -c 000001 -m fish_tub -o back_test
```

---

## 数据说明

- 行情：`data/{code}_{typ}_data.csv`，字段：
  `trade_date, open, close, high, low, volume, amount, pre_close` 以及指标
  `ma5/ma10/ma20`、`above_ma*`、`first_above_ma*`、`first_under_ma*`、`K/D/J`、`kdj_signal`。
- 个股信息：`data/{code}_{typ}_info.csv`，字段：
  `stock_code, short_name, exchange, list_date, change_date, total_shares, limit_shares, list_a_shares, change_reason`。
- `typ`：1=股票，2=指数，3=基金。

---

## 数据更新

### 单只股票

```bash
# 使用同花顺 API（需 THS_TOKEN）
python -m update.update_market -c 603007 -s 2025-01-01 -f ths

# 更新/初始化单只股票（-f 数据源：remote | ths | local）
python -m update.update_market -c 603007 -s 2025-01-01 -f remote

# 指定结束日期
python -m update.update_market -c 603007 -s 2025-01-01 -e 2026-08-29 -f remote
```

行为：本地无历史文件时默认拉取最近 5 年（`local` 源自动切换为 `remote`）；有历史文件时从最后交易日增量拉取，并自动重算 MA/KDJ。

推荐使用同花顺的数据源，相对稳定。同花顺的API可以搜索 “同花顺金融数据API” 注册申请。

若拉取数据失败，可能是数据源限制。可以自行开发其他数据源，开发指导详见下面 “数据源（可插拔）” 板块说明。

### 全市场数据并发更新

```bash
# -f 代码来源：local（本地 info 列表）| remote（adata 全市场）| file（-p 指定清单）
python -m update.update_market_patch -f local -w 5 -d 0.75 -s remote
python -m update.update_market_patch -f file -p data/zf5_top500.code -w 5 -d 0.75 -s ths
```

- `-w/--workers`：并发线程数；`-d/--delay`：请求间隔（秒）；`-s/--source`：数据源。

注意不推荐并发更新，可能导致数据接口被限速、封禁。

### 个股信息（市值/股本）

```bash
python -m update.fetch_stock_info -w 5 -d 1
```

### 数据完整性检查

```bash
python -m update.check
```

以基准股票的交易日历为准，检查各股最近 15 个交易日是否连续。

### 数据源（可插拔）

`update/sources` 采用注册表设计：新增数据源只需实现 `DailySource.fetch_daily()` 并在 `update/sources/__init__.py` 的 `SOURCE_REGISTRY` 中登记。

| 名称 | 实现 | 说明 |
|---|---|---|
| `remote` / `adata` | `adata_source.py` | adata/akshare（默认远程源） |
| `ths` | `ths_source.py` | 同花顺 API，需 `THS_TOKEN` |
| `local` | `local_source.py` | 本地全市场快照 |

---

## 策略回测与预测

入口 `strategy/predict.py`：

```bash
# 回测
python -m strategy.predict -c 603007 -m limit_up_pullback -o back_test
python -m strategy.predict -c 603007 -m fish_tub -o back_test -q 2025-08-01

# 全市场买入推荐
python -m strategy.predict -c all -m volumn_detect -o buy

# 指定代码清单（filter 产出）
python -m strategy.predict -c file,data/filtered.code -m limit_up_pullback -o buy
```

参数：

| 参数 | 说明 |
|---|---|
| `-c/--code` | 股票代码；`all` 全市场；`file,<path>` 代码清单；逗号分隔多个代码 |
| `-m/--mode` | 策略名（见下表） |
| `-o/--operate` | `back_test` 回测｜`buy` 买入推荐 |
| `-t/--tuning` | 策略参数，`k=v,k=v` 形式 |
| `-q/--date` | 截止日期 `YYYY-MM-DD`（只截取数据） |
| `-p/--path` | 数据文件路径 |
| `-d/--debug` | 调试输出 |

### 策略一览

| 策略 | 逻辑 | 主要调参（-t） |
|---|---|---|
| `fish_tub` | 鱼盆模型：MA20 趋势加速突破买入，跌破 MA20 卖出 | — |
| `kdj` | KDJ 金叉买入 | — |
| `kdj_ready` | KDJ 金叉前姿态（D 向上背离） | — |
| `volumn_detect` | 放量识别：成交量放大 + 突破前高 | `volumn_amplify, volumn_period, price_period, volumn_slope, rise` |
| `volumn_break` | 成交量爆发突破 | `prev, volumn_amplify, volumn_period, price_period, volumn_slope, rise` |
| `low_volumn_pullback` | 缩量回调：前期爆量 + 涨停后缩量回踩 MA10 | — |
| `volume_pullback` | 放量回缩 | `ma_period, volume_period, volume_base_period, volume_amplify, volume_ma5_slope, price_ma5_slope, rise` |
| `ma120_pullback` | 长期趋势回调反转 | `ma_diff_ratio_limit, hist_diff_ratio_limit` |
| `limit_up_pullback` | 涨停回调再启动：连续涨停→洗盘→再涨停 | `period, min_streak, pullback_pct, limit_up_pct, min_history, pullback_period, peak_window` |

示例：

```bash
python -m strategy.predict -c 603007 -m limit_up_pullback -o back_test -t "period=100,min_streak=2,pullback_pct=0.2,limit_up_pct=0.098"
python -m strategy.predict -c all -m volumn_detect -o buy -t "volumn_amplify=2,volumn_period=20,price_period=60,rise=0.2"
```

---

## 每日批量预测

```bash
python -m strategy.daily_predict
```

对 `MODELS` 列表中的策略并发执行全市场 `buy` 预测，结果写入 `{STOCK_WORK_DIR}/predict/`，并向 `STOCK_NOTIFY_URL` 推送结果文件的加密路径（可在 `web/pages/2_loader.py` 解密查看）。

---

## 选股筛选（predict 前置）

```bash
# 按市值/成交额筛选，产出代码清单供 predict -c file,xxx 使用
python -m filter.info_filter --market 1e10 --amount 5e8 -o data/filtered.code
```

`filter/` 下的东财快照抓取脚本（`market_top500.py` / `zf_top500.py` / `zf5_top500.py` / `all_stock.py`）直接运行即可生成当日全市场/排行文本，供 `local` 数据源使用。

---

## Web 前端

```bash
streamlit run web/app.py
```

- `1_predict`：图形化运行回测/预测
- `2_loader`：查看每日预测结果文件

---

## 常用命令速查

| 用途 | 命令 |
|---|---|
| 安装依赖 | `pip install -r requirements.txt` |
| 更新单只 | `python -m update.update_market -c 603007 -f remote` |
| 全市场更新 | `python -m update.update_market_patch -f local -w 5 -s remote` |
| 拉取个股信息 | `python -m update.fetch_stock_info` |
| 回测 | `python -m strategy.predict -c 603007 -m fish_tub -o back_test` |
| 全市场选股 | `python -m strategy.predict -c all -m volumn_detect -o buy` |
| 市值筛选 | `python -m filter.info_filter --market 1e10 -o data/filtered.code` |
| 每日预测 | `python -m strategy.daily_predict` |
| 启动前端 | `streamlit run web/app.py` |
