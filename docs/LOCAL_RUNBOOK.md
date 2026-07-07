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

## API smoke test

另开终端：

```bash
make api-smoke
```

## 常见问题

1. API 连接失败：先确认 `make api` 是否正在运行
2. 查询为空：先确认本地 parquet 是否存在
3. RQData license 不要写入代码
4. `data/` 不进 Git
5. `egg-info` 是安装生成物，不进 Git
