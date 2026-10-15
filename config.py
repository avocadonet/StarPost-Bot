from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: SecretStr = Field(..., alias="BOT_TOKEN")
    target_group_id: int = Field(..., alias="TARGET_GROUP_ID")
    stars_price: int = Field(..., gt=0, alias="STARS_PRICE")
    admin_id: int = Field(..., alias="ADMIN_ID")
    db_path: str = Field(default="transactions.db", alias="DB_PATH")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Settings()