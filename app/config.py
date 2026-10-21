from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mailtrap_api_token: str
    mailtrap_sandbox: bool = True
    mailtrap_inbox_id: str = ""
    mail_from: str
    mail_from_name: str

    app_url: str = "http://localhost:8000"
    db_path: str = ".data/app.sqlite"
    admin_password: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def _require_inbox_id_in_sandbox(self) -> "Settings":
        if self.mailtrap_sandbox and not self.mailtrap_inbox_id:
            raise ValueError("MAILTRAP_INBOX_ID is required when MAILTRAP_SANDBOX=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
