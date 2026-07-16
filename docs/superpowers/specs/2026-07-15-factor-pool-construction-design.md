# Research Factor Pool——构建与接入设计

## 1. 文档信息

- 文档版本：V1.0
- 更新日期：2026-07-15
- 状态：方案已批准，待用户复核书面规格
- 工作目录：`C:\Users\asus\Desktop\实习\实习任务\多因子模型\quant_pool`
- 开发分支：`feature/research-factor-pool`
- 数据源：米筐 RQData，市场 `cn`
- 目标平台：相邻仓库 `quant_platform`
- 本期范围：A阶段——目录、分类、配方框架及小样本烟雾测试
- 上游文档：
  - `2026-07-14-multifactor-requirements.md`
  - `2026-07-14-multifactor-design.md`
  - `docs/现有因子库框架分析说明.md`

## 2. 决策摘要

Research Factor Pool 先在独立 worktree 中构建和验收，再通过 Git 分支合并进 `quant_platform` 的因子库模块。本期不做全历史因子物化、收益评价、模型训练或平台 UI 改造。

已批准的核心决策如下：

1. 13,482 是 RQData 可查询源字段数量，不是因子数量。
2. 源字段、配方、正式因子和折内入模因子分层管理。
3. 原始财务字段不得未经配方直接进入正式因子目录。
4. 初始入库不读取收益、IC、ICIR、模型重要性或回测表现。
5. RQData 只负责数据发现与取值，分类、配方和状态由本项目管理。
6. 代码、规则、配方、schema、测试和摘要进入 Git；凭证和数据文件不进入 Git。
7. 现有 `quant_platform` 5因子日频 MVP 保持兼容，不覆盖其定义和数据。

## 3. 当前平台边界

`quant_platform` 当前因子库由静态 `BUILTIN_FACTORS` 驱动，只包含：

```text
market_cap
turnover_rate
momentum_20d
reversal_5d
volatility_20d
```

现有平台保存日频 `factor_value/factor_score`，统一执行每日1%/99%缩尾和截面Z-score。它没有动态字段目录、配方目录、因子状态机、MAD处理、行业市值中性化或滚动折筛选。

本项目新增能力，首期不修改旧语义：

```text
Built-in Factors（保留）
Research Factor Pool（新增）
├─ 源字段目录
├─ 配方目录
├─ 正式因子目录
├─ 快照与审计
└─ 后续物化接口
```

## 4. 项目结构

```text
quant_pool/
├─ .env                         # 本机可选，只允许RQDATAC_KEY；不提交
├─ .env.example                 # 仅变量名
├─ .gitignore
├─ pyproject.toml
├─ requirements.txt
├─ configs/
│  ├─ catalog.yaml
│  ├─ classification_rules.yaml
│  └─ preprocessing.yaml
├─ recipes/                     # 可版本控制的YAML配方
├─ src/factor_pool/
│  ├─ data_adapter/             # RQData认证、查询、缓存
│  ├─ catalog/                  # 字段分类和目录构建
│  ├─ contracts/                # schema与状态枚举
│  ├─ engine/                   # 配方解析及小样本计算
│  ├─ preprocessing/            # 后续MAD、标准化和中性化
│  ├─ evaluation/               # 后续折内IC、ICIR和相关性评价
│  ├─ audit/                    # PIT、覆盖率、异常与版本审计
│  ├─ cli.py
│  └─ __main__.py
├─ data/                        # 不提交Git
│  ├─ 1_source_cache/
│  ├─ 2_recipe_values/
│  └─ 3_processed_factors/
├─ manifests/                   # 提交Git：哈希、数量、版本和汇总
├─ notebooks/                   # 仅探索，不承载正式逻辑
├─ tests/
├─ docs/
└─ memory/
```

`2_raw_factors` 不作为目录名，因为源字段不是因子。只有字段通过配方生成结果后，才进入 `2_recipe_values`。

## 5. 术语和数据层级

