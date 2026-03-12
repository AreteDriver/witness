"""WatchTower configuration — all settings from environment or .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # World API — confirmed live endpoint (blockchain gateway)
    WORLD_API_BASE: str = "https://blockchain-gateway-stillness.live.tech.evefrontier.com"

    # Polling
    POLL_INTERVAL_SECONDS: int = 30
    POLL_TIMEOUT_SECONDS: float = 10.0

    # Database
    DB_PATH: str = "data/watchtower.db"

    # Discord bot
    DISCORD_TOKEN: str = ""
    DISCORD_WEBHOOK_URL: str = ""

    # Anthropic (for narrative generation)
    ANTHROPIC_API_KEY: str = ""

    # Watcher Smart Assembly owner address (for assembly tracker)
    WATCHER_OWNER_ADDRESS: str = ""

    # EVE SSO (CCP OAuth2)
    EVE_SSO_CLIENT_ID: str = ""
    EVE_SSO_SECRET_KEY: str = ""
    EVE_SSO_CALLBACK_URL: str = ""

    # Warden (autonomous threat intelligence loop)
    WARDEN_ENABLED: bool = True
    WARDEN_MAX_ITERATIONS: int = 10
    WARDEN_MAX_DURATION_HOURS: int = 24
    WARDEN_INTERVAL_SECONDS: int = 300  # 5 minutes between cycles

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_prefix": "WATCHTOWER_"}


settings = Settings()
