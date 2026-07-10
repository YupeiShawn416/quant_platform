# 常见问题

## 1. token 错误 / 401

检查 `QUANT_PLATFORM_API_TOKEN` 是否设置正确。不要把 token 发到群里。

## 2. 服务器地址错

检查 `QUANT_PLATFORM_API_URL` 是否是管理员给你的 `<SERVER_URL>`。

## 3. API 连不上

确认网络可访问服务器。如果还是不行，把完整报错发给管理员。

## 4. 缺 Python 包

把报错里缺少的包名发给管理员。不要随便安装不明来源包。

## 5. 找不到 sample_strategy_project

确认你已经进入交付包目录，然后运行：

```bash
cd sample_strategy_project
```

## 6. weights 字段缺失

weights 必须包含：

```text
trade_date
order_book_id
target_weight
```

## 7. target_weight 有负数

只能做 long-only。把负权重改成 0 或重新生成权重。

## 8. target_weight 每天加起来超过 1

每个交易日的 `target_weight` 总和必须小于等于 1。

## 9. trade_date 格式错误

使用：

```text
YYYY-MM-DD
```

例如：

```text
2025-01-02
```

## 10. order_book_id 格式错误

使用平台标准股票代码，例如：

```text
000001.XSHE
600519.XSHG
```

## 11. Current Dashboard 不是自己的结果

`current` 会显示最新一次回测，别人上传新回测后会覆盖 current。
请使用你的 `run_id` 打开：

```text
<SERVER_URL>/ui/backtests/runs/<run_id>
```

如果忘记 run_id，打开：

```text
<SERVER_URL>/ui/backtests/runs
```

## 12. result zip 下载不了

先刷新 Dashboard。如果仍然不行，把错误截图或完整报错发给管理员。

## 13. 不知道怎么办

把完整报错、你运行的命令、当前文件夹路径发给管理员。