| 层级 | 定义 | 本期是否构建 |
|---|---|---:|
| 源字段 | RQData 可查询字段 | 是 |
| 成品因子候选 | 米筐已有公式或指标定义的对象 | 是 |
| 派生因子 | 本项目用登记配方计算的变量 | 仅框架与样例 |
| 正式因子 | 通过定义与PIT审查的成品/派生因子 | 仅目录与状态 |
| 物化因子 | 指定股票、日期范围内的因子值 | 仅小样本 |
| 折内入模因子 | 在滚动训练折通过质量、有效性和去冗余筛选 | 否 |

数值层级固定为：

```text
source_value
    ↓ 配方
recipe_value
    ↓ 语义变换/MAD/角色化中性化/Z-score
processed_value
```

不得用同一个 `factor_value` 同时表示供应商原值、配方结果和模型特征。

## 6. 核心数据契约

### 6.1 源字段目录

资产名：`source_field_catalog`

主键：`(snapshot_id, vendor_field_name)`

必填字段：

```text
snapshot_id
vendor_field_name
vendor_category
field_role
data_type
frequency
unit
period_variant
point_in_time_status
classification_status
classification_reason
discovered_at
rqdatac_version
```

`field_role` 只允许：

```text
statement_field
vendor_factor
exposure_field
filter_field
identifier
market_data
unclassified
```

无法确认的数据类型、频率、单位或最早可用日期保留为空并标记待审，不得猜测填充。

### 6.2 因子配方目录

资产名：`factor_recipe_catalog`

配方 YAML 示例：

```yaml
factor_id: roe_ttm
version: "1.0.0"
name: ROE TTM
category: profitability
inputs:
  - net_profit_ttm
  - average_equity
formula:
  function: safe_divide
  arguments:
    - net_profit_ttm
    - average_equity
frequency: quarterly
availability_rule: latest_published_before_signal_date
semantic_transform: none
neutralization_policy: industry_and_size
missing_policy: preserve_nan
point_in_time_status: pending
```

配方必须是结构化表达式，禁止 `eval`、`exec` 或任意Python字符串。首批白名单函数为：

```text
safe_divide
add
subtract
multiply
log1p
signed_log1p
lag
pct_change
rolling_mean
rolling_std
```

每个函数必须定义输入类型、空值传播、除零规则、最小历史长度和输出类型。

### 6.3 正式因子目录

资产名：`factor_catalog`

主键：`(factor_id, factor_version)`

必填字段：

```text
factor_id
factor_version
factor_kind
name
category
recipe_id
source_fields
value_direction
neutralization_policy
definition_status
pit_status
materialization_status
eligible_for_model
created_at
code_hash
```

`value_direction` 保存配方结果的自然方向，不预先翻转为“越高越好”。实际预测方向只能在未来滚动训练窗内判断。

### 6.4 快照清单

资产名：`snapshot_manifest`

```text
snapshot_id
created_at
provider
market
rqdatac_version
field_count
catalog_sha256
category_counts
classification_rule_hash
recipe_set_hash
status
```

完整目录 Parquet 位于 `data/`，不进入Git；manifest和分类汇总进入Git。

## 7. 状态机

```text
discovered
    ↓
classified
    ├─ source_only
    ├─ quarantined
    └─ candidate_factor
             ↓
      definition_verified
             ↓
         pit_verified
             ↓
          eligible
             ↓
        materialized
```

规则：

1. 分类失败不删除，进入 `quarantined`。
2. 未通过定义审查不得进入PIT审查。
3. PIT未验证不得成为基准候选因子。
4. 584个成品因子候选不会自动标记 `eligible`。
5. 目录状态和某滚动折是否入模完全分开。
6. 每次状态变化记录旧状态、新状态、原因、规则版本和时间。
7. 非法状态跳转立即失败，不允许静默纠正。

## 8. RQData 接入

### 8.1 适配器职责

`data_adapter` 只负责认证、能力探测、字段枚举、小样本查询、限流、缓存、重试和响应标准化，不负责分类、配方、预处理或评价。

凭证读取顺序：

```text
系统环境变量 RQDATAC_KEY
        ↓ 不存在
本机 .env 中的 RQDATAC_KEY
        ↓ 不存在
终止
```

日志只能记录凭证来源和认证结果，不记录密钥、密钥片段或密钥哈希。

### 8.2 能力清单

