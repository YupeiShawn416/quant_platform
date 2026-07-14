# Windows Quickstart

这份文档只给 Windows 研究员使用。Windows PowerShell 不要照抄 Mac 的 `export`。

## 1. 创建目录

```powershell
mkdir C:\Users\$env:USERNAME\quant_research
cd C:\Users\$env:USERNAME\quant_research
```

## 2. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止执行脚本，先运行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

不要为了这一步随便用管理员权限修改全系统策略。

## 3. 安装依赖

```powershell
pip install pandas requests
```

## 4. 设置环境变量

```powershell
$env:QUANT_PLATFORM_API_URL = "http://39.106.218.30"
$env:QUANT_PLATFORM_API_TOKEN = "your_token_here"
```

`API_TOKEN` 由管理员单独发放。不要写进代码、README、GitHub 或聊天记录。

## 5. 测试 health

PowerShell 原生：

```powershell
Invoke-RestMethod "$env:QUANT_PLATFORM_API_URL/health"
```

或者：

```powershell
curl.exe "$env:QUANT_PLATFORM_API_URL/health"
```

PowerShell 里的 `curl` 可能是 alias，建议写 `curl.exe`。

## 6. 测试 Data API

```powershell
Invoke-RestMethod `
  -Headers @{ "X-API-Token" = $env:QUANT_PLATFORM_API_TOKEN } `
  "$env:QUANT_PLATFORM_API_URL/data/datasets"
```

## 7. 运行 Python quickstart

把下面两个文件复制到当前目录：

```text
examples/researcher_api_usage/quant_platform_client.py
examples/researcher_api_usage/data_api_quickstart.py
```

然后运行：

```powershell
python data_api_quickstart.py
```

## 8. 常见错误

- `401 Unauthorized`：token 没设置、写错，或你用了 Mac 的 `export`。
- `403 Forbidden`：token 已禁用或过期，联系管理员换新 token。
- `404 Not Found`：URL 或 endpoint 写错。
- `502 Bad Gateway`：服务器后端异常，联系管理员。
- SSL 报错：当前地址是 `http://39.106.218.30`，不是 `https`。
