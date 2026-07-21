BACKFILL_END_DATE ?= $(shell date +%F)
FACTOR_IDS ?= market_cap,turnover_rate,momentum_20d,reversal_5d,volatility_20d
UNIVERSE ?= all

.PHONY: install test api api-prod api-smoke client-smoke backtest-api-smoke dashboard-smoke data-api-smoke-local create-demo-paper-account submit-demo-paper-weights run-demo-paper-daily paper-run-daily-all paper-smoke-local compute-builtin-factors analyze-factor generate-factor-weights factor-smoke-local audit-valuation-factor-fields hxz-data-audit hxz-rqdata-probe hxz-p0-dry-run hxz-p0-smoke hxz-p0b-dry-run hxz-p0b-backfill hxz-p1-monthly-panel create-demo-weights-package submit-demo-weights-package template-smoke check-data audit-data-lake backfill-core-smoke backfill-core-dry-run backfill-core-full check-data-2016-present server-sync-manifest daily-update-dry-run daily-update daily-update-status daily-update-report reconcile-daily-update intraday-snapshot-smoke backfill-intraday-snapshots check-intraday-snapshots audit-intraday-snapshots update-index-2025 check-index-data update-tradability-2025 check-tradability-data update-valuation-2025 check-valuation-data update-industry-2025 check-industry-data update-index-membership-2025 check-index-membership-data vix-q5-exposure-audit vix-q5-build-lagged-package vix-q5-compare-lagged daily-data-update deploy-check query-sample demo-backtest view-demo-backtest demo-daily-backtest view-demo-daily-backtest status clean

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

data-api-smoke-local:
	PYTHONPATH=src python scripts/36_data_api_smoke_local.py

create-demo-paper-account:
	PYTHONPATH=src python scripts/34_create_demo_paper_account.py

submit-demo-paper-weights:
	PYTHONPATH=src python scripts/35_submit_demo_paper_weights.py

run-demo-paper-daily:
	PYTHONPATH=src python scripts/36_run_demo_paper_daily.py

paper-run-daily-all:
	@test -n "$(TRADE_DATE)" || (echo "TRADE_DATE is required, e.g. make paper-run-daily-all TRADE_DATE=2026-07-14"; exit 2)
	PYTHONPATH=src python scripts/43_run_paper_daily_all.py --trade-date $(TRADE_DATE)

paper-smoke-local:
	PYTHONPATH=src python scripts/38_paper_smoke_local.py

compute-builtin-factors:
	@test -n "$(START_DATE)" || (echo "START_DATE is required"; exit 2)
	@test -n "$(END_DATE)" || (echo "END_DATE is required"; exit 2)
	PYTHONPATH=src python scripts/38_compute_builtin_factors.py --start-date $(START_DATE) --end-date $(END_DATE) --factor-ids $(FACTOR_IDS) --universe $(UNIVERSE) --overwrite

analyze-factor:
	@test -n "$(FACTOR_ID)" || (echo "FACTOR_ID is required"; exit 2)
	PYTHONPATH=src python scripts/39_analyze_factor.py --factor-id $(FACTOR_ID) $(if $(START_DATE),--start-date $(START_DATE),) $(if $(END_DATE),--end-date $(END_DATE),)

generate-factor-weights:
	@test -n "$(FACTOR_ID)" || (echo "FACTOR_ID is required"; exit 2)
	PYTHONPATH=src python scripts/40_generate_factor_weights.py --factor-id $(FACTOR_ID) $(if $(START_DATE),--start-date $(START_DATE),) $(if $(END_DATE),--end-date $(END_DATE),) $(if $(USE_LATEST_USABLE_DATE),--use-latest-usable-date,)

factor-smoke-local:
	PYTHONPATH=src python scripts/41_factor_library_smoke.py

audit-valuation-factor-fields:
	PYTHONPATH=src python scripts/42_audit_valuation_factor_fields.py

hxz-data-audit:
	PYTHONPATH=src python scripts/46_audit_hxz_data.py

hxz-rqdata-probe:
	PYTHONPATH=src python scripts/47_probe_rqdata_hxz_fields.py

hxz-p0-dry-run:
	PYTHONPATH=src python scripts/48_hxz_p0_backfill.py --dataset all --dry-run

hxz-p0-smoke:
	PYTHONPATH=src python scripts/48_hxz_p0_backfill.py --dataset all --smoke --validate

hxz-p0b-dry-run:
	PYTHONPATH=src python scripts/50_hxz_p0b_formal_backfill.py --dataset all --dry-run

hxz-p0b-backfill:
	PYTHONPATH=src python scripts/50_hxz_p0b_formal_backfill.py --dataset all --confirm-hxz-p0b-backfill

hxz-p1-monthly-panel:
	PYTHONPATH=src python scripts/51_build_hxz_p1_monthly_panel.py $(if $(START_MONTH),--start-month $(START_MONTH),) $(if $(END_MONTH),--end-month $(END_MONTH),)

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

daily-update-dry-run:
	@test -n "$(END_DATE)" || (echo "END_DATE is required, e.g. make daily-update-dry-run END_DATE=2026-07-11"; exit 2)
	PYTHONPATH=src python scripts/31_daily_data_update.py --end-date $(END_DATE) --dry-run

daily-update:
	@test -n "$(END_DATE)" || (echo "END_DATE is required, e.g. make daily-update END_DATE=2026-07-11"; exit 2)
	PYTHONPATH=src python scripts/31_daily_data_update.py --end-date $(END_DATE) --confirm-daily-update

daily-update-status:
	PYTHONPATH=src python scripts/32_check_daily_update_status.py

daily-update-report:
	PYTHONPATH=src python scripts/32_check_daily_update_status.py

reconcile-daily-update:
	PYTHONPATH=src python scripts/37_reconcile_daily_update_coverage.py

intraday-snapshot-smoke:
	@test -n "$(START_DATE)" || (echo "START_DATE is required, e.g. make intraday-snapshot-smoke START_DATE=2025-01-01 END_DATE=2025-01-10"; exit 2)
	@test -n "$(END_DATE)" || (echo "END_DATE is required, e.g. make intraday-snapshot-smoke START_DATE=2025-01-01 END_DATE=2025-01-10"; exit 2)
	PYTHONPATH=src python scripts/43_backfill_intraday_snapshots.py --start-date $(START_DATE) --end-date $(END_DATE) --batch-size 300 --confirm-intraday-snapshot-backfill

backfill-intraday-snapshots:
	@test -n "$(START_DATE)" || (echo "START_DATE is required"; exit 2)
	@test -n "$(END_DATE)" || (echo "END_DATE is required"; exit 2)
	PYTHONPATH=src python scripts/43_backfill_intraday_snapshots.py --start-date $(START_DATE) --end-date $(END_DATE) --batch-size 300 --confirm-intraday-snapshot-backfill

check-intraday-snapshots:
	PYTHONPATH=src python scripts/44_check_intraday_snapshot_quality.py

audit-intraday-snapshots:
	PYTHONPATH=src python scripts/45_audit_intraday_snapshot_coverage.py

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
