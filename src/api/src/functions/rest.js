const { app } = require("@azure/functions");
const { Pool } = require("pg");
const crypto = require("crypto");

const IDENT = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
const JSONB_TABLES = new Set([
  "coils", "draws", "strands", "armours", "leftovers", "leftovers_backup_20260803",
  "prodlogs", "mroverrides", "settings", "machine_handbook", "setup_routing",
]);
const TABLES = {
  copper: new Set([
    "suite_apps", "profiles", "coils", "draws", "strands", "armours", "leftovers",
    "leftovers_backup_20260803", "prodlogs", "mroverrides", "settings", "machines",
    "machine_handbook", "setup_routing", "machine_daily_oee", "machine_daily_downtime_events",
    "mc_items", "mc_products", "mc_runs", "mc_run_items", "mc_run_materials",
    "mc_thickness", "mc_nav_ledger", "mc_nav_snapshots", "mc_model", "mc_run_analysis",
    "ds_cables", "ds_stages", "ds_conductors", "ds_bom", "operator_competency_summary",
  ]),
  qicc: new Set([
    "prod_dashboard_live", "prod_oee_cmp_comments", "profiles", "tr_reports",
    "tr_photos", "tr_attachments", "tr_samples", "tr_options", "tr_signatures",
    "mc_items", "mc_products", "mc_runs", "mc_run_items", "mc_run_materials",
    "mc_thickness", "mc_nav_ledger", "mc_nav_snapshots", "mc_model", "mc_run_analysis",
    "ds_cables", "ds_stages", "ds_conductors", "ds_bom", "tr_report_summary",
    "sm_operators", "sm_mistakes", "sm_trainings", "sm_evals",
  ]),
};

const pools = {};

function envName(db) {
  if (db === "copper") return "COPPER_DATABASE_URL";
  if (db === "qicc") return "QICC_DATABASE_URL";
  return null;
}

function poolFor(db) {
  const key = envName(db);
  const url = key && process.env[key];
  if (!url) throw new Error(`Missing ${key}`);
  if (!pools[db]) {
    pools[db] = new Pool({
      connectionString: url,
      ssl: { rejectUnauthorized: true },
      max: 4,
    });
  }
  return pools[db];
}

function qIdent(name) {
  if (!IDENT.test(name)) throw new Error("Invalid identifier");
  return `"${name}"`;
}

function unwrapRows(table, rows) {
  if (!JSONB_TABLES.has(table)) return rows;
  return rows.map((row) => {
    if (row && row.data && typeof row.data === "object" && !Array.isArray(row.data)) {
      return Object.assign({}, row.data, { id: row.id != null ? row.id : row.data.id });
    }
    return row;
  });
}

function isWrappedJsonb(row) {
  if (!row || typeof row !== "object" || Array.isArray(row)) return false;
  const keys = Object.keys(row);
  return (
    row.data &&
    typeof row.data === "object" &&
    !Array.isArray(row.data) &&
    keys.every((k) => k === "id" || k === "data" || k === "updated_at")
  );
}

function wrapForWrite(table, rows) {
  if (!JSONB_TABLES.has(table)) return rows;
  return rows.map((row) => {
    if (isWrappedJsonb(row)) {
      return {
        id: row.id,
        data: row.data,
        updated_at: row.updated_at || new Date().toISOString(),
      };
    }
    if (row == null || row.id == null) {
      const err = new Error("jsonb row missing id");
      err.status = 400;
      throw err;
    }
    return {
      id: row.id,
      data: row,
      updated_at: row.updated_at || new Date().toISOString(),
    };
  });
}

function parseFilters(query) {
  const reserved = new Set(["select", "order", "limit", "offset", "on_conflict", "unwrap"]);
  const where = [];
  const params = [];
  for (const [key, raw] of query.entries()) {
    if (reserved.has(key) || !IDENT.test(key)) continue;
    const value = String(raw);
    const col = qIdent(key);
    if (value.startsWith("eq.")) {
      params.push(value.slice(3));
      where.push(`${col} = $${params.length}`);
    } else if (value.startsWith("neq.")) {
      params.push(value.slice(4));
      where.push(`${col} <> $${params.length}`);
    } else if (value.startsWith("in.(") && value.endsWith(")")) {
      const items = value.slice(4, -1).split(",").map((s) => s.trim()).filter(Boolean);
      if (items.length) {
        const ph = items.map((_, i) => `$${params.length + i + 1}`);
        params.push(...items);
        where.push(`${col} IN (${ph.join(", ")})`);
      }
    } else if (value === "is.null") {
      where.push(`${col} IS NULL`);
    } else if (value === "not.is.null") {
      where.push(`${col} IS NOT NULL`);
    }
  }
  return { where, params };
}

