"""Prompt locally for rotated LinkedIn credentials and store them only in Key Vault."""

import argparse
import getpass
import json
import time
from pathlib import Path

import httpx
from azure.identity import AzureCliCredential


def configure(subscription: str, resource_group: str, outputs_path: Path):
    outputs = json.loads(outputs_path.read_text(encoding="utf-8-sig"))
    vault = outputs["keyVaultName"]["value"]
    app = outputs["webAppName"]["value"]
    username = input("LinkedIn username (stored only in Key Vault): ").strip()
    password = getpass.getpass("Rotated LinkedIn password (hidden): ")
    if not username or not password:
        raise ValueError("Both credentials are required.")
    if input("Automated access can restrict your account. Type ENABLE to configure collection: ") != "ENABLE":
        raise ValueError("Configuration cancelled; no Azure changes made.")
    base = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{resource_group}/providers"
    with AzureCliCredential(subscription=subscription) as credential, httpx.Client(timeout=120) as client:
        def request(method, url, payload=None):
            token = credential.get_token("https://management.azure.com/.default").token
            response = client.request(method, url, headers={"Authorization": f"Bearer {token}"}, json=payload)
            response.raise_for_status()
            return response.json() if response.content else {}

        # ARM secret writes work without opening the vault's private data endpoint.
        for name, value in (("linkedin-crawler-username", username), ("linkedin-crawler-password", password)):
            request("PUT", f"{base}/Microsoft.KeyVault/vaults/{vault}/secrets/{name}?api-version=2023-07-01",
                    {"properties": {"value": value}})
        url = f"{base}/Microsoft.Web/sites/{app}/config/appsettings"
        settings = request("POST", f"{url}/list?api-version=2023-12-01")["properties"]
        settings.update({
            "SIGNAL_LINKEDIN_CRAWLER_USERNAME": f"@Microsoft.KeyVault(SecretUri=https://{vault}.vault.azure.net/secrets/linkedin-crawler-username/)",
            "SIGNAL_LINKEDIN_CRAWLER_PASSWORD": f"@Microsoft.KeyVault(SecretUri=https://{vault}.vault.azure.net/secrets/linkedin-crawler-password/)",
            "SIGNAL_LINKEDIN_CRAWLER_ENABLED": "false",
            "WEBJOBS_DISABLE_SCHEDULE": "1",
        })
        request("PUT", f"{url}?api-version=2023-12-01", {"properties": settings})
        references_url = f"{base}/Microsoft.Web/sites/{app}/config/configreferences/appsettings"
        request("POST", f"{references_url}/refresh?api-version=2023-12-01")
        required = {"SIGNAL_LINKEDIN_CRAWLER_USERNAME", "SIGNAL_LINKEDIN_CRAWLER_PASSWORD"}
        for _ in range(24):
            references = request("GET", f"{references_url}?api-version=2023-12-01")["value"]
            resolved = {item["name"] for item in references if item["properties"]["status"] == "Resolved"}
            if required <= resolved:
                break
            time.sleep(5)
        else:
            raise RuntimeError("Credential references did not resolve; collection remains disabled.")
        health = client.get(f"{outputs['applicationUrl']['value']}/api/health")
        health.raise_for_status()
        if health.json() != {"status": "ok", "storage": "connected", "worker_image": True}:
            raise RuntimeError("Worker/storage health is not ready; collection remains disabled.")
        settings = request("POST", f"{url}/list?api-version=2023-12-01")["properties"]
        settings.update({"SIGNAL_LINKEDIN_CRAWLER_ENABLED": "true", "WEBJOBS_DISABLE_SCHEDULE": "0"})
        request("PUT", f"{url}?api-version=2023-12-01", {"properties": settings})
    print("Key Vault references configured and daily collection enabled. No credentials printed or saved locally.")
    print("Verify the first WebJob run. MFA/CAPTCHA/account challenges pause collection; they are never bypassed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    args = parser.parse_args()
    configure(args.subscription, args.resource_group, args.outputs)
