FROM python:3.11-slim

RUN useradd --create-home --shell /bin/bash runner

WORKDIR /app

RUN python -m pip install --no-cache-dir pandas numpy pyarrow duckdb

# Template only: production builds should copy project code or install a wheel here.
# COPY . /app
# RUN python -m pip install -e .

USER runner

CMD ["python", "-m", "rq_platform.backtest.worker"]
