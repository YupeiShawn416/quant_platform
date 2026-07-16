# 2026-07-16 因子池目录工作流运行记录（First）

## 本次范围

按因子池设计 V0.6 启动 A 阶段第一切片：工程隔离检查、RQData 能力探测、字段枚举、确定性分类、目录快照持久化及验证。未读取收益、未物化历史因子值、未执行 IC 或模型筛选。

## 关键操作

1. 确认 `quant_pool` 是 `quant_platform` 的 Git worktree，当前分支为 `quant_pool`。
2. 发现原 `tests/test_imports.py` 从全局 editable 安装错误导入 `quant_platform` 主工作区，导致假绿；改为校验实际包路径，并在 `pyproject.toml` 中为 pytest 固定 `src` 路径。
3. 新增独立 `factor_pool` 包、目录配置、RQData 适配器、规范化/分类/快照存储和 CLI。
4. 认证只从环境变量或项目 `.env` 读取；本次使用进程环境中的兼容变量 `RQDATA_HTTP_TOKEN`，任何日志、异常、manifest 和测试产物均不写入凭证。
5. 使用 RQData `get_all_factor_names(type=..., market="cn")` 按 13 个供应商原生类别枚举，不通过字段名猜测主分类。
6. 首次快照因哈希实现误加末尾换行而被标记 `changed`；复核确认设计基线使用无末尾换行规范。修正测试和实现后删除该未验收中间快照，再重新运行。
7. 将完整运行目录 `data/1_source_cache/` 加入 Git 忽略，仅保留非敏感 manifest 供审计。

## 运行结果

- RQData SDK：`3.5.5`
- 市场：`cn`
- 快照：`rqdata-cn-20260716T141020-45d11857`
- 唯一字段：13,482
- 目录 SHA-256：`45d11857ac9cce78946a2a7504ac6ec25cbb70c73764e45cb34ce313b4fbfbe0`
- 报表源字段：9,858，状态 `source_only`
- 供应商成品因子候选：584，状态 `candidate_factor`
- 隔离字段：3,040，状态 `quarantined`
- 与设计基线差异：无
- 新增 factor-pool 测试：10 个通过（包含 Parquet 篡改后的哈希失配拦截）
- 全项目回归：208 个通过，0 个失败，82 个既有弃用警告

## 产物

- 完整目录：`data/1_source_cache/catalog/rqdata-cn-20260716T141020-45d11857/source_fields.parquet`（Git 忽略）
- 隔离目录：同目录下 `quarantined_fields.parquet`（Git 忽略）
- 运行 manifest：同目录下 `request_manifest.json`（Git 忽略）
- 能力 manifest：`manifests/factor_pool/capability_manifest.json`
- 审计 manifest：`manifests/factor_pool/rqdata-cn-20260716T141020-45d11857.json`

## 风险与下一步

- RQData 返回账户约 1 天后到期警告；后续小样本取值前需要续期或更换有效授权。
- 当前环境变量仍使用兼容名 `RQDATA_HTTP_TOKEN`；建议迁移为设计标准名 `RQDATAC_KEY`。
- 下一切片应先审计 584 个候选的定义/PIT 属性，同时细分 3,040 个隔离字段；不得将两组直接加入正式因子目录。
