"""Copy dumped Supabase public tables onto Azure PostgreSQL qicc-db."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg
from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_mcp_json import extract_payload, unwrap_dump

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path.home() / ".cursor/projects/c-Users-rbasc-OneDrive-Nexans-Apps-qjcc-tools/agent-tools"
HOST = "qicc-db.postgres.database.azure.com"
USER = "qiccadmin"
AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
SKIP_TABLES = {"prod_dashboard_secrets"}

COPPER_DUMPS = [
    ("14b76085-39f3-4bc6-b853-323238165cc4.txt", "object"),
    ("c8ed739a-3759-448e-a3e8-3b030aa28eda.txt", "object"),
    ("3d035d58-4af2-48d1-897d-d9ce61c6aecc.txt", "rows:mc_thickness"),
    ("71aeb279-a306-4ead-869f-5a2b6862e650.txt", "rows:machine_daily_oee"),
    ("64e71c52-6fc5-4fa2-8728-7b6e40994d73.txt", "rows:machine_daily_oee"),
    ("ec28fc36-82f5-4d25-958d-de21aeb5bafe.txt", "rows:machine_daily_oee"),
    ("f78d29d0-b75a-42c8-af11-1698b29b3102.txt", "rows:mc_nav_ledger"),
    ("25ca605f-dc9a-48e7-ba17-0b6efca2e18c.txt", "rows:machine_daily_downtime_events"),
    ("e3f58b7e-bd4f-466f-bc77-f9c0b284f5da.txt", "rows:machine_daily_downtime_events"),
    ("1016e5aa-9f9d-4d28-a923-2b32bace46b9.txt", "rows:machine_daily_downtime_events"),
    ("0b582e0e-5c1e-495d-8f77-9df9d4c03ea1.txt", "rows:machine_daily_downtime_events"),
]
QICC_DUMPS = [
    ("876fa2e8-849c-4405-a0bf-0c5264757625.txt", "object"),
    ("ecba63ec-aa76-4563-9356-046dab584c56.txt", "rows:mc_nav_ledger"),
]

COPPER_EXPECTED = {
    "armours": 10, "bleed_scrap_daily": 0, "bleed_scrap_reason_events": 0, "change_types": 11,
    "coils": 325, "cu_al_tonnage_daily": 0, "daily_scrap_summary": 0, "downtime_categories": 17,
    "draws": 442, "ds_bom": 29, "ds_cables": 9, "ds_conductors": 9, "ds_stages": 70,
    "job_order_audit_log": 0, "job_order_process_steps": 0, "job_orders": 0, "leftovers": 70,
    "leftovers_backup_20260803": 2, "machine_daily_downtime_events": 8492, "machine_daily_oee": 6227,
    "machine_handbook": 1, "machines": 36, "materials": 13, "mc_items": 10, "mc_model": 9,
    "mc_nav_ledger": 2387, "mc_nav_snapshots": 5, "mc_products": 74, "mc_run_items": 98,
    "mc_run_materials": 8, "mc_runs": 49, "mc_thickness": 619, "monthly_tonnage_targets": 0,
    "mroverrides": 14, "operator_development_plans": 0, "operator_deviations": 0,
    "operator_skill_grades": 0, "operators": 0, "process_types": 16, "prodlogs": 1,
    "production_runs": 0, "profiles": 9, "rework_events": 0, "scrap_events": 0, "settings": 1,
    "setup_routing": 1, "shifts": 3, "strands": 93, "suite_apps": 8, "supervisor_assessments": 0,
}
QICC_EXPECTED = {
    "ds_bom": 29, "ds_cables": 9, "ds_conductors": 9, "ds_stages": 70, "mc_items": 6,
    "mc_model": 5, "mc_nav_ledger": 2109, "mc_nav_snapshots": 5, "mc_products": 38,
    "mc_run_items": 44, "mc_run_materials": 6, "mc_runs": 33, "mc_thickness": 391,
    "prod_dashboard_live": 1, "prod_dashboard_secrets": 0, "prod_oee_cmp_comments": 13,
    "profiles": 9, "tr_attachments": 46, "tr_options": 31, "tr_photos": 8, "tr_reports": 70,
    "tr_samples": 0, "tr_signatures": 3,
}


@lru_cache(maxsize=1)
def azure_password() -> str:
    env = os.environ.get("AZURE_PG_PASSWORD")
    if env:
        return env
    raw = subprocess.check_output(
        [
            AZ, "staticwebapp", "appsettings", "list",
            "-g", "rg-qicc-tools", "-n", "qicc-production",
            "--query", "properties.DATABASE_URL", "-o", "tsv",
        ],
        text=True,
    ).strip()
    parsed = urlparse(raw)
    if not parsed.password:
        raise SystemExit("could not read Azure DB password from existing SWA setting")
    return unquote(parsed.password)


def connect(dbname: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, dbname=dbname, user=USER, password=azure_password(),
        sslmode="require", connect_timeout=30,
    )


def load_schema(name: str) -> dict:
    return json.loads((ROOT / "scripts" / name).read_text(encoding="utf-8"))


def nextval_sequences(schema: dict) -> set[str]:
    found: set[str] = set()
    for cols in schema["tables"].values():
        for seq in re.findall(r"nextval\('([^']+)'", cols):
            found.add(seq.split("::", 1)[0])
    return found


def add_constraint(cur, item: dict) -> None:
    table = item["table_name"].split(".")[-1]
    cur.execute("SAVEPOINT sp_con")
    try:
        cur.execute(
            f'ALTER TABLE public."{table}" ADD CONSTRAINT "{item["conname"]}" {item["def"]}'
        )
    except psycopg.errors.DuplicateObject:
        cur.execute("ROLLBACK TO SAVEPOINT sp_con")
    except psycopg.errors.DuplicateTable:
        cur.execute("ROLLBACK TO SAVEPOINT sp_con")
    else:
        cur.execute("RELEASE SAVEPOINT sp_con")


def create_schema(conn: psycopg.Connection, schema: dict, fks: bool) -> None:
    with conn.cursor() as cur:
        if not fks:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            for seq in sorted(nextval_sequences(schema)):
                cur.execute(f'CREATE SEQUENCE IF NOT EXISTS public."{seq}";')
            for table, cols in schema["tables"].items():
                cols = cols.replace("GENERATED ALWAYS AS IDENTITY", "GENERATED BY DEFAULT AS IDENTITY")
                cols = re.sub(r"\s*DEFAULT\s+\(?auth\.uid\(\)\)?", "", cols)
                cur.execute(f'CREATE TABLE IF NOT EXISTS public."{table}" ({cols});')
            for item in schema["constraints"]:
                if item["contype"] == "f":
                    continue
                add_constraint(cur, item)
        else:
            for item in schema["constraints"]:
                if item["contype"] != "f":
                    continue
                if "auth.users" in item["def"]:
                    continue
                add_constraint(cur, item)
            for idx in schema.get("indexes", []):
                idx_sql = idx.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
                cur.execute("SAVEPOINT sp_idx")
                try:
                    cur.execute(idx_sql)
                except (psycopg.errors.DuplicateTable, psycopg.errors.DuplicateObject):
                    cur.execute("ROLLBACK TO SAVEPOINT sp_idx")
                else:
                    cur.execute("RELEASE SAVEPOINT sp_idx")
    conn.commit()


def column_types(conn: psycopg.Connection, table: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname, t.typname
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_type t ON t.oid = a.atttypid
            WHERE n.nspname = 'public' AND c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
            """,
            (table,),
        )
        return {name: typ for name, typ in cur.fetchall()}


