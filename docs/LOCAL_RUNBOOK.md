# Local Runbook

## 激活环境

```bash
cd /Users/yupeishen/Desktop/quant_platform
conda activate quant_platform
```

## 安装本地包

```bash
make install
```

## 跑测试

```bash
make test
```

## 检查数据

```bash
make check-data
```

## 启动 API

```bash
make api
```

如果当前环境不允许文件监听或端口绑定，可用生产模式本地演练命令：

```bash
make api-prod
```

## API smoke test

另开终端：

```bash
make api-smoke
```

## Client smoke test

另开终端：

```bash
make client-smoke
```

## 生产模式本地演练

```bash
make deploy-check
make api-prod
```

`api-prod` 使用 `reload=False`，用于模拟服务器启动方式。本地开发仍使用
`make api`。

## Researcher Quickstart

创建 research weights 项目：

```bash
PYTHONPATH=src python scripts/20_create_research_project_from_template.py \
  --template weights \
  --name my_first_strategy \
  --output-dir /tmp \
  --force
```

完整教学说明见：

```text
docs/RESEARCHER_QUICKSTART.md
docs/API_DATA_ACCESS_GUIDE.md
docs/DATA_USAGE_POLICY.md
```

## 2025 MVP 验收

验收清单见：

```text
docs/MVP_2025_ACCEPTANCE_CHECKLIST.md
```

当前不要把 VIX Q5 继续作为产品主线；它只是平台验收样例。

## 常见问题

1. API 连接失败：先确认 `make api` 是否正在运行
2. 查询为空：先确认本地 parquet 是否存在
3. RQData license 不要写入代码
4. `data/` 不进 Git
5. `egg-info` 是安装生成物，不进 Git
6. 部署环境需要设置强 `API_TOKEN`，并通过 `X-API-Token` 调用
7. current 会被新回测覆盖，长期保存需要下载 result zip
8. 不要把 API 返回数据、Parquet 数据或 result zip 提交进 Git
