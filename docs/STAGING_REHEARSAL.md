# Staging Migration Rehearsal Runbook (STAGING_REHEARSAL.md) — Bharat FoodSafe

**App Name:** Bharat FoodSafe
**Specification Reference:** [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) Phase 6, Step 6.1
**Document Status:** Operational Runbook Specification
**Database Engine:** PostgreSQL 18.0
**Migration Framework:** Alembic 1.14.0 + SQLAlchemy 2.0.36 + Psycopg 3.x

---

> [!NOTE]
> **Specification & Documentation Status:**
> This document specifies the operational procedure and verification protocol for executing a staging migration rehearsal. In accordance with task and release safety constraints, **no database operations, migrations, seeds, or deletions were performed during the authoring or review of this runbook**. The actual migration rehearsal must be executed on isolated staging infrastructure prior to production deployment.

---

## 1. Overview & Purpose

This runbook defines the repeatable, non-destructive Standard Operating Procedure (SOP) for executing and verifying database schema migrations on a dedicated staging database prior to applying schema changes to production.

Completing this rehearsal satisfies the **Database Migration Rehearsal** release gate requirement specified in [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md), Section 7 (Step 6.1):
> `[ ] Database Migration Rehearsal: alembic upgrade head executed against clean staging DB without error.`

---

## 2. Safety Principles & Guardrails

To prevent data loss, corruption, or unintended modifications across environments, operators must strictly adhere to the following guardrails:

1. **Strict Environment Isolation:** Rehearsals must **NEVER** run against the developer's local active database (`bharat_foodsafe`) or the production database. Rehearsals must target a dedicated, disposable database instance: `bharat_foodsafe_staging`.
2. **Credential Safety:** Connection strings and passwords must never be committed to source code or version-controlled files. All database connection details must be passed via ephemeral environment variables in the active terminal session.
3. **Mandatory Pre-Flight Target Checks:** Operators must verify the active database name (`SELECT current_database();`) immediately before executing migrations, rollbacks, seeds, or database deletion. If the active database is anything other than `bharat_foodsafe_staging`, execution must be halted immediately.
4. **Destructive Command Containment:** Database rollbacks (`alembic downgrade`) and database deletions (`DROP DATABASE`) are strictly destructive and irreversible. They must only ever be executed against an explicitly confirmed `bharat_foodsafe_staging` instance.
5. **Zero Mod-Lock Conflict:** No application source code, existing migration revisions, seeds, or locked project specifications may be altered during a staging rehearsal.

---

## 3. Database Architecture & Alembic Configuration

The Bharat FoodSafe backend dynamically configures Alembic from application settings:

