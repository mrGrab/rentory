#!/usr/bin/env python3
# coding: UTF-8
"""
CLI tool for managing application users.
"""

import sys
import click
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session, select
from rich.prompt import Prompt
from rich.console import Console
from rich.table import Table, box
from pathlib import Path

# Add parent directory to PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))
from core.database import engine, create_user, get_user_by_username, get_user_by_email
from models.user import User, UserCreate

console = Console()


@click.group()
def cli() -> None:
    """User management CLI."""
    pass


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
        table.add_column("External")

        for user in users:
            table.add_row(str(user.id), user.username, user.email,
                          str(user.is_active), str(user.is_superuser),
                          str(user.is_external))
        console.print(table)


@cli.command("create")
def create_new_user() -> None:
    """Create a new user."""
    with Session(engine) as session:
        email = Prompt.ask("Enter user email")
        username = Prompt.ask("Enter username")
        if get_user_by_email(session, email) or get_user_by_username(
                session, username):
            console.print("[red]User already exists[/red]")
            return
        password = Prompt.ask("Provide password", password=True)

        try:
            user_in = UserCreate(username=username,
                                 email=email,
                                 password=password)
            create_user(session, user_in)
            console.print(
                f"[green]New user '{username}' successfully created[/green]")
        except Exception as e:
            console.print(f"[red]Error creating user:[/red] {e}")


@cli.command("activate")
@click.option("-u",
              "--user",
              "username",
              default=None,
              help="Username of the user to activate")
@click.option("-i",
              "--id",
              "user_id",
              default=None,
              help="Username of the user to activate")
def activate_user(username: str | None, user_id: UUID | None) -> None:
    """Activate an existing user by username."""
    if not username and not user_id:
        console.print("[red]Username or user id should be provided[/red]")

    with Session(engine) as session:

        try:

            if username:
                user = get_user_by_username(session, username)
            elif user_id:
                user = session.get(User, UUID(user_id))

            if not user:
                console.print(
                    f"[red]No user found with username '{username}'[/red]")
                return

            user.is_active = True
            user.updated_at = datetime.now(timezone.utc)
            session.commit()
            console.print(
                f"[green]User '{user.username}' has been activated[/green]")
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error activating user:[/red] {e}")


if __name__ == "__main__":
    cli()
