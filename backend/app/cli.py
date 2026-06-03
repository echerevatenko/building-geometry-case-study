import typer

cli = typer.Typer(pretty_exceptions_enable=False)


def _load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv()


def _migrations_dir() -> str:
    """Absolute path to the migrations directory (backend/migrations).

    Resolved relative to this file so it works regardless of the cwd.
    """
    import pathlib

    return str(pathlib.Path(__file__).resolve().parent.parent / "migrations")


def _yoyo_uri() -> str:
    """Build a yoyo connection URI from APP_DATABASE_URL (loaded from .env).

    APP_DATABASE_URL is a libpq URI (``postgresql://``), but yoyo maps that
    scheme onto its psycopg2 backend. We use psycopg 3, so rewrite the scheme
    to ``postgresql+psycopg://`` which selects yoyo's psycopg-3 backend.
    """
    from app.config import Config

    url = Config().database_url
    for scheme in ("postgresql://", "postgres://"):
        if url.startswith(scheme):
            return "postgresql+psycopg://" + url[len(scheme) :]
    return url


@cli.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    _load_env()
    uvicorn.run("app.server:local_factory", factory=True, host=host, port=port, reload=reload)


@cli.command()
def generate_openapi(
    output: str = typer.Option("docs/openapi.json", help="Output path"),
) -> None:
    """Generate OpenAPI schema to file."""
    import json
    import pathlib

    _load_env()
    from app.server import local_factory

    app = local_factory()
    schema = app.openapi()
    path = pathlib.Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2))
    typer.echo(f"OpenAPI schema written to {output}")


migrate_app = typer.Typer(help="Database migrations (yoyo, raw SQL in ./migrations).")
cli.add_typer(migrate_app, name="migrate")


@migrate_app.command("apply")
def migrate_apply() -> None:
    """Apply all pending migrations."""
    from yoyo import get_backend, read_migrations

    _load_env()
    backend = get_backend(_yoyo_uri())
    migrations = read_migrations(_migrations_dir())
    with backend.lock():
        pending = backend.to_apply(migrations)
        if not pending:
            typer.echo("No pending migrations.")
            return
        backend.apply_migrations(pending)
        typer.echo(f"Applied {len(pending)} migration(s): {', '.join(m.id for m in pending)}")


@migrate_app.command("rollback")
def migrate_rollback(
    count: int = typer.Option(1, help="How many migrations to roll back, most recent first (0 = all)."),
) -> None:
    """Roll back applied migrations (uses the .rollback.sql files)."""
    from yoyo import get_backend, read_migrations

    _load_env()
    backend = get_backend(_yoyo_uri())
    migrations = read_migrations(_migrations_dir())
    with backend.lock():
        applied = backend.to_rollback(migrations)  # most-recent-first
        target = applied if count == 0 else applied[:count]
        if not target:
            typer.echo("Nothing to roll back.")
            return
        backend.rollback_migrations(target)
        typer.echo(f"Rolled back {len(target)} migration(s): {', '.join(m.id for m in target)}")


@migrate_app.command("list")
def migrate_list() -> None:
    """Show each migration and whether it has been applied."""
    from yoyo import get_backend, read_migrations

    _load_env()
    backend = get_backend(_yoyo_uri())
    migrations = read_migrations(_migrations_dir())
    with backend.lock():
        pending = {m.id for m in backend.to_apply(migrations)}
    for m in migrations:
        status = "pending" if m.id in pending else "applied"
        typer.echo(f"[{status}] {m.id}")


if __name__ == "__main__":
    cli()