首次成功探测生成 `capability_manifest.json`，至少记录：

```text
provider
market
rqdatac_version
authenticated
field_enumeration_supported
field_count
sample_query_supported
generated_at
```

认证失败不得生成伪造的空目录或成功manifest。

### 8.3 重试策略

| 错误 | 处理 |
|---|---|
| 凭证缺失、认证失败 | 立即终止，不重试 |
| 字段不存在、参数非法 | 请求失败，不重试 |
| 超时、连接中断 | 指数退避，最多3次 |
| 限频 | 按服务提示或退避策略重试 |
| 单字段空数据 | 标记 `vendor_empty`，继续 |
| 响应schema异常 | 阻断该批次 |
| 缓存校验失败 | 隔离损坏缓存并重新请求 |

## 9. 字段发现与分类

2026-07-15 使用 `rqdatac 3.5.5`、`market="cn"` 已枚举13,482个唯一字段。规范化目录SHA-256为：

```text
45d11857ac9cce78946a2a7504ac6ec25cbb70c73764e45cb34ce313b4fbfbe0
```

哈希规范固定为：字段名去空白、去重、按 Unicode 字典序升序排列，以 UTF-8 编码并用单个 `\n` 连接，末尾不追加换行，再计算 SHA-256。

当前分类基准：

| 类别 | 数量 | 本期处理 |
|---|---:|---|
| 三张财务报表字段及多期展开 | 9,858 | `statement_field/source_only` |
| 米筐成品因子候选 | 584 | `vendor_factor/candidate_factor` |
| 未识别兼容、旧口径或额外字段 | 3,040 | `unclassified/quarantined` |
| 合计 | 13,482 | 源字段目录 |

分类规则必须确定、可排序、可测试。同一字段命中多条规则时采用显式优先级，并记录最终规则ID。规则变更生成新快照，不回写旧快照。

## 10. 缓存与存储

```text
data/1_source_cache/
├─ catalog/<snapshot_id>/
│  ├─ source_fields.parquet
│  └─ request_manifest.json
└─ samples/<request_hash>/
   ├─ response.parquet
   └─ request_manifest.json
```

`request_hash` 由市场、字段、证券、日期、SDK版本和非敏感查询参数生成，凭证不参与。

写入顺序：临时文件 → schema/行数/主键校验 → SHA-256 → 原子重命名 → 成功manifest。中断或校验失败时不得留下成功标记。

## 11. 本期配方、预处理与评价边界

### 11.1 配方引擎

本期实现配方schema、白名单解析器、依赖检查、循环依赖检查和小样本计算。不得全量构造13,482个所谓因子，也不进行全历史物化。

### 11.2 预处理

本期只固定接口和小样本测试。未来处理顺序为：

```text
无穷值转缺失
→ 语义变换
→ MAD去极值
→ 按角色中性化
→ Z-score
```

V1行业暴露使用平台已有中信 `citics_2019` 一级分类。估值、盈利、成长、质量和普通选股Alpha默认行业+市值中性化；规模因子禁止市值中性化；已中性化因子不重复处理。

### 11.3 评价

`evaluation` 为后续阶段预留。A阶段不得读取收益，不计算Rank IC、ICIR、回测收益或模型重要性。

未来滚动筛选统一使用60个月训练、12个月验证、6个月测试和6个月步长；收益相关筛选只允许读取当前训练窗。

## 12. CLI

正式入口使用模块命令，不直接执行 `cli.py`：

```powershell
python -m factor_pool rqdata probe
python -m factor_pool catalog build
python -m factor_pool catalog validate
python -m factor_pool catalog summarize
python -m factor_pool recipe validate
python -m factor_pool smoke sample-query
```

失败命令返回非零退出码。命令输出为简短摘要，详细结果写入manifest或报告；任何输出不得包含凭证。

## 13. 烟雾测试

A阶段真实RQData测试包括：

1. 认证能力探测；
2. 13,482字段枚举、唯一性和目录哈希复核；
3. 9,858/584/3,040分类结果复现；
4. 固定少量证券、日期和字段的小样本取值；
5. 相同请求二次执行命中缓存。

