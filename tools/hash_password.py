import argparse
import getpass

import bcrypt


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a bcrypt hash for a password.")
    parser.add_argument("--password", help="Password to hash. Omit to enter it securely.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print(password_hash)


if __name__ == "__main__":
    main()
