# Researcher Training Plan

## 1. 培训目标

让研究员掌握：

- 平台数据 API 使用
- `research_weights_template` 使用
- 因子 / 信号 / 权重分层
- `strategy_package.zip` 生成
- 平台回测和 Dashboard 使用
- result zip 下载和报告撰写
- 数据使用规范

## 2. 培训对象

- 量化研究员
- 实习生
- AI agent 操作者
- 平台管理员

## 3. 90 分钟教学安排

| 时间 | 内容 |
|---:|---|
| 0-10 min | 平台定位：数据服务、统一回测裁判、Dashboard、Strategy Package |
| 10-25 min | 数据使用规范和 API token 安全 |
| 25-40 min | API 拉取 2025 数据 |
| 40-60 min | 使用模板生成 weights package |
| 60-75 min | 上传回测 + Dashboard 查看 + result zip 下载 |
| 75-90 min | 常见错误与答疑 |

## 4. 上机练习

任务：用 2025 数据做一个简单 Top N 策略。

要求：

- 使用 `close` 计算 20 日动量
- 每日选择 top 20
- 等权 long-only
- 生成 `weights.csv` 和 `weights.parquet`
- 生成 `strategy_package.zip`
- 上传平台回测
- 下载 result zip
- 写 300 字研究结论

## 5. 作业提交格式

提交：

- `strategy_package.zip`
- result zip
- 简短研究说明
- 如果使用了额外数据，说明来源

不要提交：

- API token
- `.env`
- 平台原始 Parquet 数据
- 未授权下载数据
- 未脱敏的外部共享材料

## 6. 常见错误

- 字段名不对
- `trade_date` 格式错误
- `target_weight` 单日和超过 1
- 负权重
- `order_book_id` 格式错误
- API token 错误
- package zip 结构错误
- 修改了 `package_builder.py` 导致包结构不合规
- 上传后 current 被覆盖
- 忘记下载 result zip
- 把自己算的绩效当成平台最终绩效

## 7. 培训通过标准

研究员应能独立完成：

1. 读取文档和数据使用规则。
2. 通过 API 或模板准备数据。
3. 修改 factor/signal/portfolio。
4. 生成并校验 weights package。
5. 上传平台回测。
6. 查看 Dashboard。
7. 下载 result zip。
8. 写出包含风险说明的研究结论。
