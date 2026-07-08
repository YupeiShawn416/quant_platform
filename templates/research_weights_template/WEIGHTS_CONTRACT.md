# Weights Contract

`generate_weights(signal_df, config)` returns:

```text
trade_date
order_book_id
target_weight
```

Rules:

- long-only
- no negative target weights
- no duplicate `trade_date + order_book_id`
- daily sum must be less than or equal to 1.0
- `top_n` comes from `portfolio.top_n`
