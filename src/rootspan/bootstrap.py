"""Create the local SigNoz admin and dedicated read-only RootSpan runtime key."""

import argparse
import json
import os
import secrets
from pathlib import Path
from typing import cast

import httpx

JsonObject = dict[str, object]
WEBHOOK_CHANNEL_NAME = "rootspan-webhook"
ALERT_NAME = "RootSpan checkout error rate"
DASHBOARD_NAME = "rootspan-incident-overview"


class BootstrapError(RuntimeError):
    """SigNoz bootstrap could not complete safely."""


def _json(response: httpx.Response) -> JsonObject:
    if response.is_error:
        detail = response.text[:500].replace("\n", " ")
        raise BootstrapError(
            f"SigNoz {response.request.url.path} returned {response.status_code}: {detail}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise BootstrapError(
            f"SigNoz returned an invalid response from {response.request.url.path}"
        )
    return cast(JsonObject, payload)


def _data_object(payload: JsonObject) -> JsonObject:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BootstrapError("SigNoz response did not include an object data field")
    return cast(JsonObject, data)


def _data_list(payload: JsonObject) -> list[JsonObject]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise BootstrapError("SigNoz response did not include a list data field")
    return [cast(JsonObject, item) for item in cast(list[object], data) if isinstance(item, dict)]


def _nested_data_list(payload: JsonObject, name: str) -> list[JsonObject]:
    data = _data_object(payload)
    values = data.get(name)
    if not isinstance(values, list):
        raise BootstrapError(f"SigNoz response did not include data.{name} as a list")
    return [cast(JsonObject, item) for item in cast(list[object], values) if isinstance(item, dict)]


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", maxsplit=1)
        values[name.strip()] = value.strip()
    return values


def _write_secret(path: Path, values: dict[str, str]) -> None:
    path.write_text(
        "".join(f"{name}={value}\n" for name, value in values.items()),
        encoding="utf-8",
    )
    path.chmod(0o600)


def _required_string(source: JsonObject, name: str) -> str:
    value = source.get(name)
    if not isinstance(value, str) or not value:
        raise BootstrapError(f"SigNoz response is missing {name}")
    return value


def _alert_rule() -> JsonObject:
    def query(name: str, error_only: bool) -> JsonObject:
        return {
            "type": "builder_query",
            "spec": {
                "name": name,
                "signal": "traces",
                "stepInterval": 60,
                "disabled": True,
                "aggregations": [{"expression": "count()"}],
                "filter": {
                    "expression": "name = 'gateway.checkout'"
                    + (" AND hasError = true" if error_only else "")
                },
                "groupBy": [],
            },
        }

    return cast(
        JsonObject,
        {
            "alert": ALERT_NAME,
            "alertType": "TRACES_BASED_ALERT",
            "description": "Gateway checkout errors indicate the seeded incident symptom.",
            "ruleType": "threshold_rule",
            "version": "v5",
            "schemaVersion": "v2alpha1",
            "condition": {
                "compositeQuery": {
                    "queryType": "builder",
                    "panelType": "graph",
                    "unit": "percent",
                    "queries": [
                        query("A", True),
                        query("B", False),
                        {
                            "type": "builder_formula",
                            "spec": {
                                "name": "F1",
                                "expression": "(A / B) * 100",
                                "legend": "checkout error rate",
                            },
                        },
                    ],
                },
                "selectedQueryName": "F1",
                "thresholds": {
                    "kind": "basic",
                    "spec": [
                        {
                            "name": "critical",
                            "op": "above",
                            "matchType": "at_least_once",
                            "target": 5,
                            "channels": [WEBHOOK_CHANNEL_NAME],
                        }
                    ],
                },
            },
            "evaluation": {"kind": "rolling", "spec": {"evalWindow": "1m", "frequency": "1m"}},
            "notificationSettings": {
                "groupBy": ["alertname"],
                "usePolicy": False,
            },
            "labels": {
                "severity": "critical",
                "team": "rootspan-demo",
                "rootspan_target_operation": "gateway.checkout",
            },
            "annotations": {
                "summary": "Checkout error rate crossed 5%",
                "description": "RootSpan will compare healthy and failing trace cohorts.",
            },
        },
    )


def _webhook_receiver() -> JsonObject:
    return {
        "name": WEBHOOK_CHANNEL_NAME,
        "webhook_configs": [
            {
                "url": "http://rootspan-api:8001/api/v1/webhooks/signoz",
                "send_resolved": True,
            }
        ],
    }


