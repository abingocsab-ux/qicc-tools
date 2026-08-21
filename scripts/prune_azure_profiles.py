"""Keep only the Gmail profile on Azure. Does not change Supabase auth.users."""
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect

KEEP_EMAIL = "rbasco36@gmail.com"


def prune(dbname: str) -> None:
    with connect(dbname) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM public.profiles WHERE lower(email) = %s", (KEEP_EMAIL,))
        keep = cur.fetchone()
        if not keep:
            raise SystemExit(f"{dbname}: keep email not found")
        keep_id = keep[0]
        cur.execute("UPDATE public.profiles SET role = 'editor' WHERE id = %s", (keep_id,))
        cur.execute("SELECT count(*) FROM public.profiles")
        before = cur.fetchone()[0]
        cur.execute(
            """
            SELECT conrelid::regclass::text AS tbl, a.attname AS col
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.contype = 'f' AND c.confrelid = 'public.profiles'::regclass
            """
        )
        fks = cur.fetchall()
        for tbl, col in fks:
            cur.execute("SAVEPOINT sp_fk")
            try:
                cur.execute(
                    f'UPDATE {tbl} SET "{col}" = NULL WHERE "{col}" IS NOT NULL AND "{col}" <> %s',
                    (keep_id,),
                )
            except psycopg.errors.IntegrityError:
                cur.execute("ROLLBACK TO SAVEPOINT sp_fk")
                cur.execute(
                    f'UPDATE {tbl} SET "{col}" = %s WHERE "{col}" IS NOT NULL AND "{col}" <> %s',
                    (keep_id, keep_id),
                )
            else:
                cur.execute("RELEASE SAVEPOINT sp_fk")
        cur.execute("DELETE FROM public.profiles WHERE id <> %s", (keep_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.execute("SELECT count(*) FROM public.profiles")
        after = cur.fetchone()[0]
        cur.execute("SELECT role FROM public.profiles WHERE id = %s", (keep_id,))
        role = cur.fetchone()[0]
        print(dbname, "profiles", before, "->", after, "deleted", deleted, "fks", len(fks), "keep_role", role)


if __name__ == "__main__":
    prune("copper_traceability")
    prune("qicc_production")
