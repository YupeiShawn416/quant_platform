# Deployment

## 服务器目标架构

```text
Aliyun ECS Ubuntu
  ↓
/opt/quant_platform 项目目录
  ↓
/opt/quant_platform/.venv Python 环境
  ↓
/opt/quant_platform/data 本地数据目录
  ↓
systemd 管理 FastAPI
  ↓
Nginx 反向代理
  ↓
研究员通过 Python Client + X-API-Token 调用
```

## 服务器目录

```text
/opt/quant_platform/
├── src/
├── scripts/
├── docs/
├── deploy/
├── data/
│   ├── research_data/
│   └── rqalpha_bundle/
├── logs/
├── .env
└── .venv/
```

## 服务器初始化步骤

以下命令是示例，不要在本地项目目录中执行：

```bash
sudo useradd -m -s /bin/bash quant
sudo mkdir -p /opt/quant_platform
sudo chown -R quant:quant /opt/quant_platform
```

如果服务器不使用 `quant` 用户，需要同步修改 systemd 模板里的 `User` 和 `Group`。

## 代码部署

```bash
cd /opt
git clone <your_repo_url> quant_platform
cd /opt/quant_platform
```

如果不用 git，也可以用 `rsync` 上传项目代码。

## Python 环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e .
```

## `.env`

```bash
cp .env.production.example .env
nano .env
```

`API_TOKEN` 必须换成强随机字符串，`RQDATA_LICENSE` 不要写进代码，
`DATA_ROOT` 使用服务器绝对路径。

## 数据迁移

从本机同步数据到服务器：

```bash
rsync -avz data/research_data/rqdata/ quant@your_server:/opt/quant_platform/data/research_data/rqdata/
```

当前已有 2025 数据约 116M。`.env` 不通过 rsync 上传，`data/` 不进 Git。

## 部署前检查

```bash
PYTHONPATH=src python scripts/11_deploy_check.py
```

## systemd

```bash
sudo cp deploy/systemd/quant-platform-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable quant-platform-api
sudo systemctl start quant-platform-api
sudo systemctl status quant-platform-api
```

## Nginx

```bash
sudo cp deploy/nginx/quant-platform.conf /etc/nginx/sites-available/quant-platform.conf
sudo ln -s /etc/nginx/sites-available/quant-platform.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

正式部署建议配置 HTTPS，不要把真实域名写进模板文件。

## 本地 client 远程调用

```python
from rq_platform.client import QuantPlatformClient

client = QuantPlatformClient(
    base_url="http://your.domain.com",
    token="your_api_token",
)

df = client.get_prices(
    symbols=["000001.XSHE", "600519.XSHG"],
    start="2025-01-02",
    end="2025-01-10",
    adjust_type="pre",
    fields=["open", "close", "volume"],
)

print(df.head())
```

## 安全注意事项

1. 生产 API_TOKEN 不能使用 change_me。
2. `.env` 不能提交 Git。
3. RQDATA_LICENSE 不能打印到日志。
4. 5432/8000 不建议直接暴露公网。
5. 生产建议通过 Nginx + HTTPS。
6. 服务器安全组只开放必要端口。
7. `data/` 不进 Git。
