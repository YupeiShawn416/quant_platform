# Data Contract

`load_market_data(config)` returns:

```text
trade_date
order_book_id
close
volume
amount
```

`load_universe(config)` returns at least `order_book_id`.

`load_benchmark(config)` returns at least `trade_date` and `benchmark_close`.

V0 demo data is deterministic and does not call RQData.
