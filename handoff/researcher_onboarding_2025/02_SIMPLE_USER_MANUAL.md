# 傻瓜操作手册：如何生成并上传回测 zip

## 0. 你最终要交什么

- `strategy_package.zip`
- 平台下载的 result zip
- 一份 300-800 字研究说明

## 1. 准备信息

管理员会给你：

- 服务器地址：`<SERVER_URL>`
- API token：通过私聊单独给
- 样板项目文件夹：`sample_strategy_project/`

## 2. 设置环境变量

Mac / Linux：

```bash
export QUANT_PLATFORM_API_URL=<SERVER_URL>
export QUANT_PLATFORM_API_TOKEN=<API_TOKEN>
```

Windows PowerShell：

```powershell
$env:QUANT_PLATFORM_API_URL="<SERVER_URL>"
$env:QUANT_PLATFORM_API_TOKEN="<API_TOKEN>"
```

## 3. 进入样板项目

```bash
cd sample_strategy_project
```

## 4. 运行 01-06

```bash
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
```

每一步做什么：

- `01_load_data.py`：从平台 API 拉一小段 2025 数据。
- `02_compute_factor.py`：计算 20 日动量因子。
- `03_generate_signal.py`：把因子变成信号分数。
- `04_generate_weights.py`：生成目标权重。
- `05_validate_outputs.py`：检查权重格式是否合格。
- `06_build_package.py`：生成 `strategy_package.zip`。

## 5. 上传回测

```bash
python scripts/07_submit_package.py
```

## 6. 打开 Dashboard

浏览器打开：

```text
<SERVER_URL>/ui/backtests/current
```

## 7. 下载 result zip

从 Dashboard 左侧下载按钮下载。

如果 current 被别人覆盖，不要慌，重新上传一次你的 `strategy_package.zip`。

## 8. 写研究说明

打开 `06_RESEARCH_REPORT_TEMPLATE.md` 填写。

## 9. 提交给管理员

提交：

- `strategy_package.zip`
- result zip
- 研究说明
- 遇到的问题

## 10. 常见提醒

- 不要改字段名。
- 不要让 `target_weight` 每天加起来超过 1。
- 不要上传 token。
- 不要上传数据文件。
- 不要把自己的结果明细发到公开平台。
