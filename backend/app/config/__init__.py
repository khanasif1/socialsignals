from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIGNAL_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    env: Literal["development", "production"] = "development"
    login_secret: SecretStr = Field(min_length=32)
    session_secret: SecretStr = Field(min_length=32)
    storage: Literal["local", "azure"] = "local"
    local_path: str = ".signal-data"
    storage_account: str = ""
    storage_container: str = "signal-data"
    cors_origins: list[str] = []
    ai_provider: Literal["none", "openai", "azure"] = "none"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o-mini"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"
    linkedin_client_id: str = ""
    linkedin_client_secret: SecretStr = SecretStr("")
    linkedin_redirect_uri: str = "http://localhost:8000/api/linkedin/callback"
    scheduler_enabled: bool = True

    @model_validator(mode="after")
    def validate_configuration(self):
        for secret in (self.login_secret, self.session_secret):
            value = secret.get_secret_value()
            if value.startswith("@Microsoft.KeyVault(") or value.startswith("replace-with-"):
                raise ValueError("Authentication secrets must be configured and Key Vault references resolved")
        if self.login_secret == self.session_secret:
            raise ValueError("Login and signing secrets must be independent")
        if self.storage == "azure" and not self.storage_account:
            raise ValueError("Azure storage account is required")
        if self.env == "production" and self.storage != "azure":
            raise ValueError("Production requires Azure Blob Storage")
        if self.env == "production" and not self.linkedin_redirect_uri.startswith("https://"):
            raise ValueError("Production OAuth redirect must use HTTPS")
        if self.ai_provider == "openai" and not self.openai_api_key.get_secret_value():
            raise ValueError("OpenAI API key is required")
        if self.ai_provider == "azure" and not (
            self.azure_openai_endpoint and self.azure_openai_deployment
        ):
            raise ValueError("Azure OpenAI endpoint and deployment are required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
