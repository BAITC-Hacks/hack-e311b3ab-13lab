"""Create a user from the command line, e.g. the first administrator.

    python -m scripts.create_user --email admin@example.kz --name "Администратор" --role admin
"""

import argparse
import getpass
import sys

from app.config import Settings
from app.rbac import Role
from app.security import MIN_PASSWORD_LENGTH
from app.store import Store


def main():
    parser = argparse.ArgumentParser(description="Create a HATTAMA.AI user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True, choices=[role.value for role in Role])
    parser.add_argument("--password-stdin", action="store_true", help="read the password from standard input")
    args = parser.parse_args()
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Пароль: ")
        if password != getpass.getpass("Повторите пароль: "):
            raise SystemExit("Пароли не совпадают")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    store = Store(Settings.from_env())
    try:
        user = store.create_user(args.email, args.name, Role(args.role), password)
    except ValueError:
        raise SystemExit("Пользователь с таким email уже существует")
    store.audit("user_created", email=user["email"], role=user["role"], source="cli")
    print(f"Создан пользователь {user['email']} ({user['role']})")


if __name__ == "__main__":
    main()
