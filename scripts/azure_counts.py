"""Print Azure public table/view counts. No secrets."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect


def dump(dbname: str) -> None:
    with connect(dbname) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, c.relkind,
                   (xpath('1', query_to_xml(format('SELECT count(*) AS c FROM public.%I', c.relname), false, true, '')))[1]::text
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v')
            ORDER BY c.relkind, c.relname
            """
        )
        # query_to_xml xpath is fragile; use count per table instead
    with connect(dbname) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v')
            ORDER BY c.relkind, c.relname
            """
        )
        rels = cur.fetchall()
        print("===", dbname, "===")
        for name, kind in rels:
            cur.execute(f'SELECT count(*) FROM public."{name}"')
            n = cur.fetchone()[0]
            print(("VIEW" if kind == "v" else "TBL"), name, n)


if __name__ == "__main__":
    dump("copper_traceability")
    dump("qicc_production")