def _dashboard() -> JsonObject:
    builder_queries = [
        {
            "type": "builder_query",
            "spec": {
                "name": "A",
                "signal": "traces",
                "stepInterval": 60,
                "disabled": True,
                "aggregations": [{"expression": "count()"}],
                "filter": {"expression": "name = 'gateway.checkout' AND hasError = true"},
                "groupBy": [],
            },
        },
        {
            "type": "builder_query",
            "spec": {
                "name": "B",
                "signal": "traces",
                "stepInterval": 60,
                "disabled": True,
                "aggregations": [{"expression": "count()"}],
                "filter": {"expression": "name = 'gateway.checkout'"},
                "groupBy": [],
            },
        },
        {
            "type": "builder_formula",
            "spec": {
                "name": "F1",
                "expression": "(A / B) * 100",
                "legend": "checkout error rate",
            },
        },
    ]
    return cast(
        JsonObject,
        {
            "name": DASHBOARD_NAME,
            "schemaVersion": "v6",
            "tags": [{"key": "project", "value": "rootspan"}],
            "spec": {
                "display": {
                    "name": "RootSpan incident overview",
                    "description": "Upstream symptom used to trigger RootSpan correlation.",
                },
                "duration": "15m",
                "refreshInterval": "30s",
                "variables": [],
                "panels": {
                    "checkout-error-rate": {
                        "kind": "Panel",
                        "spec": {
                            "display": {
                                "name": "Checkout error rate",
                                "description": "Failing gateway.checkout spans divided by total.",
                            },
                            "plugin": {"kind": "signoz/TimeSeriesPanel", "spec": {}},
                            "queries": [
                                {
                                    "kind": "time_series",
                                    "spec": {
                                        "name": "Checkout error rate",
                                        "plugin": {
                                            "kind": "signoz/CompositeQuery",
                                            "spec": {"queries": builder_queries},
                                        },
                                    },
                                }
                            ],
                        },
                    }
                },
                "layouts": [
                    {
                        "kind": "Grid",
                        "spec": {
                            "items": [
                                {
                                    "x": 0,
                                    "y": 0,
                                    "width": 12,
                                    "height": 8,
                                    "content": {"$ref": "#/spec/panels/checkout-error-rate"},
                                }
                            ]
                        },
                    }
                ],
            },
        },
    )


