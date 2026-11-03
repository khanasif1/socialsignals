import os
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash")
ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not BASH, reason="Bash is required for deployment-script checks")


@pytest.fixture
def deployment(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    commands = {
        "az": """
printf '%s\\t' "$@" >> "$TRACE"
printf '\\n' >> "$TRACE"
case "$1 $2 $3" in
  "webapp show --resource-group") echo app,linux ;;
  "acr show --ids") echo fixture.azurecr.io ;;
  "webapp identity show") echo fixture-principal ;;
  "role assignment list") echo fixture-role ;;
esac
""",
        "curl": 'printf \'%s\\n\' "$FIXTURE_HEALTH"',
        "sleep": "exit 0",
        "seq": "echo 1",
    }
    for name, body in commands.items():
        path = tools / name
        path.write_text("#!/usr/bin/env bash\nset -eu\n" + body, newline="\n")
        path.chmod(0o755)
    trace = tmp_path / "calls.txt"
    env = {
        **os.environ,
        "PATH": str(tools) + os.pathsep + os.environ.get("PATH", ""),
        "TRACE": str(trace),
        "MOCK_BIN": str(tools),
        "DEPLOY_SCRIPT": str(ROOT / "deployment" / "deploy-crawler.sh"),
        "AZURE_SUBSCRIPTION": "fixture-subscription",
        "RESOURCE_GROUP": "fixture-group",
        "APP_NAME": "fixture-app",
        "SIGNAL_CONTAINER_IMAGE": "fixture.azurecr.io/signal:test",
        "LINKEDIN_USERNAME_SECRET_URI": "https://fixture.vault.azure.net/secrets/login/",
        "LINKEDIN_PASSWORD_SECRET_URI": "https://fixture.vault.azure.net/secrets/credential/",
        "CONTAINER_REGISTRY_RESOURCE_ID": "/subscriptions/fixture/resourceGroups/fixture/providers/Microsoft.ContainerRegistry/registries/fixture",
        "FIXTURE_HEALTH": '{"status":"ok","storage":"connected","worker_image":true}',
    }

    def run(**overrides):
        result = subprocess.run(
            [BASH, "-c", """
set -eu
if command -v cygpath >/dev/null; then MOCK_BIN="$(cygpath -u "$MOCK_BIN")"; fi
export PATH="$MOCK_BIN:$PATH"
for tool in az curl sleep seq; do
  [[ "$(command -v "$tool")" == "$MOCK_BIN/$tool" ]] || exit 99
done
exec bash "$DEPLOY_SCRIPT"
"""], cwd=ROOT, env={**env, **overrides},
            text=True, capture_output=True, timeout=30,
        )
        return result, trace.read_text() if trace.exists() else ""

    return run


def test_container_deployment_enables_only_after_worker_health(deployment):
    result, calls = deployment()
    assert result.returncode == 0, result.stderr
    disabled = calls.index("SIGNAL_LINKEDIN_CRAWLER_ENABLED=false")
    image = calls.index("--container-image-name")
    enabled = calls.index("SIGNAL_LINKEDIN_CRAWLER_ENABLED=true")
    assert disabled < image < enabled
    assert "SIGNAL_LINKEDIN_CRAWLER_PASSWORD=@Microsoft.KeyVault(" in calls
    assert "WEBSITE_SKIP_RUNNING_KUDUAGENT=false" in calls
    assert "role\tassignment\tcreate" not in calls


def test_old_api_health_does_not_enable_collection(deployment):
    result, calls = deployment(FIXTURE_HEALTH='{"status":"ok","storage":"connected"}')
    assert result.returncode != 0
    assert "collection remains disabled" in result.stderr
    assert "SIGNAL_LINKEDIN_CRAWLER_ENABLED=true" not in calls


def test_invalid_secret_reference_stops_before_azure_calls(deployment):
    result, calls = deployment(LINKEDIN_PASSWORD_SECRET_URI="not-a-secret-uri")
    assert result.returncode != 0
    assert "Expected an Azure Key Vault secret URI" in result.stderr
    assert not calls


def test_registry_mismatch_stops_before_permissions_or_app_changes(deployment):
    result, calls = deployment(SIGNAL_CONTAINER_IMAGE="different.azurecr.io/signal:test")
    assert result.returncode != 0
    assert "specified Azure Container Registry" in result.stderr
    assert "role\tassignment" not in calls
    assert "appsettings" not in calls
