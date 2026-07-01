import os
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


BOOTSTRAP_USER_DEFAULTS = {
    "ADMIN": ("admin", "admin", "Administrator", "all"),
    "BGH": ("bgh", "bangiamhieu", "Ban Giám Hiệu", "all"),
    "QUANLY": ("quanly", "quanly", "Quản lý trường", "all"),
    "GIAMTHI": ("giamthi", "giamthi", "Bộ phận Giám thị", "giamthi"),
    "BANTRU": ("bantru", "bantru", "Bộ phận Bán trú", "bantru"),
}


class Settings:
    def __init__(self) -> None:
        self.secret_key = self._required("FSCHP_SECRET_KEY", min_length=32)
        self.environment = os.getenv("FSCHP_ENV", "development").strip().lower()
        self.algorithm = os.getenv("FSCHP_JWT_ALGORITHM", "HS256")
        if self.algorithm.lower() == "none":
            raise RuntimeError("FSCHP_JWT_ALGORITHM must not be 'none'")
        self.access_token_expire_minutes = self._int(
            "FSCHP_ACCESS_TOKEN_EXPIRE_MINUTES",
            default=480,
            minimum=1,
        )
        self.override_password_hash = os.getenv("FSCHP_OVERRIDE_PASSWORD_HASH", "")
        self.db_path = Path(os.getenv("FSCHP_DB_PATH", str(PROJECT_ROOT / "nenep.db")))
        self.frontend_dir = Path(os.getenv("FSCHP_FRONTEND_DIR", str(FRONTEND_DIR)))
        self.cors_origins = self._csv("FSCHP_CORS_ORIGINS", default=["http://localhost:8000"])
        self.cookie_name = os.getenv("FSCHP_COOKIE_NAME", "fschp_access_token")
        self.cookie_secure = self._bool("FSCHP_COOKIE_SECURE", default=False)
        if self.environment == "production" and not self.cookie_secure:
            raise RuntimeError("FSCHP_COOKIE_SECURE must be true in production")
        self.cookie_samesite = os.getenv("FSCHP_COOKIE_SAMESITE", "lax")
        self.rate_limit_window_seconds = self._int("FSCHP_RATE_LIMIT_WINDOW_SECONDS", default=60, minimum=1)
        self.auth_rate_limit = self._int("FSCHP_AUTH_RATE_LIMIT", default=10, minimum=1)
        self.api_rate_limit = self._int("FSCHP_API_RATE_LIMIT", default=240, minimum=1)
        self.bootstrap_admin_username = os.getenv("FSCHP_BOOTSTRAP_ADMIN_USERNAME", "").strip()
        self.bootstrap_admin_password = os.getenv("FSCHP_BOOTSTRAP_ADMIN_PASSWORD", "")
        self.bootstrap_admin_display_name = os.getenv("FSCHP_BOOTSTRAP_ADMIN_DISPLAY_NAME", "Administrator")
        self.bootstrap_users = self._bootstrap_users()

    @staticmethod
    def _required(name: str, min_length: int = 1) -> str:
        value = os.getenv(name, "")
        if len(value) < min_length:
            raise RuntimeError(f"{name} must be set and at least {min_length} characters long")
        return value

    @staticmethod
    def _int(name: str, default: int, minimum: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be an integer") from exc
        if value < minimum:
            raise RuntimeError(f"{name} must be at least {minimum}")
        return value

    @staticmethod
    def _csv(name: str, default: list[str]) -> list[str]:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
        return values or default

    @staticmethod
    def _bool(name: str, default: bool) -> bool:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    def _bootstrap_users(self) -> list[dict[str, str]]:
        users: list[dict[str, str]] = []
        for key, (default_username, role, default_display_name, folder) in BOOTSTRAP_USER_DEFAULTS.items():
            username = os.getenv(f"FSCHP_BOOTSTRAP_{key}_USERNAME", default_username).strip()
            password = os.getenv(f"FSCHP_BOOTSTRAP_{key}_PASSWORD", "")
            display_name = os.getenv(f"FSCHP_BOOTSTRAP_{key}_DISPLAY_NAME", default_display_name).strip()
            if username and password:
                users.append({
                    "username": username,
                    "password": password,
                    "role": role,
                    "display_name": display_name or default_display_name,
                    "folder": folder,
                })
        return users


@lru_cache
def get_settings() -> Settings:
    return Settings()
