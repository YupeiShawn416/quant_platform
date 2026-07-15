# 因子池构建设计阶段记录

## 已完成

- 阅读并对齐基准多因子模型需求与技术设计文档。
- 分析现有 Quant Platform 因子库、因子详情和研究员数据页面。
- 确认采用本地先建、后续接入现有平台的混合方案。
- 确认初始因子入库不使用收益、IC、回测或模型重要性。
- 安装全局 `rqdatac 3.5.5`，通过进程环境中的已轮换许可证完成认证，凭证未进入代码、日志或产物。
- 实际枚举13,482个唯一字段：官方12类合计10,442个，另有3,040个未分类字段。
- 当前目录规范化 SHA-256：`45d11857ac9cce78946a2a7504ac6ec25cbb70c73764e45cb34ce313b4fbfbe0`。
- 将 `docs/superpowers/specs/2026-07-15-factor-pool-construction-design.md` 更新至 V0.2。
- 根据用户指出的“原始字段不是因子”问题，将设计文档重构至 V0.3。
- 补订窗口与中性化规则，将设计文档更新至 V0.4。
- 读取 `quant_platform` README、数据/因子规格、`src/rq_platform/factors/` 实现与测试，将全套文档按真实框架修订；因子池设计更新至 V0.5。
- 用户批准 Research Factor Pool A阶段：完成源字段目录、分类、配方框架和小样本烟雾测试，不做全历史物化。
- 用户批准可迁移包结构、四层数据契约、状态机、RQData接入、缓存、测试、验收和Git worktree流程。
- 已从最新 `origin/main` 建立 `feature/research-factor-pool` worktree，路径仍为 `quant_pool`。
- 基线测试197项通过、1项失败；失败由 `tests/test_imports.py` 硬编码checkout目录名必须为 `quant_platform` 导致，已列为实施首项修复。
- 将因子池设计整体重构为 V1.0，作为A阶段唯一实施规格。
- 根据预处理节点建议引入“双质量门”，将工作流、状态机、产物和目标代码映射更新至 V0.6。

## 关键注意事项

- 对话中出现的 RQData 凭证视为已泄露，必须撤销，不得进入命令、代码、日志或产物。
- RQData可查询字段实际为13,482项；`_mrq_n/_ttm_n/_lyr_n` 等多期展开约占82%，不能将其称为13,482个因子。
- 其中9,858项为三张报表原始字段及多期展开，默认只进入 `source_field_catalog`，禁止直接入模。
- 首批明确的米筐成品因子为584项，需通过非收益资格审查后才能进入 `factor_catalog`。
- 3,040项未分类字段进入隔离区，定义未确认前不得进入因子配方或正式因子库。
- 新工作流以 `source_field_catalog → factor_recipe_catalog → factor_catalog → monthly_raw_factor_panel → monthly_processed_factor_panel → fold_selected_factors` 为主线。
- 上述目录和月度面板是 `quant_pool` 待建资产，不是 `quant_platform` 已实现能力；首期不得把13,482个字段写进静态 `BUILTIN_FACTORS`。
- 现有平台只有5个日频内置因子，清洗为1%/99%缩尾和每日Z-score，无MAD、行业/市值中性化、动态注册或滚动折筛选。
- 首期只读复用平台 Parquet 数据湖/API；RQData枚举和补数只在持牌本机执行，校验后同步数据湖。
- 持久化对象分为原始字段库、因子配方库、正式因子库、月度因子面板和折内入模结果。
- 覆盖率和有效性筛选必须在滚动训练窗内重新计算，验证期和测试期不得参与选择。
- 全量字段进入不可变原始字段目录；财务 `_0/_1/_4` 作为当前、环比和同比配方输入，不能以原始绝对值身份直接入模。
- 第一版统一候选池只启用跨行业通用因子，行业专属因子保留在目录。
- 保留米筐原始方向；按数值语义做 log/signed-log 固定变换；缺失值保留为 NaN。
- 只在入库阶段删除确定重复，高相关去冗余必须在滚动训练窗内执行。
- 财务因子使用截至 T-1 可用值，量价与技术因子使用 T 日收盘值，统一在 T+1 起算收益。
- 正式基线采用60个月训练、12个月验证、6个月测试、6个月滚动步长；测试月份不重叠。
- 切分边界按 `label_end_date < next_period.signal_date` 断言，不能只按月份位置切分。
- 不对所有因子统一做行业和市值中性化；每个正式因子保存固定的 `neutralization_policy`。
- 估值、盈利、成长、质量、现金流及普通选股Alpha默认行业+市值中性化；规模因子禁止市值中性化，已中性化因子不重复处理。
- V1行业暴露固定使用平台现有的中信 `citics_2019` 一级；申万只有在新增PIT数据并建立独立快照后才能启用。
- 新面板采用 `source_value → recipe_value → processed_value` 分层，避免与现有MVP中已经包含公式取负的 `factor_value` 混淆。
- 预处理采用双质量门：先在训练窗检查原始覆盖率、类型、常量和无穷值，再执行MAD、中性化、Z-score，随后检查处理后方差、覆盖和回归退化，最后才允许计算IC。
- `neutralization_policy`、处理顺序和参数在正式因子目录中锁定，验证期与测试期不得根据表现修改。
- `quant_pool/src/factor_pool/` 目标拆分为 `data_adapter/catalog/engine/audit/preprocessing/validation/evaluation/storage`，当前仍是待建结构。
- 财务及衍生因子必须通过 PIT 抽样审计，未验证因子不得进入基准候选池。
- 目录快照不可变，供应商变化生成新版本，不回写旧实验。
- 历史状态：最初目录不是Git仓库；现已转换为 `feature/research-factor-pool` worktree，可提交版本记录。
- `quant_platform` 工作树在本次核对时为干净状态，本轮仅修改 `quant_pool` 文档，未修改框架代码。
- `quant_pool` 现在是 `quant_platform` 的独立worktree；后续提交进入 `feature/research-factor-pool`，不得在相邻 `quant_platform/main` 直接开发。
