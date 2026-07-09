# Server Deployment MVP Checklist

## 1. 服务器规格

MVP 推荐：

- 轻量云或 ECS
- x86_64
- Ubuntu 22.04 LTS
- 4 vCPU
- 16GB RAM
- 至少 80GB 磁盘
- 正式长期建议 ECS + 独立数据盘

## 2. 服务器角色

服务器负责：

- API
- Dashboard
- 回测
- result zip 下载
- 本地 Parquet 数据服务

服务器暂时不负责：

- 直接访问 RQData
- 所有人研究代码执行
- 长期保存所有完整回测结果
- 对外数据分发服务

## 3. 部署步骤摘要

- [ ] 创建服务器用户和目录
- [ ] `git clone` 项目
- [ ] 创建 Python venv
- [ ] `python -m pip install -r requirements.txt`
- [ ] `python -m pip install -e .`
- [ ] 配置 `.env`
- [ ] `rsync` 本地数据到服务器
- [ ] 如需 Docker 回测，build Docker image
- [ ] systemd 启动 API
- [ ] nginx 反代
- [ ] smoke test

完整命令见 `docs/SERVER_DEPLOYMENT_RUNBOOK_MVP.md`。上线后按
`docs/SERVER_DEPLOYMENT_SMOKE_TEST.md` 验收。

## 4. 数据同步

本地执行：

```bash
rsync -avz --progress \
  ~/Desktop/quant_platform/data/research_data/rqdata/ \
  quant@SERVER_IP:/opt/quant_platform/data/research_data/rqdata/
```

不要同步 `.env`。不要通过 Git 提交 `data/`。

## 5. 安全组

- [ ] 22 只允许管理员 IP
- [ ] 80/443 开放
- [ ] 8000 不开放公网
- [ ] 数据库端口不开放公网
- [ ] 后续配置 HTTPS

## 6. RQData 风险

服务器默认不直接访问 RQData。

如需服务器 ETL，必须先确认：

- 数据授权
- IP 白名单
- license 使用范围
- 服务商协议
- 内部安全制度

不要默认用公网 IP 大规模访问数据源。

## 7. 上线验收

- [ ] `/health`
- [ ] `/status`
- [ ] `/prices` 小范围查询
- [ ] `/ui/backtests/current`
- [ ] `/backtests/run-package`
- [ ] `/backtests/current/summary`
- [ ] `/backtests/current/nav`
- [ ] result zip download
- [ ] dashboard smoke
- [ ] demo package smoke
- [ ] token 鉴权有效
- [ ] `API_TOKEN` 不是 `change_me`
- [ ] `DATA_ROOT` 使用服务器绝对路径
- [ ] `data/` 已同步且权限正确
- [ ] systemd restart 正常
- [ ] nginx reload 正常

## 8. Production Template Checks

- [ ] `.env.production.example` contains `HOST`, `PORT`, `WORKERS`, `API_TOKEN`, `DATA_ROOT`, backtest dirs and limits.
- [ ] systemd uses `/opt/quant_platform/.env` through `EnvironmentFile`.
- [ ] nginx proxies to `127.0.0.1:8000`.
- [ ] nginx `client_max_body_size` is large enough for package uploads.
- [ ] port 8000 is not public.
- [ ] Docker image is built or execution mode is explicitly set to trusted local mode for trial only.

## 9. 回滚方案

- 保留上一版代码 commit。
- 保留 `.env` 备份，不进入 Git。
- 保留上一份可用数据目录快照或 rsync 源。
- 如果 API 异常，先停 systemd，再回退代码或配置。
