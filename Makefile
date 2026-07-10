BACKFILL_END_DATE ?= $(shell date +%F)

.PHONY: install test api api-prod api-smoke client-smoke backtest-api-smoke dashboard-smoke create-demo-weights-package submit-demo-weights-package template-smoke check-data audit-data-lake backfill-core-smoke backfill-core-dry-run backfill-core-full check-data-2016-present server-sync-manifest update-index-2025 check-index-data update-tradability-2025 check-tradability-data update-valuation-2025 check-valuation-data update-industry-2025 check-industry-data update-index-membership-2025 check-index-membership-data vix-q5-exposure-audit vix-q5-build-lagged-package vix-q5-compare-lagged daily-data-update deploy-check query-sample demo-backtest view-demo-backtest demo-daily-backtest view-demo-daily-backtest status clean

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

dashboard-smoke:
	PYTHONPATH=src python scripts/17_dashboard_smoke_test.py

create-demo-weights-package:
	PYTHONPATH=src python scripts/18_create_demo_weights_package.py

submit-demo-weights-package:
	PYTHONPATH=src python scripts/19_submit_demo_weights_package.py

template-smoke:
	PYTHONPATH=src python scripts/21_template_smoke_test.py

check-data:
	PYTHONPATH=src python scripts/05_check_local_data.py

audit-data-lake:
	PYTHONPATH=src python scripts/25_audit_data_lake_coverage.py

backfill-core-smoke:
	PYTHONPATH=src python scripts/26_backfill_2016_present_core_data.py --start-date 2025-01-02 --end-date 2025-01-31 --datasets index_prices,calendar --smoke

backfill-core-dry-run:
	PYTHONPATH=src python scripts/26_backfill_2016_present_core_data.py --start-date 2016-01-01 --end-date $(BACKFILL_END_DATE) --datasets prices,index_prices,calendar,instruments,tradability,valuation,industry,index_members --dry-run

backfill-core-full:
	PYTHONPATH=src python scripts/26_backfill_2016_present_core_data.py --start-date 2016-01-01 --end-date $(BACKFILL_END_DATE) --datasets prices,index_prices,calendar,instruments,tradability,valuation,industry,index_members --confirm-full-backfill

check-data-2016-present:
	PYTHONPATH=src python scripts/27_check_2016_present_data_quality.py

server-sync-manifest:
	PYTHONPATH=src python scripts/28_generate_server_sync_manifest.py

update-index-2025:
	PYTHONPATH=src python scripts/22_update_2025_index_prices.py

check-index-data:
	PYTHONPATH=src python scripts/23_check_index_data.py

update-tradability-2025:
	PYTHONPATH=src python scripts/25_update_2025_tradability.py

check-tradability-data:
	PYTHONPATH=src python scripts/26_check_tradability_data.py

update-valuation-2025:
	PYTHONPATH=src python scripts/27_update_2025_valuation.py

check-valuation-data:
	PYTHONPATH=src python scripts/28_check_valuation_data.py

update-industry-2025:
	PYTHONPATH=src python scripts/29_update_2025_industry.py

check-industry-data:
	PYTHONPATH=src python scripts/30_check_industry_data.py

update-index-membership-2025:
	PYTHONPATH=src python scripts/31_update_2025_index_membership.py

check-index-membership-data:
	PYTHONPATH=src python scripts/32_check_index_membership_data.py

vix-q5-exposure-audit:
	PYTHONPATH=src python scripts/33_audit_vix_q5_exposure.py

vix-q5-build-lagged-package:
	PYTHONPATH=src python scripts/34_build_vix_q5_lagged_package.py

vix-q5-compare-lagged:
	PYTHONPATH=src python scripts/35_compare_vix_q5_same_day_vs_lagged.py

daily-data-update:
	PYTHONPATH=src python scripts/24_daily_data_update.py --year 2025 --skip-stocks

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
