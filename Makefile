.PHONY: install test api api-prod api-smoke client-smoke backtest-api-smoke check-data deploy-check query-sample demo-backtest view-demo-backtest demo-daily-backtest view-demo-daily-backtest status clean

install:
	python -m pip install -e .

test:
	PYTHONPATH=src pytest -q

api:
	PYTHONPATH=src python scripts/07_run_api_local.py

api-prod:
	PYTHONPATH=src python scripts/10_run_api_prod.py

api-smoke:
	PYTHONPATH=src python scripts/08_api_smoke_test.py

client-smoke:
	PYTHONPATH=src python scripts/09_client_smoke_test.py

backtest-api-smoke:
	PYTHONPATH=src python scripts/16_run_backtest_api_smoke.py

check-data:
	PYTHONPATH=src python scripts/05_check_local_data.py

deploy-check:
	PYTHONPATH=src python scripts/11_deploy_check.py

query-sample:
	PYTHONPATH=src python scripts/06_query_2025_sample.py

demo-backtest:
	PYTHONPATH=src python scripts/12_create_demo_backtest_result.py

view-demo-backtest:
	PYTHONPATH=src python scripts/13_view_demo_backtest_result.py

demo-daily-backtest:
	PYTHONPATH=src python scripts/14_run_demo_daily_backtest.py

view-demo-daily-backtest:
	PYTHONPATH=src python scripts/15_view_demo_daily_backtest.py

status:
	git status --short
	find data/research_data/rqdata -maxdepth 3 -type f | sort || true

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
