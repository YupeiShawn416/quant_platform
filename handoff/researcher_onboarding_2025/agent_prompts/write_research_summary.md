# Agent Prompt: Write Research Summary

You are writing a short research summary after a Quant Platform backtest.

Input:

- result zip downloaded from the platform
- `summary.json`
- `nav.csv`
- `trades.csv`
- optional validation report

Do not include API token, server IP, raw data rows, or private credentials.

Write a 300-800 word Chinese summary with:

- strategy idea
- data period
- universe description
- portfolio construction
- total_return
- sharpe
- max_drawdown
- benchmark_return
- excess_return
- trade_count
- benchmark reliability flags
- main risk observations
- whether the result is suitable for further research

Use cautious language. Do not claim production readiness from a short MVP
backtest.
