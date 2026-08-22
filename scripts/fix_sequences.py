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
        select table_name, column_name, column_default
        from information_schema.columns
        where table_schema = 'public' and column_default like 'nextval%%'
        order by 1, 2
        """
    )
    behind = []
    rows = []
    for table, col, default in cur.fetchall():
        match = SEQ_RE.search(default or "")
        if not match:
            rows.append((table, col, None, None, None, "parse-fail"))
            continue
        seq = match.group(1).split("::", 1)[0]
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