- **Alembic Configuration File:** [`backend/alembic.ini`](file:///c:/Users/Victus/Desktop/Technologies/MCA_Project/Foodsafe/backend/alembic.ini)
- **Environment Bootstrapper:** [`backend/migrations/env.py`](file:///c:/Users/Victus/Desktop/Technologies/MCA_Project/Foodsafe/backend/migrations/env.py)
- **Settings Loader:** [`backend/app/core/config.py`](file:///c:/Users/Victus/Desktop/Technologies/MCA_Project/Foodsafe/backend/app/core/config.py)
- **Connection Driver:** `postgresql+psycopg://`
- **Dynamic Override Mechanism:** In `backend/migrations/env.py`, line 23 binds Alembic's `sqlalchemy.url` dynamically from `settings.DATABASE_URL`. When the `DATABASE_URL` environment variable is defined in the operating shell, `pydantic-settings` prioritizes it over any default or `.env` configuration file.

### Migration Revision History
The canonical migration chain consists of 4 version files in [`backend/migrations/versions/`](file:///c:/Users/Victus/Desktop/Technologies/MCA_Project/Foodsafe/backend/migrations/versions):

| Revision ID | Down Revision | Migration Script Filename | Primary DDL Changes |
| :--- | :--- | :--- | :--- |
| `9770c6f04c04` | `None` (Base) | `9770c6f04c04_create_initial_schema_37_tables.py` | Creates core identity, task, rule, and audit schema (37 domain tables) |
| `b770c6f05` | `9770c6f04c04` | `b770c6f04c05_add_incidents_unique_and_capa_fields.py` | Adds `uq_incidents_entry_id` constraint and CAPA recheck tracking columns |
| `c770c6f06` | `b770c6f05` | `c770c6f04c06_update_anomaly_results_constraints.py` | Updates `chk_anomaly_decision` check constraint and adds `uq_anomaly_results_entry_id` |
| `d770c6f04c07` | `c770c6f06` | `d770c6f04c07_add_outbox_dedupe_and_notification_fk.py` | Adds `outbox_events.dedupe_key` unique constraint and `notifications.outbox_event_id` FK |

**Expected HEAD Revision:** `d770c6f04c07`

---

## 4. Step-by-Step Rehearsal Procedure

### Step 4.1: Provision the Dedicated Staging Database

Connect to the PostgreSQL 18 instance using an administrative client (`psql` or administrative credentials) and provision a clean, isolated staging database:

```sql
-- Connect to administrative PostgreSQL session (e.g., 'postgres')
-- Terminate existing connections and drop previous staging instance if re-creating
DROP DATABASE IF EXISTS bharat_foodsafe_staging WITH (FORCE);

-- Create fresh isolated staging database
CREATE DATABASE bharat_foodsafe_staging
    WITH OWNER = foodsafety
    ENCODING = 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE = template0;
```

---

### Step 4.2: Supply Staging Credentials via Secure Environment Variable

Export the target `DATABASE_URL` strictly in the local shell session. Do **NOT** edit or persist this in `backend/.env`.

#### Linux / macOS (Bash):
```bash
export DATABASE_URL="postgresql+psycopg://<staging_user>:<staging_password>@<staging_host>:<staging_port>/bharat_foodsafe_staging"
```

#### Windows (PowerShell):
```powershell
$env:DATABASE_URL = "postgresql+psycopg://<staging_user>:<staging_password>@<staging_host>:<staging_port>/bharat_foodsafe_staging"
```

---

### Step 4.3: Pre-Flight Target & Clean-State Verification (Mandatory Check 1)

Before executing any migrations, run a pre-flight sanity check to assert that:
1. The active connection string resolves strictly to `bharat_foodsafe_staging`.
2. The schema is entirely clean (zero base tables exist in the `public` schema).

#### Bash / Linux / macOS:
```bash
cd backend
python -c '
import os, sys
from sqlalchemy import create_engine, text

db_url = os.environ.get("DATABASE_URL", "")
if "bharat_foodsafe_staging" not in db_url:
    print(f"FATAL: DATABASE_URL does not target staging: {db_url}")
    sys.exit(1)

engine = create_engine(db_url)
with engine.connect() as conn:
    current_db = conn.scalar(text("SELECT current_database();"))
    table_count = conn.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\'' AND table_type = '\''BASE TABLE'\'';"))

    print(f"Active database: {current_db}")
    print(f"Initial public table count: {table_count}")

    if current_db != "bharat_foodsafe_staging":
        print("FATAL: Aborting. Target database is NOT bharat_foodsafe_staging.")
        sys.exit(1)
    if table_count != 0:
        print(f"FATAL: Staging database is not clean ({table_count} tables found).")
        sys.exit(1)

print("Pre-flight Check 1 PASSED: Target is clean bharat_foodsafe_staging.")
'
```

#### Windows PowerShell:
```powershell
cd backend
python -c "import os, sys; from sqlalchemy import create_engine, text; db_url = os.environ.get('DATABASE_URL', ''); sys.exit('FATAL: Not staging') if 'bharat_foodsafe_staging' not in db_url else None; engine = create_engine(db_url); conn = engine.connect(); db = conn.scalar(text('SELECT current_database();')); count = conn.scalar(text(\"\"\"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'\"\"\")); conn.close(); print(f'Target: {db}, Initial Tables: {count}'); sys.exit(1) if db != 'bharat_foodsafe_staging' or count != 0 else print('Pre-flight Check 1 PASSED')"
```

#### Pre-Flight Alembic Status:
```bash
alembic current
```
*Expected Result:* Blank output / no revisions stamped, confirming Alembic has not yet initialized tables.

---

### Step 4.4: Execute Forward Migration (`alembic upgrade head`)

Execute the complete migration sequence against the clean staging database:

```bash
cd backend
alembic upgrade head
```

#### Expected Execution Output Log:
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 9770c6f04c04, create_initial_schema_37_tables
INFO  [alembic.runtime.migration] Running upgrade 9770c6f04c04 -> b770c6f05, add_incidents_unique_and_capa_fields
INFO  [alembic.runtime.migration] Running upgrade b770c6f05 -> c770c6f06, update_anomaly_results_constraints
INFO  [alembic.runtime.migration] Running upgrade c770c6f06 -> d770c6f04c07, add outbox dedupe key and notification fk
```

---

### Step 4.5: Post-Migration Schema & Revision Verification

Verify that the staging database schema is in complete alignment with specifications.

#### 1. Alembic Revision Check:
```bash
cd backend
alembic current
```
*Expected Result:*
```text
d770c6f04c07 (head)
```

#### 2. Table Count Verification:
Query PostgreSQL directly to confirm all tables are present. The expected count in schema `public` is **38 tables** (37 application domain tables + 1 `alembic_version` metadata table).

```sql
SELECT count(*) AS total_tables
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';
-- Expected result: 38
```

#### 3. Domain Entity Membership Verification:
Verify that all 37 application domain tables created in `9770c6f04c04` are present:

```sql
SELECT count(*) AS domain_table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
  AND table_name IN (
    -- Identity & RBAC (8)
    'restaurants', 'users', 'roles', 'permissions', 'role_permissions', 'user_roles', 'devices', 'auth_sessions',
    -- Tasks & Safety Rules (13)
    'task_categories', 'rule_sources', 'safety_rules', 'safety_rule_bindings', 'task_templates',
    'task_template_versions', 'equipment', 'tasks', 'task_assignments', 'evidence_files',
    'idempotency_keys', 'entries', 'entry_safety_evaluations',
    -- Analytics & Incidents (9)
    'model_versions', 'anomaly_results', 'incidents', 'corrective_actions', 'suppliers',
    'products', 'batches', 'business_verifications', 'verification_documents',
    -- Notifications & Audit (7)
    'notifications', 'notification_preferences', 'outbox_events', 'audit_log',
    'public_profile_settings', 'customer_follows', 'official_records'
  );
-- Expected result: 37
```

#### 4. Critical Constraint Verification:
Verify that constraints added across subsequent migrations were successfully applied:

```sql
-- 1. Verify unique constraint on incidents.entry_id (from b770c6f05)
SELECT conname, contype
FROM pg_constraint
WHERE conname = 'uq_incidents_entry_id';

-- 2. Verify check constraint on anomaly_results.decision (from c770c6f06)
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'chk_anomaly_decision';
-- Expected constraint definition includes:
-- CHECK (decision::text = ANY (ARRAY['NO_FLAG'::character varying, 'REVIEW'::character varying, 'SUSPICIOUS'::character varying, 'UNAVAILABLE'::character varying, 'ESCALATE'::character varying]::text[]))

-- 3. Verify unique constraint on anomaly_results.entry_id (from c770c6f06)
SELECT conname, contype
FROM pg_constraint
WHERE conname = 'uq_anomaly_results_entry_id';

-- 4. Verify outbox dedupe unique constraint (from d770c6f04c07)
SELECT conname, contype
FROM pg_constraint
WHERE conname = 'uq_outbox_events_dedupe_key';

-- 5. Verify notification foreign key and unique constraint (from d770c6f04c07)
SELECT conname, contype
FROM pg_constraint
WHERE conname IN ('fk_notifications_outbox_event_id', 'uq_notifications_user_outbox_event');
```

---

### Step 4.6: Re-run & Idempotency Check

Re-run `alembic upgrade head` immediately after a successful migration:

```bash
cd backend
alembic upgrade head
```
*Expected Result:* Clean exit with no actions executed, confirming migration runner idempotency.

---

### Step 4.7: Rollback (Downgrade) Rehearsal

> [!CAUTION]
> **DESTRUCTIVE OPERATION WARNING:**
> Database downgrades (`alembic downgrade`) roll back schema revisions and drop database objects (columns and constraints). This operation is **strictly prohibited** on development (`bharat_foodsafe`) or production databases. It must **ONLY** ever be rehearsed against an explicitly verified, disposable staging database (`bharat_foodsafe_staging`).

#### Mandatory Pre-Downgrade Target Check (Mandatory Check 2):
```bash
python -c 'import os, sys; from sqlalchemy import create_engine, text; engine = create_engine(os.environ["DATABASE_URL"]); db = engine.connect().scalar(text("SELECT current_database();")); sys.exit(0 if db == "bharat_foodsafe_staging" else 1);'
```

#### Execute Stepwise Rollback:
```bash
cd backend

# Rehearse single-step downgrade (reverts d770c6f04c07 to c770c6f06)
alembic downgrade -1

# Verify current revision
alembic current
# Expected: c770c6f06

# Confirm dropped constraint from d770c6f04c07
# (uq_outbox_events_dedupe_key must no longer exist)

# Re-apply upgrade to return to HEAD
alembic upgrade head

# Verify restoration of HEAD
alembic current
# Expected: d770c6f04c07 (head)
```

---

### Step 4.8: Optional Baseline Seed Rehearsal

> [!NOTE]
> **Seed Rehearsal Scope & Prerequisites:**
> Inspecting [`database/seeds/run_all.py`](file:///c:/Users/Victus/Desktop/Technologies/MCA_Project/Foodsafe/database/seeds/run_all.py) confirms that the script connects via `SessionLocal` (which inherits `DATABASE_URL`). Its operations are strictly additive and idempotent: it checks for existing records by unique identifiers (`name`, `code`, `phone`, `email`), inserts records only when absent, and updates credential hashes. It executes **zero table drops, zero column alterations, and zero row deletions**.
> This seed rehearsal is **optional** during migration rehearsal because staging and production deployments may utilize custom administrative bootstrap scripts rather than local development demo fixtures.

If rehearsing seed data on staging:

#### Mandatory Pre-Seed Target Check (Mandatory Check 3):
```bash
python -c 'import os, sys; from sqlalchemy import create_engine, text; engine = create_engine(os.environ["DATABASE_URL"]); db = engine.connect().scalar(text("SELECT current_database();")); sys.exit(0 if db == "bharat_foodsafe_staging" else 1);'
```

#### Execute Seed Script:
```bash
python database/seeds/run_all.py
```

*Expected Result:*
- System roles (`STAFF`, `MANAGER`, `PLATFORM_ADMIN`) seeded/verified.
- Base permissions seeded.
- Demo restaurant tenant and users initialized.
- Zero foreign key or unique constraint errors.

---

## 5. Failure Handling & Recovery Protocols

If any step of the rehearsal encounters an error:

1. **Capture Diagnostic Artifacts:** Immediately record the terminal stdout/stderr, active `git rev-parse HEAD`, and the output of `alembic current`.
2. **Do Not Touch Production or Development:** Do not attempt manual SQL fixes or migrations against shared or persistent databases.
3. **Safe Teardown of Staging:**
   ```sql
   -- Connect to administrative PostgreSQL session
   DROP DATABASE IF EXISTS bharat_foodsafe_staging WITH (FORCE);
   ```
4. **Root Cause Analysis:**
   - **Syntax / Dialect Error:** Check for PostgreSQL 18-incompatible syntax in the migration script.
   - **Constraint / Ordering Issue:** Verify `down_revision` ordering in `backend/migrations/versions/`.
   - **Model Drift:** Compare SQLAlchemy model definitions against migration operations.
5. **Re-Test:** Once the migration script is corrected and passes automated CI checks, restart this procedure from Step 4.1.

---

## 6. Teardown / Cleanup Procedure

> [!CAUTION]
> **DESTRUCTIVE DROP GUARD:**
> Dropping a database is permanent and irreversible. Confirm that the database being dropped is strictly `bharat_foodsafe_staging`. Never run drop commands against `bharat_foodsafe` or production.

After the rehearsal has been completed and documented:

```sql
-- Connect to administrative PostgreSQL session (e.g. 'postgres')
-- Terminate lingering connections and remove the staging rehearsal database
DROP DATABASE IF EXISTS bharat_foodsafe_staging WITH (FORCE);
```

Clear the environment variable in the terminal session:

#### Linux / macOS:
```bash
unset DATABASE_URL
```

#### Windows PowerShell:
```powershell
Remove-Item Env:\DATABASE_URL
```

---

## 7. Staging Rehearsal Sign-off Record Template

Complete and record this template in the release notes for each staging deployment rehearsal:

```markdown
### Staging Migration Rehearsal Sign-off Record
- **Date & Time (UTC):** YYYY-MM-DD HH:MM:SS
- **Operator Name:** [Name / Role]
- **Git Commit SHA:** [Full 40-character commit hash]
- **Target Staging Database:** bharat_foodsafe_staging
- **Pre-Flight Check 1 (Target & Clean State):** [PASS / FAIL] (Table count: 0)
- **Alembic Upgrade Head Status:** [PASS / FAIL]
- **Target HEAD Revision Verified:** d770c6f04c07 (head)
- **Table Count Post-Migration:** 38 base tables (37 domain + 1 alembic_version)
- **Domain Tables Set Membership Check (37 tables):** [PASS / FAIL]
- **Critical Constraints Verified:** [PASS / FAIL]
- **Downgrade / Re-upgrade Rehearsal:** [PASS / FAIL / SKIPPED]
- **Seed Suite Execution (`run_all.py`):** [PASS / FAIL / SKIPPED]
- **Teardown Completed:** [YES / NO]
- **Release Gate Recommendation:** [READY FOR PRODUCTION / BLOCKED]
- **Notes / Observations:** [None / List observations]
```