def adapt(value, typ: str):
    if value is None:
        return None
    if typ == "jsonb":
        return Jsonb(value)
    return value


def insert_rows(conn: psycopg.Connection, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    types = column_types(conn, table)
    cols = [c for c in rows[0].keys() if c in types]
    col_sql = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = (
        f'INSERT INTO public."{table}" ({col_sql}) OVERRIDING SYSTEM VALUE '
        f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    )
    data = [tuple(adapt(row.get(c), types[c]) for c in cols) for row in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, data)
    conn.commit()
    return len(rows)


def reset_sequences(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, a.attname,
                   pg_get_serial_sequence(format('%I.%I', n.nspname, c.relname), a.attname)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = 'public' AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
            """
        )
        for table, col, seq in cur.fetchall():
            if not seq:
                continue
            cur.execute(
                f'SELECT COALESCE(MAX("{col}"), 1) FROM public."{table}"'
            )
            max_id = cur.fetchone()[0]
            cur.execute("SELECT setval(%s, %s, true)", (seq, int(max_id)))
    conn.commit()


def merge_dumps(files: list[tuple[str, str]]) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for name, kind in files:
        payload = unwrap_dump(extract_payload(TOOLS / name))
        if kind == "object":
            for table, rows in payload.items():
                if table in SKIP_TABLES:
                    continue
                out[table].extend(rows or [])
        elif kind.startswith("rows:"):
            table = kind.split(":", 1)[1]
            if table in SKIP_TABLES:
                continue
            out[table].extend(payload or [])
        else:
            raise SystemExit(kind)
    return out


def copy_one(dbname: str, schema_file: str, dumps: list[tuple[str, str]], expected: dict[str, int]) -> list[str]:
    schema = load_schema(schema_file)
    data = merge_dumps(dumps)
    conn = connect(dbname)
    try:
        create_schema(conn, schema, fks=False)
        loaded = {}
        for table, rows in sorted(data.items()):
            print(f"{dbname}.{table}: inserting {len(rows)} dump rows", flush=True)
            loaded[table] = insert_rows(conn, table, rows)
        create_schema(conn, schema, fks=True)
        reset_sequences(conn)
        mismatches = []
        with conn.cursor() as cur:
            for table, want in sorted(expected.items()):
                cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                got = cur.fetchone()[0]
                status = "OK" if got == want else "MISMATCH"
                print(f"{status} {dbname}.{table}: azure={got} source={want} dump={loaded.get(table, 0)}")
                if got != want:
                    mismatches.append(f"{dbname}.{table}: azure={got} source={want} dump={loaded.get(table, 0)}")
        return mismatches
    finally:
        conn.close()


def main() -> int:
    copper = copy_one("copper_traceability", "schema_copper.json", COPPER_DUMPS, COPPER_EXPECTED)
    qicc = copy_one("qicc_production", "schema_qicc.json", QICC_DUMPS, QICC_EXPECTED)
    problems = copper + qicc
    if problems:
        print("COUNT MISMATCHES")
        for line in problems:
            print(line)
        return 1
    print("COPY OK")
    print(f"copper_traceability tables checked: {len(COPPER_EXPECTED)}")
    print(f"qicc_production tables checked: {len(QICC_EXPECTED)}")
    print("Skipped prod_dashboard_secrets (publish passcode). Set the same passcode on Azure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
