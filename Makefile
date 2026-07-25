.PHONY: app-down app-up bootstrap-signoz format frontend-build frontend-sync frontend-test \
	frontend-typecheck frontend-verify healthy incident lint live-smoke live-verify \
	reset run-api sync telemetry-check test test-webhook typecheck verify

UV_CACHE_DIR ?= .uv-cache
export UV_CACHE_DIR

sync:
	uv sync

frontend-sync:
	pnpm --dir apps/rootspan-console install --frozen-lockfile

format:
	uv run --no-sync ruff format .
	uv run --no-sync ruff check --fix .

lint:
	uv run --no-sync ruff format --check .
	uv run --no-sync ruff check .

typecheck:
	uv run --no-sync pyright

test:
	uv run --no-sync pytest

frontend-typecheck:
	pnpm --dir apps/rootspan-console run typecheck

frontend-test:
	pnpm --dir apps/rootspan-console test

frontend-build:
	pnpm --dir apps/rootspan-console run build

frontend-verify: frontend-typecheck frontend-test frontend-build

verify: lint typecheck test frontend-verify

run-api:
	uv run --no-sync rootspan-api

bootstrap-signoz:
	uv run --no-sync rootspan-bootstrap-signoz

test-webhook:
	uv run --no-sync rootspan-bootstrap-signoz --test-webhook

app-up:
	docker compose up --build --detach --wait

app-down:
	docker compose down

healthy:
	uv run --no-sync rootspan-traffic --gateway-url http://127.0.0.1:9001 --mode healthy --count 10

incident:
	curl --fail --silent --show-error --request POST \
		--header 'Content-Type: application/json' \
		--data '{"enabled":true}' \
		http://127.0.0.1:9003/scenario/failure
	uv run --no-sync rootspan-traffic --gateway-url http://127.0.0.1:9001 --mode incident --count 10

reset:
	curl --fail --silent --show-error --request POST \
		--header 'Content-Type: application/json' \
		--data '{"enabled":false}' \
		http://127.0.0.1:9003/scenario/failure

live-smoke:
	uv run --no-sync rootspan-smoke

telemetry-check:
	docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client --query \
		"SELECT end_to_end_traces, failing_traces, throwIf(end_to_end_traces < 20 OR failing_traces < 10, 'incomplete RootSpan trace cohorts') FROM (SELECT count() AS end_to_end_traces, countIf(has_error = 1) AS failing_traces FROM (SELECT trace_id, uniq(serviceName) AS service_count, max(has_error) AS has_error FROM signoz_traces.distributed_signoz_index_v3 WHERE timestamp >= now() - INTERVAL 15 MINUTE AND name IN ('gateway.checkout', 'checkout.place_order', 'inventory.reserve') GROUP BY trace_id HAVING service_count = 3)) FORMAT PrettyCompact"
	docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client --query \
		"SELECT metric_count, throwIf(metric_count < 2, 'RootSpan lab counters are missing') FROM (SELECT uniq(metric_name) AS metric_count FROM signoz_metrics.distributed_metadata WHERE metric_name IN ('rootspan.lab.requests', 'rootspan.lab.failures') AND last_reported_unix_milli >= toUnixTimestamp64Milli(now64()) - 900000) FORMAT PrettyCompact"
	docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client --query \
		"SELECT log_count, throwIf(log_count < 10, 'RootSpan incident logs are missing') FROM (SELECT count() AS log_count FROM signoz_logs.distributed_logs_v2 WHERE timestamp >= toUnixTimestamp64Nano(now64()) - 900000000000 AND body LIKE '%inventory.reserve.timeout%') FORMAT PrettyCompact"
	docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client --query \
		"SELECT stage_count, throwIf(stage_count < 6, 'RootSpan investigation stage spans are missing') FROM (SELECT uniq(name) AS stage_count FROM signoz_traces.distributed_signoz_index_v3 WHERE timestamp >= now() - INTERVAL 15 MINUTE AND name IN ('incident.window.build', 'cohort.select', 'trace.align', 'divergence.rank', 'blast_radius.calculate', 'brief.compile')) FORMAT PrettyCompact"

live-verify:
	$(MAKE) live-smoke
	$(MAKE) telemetry-check