function parseOrder(raw) {
  if (!raw) return "";
  const parts = String(raw).split(",").map((p) => p.trim()).filter(Boolean);
  const sql = [];
  for (const part of parts) {
    const [col, dir] = part.split(".");
    if (!IDENT.test(col)) continue;
    sql.push(`${qIdent(col)} ${dir === "desc" ? "DESC" : "ASC"}`);
  }
  return sql.length ? ` ORDER BY ${sql.join(", ")}` : "";
}

function parseSelect(raw) {
  if (!raw || raw === "*") return "*";
  const cols = String(raw).split(",").map((c) => c.trim()).filter((c) => IDENT.test(c));
  return cols.length ? cols.map(qIdent).join(", ") : "*";
}

function json(status, body) {
  return {
    status,
    jsonBody: body,
    headers: { "Content-Type": "application/json" },
  };
}

function sitePin() {
  return String(process.env.SITE_PIN || "").trim();
}

function gateSecret() {
  return process.env.JWT_SECRET || sitePin() || "qicc-gate";
}

function safeEqual(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  if (x.length !== y.length) return false;
  return crypto.timingSafeEqual(x, y);
}

function makeGateToken() {
  const exp = String(Date.now() + 12 * 60 * 60 * 1000);
  const sig = crypto.createHmac("sha256", gateSecret()).update(exp).digest("hex");
  return exp + "." + sig;
}

function validGateToken(token) {
  if (!token || typeof token !== "string") return false;
  const parts = token.split(".");
  if (parts.length !== 2) return false;
  const exp = Number(parts[0]);
  if (!Number.isFinite(exp) || Date.now() > exp) return false;
  const sig = crypto.createHmac("sha256", gateSecret()).update(parts[0]).digest("hex");
  return safeEqual(sig, parts[1]);
}

function cookieValue(request, name) {
  try {
    if (request.cookies && typeof request.cookies.get === "function") {
      const parsed = request.cookies.get(name);
      if (parsed && parsed.value) return String(parsed.value);
      if (typeof parsed === "string" && parsed) return parsed;
    }
  } catch (e) { /* ignore */ }
  const raw = request.headers.get("cookie") || request.headers.get("Cookie") || "";
  for (const part of raw.split(";")) {
    const i = part.indexOf("=");
    if (i < 1) continue;
    if (part.slice(0, i).trim() === name) {
      try { return decodeURIComponent(part.slice(i + 1).trim()); }
      catch (err) { return part.slice(i + 1).trim(); }
    }
  }
  return "";
}

function requestToken(request) {
  const custom = request.headers.get("x-qicc-gate") || request.headers.get("X-Qicc-Gate") || "";
  if (custom) return custom.trim();
  const auth = request.headers.get("authorization") || request.headers.get("Authorization") || "";
  if (auth.toLowerCase().startsWith("bearer ")) return auth.slice(7).trim();
  return cookieValue(request, "qicc_gate");
}

function gateDenied(request) {
  if (!sitePin()) return null;
  if (validGateToken(requestToken(request))) return null;
  return json(401, { message: "PIN required" });
}

function gateCookie(token) {
  return {
    name: "qicc_gate",
    value: token,
    maxAge: 12 * 60 * 60,
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
    path: "/",
  };
}

app.http("health", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "health",
  handler: async () => json(200, {
    ok: true,
    copper: Boolean(process.env.COPPER_DATABASE_URL),
    qicc: Boolean(process.env.QICC_DATABASE_URL),
  }),
});

app.http("gate", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "gate",
  handler: async (request) => {
    if (!sitePin()) return json(200, { ok: true, open: true });
    if (validGateToken(requestToken(request))) return json(200, { ok: true });
    return json(401, { ok: false });
  },
});

app.http("unlock", {
  methods: ["POST"],
  authLevel: "anonymous",
  route: "unlock",
  handler: async (request) => {
    if (!sitePin()) return json(200, { ok: true, open: true });
    let body = {};
    try { body = await request.json(); } catch (e) { body = {}; }
    const entered = String((body && body.pin) || "").trim();
    const pinHash = crypto.createHash("sha256").update(entered).digest();
    const wantHash = crypto.createHash("sha256").update(sitePin()).digest();
    if (!crypto.timingSafeEqual(pinHash, wantHash)) return json(401, { message: "Wrong PIN" });
    const token = makeGateToken();
    return {
      status: 200,
      jsonBody: { ok: true, token },
      headers: { "Content-Type": "application/json" },
      cookies: [gateCookie(token)],
    };
  },
});

