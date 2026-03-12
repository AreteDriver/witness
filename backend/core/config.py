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

    # Admin wallet addresses (comma-separated Sui addresses)
    ADMIN_ADDRESSES: str = ""

    @property
    def admin_address_set(self) -> set[str]:
        """Return normalized set of admin wallet addresses."""
        if not self.ADMIN_ADDRESSES:
            return set()
        return {a.strip().lower() for a in self.ADMIN_ADDRESSES.split(",") if a.strip()}

    # Hackathon mode — all users get Spymaster tier
    # Auto-expires after HACKATHON_ENDS date (YYYY-MM-DD)
    HACKATHON_MODE: bool = False
    HACKATHON_ENDS: str = "2026-04-01"

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
