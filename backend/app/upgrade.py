"""Bring an existing database up to date with the current models.

`db.create_all()` creates missing tables but never changes tables that already exist.
When we add a column or a new status later, this function adds it to databases created
by an older version, so team members do not have to delete their data.
It is safe to run many times: it only changes what is missing.
"""
import logging

import sqlalchemy as sa

from .extensions import db
from .models import EXTRACTION_METHODS, FILE_STATUSES

log = logging.getLogger(__name__)

# Columns added after v0.1: (table, column, SQL type)
NEW_COLUMNS = [
    ("files", "deleted_at", "DATETIME NULL"),
    ("files", "deleted_from_path", "VARCHAR(500) NULL"),
    ("document_metadata", "folder_reason", "VARCHAR(300) NULL"),
]


def prepare_database() -> list[str]:
    """Make the database ready to use: create it (MySQL) if it doesn't exist yet, then its tables/columns."""
    create_mysql_database_if_missing()
    return upgrade_database()


def create_mysql_database_if_missing() -> None:
    url = sa.engine.make_url(db.engine.url)
    if not url.drivername.startswith("mysql") or not url.database:
        return
    # Connect to the server without choosing a database (url.set(database=None) would keep the name).
    server_url = sa.engine.URL.create(url.drivername, username=url.username, password=url.password,
                                      host=url.host, port=url.port, query=url.query)
    server = sa.create_engine(server_url)
    try:
        with server.connect() as conn:
            conn.execute(sa.text(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    finally:
        server.dispose()


def upgrade_database() -> list[str]:
    """Create missing tables/columns. Returns a list of the changes made."""
    db.create_all()
    changes = []
    inspector = sa.inspect(db.engine)
    with db.engine.begin() as conn:
        for table, column, sql_type in NEW_COLUMNS:
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
                changes.append(f"added {table}.{column}")

        # MySQL stores the allowed statuses in the column type, so add the new 'DELETED' status there too.
        if db.engine.dialect.name == "mysql":
            status = next(c for c in inspector.get_columns("files") if c["name"] == "status")
            if "DELETED" not in getattr(status["type"], "enums", []):
                values = ", ".join(f"'{s}'" for s in FILE_STATUSES)
                conn.execute(sa.text(f"ALTER TABLE files MODIFY COLUMN status ENUM({values}) NOT NULL DEFAULT 'UPLOADED'"))
                changes.append("added the DELETED file status")

            # ...and the 'OPENAI_VISION' extraction method (scans read by GPT when Tesseract isn't installed).
            method = next(c for c in inspector.get_columns("document_metadata") if c["name"] == "extraction_method")
            if "OPENAI_VISION" not in getattr(method["type"], "enums", []):
                values = ", ".join(f"'{m}'" for m in EXTRACTION_METHODS)
                conn.execute(sa.text(f"ALTER TABLE document_metadata MODIFY COLUMN extraction_method ENUM({values}) NULL"))
                changes.append("added the OPENAI_VISION extraction method")
    for change in changes:
        log.info("Database upgrade: %s", change)
    return changes
