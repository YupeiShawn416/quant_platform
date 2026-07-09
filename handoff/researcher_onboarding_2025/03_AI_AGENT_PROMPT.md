# Prompt for AI Agent: Build and Submit a Quant Platform Weights Strategy

Copy the following prompt into your AI agent:

```text
你现在在 sample_strategy_project 中工作。

目标：用 2025 数据构建一个简单 weights 策略，生成 strategy_package.zip，上传到 Quant Platform，并汇总回测结果。

严格限制：
1. 不要修改平台服务器。
2. 不要调用 RQData。
3. 不要抓外部数据。
4. 不要泄露 API token。
5. 不要把 token 写入任何文件。
6. 不要提交或外传数据文件。
7. 不要改标准字段名。
8. 不要绕过 package 校验。

环境变量：
- 从 QUANT_PLATFORM_API_URL 读取服务器地址。
- 从 QUANT_PLATFORM_API_TOKEN 读取 API token。

默认策略任务：
- 使用 2025 数据。
- 计算 20 日动量。
- 每个交易日选择 Top 20。
- 等权 long-only。

只允许修改这些文件：
- configs/strategy.yaml
- src/strategy_research/factor.py
- src/strategy_research/signal.py
- src/strategy_research/portfolio.py

依次运行：
- python scripts/01_load_data.py
- python scripts/02_compute_factor.py
- python scripts/03_generate_signal.py
- python scripts/04_generate_weights.py
- python scripts/05_validate_outputs.py
- python scripts/06_build_package.py
- python scripts/07_submit_package.py

最终交付：
1. package 路径
2. 回测 summary
3. result zip 路径或下载方式
4. 简短研究结论
5. 遇到的问题

如果 API 不通，先报告错误，不要猜。
如果 package 校验失败，修复 weights 格式，不要绕过校验。
```
