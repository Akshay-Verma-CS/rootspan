"""Security and contract tests for local SigNoz resource provisioning."""

# pyright: reportPrivateUsage=false

import json
import stat
from pathlib import Path

from rootspan.bootstrap import (
    ALERT_NAME,
    DASHBOARD_NAME,
    WEBHOOK_CHANNEL_NAME,
    _alert_rule,
    _dashboard,
    _load_env,
    _webhook_receiver,
    _write_secret,
)


def test_bootstrap_resources_target_rootspan_without_runtime_write_access() -> None:
    rule = json.dumps(_alert_rule(), sort_keys=True)
    dashboard = json.dumps(_dashboard(), sort_keys=True)
    receiver = json.dumps(_webhook_receiver(), sort_keys=True)

    assert ALERT_NAME in rule
    assert WEBHOOK_CHANNEL_NAME in rule
    assert "gateway.checkout" in rule
    assert "rootspan_target_operation" in rule
    assert DASHBOARD_NAME in dashboard
    assert '"schemaVersion": "v6"' in dashboard
    assert '"width": 12' in dashboard
    assert "rootspan-api:8001/api/v1/webhooks/signoz" in receiver
    assert "send_resolved" in receiver


def test_secret_files_are_reusable_and_owner_only(tmp_path: Path) -> None:
    path = tmp_path / ".env.rootspan"

    _write_secret(path, {"SIGNOZ_API_KEY": "test-value"})

    assert _load_env(path) == {"SIGNOZ_API_KEY": "test-value"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