小样本字段覆盖估值、利润表、资产负债表、现金流量表、供应商成品因子和技术指标。不得查询未来收益。

## 14. 测试策略

### 14.1 离线测试

CI不使用真实密钥。固定fixture覆盖：

- 配置与schema；
- 响应标准化；
- 后缀识别、分类和优先级；
- 去重、稳定排序和SHA-256；
- 配方白名单和非法表达式拦截；
- 请求哈希、缓存命中和原子写入；
- 状态机合法/非法转换；
- 日志与异常脱敏。

### 14.2 RQData测试

真实测试标记为 `rqdata`，仅在本机存在凭证时显式运行：

```powershell
python -m pytest -m rqdata
```

缺少凭证时跳过，不失败；认证失败时测试失败，不降级为伪数据。

### 14.3 平台兼容测试

- `factor_id` 唯一稳定；
- 日期使用 `YYYY-MM-DD`；
- 证券标识使用 `order_book_id`；
- Parquet字段类型固定；
- 目录和配方可由平台适配器加载；
- 现有5因子行为不变；
- 不写入旧 `data/factor_library/values`。

当前平台测试 `tests/test_imports.py` 硬编码 `PROJECT_ROOT.name == "quant_platform"`，在名为 `quant_pool` 的worktree中会失败。实施首步必须把该断言改为验证项目标志文件或包路径，而不是checkout目录名。

## 15. A阶段验收标准

1. CLI能完成RQData能力探测。
2. 枚举13,482个唯一字段；数量变化时输出新增、删除和分类变化报告。
3. 相同输入生成相同规范化SHA-256。
4. 9,858/584/3,040分类结果可复现，变化必须有规则版本和差异报告。
5. 每个字段都有角色、状态和分类原因。
6. 原始报表字段不会进入正式因子目录。
7. 584个候选不会自动成为 `eligible`。
8. 至少一组合法和非法配方测试通过。
9. 小样本查询覆盖六类代表数据。
10. 相同请求二次命中缓存。
11. 凭证不进入Git、日志、manifest、异常和测试快照。
12. 离线单元和集成测试全部通过。
13. 输出字段目录、分类汇总、隔离清单和快照manifest。
14. 未读取收益、IC、ICIR或回测表现。
15. 现有平台5因子、API和回测测试无新增回归。

## 16. Git与合并流程

开发采用平台仓库worktree：

```text
quant_platform/  → main
quant_pool/      → feature/research-factor-pool
```

提交建议：

```text
docs: finalize research factor pool specification
chore: scaffold research factor pool package
feat: add secure RQData capability probe
feat: build deterministic source field catalog
feat: add field classification and quarantine rules
feat: add recipe contracts and validation engine
test: add RQData smoke and cache verification
docs: add factor pool acceptance report
```

合并进入平台的内容：代码、配置、分类规则、配方、schema、测试、manifest摘要和文档。

不合并的内容：凭证、`.env`、原始缓存、Parquet数据、Notebook输出、全历史因子值和收益评价结果。

## 17. 实施顺序

1. 修正平台测试对checkout目录名的硬编码依赖；
2. 创建包结构、配置模型和Git忽略规则；
3. 实现安全配置加载和RQData能力探测；
4. 实现字段枚举、规范化、去重、稳定排序和快照哈希；
5. 实现确定性分类、隔离区和差异报告；
6. 实现数据契约、状态机和审计事件；
7. 实现配方schema、白名单解析和小样本计算；
8. 实现缓存、原子写入和错误分类；
9. 完成离线测试与RQData小样本烟雾测试；
10. 生成A阶段验收报告；
11. 用户复核后再设计B阶段全历史月度面板。

## 18. 明确不在A阶段实施

- 全历史批量因子下载；
- 584个候选全部物化；
- 财务派生因子全集；
- MAD与中性化的全历史运行；
- Rank IC、ICIR和收益筛选；
- 多重共线性或高相关去冗余；
- LightGBM、XGBoost、CatBoost与NNI；
- 理论多空回测；
- 平台因子库UI和API改造；
- 向平台生产数据目录同步。

任何扩大范围的需求必须进入B阶段设计，不能在A阶段通过临时脚本绕过数据契约和验收门槛。
