import argparse
import getpass
import os
import sqlite3
from pathlib import Path

import bcrypt


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "nenep.db"
ROLES = ("admin", "bangiamhieu", "quanly", "giamthi", "bantru")
GLOBAL_ROLES = {"admin", "bangiamhieu", "quanly"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update an application user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--folder", default="")
    parser.add_argument("--password", help="Omit to enter it securely.")
    parser.add_argument("--db-path", default=os.getenv("FSCHP_DB_PATH", str(DEFAULT_DB_PATH)))
    args = parser.parse_args()

    folder = args.folder or ("all" if args.role in GLOBAL_ROLES else args.role)
    if folder == "all" and args.role not in GLOBAL_ROLES:
        raise SystemExit("folder=all is only allowed for admin, bangiamhieu, or quanly roles")
    password = args.password or getpass.getpass("Password: ")
    password_hash = hash_password(password)

    conn = sqlite3.connect(args.db_path)
    cur = conn.cursor()
    existing = cur.execute("SELECT id FROM users WHERE username = ?", (args.username,)).fetchone()

    if existing:
        cur.execute(
            """
            UPDATE users
            SET password = ?, role = ?, display_name = ?, folder = ?, is_active = 1
            WHERE username = ?
            """,
            (password_hash, args.role, args.display_name, folder, args.username),
        )
    else:
        cur.execute(
            """
            INSERT INTO users (username, password, role, display_name, folder, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (args.username, password_hash, args.role, args.display_name, folder),
        )

    conn.commit()
    conn.close()
    print(f"User '{args.username}' saved with role '{args.role}'.")


if __name__ == "__main__":
    main()
