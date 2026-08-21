"""Create the Supabase public views on Azure. Does not delete or change Supabase."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_to_azure import connect

OPERATOR_VIEW = """
CREATE OR REPLACE VIEW public.operator_competency_summary AS
 SELECT o.id AS operator_id,
    o.full_name,
    count(g.id) AS graded_items,
    COALESCE(sum(g.grade), 0::bigint) AS total_score,
        CASE
            WHEN count(g.id) > 0 THEN round(COALESCE(sum(g.grade), 0::bigint)::numeric / (count(g.id) * 4)::numeric, 4)
            ELSE NULL::numeric
        END AS competency_ratio
   FROM operators o
     LEFT JOIN operator_skill_grades g ON g.operator_id = o.id
  GROUP BY o.id, o.full_name;
"""

TRIALS_VIEW = """
CREATE OR REPLACE VIEW public.tr_report_summary AS
 SELECT id,
    ref_no,
    trial_no,
    trial_ref,
    sort_key,
    title,
    template,
    status,
    area,
    form_no,
    trial_date,
    shift,
    machine_code,
    process,
    trial_material,
    supplier,
    batch_lot_no,
    conductor_size,
    job_order,
    sor_no,
    fg_code,
    drum_no,
    conclusion,
    prepared_by,
    prepared_by2,
    reviewed_by,
    comments_list,
    conclusion_list,
    source_file,
    jsonb_array_length(sections) AS section_count,
    ( SELECT count(*) AS count
           FROM tr_samples s
          WHERE s.report_id = r.id) AS sample_count,
    ( SELECT count(*) AS count
           FROM tr_photos p
          WHERE p.report_id = r.id) AS photo_count,
    ( SELECT count(*) AS count
           FROM tr_attachments a
          WHERE a.report_id = r.id) AS attachment_count,
    created_at,
    updated_at,
    approver_name,
    approver_email,
    submitted_by,
    submitted_at,
    approved_by,
    approved_at,
    sent_at,
    decision_note,
    approval_required
   FROM tr_reports r;
"""

MC_VIEW_PATH = Path(__file__).with_name("sql") / "mc_run_analysis.sql"


def apply(dbname: str, sql: str) -> None:
    with connect(dbname) as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()
    print("applied view on", dbname)


if __name__ == "__main__":
    mc_sql = MC_VIEW_PATH.read_text(encoding="utf-8")
    apply("copper_traceability", OPERATOR_VIEW)
    apply("copper_traceability", mc_sql)
    apply("qicc_production", TRIALS_VIEW)
    apply("qicc_production", mc_sql)
    with connect("copper_traceability") as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM mc_run_analysis")
        print("copper mc_run_analysis", cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM operator_competency_summary")
        print("copper operator_competency_summary", cur.fetchone()[0])
    with connect("qicc_production") as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM mc_run_analysis")
        print("qicc mc_run_analysis", cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM tr_report_summary")
        print("qicc tr_report_summary", cur.fetchone()[0])