app.http("rest", {
  methods: ["GET", "POST", "PATCH", "DELETE"],
  authLevel: "anonymous",
  route: "{db}/{table}",
  handler: async (request, context) => {
    const blocked = gateDenied(request);
    if (blocked) return blocked;
    const db = String(request.params.db || "");
    const table = String(request.params.table || "");
    if (!TABLES[db] || !TABLES[db].has(table)) {
      return json(404, { message: "Unknown table" });
    }
    const VIEWS = new Set(["mc_run_analysis", "tr_report_summary", "operator_competency_summary"]);
    if (VIEWS.has(table) && request.method !== "GET") {
      return json(405, { message: "View is read-only" });
    }
    let client;
    try {
      const pool = poolFor(db);
      client = await pool.connect();
      const query = request.query;
      const { where, params } = parseFilters(query);
      const whereSql = where.length ? ` WHERE ${where.join(" AND ")}` : "";
      const rel = `public.${qIdent(table)}`;

      if (request.method === "GET") {
        const select = parseSelect(query.get("select"));
        const order = parseOrder(query.get("order"));
        const limit = Number(query.get("limit"));
        const offset = Number(query.get("offset"));
        let sql = `SELECT ${select} FROM ${rel}${whereSql}${order}`;
        if (Number.isFinite(limit) && limit > 0) {
          params.push(Math.min(limit, 20000));
          sql += ` LIMIT $${params.length}`;
        }
        if (Number.isFinite(offset) && offset > 0) {
          params.push(offset);
          sql += ` OFFSET $${params.length}`;
        }
        const result = await client.query(sql, params);
        const unwrap = query.get("unwrap") === "1" || JSONB_TABLES.has(table);
        return json(200, unwrap ? unwrapRows(table, result.rows) : result.rows);
      }

      if (request.method === "DELETE") {
        if (!where.length) return json(400, { message: "Refusing unfiltered delete" });
        await client.query(`DELETE FROM ${rel}${whereSql}`, params);
        return { status: 204 };
      }

      const body = await request.json();
      const incoming = Array.isArray(body) ? body : [body];
      if (!incoming.length) return json(400, { message: "Empty body" });
      const rows = wrapForWrite(table, incoming);

      if (request.method === "POST") {
        const cols = Object.keys(rows[0]).filter((c) => IDENT.test(c));
        if (!cols.length) return json(400, { message: "No columns" });
        const conflict = String(query.get("on_conflict") || "")
          .split(",")
          .map((s) => s.trim())
          .filter((c) => IDENT.test(c));
        const inserted = [];
        for (const row of rows) {
          const values = cols.map((c) => row[c]);
          const placeholders = cols.map((_, i) => `$${i + 1}`).join(", ");
          let sql = `INSERT INTO ${rel} (${cols.map(qIdent).join(", ")}) VALUES (${placeholders})`;
          if (conflict.length) {
            const updates = cols
              .filter((c) => !conflict.includes(c))
              .map((c) => `${qIdent(c)} = EXCLUDED.${qIdent(c)}`);
            if (updates.length) {
              sql += ` ON CONFLICT (${conflict.map(qIdent).join(", ")}) DO UPDATE SET ${updates.join(", ")}`;
            } else {
              sql += ` ON CONFLICT (${conflict.map(qIdent).join(", ")}) DO NOTHING`;
            }
          }
          sql += " RETURNING *";
          const result = await client.query(sql, values);
          if (result.rows[0]) inserted.push(result.rows[0]);
        }
        return json(201, unwrapRows(table, inserted));
      }

      if (request.method === "PATCH") {
        if (!where.length) return json(400, { message: "Refusing unfiltered update" });
        const patch = rows[0];
        const cols = Object.keys(patch).filter((c) => IDENT.test(c));
        const sets = cols.map((c, i) => `${qIdent(c)} = $${i + 1}`);
        const values = cols.map((c) => patch[c]).concat(params);
        const shifted = where.map((clause) => clause.replace(/\$(\d+)/g, (_, n) => `$${Number(n) + cols.length}`));
        const result = await client.query(
          `UPDATE ${rel} SET ${sets.join(", ")}${shifted.length ? ` WHERE ${shifted.join(" AND ")}` : ""} RETURNING *`,
          values,
        );
        return json(200, unwrapRows(table, result.rows));
      }

      return json(405, { message: "Method not allowed" });
    } catch (err) {
      if (err && err.status === 400) return json(400, { message: err.message || "Bad request" });
      context.error(err);
      return json(500, { message: "Query failed" });
    } finally {
      if (client) client.release();
    }
  },
});
