# Azure Deployment Plan

> **Status:** Approved / Executing

Generated: 2026-08-20

---

## 1. Project Overview

**Goal:** Move all QICC shop-floor apps off Netlify and Supabase onto Azure. Reuse the existing PostgreSQL Flexible Server `qjcc-db` in resource group `rg-qjcc-tools` (UAE North). Host the static HTML apps on Azure Static Web Apps, replace Supabase Auth with Entra ID, replace Supabase Storage with Blob Storage, and replace the `scan-report` edge function with Azure Functions.

**Path:** Modernize Existing (existing Postgres) + New Project (this repo for hosting, API, and infra)

**Source of truth until cutover:** Supabase projects `copper-traceability` and `qicc-production`; Netlify/Firebase front-ends stay live.

---

## 2. Requirements

| Attribute | Value |
|-----------|-------|
| Classification | Production |
| Scale | Small |
| Budget | Cost-Optimized |
| **Subscription** | Azure subscription 1 (`a4da890c-1786-43dd-9f38-bd0986083051`) |
| **Location** | UAE North (`uaenorth`) for Postgres; SWA is East US 2 |
| Azure account | `rbasco36@gmail.com` / Default Directory |
| Existing resource group | `rg-qicc-tools` |
| Existing database | `qicc-db` (PostgreSQL 17, Burstable B1ms, FQDN `qicc-db.postgres.database.azure.com`) |
| Existing SWA | `qicc-tools` Free — https://calm-meadow-07f7eb10f.7.azurestaticapps.net (placeholder until we deploy) |

---

## 3. Components Detected

| Component | Type | Technology | Path / source |
|-----------|------|------------|---------------|
| Production Dashboard | Frontend | Standalone HTML + supabase-js | production-performance-dashboard.netlify.app |
| Copper Traceability | Frontend | Standalone HTML + supabase-js | qicc-production.netlify.app |
| Production Trials | Frontend | Standalone HTML + supabase-js | production-trials.netlify.app |
| Raw Material Consumption | Frontend | Standalone HTML + supabase-js | material-consumption.netlify.app |
| Setup Time & Scrap | Frontend (inactive) | Standalone HTML | setuptime-scrap-routing.netlify.app |
| Machine Capacity | Frontend (inactive) | Standalone HTML | machine-capacity.netlify.app |
| Production Skill Matrix | Frontend | Firebase Hosting | qicc-production-skill-matrix.web.app |
| CCV Line Control | Frontend | Local HTML | ccv-line.html |
| Landing page catalog | Data | `suite_apps` table | copper-traceability |
| MES / traceability DB | Data | Postgres 17 + RLS | Supabase `copper-traceability` |
| Dashboard / trials DB | Data | Postgres 17 + RLS | Supabase `qicc-production` |
| Auth | Identity | Supabase Auth (9 users each) | Both Supabase projects |
| Trial photos / attachments | Files | Supabase Storage | qicc-production |
| scan-report | API | Supabase Edge Function | qicc-production |
| publish_prod_dashboard | API | Postgres RPC | qicc-production |

---

## 4. Recipe Selection

**Selected:** AZD (Bicep)

**Rationale:**
- Default Azure recipe for a new multi-service app (static front-end + Functions + storage)
- Postgres already exists — Bicep will **reference** `qjcc-db`, not recreate it
- Want reproducible `azd up` / `azd deploy` rather than one-off portal clicks
- No existing Terraform in this workspace

---

## 5. Architecture

**Stack:** App Service (Static Web Apps) + Serverless (Functions)

### Service Mapping

| Component | Azure Service | SKU |
|-----------|---------------|-----|
| Combined shop-floor site | Azure Static Web Apps | Free (dev) then Standard if custom domain / Entra needed |
| REST API + scan-report + publish RPC | Azure Functions | Flex Consumption (FC1) |
| Postgres API (replaces PostgREST / supabase-js) | Data API Builder on Functions or Container Apps | Consumption |
| Existing database | Azure Database for PostgreSQL Flexible Server `qjcc-db` | **Reuse existing — do not recreate** |
| Databases on that server | `copper_traceability`, `qicc_production` | Created on existing server |
| Trial photos / attachments | Azure Blob Storage | Standard LRS |
| Secrets (DB URL, publish passcode) | Azure Key Vault | Standard |
| Auth (Nexans emails) | Static Web Apps Easy Auth / Entra ID | Built-in |
| Logs / APM | Log Analytics + Application Insights | Pay-as-you-go |

### Supporting Services

| Service | Purpose |
|---------|---------|
| Log Analytics | Centralized logging |
| Application Insights | Monitoring |
| Key Vault | DB connection string, publish passcode |
| Managed Identity | Functions → Postgres / Blob / Key Vault |

### What we will not do

- Do not self-host Supabase on Azure
- Do not delete Netlify or pause Supabase until Azure is verified live
- Do not move to the QICC company tenant in this pass
- Do not recreate `qjcc-db`

