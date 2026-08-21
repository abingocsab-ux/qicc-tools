CREATE OR REPLACE VIEW public.mc_run_analysis AS
 WITH base AS (
         SELECT r.id,
            r.item_id,
            r.sheet_ref,
            r.line,
            r.started_at,
            r.stopped_at,
            r.phys_wip_open,
            r.phys_wip_close,
            r.wip_on_hold,
            r.rm_withdrawn,
            r.scrap_kg,
            r.nav_wip_open,
            r.nav_wip_close,
            r.nav_posted_kg,
            r.notes,
            r.data_quality_note,
            r.created_by,
            r.created_at,
            r.updated_at,
            r.record_type,
            r.machine,
            r.cores,
            r.scrap_start_m,
            r.scrap_joint_m,
            r.scrap_stop_m,
            r.good_metres,
            r.times_recorded,
            COALESCE(( SELECT sum(ri.bom_kg_per_km * ri.metres / 1000.0) AS sum
                   FROM mc_run_items ri
                  WHERE ri.run_id = r.id), 0::numeric) AS expected_kg,
            COALESCE(( SELECT sum(ri.metres) AS sum
                   FROM mc_run_items ri
                  WHERE ri.run_id = r.id), 0::numeric) AS total_metres,
            ( SELECT string_agg(DISTINCT ri.size, ' + '::text ORDER BY ri.size) AS string_agg
                   FROM mc_run_items ri
                  WHERE ri.run_id = r.id) AS sizes,
            ( SELECT count(*) AS count
                   FROM mc_run_items ri
                  WHERE ri.run_id = r.id) AS n_products,
            ( SELECT string_agg(DISTINCT ri.machine, ','::text ORDER BY ri.machine) AS string_agg
                   FROM mc_run_items ri
                  WHERE ri.run_id = r.id AND ri.machine IS NOT NULL) AS machines,
            ( SELECT avg(t.thk_ave) AS avg
                   FROM mc_thickness t
                  WHERE t.run_id = r.id) AS thk_actual_ave,
            ( SELECT count(*) AS count
                   FROM mc_thickness t
                  WHERE t.run_id = r.id) AS thk_n,
            ( SELECT avg(t.thk_ave) AS avg
                   FROM mc_thickness t
                  WHERE t.run_id = r.id AND t."position" = 'START'::text) AS thk_start_ave,
            ( SELECT avg(t.thk_ave) AS avg
                   FROM mc_thickness t
                  WHERE t.run_id = r.id AND t."position" = 'END'::text) AS thk_end_ave,
            ( SELECT avg(p.std_thk_nom) AS avg
                   FROM mc_run_items ri
                     JOIN mc_products p ON p.id = ri.product_id
                  WHERE ri.run_id = r.id) AS thk_std_nom,
            ( SELECT - sum(l.quantity)
                   FROM mc_nav_ledger l
                  WHERE l.run_id = r.id AND l.entry_type ~~* 'Consumption'::text) AS ledger_consumption_kg,
            ( SELECT sum(l.quantity) AS sum
                   FROM mc_nav_ledger l
                  WHERE l.run_id = r.id AND l.entry_type ~~* 'Transfer'::text) AS ledger_transfer_kg,
            ( SELECT max(l.scrap_qty) AS max
                   FROM mc_nav_ledger l
                  WHERE l.run_id = r.id) AS ledger_scrap_qty,
            lag(r.phys_wip_close) OVER (PARTITION BY r.item_id ORDER BY r.started_at) AS prev_phys_close,
            lag(r.nav_wip_close) OVER (PARTITION BY r.item_id ORDER BY r.started_at) AS prev_nav_close
           FROM mc_runs r
        ), calc AS (
         SELECT b.id,
            b.item_id,
            b.sheet_ref,
            b.line,
            b.started_at,
            b.stopped_at,
            b.phys_wip_open,
            b.phys_wip_close,
            b.wip_on_hold,
            b.rm_withdrawn,
            b.scrap_kg,
            b.nav_wip_open,
            b.nav_wip_close,
            b.nav_posted_kg,
            b.notes,
            b.data_quality_note,
            b.created_by,
            b.created_at,
            b.updated_at,
            b.record_type,
            b.machine,
            b.cores,
            b.scrap_start_m,
            b.scrap_joint_m,
            b.scrap_stop_m,
            b.good_metres,
            b.times_recorded,
            b.expected_kg,
            b.total_metres,
            b.sizes,
            b.n_products,
            b.machines,
            b.thk_actual_ave,
            b.thk_n,
            b.thk_start_ave,
            b.thk_end_ave,
            b.thk_std_nom,
            b.ledger_consumption_kg,
            b.ledger_transfer_kg,
            b.ledger_scrap_qty,
            b.prev_phys_close,
            b.prev_nav_close,
            b.phys_wip_open + b.rm_withdrawn AS material_available,
            b.phys_wip_open + b.rm_withdrawn - COALESCE(b.phys_wip_close, 0::numeric) - COALESCE(b.scrap_kg, 0::numeric) AS actual_kg,
            b.phys_wip_open + b.rm_withdrawn - COALESCE(b.phys_wip_close, 0::numeric) AS gross_out_kg,
            b.phys_wip_open - b.nav_wip_open AS sys_var_open,
            b.phys_wip_close - b.nav_wip_close AS sys_var_close,
                CASE
                    WHEN b.nav_wip_close IS NOT NULL AND b.nav_wip_open IS NOT NULL THEN b.nav_wip_open + b.rm_withdrawn - b.nav_wip_close
                    ELSE NULL::numeric
                END AS nav_implied_posted,
            b.phys_wip_open - b.prev_phys_close AS phys_chain_gap,
            b.nav_wip_open - b.prev_nav_close AS nav_chain_gap,
            EXTRACT(epoch FROM b.stopped_at - b.started_at) / 3600.0 AS run_hours,
            COALESCE(b.scrap_start_m, 0::numeric) + COALESCE(b.scrap_joint_m, 0::numeric) + COALESCE(b.scrap_stop_m, 0::numeric) AS core_scrap_m
           FROM base b
        )
 SELECT id,
    item_id,
    sheet_ref,
    line,
    started_at,
    stopped_at,
    phys_wip_open,
    phys_wip_close,
    wip_on_hold,
    rm_withdrawn,
    scrap_kg,
    nav_wip_open,
    nav_wip_close,
    nav_posted_kg,
    notes,
    data_quality_note,
    created_by,
    created_at,
    updated_at,
    record_type,
    machine,
    cores,
    scrap_start_m,
    scrap_joint_m,
    scrap_stop_m,
    good_metres,
    times_recorded,
    expected_kg,
    total_metres,
    sizes,
    n_products,
    machines,
    thk_actual_ave,
    thk_n,
    thk_start_ave,
    thk_end_ave,
    thk_std_nom,
    ledger_consumption_kg,
    ledger_transfer_kg,
    ledger_scrap_qty,
    prev_phys_close,
    prev_nav_close,
    material_available,
    actual_kg,
    gross_out_kg,
    sys_var_open,
    sys_var_close,
    nav_implied_posted,
    phys_chain_gap,
    nav_chain_gap,
    run_hours,
    core_scrap_m,
    expected_kg - actual_kg AS variance_kg,
        CASE
            WHEN expected_kg > 0::numeric THEN (expected_kg - actual_kg) / expected_kg * 100::numeric
            ELSE NULL::numeric
        END AS variance_pct,
        CASE
            WHEN nav_implied_posted IS NOT NULL THEN nav_implied_posted - (actual_kg + COALESCE(scrap_kg, 0::numeric))
            ELSE NULL::numeric
        END AS nav_posting_gap_kg,
        CASE
            WHEN ledger_consumption_kg IS NOT NULL THEN ledger_consumption_kg - (actual_kg + COALESCE(scrap_kg, 0::numeric))
            ELSE NULL::numeric
        END AS ledger_posting_gap_kg,
        CASE
            WHEN run_hours > 0::numeric AND times_recorded THEN total_metres / run_hours
            ELSE NULL::numeric
        END AS metres_per_hour,
        CASE
            WHEN actual_kg > 0::numeric THEN COALESCE(scrap_kg, 0::numeric) / actual_kg * 100::numeric
            ELSE NULL::numeric
        END AS scrap_pct,
        CASE
            WHEN thk_std_nom > 0::numeric AND thk_actual_ave IS NOT NULL THEN (thk_actual_ave / thk_std_nom - 1::numeric) * 100::numeric
            ELSE NULL::numeric
        END AS thickness_dev_pct,
        CASE
            WHEN thk_end_ave > 0::numeric AND thk_start_ave IS NOT NULL THEN (thk_start_ave / thk_end_ave - 1::numeric) * 100::numeric
            ELSE NULL::numeric
        END AS start_end_dev_pct,
        CASE
            WHEN (COALESCE(good_metres, 0::numeric) + core_scrap_m) > 0::numeric THEN core_scrap_m / (good_metres + core_scrap_m) * 100::numeric
            ELSE NULL::numeric
        END AS core_scrap_pct,
    scrap_kg IS NULL AS scrap_missing
   FROM calc c;
