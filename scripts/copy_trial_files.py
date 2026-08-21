"""Copy trial photos and attachments from the Supabase public bucket into Azure."""
import base64
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect

PUBLIC = "https://svbpruvplhfkbintcogy.supabase.co/storage/v1/object/public/trial-photos/"


def to_data_url(raw: bytes, content_type: str) -> str:
    return "data:" + content_type + ";base64," + base64.b64encode(raw).decode("ascii")


def fetch_path(path: str) -> tuple[bytes, str]:
    req = Request(PUBLIC + path, method="GET")
    with urlopen(req, timeout=120) as resp:
        raw = resp.read()
        ctype = resp.headers.get_content_type() or "application/octet-stream"
        return raw, ctype


def copy_table(cur, table: str, id_col: str) -> tuple[int, int, int]:
    cur.execute(f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS file_data text")
    cur.execute(f"SELECT {id_col}, storage_path, length(file_data) FROM public.{table}")
    rows = cur.fetchall()
    copied = skipped = failed = 0
    total_bytes = 0
    for row_id, path, existing in rows:
        if existing and existing > 20:
            skipped += 1
            continue
        if not path:
            failed += 1
            continue
        try:
            raw, ctype = fetch_path(path)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            print("fail", table, path, type(exc).__name__)
            failed += 1
            continue
        data_url = to_data_url(raw, ctype)
        cur.execute(
            f"UPDATE public.{table} SET file_data = %s WHERE {id_col} = %s",
            (data_url, row_id),
        )
        copied += 1
        total_bytes += len(raw)
        print("copied", table, path, "bytes", len(raw))
    print(table, "copied", copied, "skipped", skipped, "failed", failed, "raw_bytes", total_bytes)
    return copied, skipped, failed


def main() -> None:
    with connect("qicc_production") as conn, conn.cursor() as cur:
        copy_table(cur, "tr_photos", "id")
        copy_table(cur, "tr_attachments", "id")
        conn.commit()
        cur.execute("SELECT count(*) FROM public.tr_photos WHERE file_data IS NOT NULL")
        print("photos_with_file_data", cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM public.tr_attachments WHERE file_data IS NOT NULL")
        print("attachments_with_file_data", cur.fetchone()[0])


if __name__ == "__main__":
    main()
