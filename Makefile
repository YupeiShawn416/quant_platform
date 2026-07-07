.PHONY: install test api api-smoke check-data query-sample status clean

install:
	python -m pip install -e .

test:
	PYTHONPATH=src pytest -q

api:
	PYTHONPATH=src python scripts/07_run_api_local.py

api-smoke:
	PYTHONPATH=src python scripts/08_api_smoke_test.py

check-data:
	PYTHONPATH=src python scripts/05_check_local_data.py

query-sample:
	PYTHONPATH=src python scripts/06_query_2025_sample.py

status:
	git status --short
	find data/research_data/rqdata -maxdepth 3 -type f | sort || true

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
