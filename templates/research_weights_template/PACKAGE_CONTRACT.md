# Package Contract

The built zip must contain:

```text
manifest.json
config.json
weights.csv
README.md
```

When `pyarrow` is available it also contains `weights.parquet`, and
`config.json` points `weight_file` to that parquet file. Otherwise it points to
`weights.csv`.
