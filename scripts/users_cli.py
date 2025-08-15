#!/usr/bin/env python3
# coding: UTF-8
"""
CLI tool for managing application users.
"""

import sys
import click
from datetime import datetime, timezone
from sqlmodel import Session, select
from rich.prompt import Prompt
from rich.console import Console
from rich.table import Table, box
from pathlib import Path

# Add parent directory to PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from core.dependency import hash_password, engine, get_user_by_email, get_user_by_username
from core.models import User

console = Console()


@click.group()
def cli() -> None:
    """User management CLI."""
    pass


@cli.command("create")
def create_user() -> None:
    """Create a new user."""
    with Session(engine) as session:
        email = Prompt.ask("Enter user email")
        if get_user_by_email(session, email):
            console.print("[red]User with this email already exists[/red]")
            return

        username = Prompt.ask("Enter username")
        if get_user_by_username(session, username):
            console.print("[red]User with this username already exists[/red]")
            return

        password = Prompt.ask("Provide password", password=True)
        hashed_password = hash_password(password)
        now = datetime.now(timezone.utc)

        try:
            user = User(username=username,
                        email=email,
                        hashed_password=hashed_password,
                        created_at=now,
                        updated_at=now)
            session.add(user)
            session.commit()
            console.print(
                f"[green]New user '{username}' successfully created[/green]")
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error creating user:[/red] {e}")


@cli.command("activate")
@click.option("-u",
              "--user",
              "username",
              required=True,
              help="Username of the user to activate")
def activate_user(username: str) -> None:
    """Activate an existing user by username."""
    with Session(engine) as session:
        user = get_user_by_username(session, username)
        if not user:
            console.print(
                f"[red]No user found with username '{username}'[/red]")
            return

        try:
            user.is_active = True
            user.updated_at = datetime.now(timezone.utc)
            session.commit()
            console.print(
                f"[green]User '{username}' has been activated[/green]")
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error activating user:[/red] {e}")


@cli.command("list")
def list_users() -> None:
    """List all users."""
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        if not users:
            console.print("[yellow]No users found[/yellow]")
            return

        table = Table(title="Rentory Users", box=box.SQUARE)
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Email")
        table.add_column("Active")
        table.add_column("Admin")

        for user in users:
            table.add_row(str(user.id), user.username, user.email,
                          str(user.is_active), str(user.is_superuser))
        console.print(table)


if __name__ == "__main__":
    cli()
