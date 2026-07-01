# Security setup

## Required environment variables

Set these on the server before running the app:

```bash
FSCHP_SECRET_KEY=<long-random-secret-at-least-32-chars>
FSCHP_CORS_ORIGINS=https://your-domain.example
FSCHP_ENV=production
FSCHP_COOKIE_SECURE=true
```

Optional variables:

```bash
FSCHP_ACCESS_TOKEN_EXPIRE_MINUTES=60
FSCHP_DB_PATH=/secure/path/nenep.db
FSCHP_OVERRIDE_PASSWORD_HASH=<bcrypt-hash>
```

Generate the override password hash:

```bash
python tools/hash_password.py
```

## First admin account

For a brand-new database, either set bootstrap variables once:

```bash
FSCHP_BOOTSTRAP_ADMIN_USERNAME=<admin-username>
FSCHP_BOOTSTRAP_ADMIN_PASSWORD=<strong-password>
FSCHP_BOOTSTRAP_ADMIN_DISPLAY_NAME=Administrator
```

Or create/update users manually:

```bash
python tools/create_user.py --username <username> --role admin --display-name "Administrator"
python tools/create_user.py --username <username> --role bangiamhieu --display-name "Ban Giam Hieu" --folder all
```

## Deploy artifact

Build from an allowlist instead of zipping the whole working directory:

- `backend/app/`
- `backend/requirements.txt`
- `frontend/`
- `tools/` if you need admin utilities on the server
- `SECURITY.md` and `.env.example`

Exclude local runtime data such as `nenep.db`, `venv/`, `__pycache__/`, uploads, and Excel source files.

## Before pushing to GitHub

Do not commit:

- `.env` or any file containing real secrets.
- `nenep.db` or other SQLite databases.
- `venv/`, `__pycache__/`, local uploads, or Excel source files.

If any real secret was already committed, rotate it before deploying.
