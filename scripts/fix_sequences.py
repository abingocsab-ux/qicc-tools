"""Advance Azure sequences that lagged behind copied row IDs."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect

SEQ_RE = re.compile(r"nextval\('([^']+)'")


def list_behind(cur):
    cur.execute(
        """
        select c.relname as table_name, a.attname as column_name,
               pg_get_expr(d.adbin, d.adrelid) as column_default,
               pg_get_serial_sequence(n.nspname||'.'||c.relname, a.attname) as seqreg
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
        left join pg_attrdef d on d.adrelid = c.oid and d.adnum = a.attnum
        where n.nspname = 'public'
          and (
            (d.adbin is not null and pg_get_expr(d.adbin, d.adrelid) like 'nextval%%')
            or a.attidentity <> ''
          )
        order by 1, 2
        """
    )
    behind = []
    rows = []
    for table, col, default, seqreg in cur.fetchall():
        seq = None
        if seqreg:
            seq = seqreg.split(".")[-1] if "." in seqreg else seqreg
        elif default:
            match = SEQ_RE.search(default)
            if match:
                seq = match.group(1).split("::", 1)[0]
        if not seq:
            rows.append((table, col, None, None, None, "parse-fail"))
            continue
        cur.execute(f"select last_value, is_called from {seq}")
        last, called = cur.fetchone()
        cur.execute(f'select coalesce(max("{col}"), 0) from public."{table}"')
        mx = int(cur.fetchone()[0])
        nxt = last + 1 if called else last
        status = "BEHIND" if nxt <= mx else "ok"
        rows.append((table, col, seq, nxt, mx, status))
        if status == "BEHIND":
            behind.append((table, col, seq, mx))
    return rows, behind


def main() -> None:
    apply = "--apply" in sys.argv
    for db in ("copper_traceability", "qicc_production"):
        conn = connect(db)
        cur = conn.cursor()
        rows, behind = list_behind(cur)
        print(f"=== {db}")
        for table, col, seq, nxt, mx, status in rows:
            print(f"  {table}.{col} {seq} next={nxt} max={mx} {status}")
        if apply:
            for table, col, seq, mx in behind:
                cur.execute("select setval(%s, %s, true)", (seq, mx))
                print(f"  setval {seq} -> {mx}")
            conn.commit()
            _, behind_after = list_behind(cur)
            print("behind_after", len(behind_after))
        else:
            print("behind_count", len(behind), "(dry run)")
        conn.close()


if __name__ == "__main__":
    main()
