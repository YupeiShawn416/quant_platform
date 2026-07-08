# Workflow

1. Load or generate market data.
2. Compute a long-table factor.
3. Convert factor values into signal scores.
4. Convert signal scores into long-only target weights.
5. Validate factor, signal, and weights outputs.
6. Build a Strategy Package V1 zip.
7. Upload the package to quant_platform when the API is running.

The template demo uses deterministic local data. Production projects should
replace only the data-loading internals with calls to the data platform, Python
client, or standard parquet files.
