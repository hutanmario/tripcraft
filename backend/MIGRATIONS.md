# Database migrations

TripCraft uses Alembic for schema changes. The application no longer runs
`ALTER TABLE` or `create_all()` at startup.

Run pending migrations from `tripcraft/backend`:

```bash
venv\Scripts\python.exe -m alembic upgrade head
```

Check the current database revision:

```bash
venv\Scripts\python.exe -m alembic current
```

Create a new migration after changing SQLAlchemy models:

```bash
venv\Scripts\python.exe -m alembic revision -m "short migration name"
```

Then edit the generated file in `alembic/versions/` and run `upgrade head`.
