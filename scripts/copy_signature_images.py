"""Copy signature PNGs into Azure as data URLs. Does not touch Supabase."""
import base64
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect

PUBLIC = "https://svbpruvplhfkbintcogy.supabase.co/storage/v1/object/public/trial-photos/"


def to_data_url(raw: bytes, content_type: str) -> str:
    return "data:" + content_type + ";base64," + base64.b64encode(raw).decode("ascii")


def main() -> None:
    with connect("qicc_production") as conn, conn.cursor() as cur:
        cur.execute("ALTER TABLE public.tr_signatures ADD COLUMN IF NOT EXISTS image_data text")
        conn.commit()
        cur.execute("SELECT id, storage_path FROM public.tr_signatures")
        rows = cur.fetchall()
        copied = 0
        for sig_id, path in rows:
            if not path:
                continue
            with urlopen(PUBLIC + path, timeout=60) as resp:
                raw = resp.read()
                ctype = resp.headers.get_content_type() or "image/png"
            data_url = to_data_url(raw, ctype)
            cur.execute(
                "UPDATE public.tr_signatures SET image_data = %s WHERE id = %s",
                (data_url, sig_id),
            )
            copied += 1
            print("copied", path, "bytes", len(raw))
        conn.commit()
        cur.execute("SELECT count(*) FROM public.tr_signatures WHERE image_data IS NOT NULL")
        print("signatures with image_data", cur.fetchone()[0], "copied this run", copied)


if __name__ == "__main__":
    main()
