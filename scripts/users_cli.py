#!/usr/bin/env python3
# coding: UTF-8
"""
CLI tool for managing application users.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table, box
from sqlmodel import Session, select

# Add parent directory to PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from core.database import (
    create_user,
    engine,
    get_user_by_email,
    get_user_by_username,
    hash_password,
)
from models.user import User, UserCreate

console = Console()

ERR_ONE_IDENTIFIER = "[red]Provide exactly one: --user, --email, or --id[/red]"
ERR_USER_NOT_FOUND = "[red]User not found[/red]"


@click.group()
def cli() -> None:
    """User management CLI."""


def _find_user(
    session: Session,
    username: str | None,
    email: str | None,
    user_id: UUID | None,
) -> User | None:
    if user_id:
        return session.get(User, user_id)
    if username:
        return get_user_by_username(session, username)
    if email:
        return get_user_by_email(session, email)
    return None


def _touch(user: User) -> None:
    user.updated_at = datetime.now(UTC)


def _render_user(user: User) -> Table:
    table = Table(title=f"User: {user.username}", box=box.SQUARE)
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("ID", str(user.id))
    table.add_row("Username", user.username)
    table.add_row("Email", user.email)
    table.add_row("Avatar", user.avatar or "-")
    table.add_row("Active", str(user.is_active))
    table.add_row("Admin", str(user.is_superuser))
    table.add_row("External", str(user.is_external))
    table.add_row("Created", user.created_at.isoformat())
    table.add_row("Updated", user.updated_at.isoformat())
    return table


@cli.command("list")
@click.option(
    "--active",
    "is_active",
    flag_value=True,
    default=None,
    help="Show only active users",
)
@click.option(
    "--inactive", "is_active", flag_value=False, help="Show only inactive users"
)
@click.option(
    "--admin",
    "is_superuser",
    flag_value=True,
    default=None,
    help="Show only admin users",
)
@click.option(
    "--regular", "is_superuser", flag_value=False, help="Show only regular users"
)
@click.option(
    "--external",
    "is_external",
    flag_value=True,
    default=None,
    help="Show only external users",
)
@click.option(
    "--internal", "is_external", flag_value=False, help="Show only internal users"
)
def list_users(
    is_active: bool | None,
    is_superuser: bool | None,
    is_external: bool | None,
) -> None:
    """List all users."""
    with Session(engine) as session:
        stmt = select(User)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if is_superuser is not None:
            stmt = stmt.where(User.is_superuser == is_superuser)
        if is_external is not None:
            stmt = stmt.where(User.is_external == is_external)

        users = session.exec(stmt.order_by(User.username)).all()

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
            table.add_row(
                str(user.id),
                user.username,
                user.email,
                str(user.is_active),
                str(user.is_superuser),
                str(user.is_external),
            )
        console.print(table)


@cli.command("create")
def create_new_user() -> None:
    """Create a new user."""
    with Session(engine) as session:
        email = Prompt.ask("Enter user email").strip()
        username = Prompt.ask("Enter username").strip()
        avatar = Prompt.ask("Avatar URL (optional)", default="").strip() or None
        is_external = Confirm.ask("Is external user?", default=False)
        is_active = Confirm.ask("Activate immediately?", default=True)
        is_superuser = Confirm.ask("Grant admin rights?", default=False)

        if get_user_by_email(session, email):
            console.print(f"[red]Email '{email}' is already in use[/red]")
            return

        if get_user_by_username(session, username):
            console.print(f"[red]Username '{username}' is already in use[/red]")
            return

        password = Prompt.ask("Provide password", password=True)

        try:
            user_in = UserCreate(
                username=username,
                email=email,
                password=password,
                avatar=avatar,
                is_external=is_external,
            )
            user = create_user(session, user_in)
            user.is_active = is_active
            user.is_superuser = is_superuser
            _touch(user)
            session.add(user)
            session.commit()
            session.refresh(user)

            console.print(f"[green]New user '{username}' successfully created[/green]")
            console.print(_render_user(user))
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error creating user:[/red] {e}")


@cli.command("show")
@click.option("-u", "--user", "username", default=None, help="Username of the user")
@click.option("-e", "--email", "email", default=None, help="Email of the user")
@click.option("-i", "--id", "user_id", type=click.UUID, default=None, help="User ID")
def show_user(username: str | None, email: str | None, user_id: UUID | None) -> None:
    """Show user details by username, email, or id."""
    identifiers = [username, email, user_id]
    if sum(value is not None for value in identifiers) != 1:
        console.print(ERR_ONE_IDENTIFIER)
        return

    with Session(engine) as session:
        user = _find_user(session, username=username, email=email, user_id=user_id)
        if not user:
            console.print(ERR_USER_NOT_FOUND)
            return

        console.print(_render_user(user))


@cli.command("update")
@click.option(
    "-u", "--user", "username", default=None, help="Current username of the user"
)
@click.option("-e", "--email", "email", default=None, help="Current email of the user")
@click.option("-i", "--id", "user_id", type=click.UUID, default=None, help="User ID")
def update_user(
    username: str | None,
    email: str | None,
    user_id: UUID | None,
) -> None:
    """Update an existing user."""
    identifiers = [username, email, user_id]
    if sum(value is not None for value in identifiers) != 1:
        console.print(ERR_ONE_IDENTIFIER)
        return

    with Session(engine) as session:
        user = _find_user(session, username=username, email=email, user_id=user_id)
        if not user:
            console.print(ERR_USER_NOT_FOUND)
            return

        new_username = Prompt.ask("New username", default=user.username).strip()
        new_email = Prompt.ask("New email", default=user.email).strip()
        new_avatar = (
            Prompt.ask("New avatar URL", default=user.avatar or "").strip() or None
        )
        set_password = Confirm.ask("Change password?", default=False)
        new_password = None
        if set_password:
            new_password = Prompt.ask("New password", password=True)

        is_active = Confirm.ask("Should be active?", default=user.is_active)
        is_superuser = Confirm.ask("Should be admin?", default=user.is_superuser)
        is_external = Confirm.ask("Is external?", default=user.is_external)

        if new_username != user.username:
            existing = get_user_by_username(session, new_username)
            if existing and existing.id != user.id:
                console.print(f"[red]Username '{new_username}' is already in use[/red]")
                return

        if new_email != user.email:
            existing = get_user_by_email(session, new_email)
            if existing and existing.id != user.id:
                console.print(f"[red]Email '{new_email}' is already in use[/red]")
                return

        try:
            user.username = new_username
            user.email = new_email
            user.avatar = new_avatar
            user.is_active = is_active
            user.is_superuser = is_superuser
            user.is_external = is_external
            if new_password:
                user.hashed_password = hash_password(new_password)
            _touch(user)

            session.add(user)
            session.commit()
            session.refresh(user)
            console.print(f"[green]User '{user.username}' updated[/green]")
            console.print(_render_user(user))
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error updating user:[/red] {e}")


@cli.command("activate")
@click.option(
    "-u", "--user", "username", default=None, help="Username of the user to activate"
)
@click.option(
    "-e", "--email", "email", default=None, help="Email of the user to activate"
)
@click.option(
    "-i",
    "--id",
    "user_id",
    type=click.UUID,
    default=None,
    help="ID of the user to activate",
)
def activate_user(
    username: str | None,
    email: str | None,
    user_id: UUID | None,
) -> None:
    """Activate an existing user."""
    identifiers = [username, email, user_id]
    if sum(value is not None for value in identifiers) != 1:
        console.print(ERR_ONE_IDENTIFIER)
        return

    with Session(engine) as session:
        try:
            user = _find_user(session, username=username, email=email, user_id=user_id)

            if not user:
                console.print(ERR_USER_NOT_FOUND)
                return

            user.is_active = True
            _touch(user)
            session.commit()
            console.print(f"[green]User '{user.username}' has been activated[/green]")
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error activating user:[/red] {e}")


@cli.command("deactivate")
@click.option(
    "-u", "--user", "username", default=None, help="Username of the user to deactivate"
)
@click.option(
    "-e", "--email", "email", default=None, help="Email of the user to deactivate"
)
@click.option(
    "-i",
    "--id",
    "user_id",
    type=click.UUID,
    default=None,
    help="ID of the user to deactivate",
)
def deactivate_user(
    username: str | None,
    email: str | None,
    user_id: UUID | None,
) -> None:
    """Deactivate an existing user."""
    identifiers = [username, email, user_id]
    if sum(value is not None for value in identifiers) != 1:
        console.print(ERR_ONE_IDENTIFIER)
        return

    with Session(engine) as session:
        try:
            user = _find_user(session, username=username, email=email, user_id=user_id)
            if not user:
                console.print(ERR_USER_NOT_FOUND)
                return

            user.is_active = False
            _touch(user)
            session.commit()
            console.print(f"[green]User '{user.username}' has been deactivated[/green]")
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error deactivating user:[/red] {e}")


@cli.command("delete")
@click.option(
    "-u", "--user", "username", default=None, help="Username of the user to delete"
)
@click.option(
    "-e", "--email", "email", default=None, help="Email of the user to delete"
)
@click.option(
    "-i",
    "--id",
    "user_id",
    type=click.UUID,
    default=None,
    help="ID of the user to delete",
)
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def delete_user(
    username: str | None,
    email: str | None,
    user_id: UUID | None,
    yes: bool,
) -> None:
    """Delete a user permanently."""
    identifiers = [username, email, user_id]
    if sum(value is not None for value in identifiers) != 1:
        console.print(ERR_ONE_IDENTIFIER)
        return

    with Session(engine) as session:
        try:
            user = _find_user(session, username=username, email=email, user_id=user_id)
            if not user:
                console.print(ERR_USER_NOT_FOUND)
                return

            if not yes and not Confirm.ask(
                f"Delete user '{user.username}' ({user.email})?", default=False
            ):
                console.print("[yellow]Cancelled[/yellow]")
                return

            session.delete(user)
            session.commit()
            console.print(f"[green]User '{user.username}' deleted[/green]")
        except Exception as e:
            session.rollback()
            console.print(f"[red]Error deleting user:[/red] {e}")


if __name__ == "__main__":
    cli()
