# Research Weights Template

This template is the default client-side research starter kit for quant_platform.
It guides a researcher from deterministic demo data through factor, signal, and
portfolio construction, then builds a Strategy Package V1 `weights` zip that can
be uploaded to `/backtests/run-package`.

The research code can run on a local machine, notebook, or AI-agent project.
The server unifies the backtest result, not every research script. The final
deliverable for the platform is a standard `strategy_package.zip`.

Change these files for a real study:

- `configs/strategy.yaml`
- `src/strategy_research/factor.py`
- `src/strategy_research/signal.py`
- `src/strategy_research/portfolio.py`

Keep these stable unless you are changing the platform contract deliberately:

- `src/strategy_research/package_builder.py`
- standard field names such as `trade_date`, `order_book_id`, `target_weight`
- the Strategy Package output layout

Run the full local workflow:

```bash
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
```

The default package is written to `/tmp/demo_weights_template_package.zip`.

To upload after the quant_platform API is running:

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="<token_sent_securely>"
python scripts/07_submit_package.py
```

For local development, use `http://127.0.0.1:8000` instead. If the local API
uses `API_TOKEN=change_me`, the token can be omitted.

Then open the dashboard:

```text
http://39.106.218.30/ui/backtests/current
```

The submit script prints the returned `run_id`, downloads the result zip, and
uses `/backtests/runs/{run_id}/...` for follow-up reads. The dashboard's
`current` view can still be overwritten by later uploads.

Common failures:

- Missing standard columns: fix the upstream output instead of changing the
  validator.
- Daily weight sum above 1.0: reduce `top_n` or normalize weights deliberately.
- API not running: start quant_platform with `make api`.
- Package rejected: compare `manifest.json`, `config.json`, and weights columns
  with `docs/STRATEGY_PACKAGE_SPEC.md` in the platform repository.
- Data policy violation: do not commit API tokens, raw data, generated output,
  result zips, or downloaded API responses.
