"""Create Skill Matrix tables on existing qicc_production. Does not recreate qicc-db."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect

TABLES = ("sm_operators", "sm_mistakes", "sm_trainings", "sm_evals")

DDL = """
CREATE TABLE IF NOT EXISTS public.{table} (
  id text PRIMARY KEY,
  section text NOT NULL,
  payload jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS {table}_section_idx ON public.{table} (section);
COMMENT ON TABLE public.{table} IS 'QICC Production Skill Matrix shared store';
"""


def main() -> int:
    conn = connect("qicc_production")
    try:
        with conn.cursor() as cur:
            for table in TABLES:
                cur.execute(DDL.format(table=table))
            conn.commit()
            for table in TABLES:
                cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                print(f"qicc_production.{table}: {cur.fetchone()[0]} rows")
        print("SKILL MATRIX TABLES OK")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