---

## 6. Provisioning Limit Checklist

### Phase 1: Prepare Resource Inventory

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---------------|------------------|------------------------|-------------|-------|
| Microsoft.Web/staticSites | 1 | Pending az login | Pending az login | New SWA in `rg-qjcc-tools` |
| Microsoft.Web/sites (Function App FC1) | 1 | Pending az login | Pending az login | Flex Consumption |
| Microsoft.Storage/storageAccounts | 1 | Pending az login | Pending az login | Blobs + Functions deployment storage |
| Microsoft.KeyVault/vaults | 1 | Pending az login | Pending az login | Secrets |
| Microsoft.Insights/components | 1 | Pending az login | Pending az login | App Insights |
| Microsoft.OperationalInsights/workspaces | 1 | Pending az login | Pending az login | Log Analytics |
| Microsoft.DBforPostgreSQL/flexibleServers | 0 | 1 existing (`qjcc-db`) | n/a | Reuse — no new server |

### Phase 2: Fetch Quotas and Validate Capacity

**Status:** Blocked — Azure CLI is installed, but this machine is not logged in (`az account list` empty from MCP). Quota CLI cannot run until `az login` as `rbasco36@gmail.com` and the subscription ID is known.

**Fallback (public Azure service limits, UAE North, typical pay-as-you-go):**

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---------------|------------------|------------------------|-------------|-------|
| Microsoft.Web/staticSites | 1 | 1 | 100 SWA / subscription (Free: 10) | Official docs; will confirm with `az quota` after login |
| Microsoft.Web/sites | 1 | 1 | 10 App Service plans (Free) / region; FC1 is regional quota | Official docs — confirm after login |
| Microsoft.Storage/storageAccounts | 1 | 1+existing | 250 storage accounts / region | Official docs |
| Microsoft.KeyVault/vaults | 1 | 1 | 1000 vaults / subscription | Official docs |
| Microsoft.Insights/components | 1 | 1 | Soft limit, typically 100+ | Official docs |
| Microsoft.OperationalInsights/workspaces | 1 | 1 | 5000 / subscription | Official docs |
| Microsoft.DBforPostgreSQL/flexibleServers | 0 | 1 | n/a | Existing `qjcc-db` |

**Status:** ⚠️ Quota CLI not yet run. Public limits are far above 1 of each resource. Re-run azure-quotas after `az login`.

---

## 7. Execution Checklist

### Phase 1: Planning
- [x] Analyze workspace
- [x] Gather requirements
- [x] Confirm subscription ID with user (name known: personal Gmail / Default Directory)
- [x] Confirm location: UAE North
- [x] Prepare resource inventory
- [x] Capacity: 1 SWA + 1 Postgres already exist; remaining adds are well under public limits
- [x] Scan source platforms (Supabase + Netlify catalog)
- [x] Select recipe: AZD (Bicep)
- [x] Plan architecture
- [x] **User approved this plan**

### Phase 2: Execution
- [x] Research components
- [ ] Generate infrastructure (reference existing Postgres, do not recreate)
- [ ] Generate Functions + Data API
- [x] Combine HTML apps under one SWA
- [x] Dump/restore Supabase → `qicc-db` (`copper_traceability` + `qicc_production`; row counts match 2026-08-20)
- [ ] Update plan status to Ready for Validation

### Phase 3: Validation
- [ ] azure-validate
- [ ] Update status to Validated

### Phase 4: Deployment
- [ ] azure-deploy
- [ ] Verify endpoints
- [ ] Cut over `suite_apps` URLs
- [ ] Retire Netlify + Supabase only after verification

---

## 7. Validation Proof

| Check | Command Run | Result | Timestamp |
|-------|-------------|--------|-----------|
| | | | |

**Validated by:** —
**Validation timestamp:** —

---

## 8. Files to Generate

| File | Purpose | Status |
|------|---------|--------|
| `.azure/deployment-plan.md` | This plan | ✅ |
| `azure.yaml` | AZD configuration | ⏳ |
| `infra/main.bicep` | Infrastructure (SWA, Functions, Storage, Key Vault; reference Postgres) | ⏳ |
| `src/web/` | Combined static apps | ⏳ |
| `src/api/` | Azure Functions | ⏳ |
| `.gitignore` | Ignore `.netlify`, `.env`, secrets | ⏳ |

---

## 9. Next Steps

> Current: Hosting live on Azure SWA. Postgres copies are on `qicc-db`. Apps still read Supabase.

1. Replace supabase-js / Auth with Azure Postgres + Entra
2. Copy trial photos to Blob Storage
3. Port `scan-report` to Azure Functions
4. Set the production-dashboard publish passcode on Azure (`prod_dashboard_secrets` was not copied)
5. Retire Netlify sites and pause Supabase only after a few days of good data
