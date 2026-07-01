from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.main import app  # noqa: E402
except Exception as exc:  # pragma: no cover - deployment safety net
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    import_error = str(exc)
    app = FastAPI(title="FSCHP configuration error")

    @app.get("/{path:path}")
    def configuration_error(path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Application configuration error",
                "error": import_error,
                "required_env": [
                    "FSCHP_SECRET_KEY",
                    "FSCHP_ENV",
                    "FSCHP_COOKIE_SECURE",
                    "FSCHP_BOOTSTRAP_ADMIN_PASSWORD",
                ],
            },
        )