def bootstrap(
    *,
    signoz_url: str,
    bootstrap_file: Path,
    runtime_file: Path,
    test_webhook: bool = False,
) -> JsonObject:
    """Idempotently configure a Viewer-only service account without printing secrets."""

    configured = _load_env(bootstrap_file)
    email = os.getenv(
        "SIGNOZ_BOOTSTRAP_EMAIL",
        configured.get("SIGNOZ_BOOTSTRAP_EMAIL", "rootspan-admin@localhost.local"),
    )
    password = os.getenv(
        "SIGNOZ_BOOTSTRAP_PASSWORD",
        configured.get("SIGNOZ_BOOTSTRAP_PASSWORD", ""),
    )
    org_id = os.getenv(
        "SIGNOZ_BOOTSTRAP_ORG_ID",
        configured.get("SIGNOZ_BOOTSTRAP_ORG_ID", ""),
    )

    with httpx.Client(base_url=signoz_url.rstrip("/"), timeout=20) as client:
        version = _json(client.get("/api/v1/version"))
        setup_complete = version.get("setupCompleted") is True
        created_admin = False
        if not setup_complete:
            password = password or secrets.token_urlsafe(32)
            registered = _data_object(
                _json(
                    client.post(
                        "/api/v1/register",
                        json={
                            "name": "RootSpan Bootstrap",
                            "email": email,
                            "password": password,
                            "orgDisplayName": "RootSpan Lab",
                            "orgName": "rootspan-lab",
                        },
                    )
                )
            )
            org_id = _required_string(registered, "orgId")
            _write_secret(
                bootstrap_file,
                {
                    "SIGNOZ_BOOTSTRAP_EMAIL": email,
                    "SIGNOZ_BOOTSTRAP_PASSWORD": password,
                    "SIGNOZ_BOOTSTRAP_ORG_ID": org_id,
                },
            )
            created_admin = True
        elif not password or not org_id:
            raise BootstrapError(
                "SigNoz is already initialized; provide the local bootstrap credential file"
            )

        session = _data_object(
            _json(
                client.post(
                    "/api/v2/sessions/email_password",
                    json={"email": email, "password": password, "orgId": org_id},
                )
            )
        )
        token = _required_string(session, "accessToken")
        headers = {"Authorization": f"Bearer {token}"}

        accounts = _data_list(_json(client.get("/api/v1/service_accounts", headers=headers)))
        account = next((item for item in accounts if item.get("name") == "rootspan-runtime"), None)
        created_account = account is None
        if account is None:
            account = _data_object(
                _json(
                    client.post(
                        "/api/v1/service_accounts",
                        json={"name": "rootspan-runtime"},
                        headers=headers,
                    )
                )
            )
        account_id = _required_string(account, "id")

        roles = _data_list(_json(client.get("/api/v1/roles", headers=headers)))
        viewer = next((item for item in roles if item.get("name") == "signoz-viewer"), None)
        if viewer is None:
            raise BootstrapError("SigNoz did not expose the built-in signoz-viewer role")
        viewer_id = _required_string(viewer, "id")
        assigned_roles = _data_list(
            _json(client.get(f"/api/v1/service_accounts/{account_id}/roles", headers=headers))
        )
        if not any(item.get("id") == viewer_id for item in assigned_roles):
            _json(
                client.post(
                    "/api/v1/service_account_roles",
                    json={"serviceAccountId": account_id, "roleId": viewer_id},
                    headers=headers,
                )
            )

        channels = _data_list(_json(client.get("/api/v1/channels", headers=headers)))
        channel = next(
            (item for item in channels if item.get("name") == WEBHOOK_CHANNEL_NAME),
            None,
        )
        created_channel = channel is None
        if channel is None:
            _data_object(
                _json(
                    client.post(
                        "/api/v1/channels",
                        json=_webhook_receiver(),
                        headers=headers,
                    )
                )
            )

        dashboards = _nested_data_list(
            _json(client.get("/api/v2/dashboards?limit=100", headers=headers)),
            "dashboards",
        )
        created_dashboard = not any(item.get("name") == DASHBOARD_NAME for item in dashboards)
        if created_dashboard:
            _data_object(
                _json(
                    client.post(
                        "/api/v2/dashboards",
                        json=_dashboard(),
                        headers=headers,
                    )
                )
            )

        rules = _data_list(_json(client.get("/api/v2/rules", headers=headers)))
        created_rule = not any(item.get("alert") == ALERT_NAME for item in rules)
        if created_rule:
            _data_object(
                _json(
                    client.post(
                        "/api/v2/rules",
                        json=_alert_rule(),
                        headers=headers,
                    )
                )
            )

        if test_webhook:
            response = client.post(
                "/api/v1/channels/test",
                json=_webhook_receiver(),
                headers=headers,
            )
            response.raise_for_status()

        runtime = _load_env(runtime_file)
        created_key = not bool(runtime.get("SIGNOZ_API_KEY"))
        if created_key:
            key = _data_object(
                _json(
                    client.post(
                        f"/api/v1/service_accounts/{account_id}/keys",
                        json={
                            "name": f"rootspan-runtime-{secrets.token_hex(4)}",
                            "expiresAt": 0,
                        },
                        headers=headers,
                    )
                )
            )
            _write_secret(runtime_file, {"SIGNOZ_API_KEY": _required_string(key, "key")})

    return {
        "status": "ready",
        "createdAdmin": created_admin,
        "createdServiceAccount": created_account,
        "createdWebhookChannel": created_channel,
        "createdAlertRule": created_rule,
        "createdDashboard": created_dashboard,
        "createdRuntimeKey": created_key,
        "runtimeRole": "signoz-viewer",
        "testedWebhook": test_webhook,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signoz-url", default="http://127.0.0.1:8080")
    parser.add_argument("--bootstrap-file", type=Path, default=Path(".env.rootspan-bootstrap"))
    parser.add_argument("--runtime-file", type=Path, default=Path(".env.rootspan"))
    parser.add_argument(
        "--test-webhook",
        action="store_true",
        help="send a SigNoz test notification after RootSpan is running",
    )
    args = parser.parse_args()
    try:
        result = bootstrap(
            signoz_url=str(args.signoz_url),
            bootstrap_file=cast(Path, args.bootstrap_file),
            runtime_file=cast(Path, args.runtime_file),
            test_webhook=bool(args.test_webhook),
        )
    except (BootstrapError, httpx.HTTPError) as error:
        parser.exit(1, f"bootstrap failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
