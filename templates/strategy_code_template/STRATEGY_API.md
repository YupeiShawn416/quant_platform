# Strategy API

`strategy.py` must define:

```python
def generate_weights(context, data) -> dict[str, float] | None:
    ...
```

Return a dict to rebalance to target weights. Return `None` to keep current
positions unchanged. Return `{}` to target an empty portfolio.
