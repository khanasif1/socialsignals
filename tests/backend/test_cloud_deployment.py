import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest


@pytest.mark.parametrize("resolved,healthy", [(True, True), (False, True), (True, False)])
def test_private_vault_setup_enables_only_after_resolved_credentials_and_health(
    tmp_path, monkeypatch, capsys, resolved, healthy,
):
    script = Path(__file__).resolve().parents[2] / "deployment" / "configure-crawler.py"
    spec = importlib.util.spec_from_file_location("configure_crawler", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    outputs = tmp_path / "outputs.json"
    outputs.write_text(json.dumps({
        "keyVaultName": {"value": "fixture-vault"}, "webAppName": {"value": "fixture-app"},
        "applicationUrl": {"value": "https://fixture.azurewebsites.net"},
    }))
    answers = iter(["fixture-member", "ENABLE"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(module.getpass, "getpass", lambda prompt: "fixture-password")
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    credential = MagicMock()
    credential.__enter__.return_value.get_token.return_value = SimpleNamespace(token="fixture-token")
    monkeypatch.setattr(module, "AzureCliCredential", lambda **kwargs: credential)
    settings_writes = []
    secret_writes = []

    def handle(request):
        assert request.url.scheme == "https"
        if "/secrets/" in request.url.path:
            secret_writes.append(json.loads(request.content)["properties"]["value"])
        elif request.url.path.endswith("/appsettings/list"):
            return httpx.Response(200, json={"properties": settings_writes[-1] if settings_writes else {"UNCHANGED": "retained"}})
        elif "/config/configreferences/" in request.url.path and request.method == "GET":
            return httpx.Response(200, json={"value": [
                {"name": name, "properties": {"status": "Resolved" if resolved else "AccessToKeyVaultDenied"}}
                for name in ("SIGNAL_LINKEDIN_CRAWLER_USERNAME", "SIGNAL_LINKEDIN_CRAWLER_PASSWORD")
            ]})
        elif request.url.path.endswith("/config/appsettings") and request.method == "PUT":
            settings_writes.append(json.loads(request.content)["properties"])
        elif request.url.path == "/api/health":
            return httpx.Response(200, json={
                "status": "ok", "storage": "connected", "worker_image": healthy,
            })
        return httpx.Response(200, json={})

    client = httpx.Client
    monkeypatch.setattr(module.httpx, "Client", lambda **kwargs: client(transport=httpx.MockTransport(handle)))
    if resolved and healthy:
        module.configure("fixture-subscription", "fixture-group", outputs)
        assert settings_writes[-1]["SIGNAL_LINKEDIN_CRAWLER_ENABLED"] == "true"
        assert "@Microsoft.KeyVault(" in settings_writes[-1]["SIGNAL_LINKEDIN_CRAWLER_PASSWORD"]
    else:
        with pytest.raises(RuntimeError, match="collection remains disabled"):
            module.configure("fixture-subscription", "fixture-group", outputs)
        assert all(write["SIGNAL_LINKEDIN_CRAWLER_ENABLED"] == "false" for write in settings_writes)
    assert secret_writes == ["fixture-member", "fixture-password"]
    assert settings_writes[0]["SIGNAL_LINKEDIN_CRAWLER_ENABLED"] == "false"
    assert all(write["UNCHANGED"] == "retained" for write in settings_writes)
    assert "fixture-password" not in json.dumps(settings_writes)
    assert "fixture-password" not in capsys.readouterr().out
