from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

import psycopg

from database.postgres_schema import compile_postgres_schema
from database.setup_microfinance import (
    AS_OF_DATE,
    DATABASE_NAME,
    HERE,
    NOW_UTC,
    RANDOM_SEED,
    execute_sql_file,
    seed_loans_and_transactions,
    seed_members,
    seed_profile_updates,
    seed_proposals,
    seed_reference_data,
    verify_invariants,
)


POSTGRES_HOST = os.getenv("RAGDB_POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("RAGDB_POSTGRES_PORT", "55432"))
POSTGRES_USER = os.getenv("RAGDB_POSTGRES_USER", "ragdb")
POSTGRES_PASSWORD = os.getenv("RAGDB_POSTGRES_PASSWORD", "")


def connection(database: str = DATABASE_NAME, *, autocommit: bool = False):
    if not POSTGRES_PASSWORD:
        raise RuntimeError(
            "Set RAGDB_POSTGRES_PASSWORD to the POSTGRES_PASSWORD from docker/postgres.env before running this setup."
        )
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=database,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        autocommit=autocommit,
    )


def ensure_database() -> None:
    with connection("postgres", autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE_NAME,))
            if cursor.fetchone() is None:
                cursor.execute(f'CREATE DATABASE "{DATABASE_NAME}"')


def prepare_schema(reset: bool) -> None:
    ensure_database()
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
            populated = int(cursor.fetchone()[0]) > 0
            if populated and not reset:
                raise RuntimeError(
                    f"PostgreSQL database {DATABASE_NAME} already contains tables. Re-run with --reset to rebuild it."
                )
            if reset:
                cursor.execute("DROP SCHEMA public CASCADE")
                cursor.execute("CREATE SCHEMA public AUTHORIZATION CURRENT_USER")
        conn.commit()


def execute_script(cursor, sql: str) -> None:
    for statement in sql.split(";\n"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def setup(reset: bool = False) -> dict[str, int]:
    prepare_schema(reset)
    rng = random.Random(RANDOM_SEED)
    counts: dict[str, int] = {}
    with connection() as conn:
        with conn.cursor() as cursor:
            postgres_schema = compile_postgres_schema(HERE / "schema_v1.sql")
            execute_script(cursor, postgres_schema)
            cursor.execute(
                "INSERT INTO schema_metadata VALUES (1,%s,%s,%s,NULL,'SCHEMA_READY')",
                ("BRAC-inspired synthetic microfinance reporting demo", RANDOM_SEED, AS_OF_DATE),
            )
            refs = seed_reference_data(cursor, rng)
            members = seed_members(cursor, rng, refs)
            seed_profile_updates(cursor, rng, members, refs)
            approved = seed_proposals(cursor, rng, members, refs)
            counts = seed_loans_and_transactions(cursor, rng, approved, refs)
            execute_sql_file(cursor, HERE / "views_postgres_v1.sql")
            verify_invariants(cursor)
            cursor.execute(
                "UPDATE schema_metadata SET seeded_at_utc=%s, seed_status='COMPLETE' WHERE version_no=1",
                (NOW_UTC,),
            )
            for table in ["members", "member_enrollments", "loan_proposals", "loan_accounts"]:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                counts[table] = int(cursor.fetchone()[0])
        conn.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the deterministic microfinance dataset in Docker PostgreSQL.")
    parser.add_argument("--reset", action="store_true", help="Rebuild only the public schema in the demo PostgreSQL database.")
    args = parser.parse_args()
    counts = setup(reset=args.reset)
    print(f"Created PostgreSQL {DATABASE_NAME} through {AS_OF_DATE.isoformat()} with seed {RANDOM_SEED}.")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count:,}")


if __name__ == "__main__":
    main()
