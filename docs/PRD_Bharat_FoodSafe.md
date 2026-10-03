# Product Requirements Document (PRD) — Bharat FoodSafe

**Document Title:** Bharat FoodSafe — Product Requirements Document  
**Version:** 1.5.0  
**Product Status:** Build-Locked Specification  
**Target Platform:** Mobile-First Web Application (Staff) & Responsive Desktop Web Dashboard (Manager / Admin)  

---

## 1. Problem Statement

Commercial food businesses in India—including restaurants, cloud kitchens, canteens, and caterers—face critical challenges in maintaining daily operational food safety compliance:

- **Unreliable Manual Record Keeping:** Over 85% of food safety logs (temperature logs, sanitation checklists, receiving checks) are maintained on paper registers, leading to retroactive "paper filling" right before inspections rather than real-time operational compliance.
- **Lack of Verification & Evidence:** Standard checklists contain unchecked self-reported numbers without physical evidence, making it impossible for management or auditors to verify if checks were actually performed at the declared time.
- **Inspection Panic & Audit Failures:** FSSAI inspections and internal audits result in heavy penalties or temporary suspensions due to missing logs, uncalibrated equipment logs, or untracked corrective actions.
- **Fraud vs. Operational Risk Ambiguity:** Management lacks data-driven signals to distinguish between genuine operational deviations (e.g., a broken chiller) and statistical record-falsification patterns (e.g., staff filling 30 days of identical values in 2 minutes).

---

## 2. Goals & Objectives

The primary objective of Bharat FoodSafe is to establish an operational assurance layer between FSSAI food-safety regulations/SOPs and daily kitchen execution.

1. **SMART Goal 1 (Task Execution & Evidence Compliance):** Achieve $\ge 95\%$ daily task completion rate with mandatory photo/numerical evidence across onboarded kitchen outlets within 30 days of deployment.
2. **SMART Goal 2 (Real-Time Safety Evaluation):** Evaluate $100\%$ of submitted entries deterministically against active, verified FSSAI/SOP safety rules within $< 500\text{ ms}$ of submission.
3. **SMART Goal 3 (Corrective Action Closure Time):** Reduce the mean time to resolution (MTTR) for critical food-safety incidents and Corrective and Preventive Actions (CAPA) from an industry average of 48 hours to $< 4\text{ hours}$.
4. **SMART Goal 4 (Audit Readiness):** Enable $100\%$ digital inspection readiness by generating cryptographically verified audit reports (with 0 broken hash chain links) instantly upon auditor request.

---

## 3. Success Metrics

| Metric | Target | Measurement Method | Frequency |
| :--- | :--- | :--- | :--- |
| **Daily Task Completion Rate (DTCR)** | $\ge 95\%$ | (Completed Tasks / Total Scheduled Tasks) * 100 | Daily |
| **Evidence Submission Rate (ESR)** | $100\%$ for mandatory tasks | Percentage of completed tasks with valid, validated binary evidence | Real-time |
| **Critical Incident Resolution Time (CIRT)**| $< 4\text{ hours}$ | Time elapsed from entry evaluation (`CRITICAL`) to CAPA verification by Manager | Per Incident |
| **Audit Hash Integrity Rate** | $100\%$ (0 broken links) | Automated daily audit log re-hash validation utility execution | Daily |
| **False Positive Anomaly Flag Rate** | $< 5\%$ | Percentage of flagged anomaly reviews marked as "Legitimate Operation" by Managers | Weekly |

---

## 4. Target Personas

### Persona 1: Rajesh Kumar — Senior Kitchen Operations Staff
- **Demographics:** 29 years old, Line Cook / Kitchen Supervisor, Tier-1 city cloud kitchen.
- **Tech Proficiency:** Moderate (uses WhatsApp, UPI payment apps, basic mobile browsers; prefers Android).
- **Pain Points:** 
  - Overwhelmed during peak meal prep hours; paper logs feel like an unnecessary administrative burden.
  - Gets blamed when equipment fails if past paper logs were missing or illegible.
- **Goals:**
  - Complete daily safety checks in under 3 minutes per shift directly from his smartphone.
  - Have clear proof that he performed his checks on time.
- **User Environment:** Fast-paced, noisy kitchen, high-humidity, single-handed mobile phone usage.

### Persona 2: Ananya Sharma — Store Manager / Operations Head
- **Demographics:** 36 years old, Multi-outlet Restaurant Manager, 12 years hospitality experience.
- **Tech Proficiency:** High (proficient with POS systems, Excel, web dashboards, laptop and smartphone).
- **Pain Points:** 
  - Cannot monitor whether 15 kitchen staff members are actually checking chiller temperatures during morning shifts.
  - FEAR of surprise FSSAI inspections or customer food-poisoning complaints.
  - Receives too many false alarms or late notifications about spoiled inventory.
- **Goals:**
  - View real-time shift compliance scores across temperature, hygiene, and receiving categories.
  - Receive instant alerts on critical deviations and verify corrective actions taken by staff.
  - Export instant, verified PDF/CSV audit reports for FSSAI inspectors.

---

## 5. Feature Requirements Matrix

### P0 (MVP Must-Haves)

#### Feature 1: Role-Based Access Control (RBAC) & Tenant Isolation
- **Description:** Multi-tenant architecture ensuring staff and managers can only view and mutate records within their explicitly assigned `restaurant_id`.
- **User Story:** *As a Kitchen Staff member, I want to log in with my Phone & PIN so that I can securely access my assigned daily tasks for my specific kitchen outlet.*
- **Acceptance Criteria:**
  1. System supports `Staff` (Phone + PIN), `Manager` (Phone + PIN), and `Platform Admin` (Email + Password) authentication.
  2. Every API request enforces server-side `TenantContext` isolation; cross-tenant queries must return `403 Forbidden` or `404 Not Found`.
  3. Session refresh tokens are stored only as SHA-256 hashes and rotate upon usage with token family reuse revocation.
- **Success Metric:** 0 cross-tenant data leaks in automated IDOR security test suites.

#### Feature 2: Versioned Task Templates & Idempotent Task Scheduler
- **Description:** System generates recurring task instances based on versioned task templates without creating duplicate tasks for the same scheduled occurrence.
- **User Story:** *As a Manager, I want recurring daily temperature tasks automatically scheduled every morning so that staff have clear tasks assigned without manual creation.*
- **Acceptance Criteria:**
  1. Task configurations are stored in immutable `task_template_versions` rows linked to parent `task_templates`.
  2. Scheduler uses `occurrence_key` with a database unique constraint `UNIQUE(template_id, occurrence_key)` to guarantee idempotency.
  3. Tasks transition automatically through states: `PENDING` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED` or `OVERDUE`.
- **Success Metric:** $100\%$ on-time task generation with $0\%$ duplicate occurrence keys.

#### Feature 3: Staff Task Dashboard & Evidence Submission
- **Description:** Mobile-first interface for staff to select tasks, input numerical/text values, and attach mandatory photo evidence.
- **User Story:** *As a Staff member, I want to take a photo of a chiller thermometer and submit the temperature reading so that my check is recorded and verified.*
- **Acceptance Criteria:**
  1. Client uploads binary evidence via presigned S3 URLs; server validates magic bytes, declared MIME type, maximum size (10MB), and SHA-256 hash before marking evidence `AVAILABLE`.
  2. Mandatory evidence requirements configured in the task template version cannot be bypassed; API rejects submissions missing required evidence with HTTP `422`.
  3. Submissions enforce persistent idempotency using `Idempotency-Key` headers to prevent duplicate task completions on network retries.
- **Success Metric:** $100\%$ valid evidence confirmation rate; 0 duplicate submissions recorded.

#### Feature 4: Deterministic Safety Rules Engine
- **Description:** Evaluates entry values against active, versioned safety rules linked to official FSSAI regulatory sources.
- **User Story:** *As a Manager, I want temperature readings evaluated immediately against FSSAI rules so that any out-of-range value triggers an immediate alert.*
- **Acceptance Criteria:**
  1. Evaluates numeric/text entries instantly and outputs `NORMAL`, `DEVIATION`, or `CRITICAL` safety status.
  2. Safety rules MUST link to a `VERIFIED` `RuleSource` (FSSAI regulation or formal SOP) to be activated.
  3. Historical entry evaluations store immutable snapshots (`entry_safety_evaluations`) referencing the exact rule ID, source ID, version, result, and reason used at submission time.
- **Success Metric:** $100\%$ evaluation accuracy against rule specifications; $< 500\text{ ms}$ evaluation latency.

#### Feature 5: Incidents & Corrective Action (CAPA) Workflow
- **Description:** Automated incident creation and corrective action tracking when a `CRITICAL` or `DEVIATION` safety evaluation occurs.
- **User Story:** *As a Manager, I want an incident automatically opened when a chiller temperature is critical so that staff perform a corrective action and record a re-check.*
- **Acceptance Criteria:**
  1. `CRITICAL` safety entries trigger an automatic `OPEN` incident and an associated `OPEN` CAPA assignment.
  2. State transitions use explicit command endpoints (`/start`, `/complete`, `/verify`, `/reopen`, `/cancel`); generic status `PATCH` is strictly prohibited.
  3. CAPA resolution requires staff to record a re-check reading and the Manager to explicitly verify resolution.
- **Success Metric:** $100\%$ of `CRITICAL` entries have an associated incident; $< 4\text{ hours}$ average MTTR.

#### Feature 6: Append-Only Cryptographic Audit Hash Chain
- **Description:** Complete, tamper-evident audit trail of all business mutations and security events.
- **User Story:** *As an Auditor, I want to verify that past food safety records have not been altered or deleted after the fact.*
- **Acceptance Criteria:**
  1. All auditable mutations append a row to `audit_log` within the same database transaction.
  2. Computes `record_hash = SHA256(UTF8_JSON(event + previous_hash))` per `chain_scope`.
  3. Concurrency is controlled using transaction-level PostgreSQL advisory locks (`pg_advisory_xact_lock`) before hash computation.
  4. Application provides zero `UPDATE` or `DELETE` endpoints for `audit_log`.
- **Success Metric:** $100\%$ audit chain integrity during automated re-hash audits.

---

### P1 (Important)

#### Feature 7: Record-Integrity Anomaly Engine
- **Description:** Machine-learning powered statistical review flag to identify unusual submission timing, burst patterns, or photo reuse.
- **User Story:** *As a Manager, I want to be flagged if 20 tasks are submitted within 45 seconds so I can review whether staff are properly performing checks.*
- **Acceptance Criteria:**
  1. Feature extractor calculates `timing_regularity`, `value_variance`, `burst_score`, `photo_reuse_count`, `edit_frequency`, `device_novelty`, and `late_submission_ratio`.
  2. Isolation Forest model outputs decision (`NO_FLAG`, `REVIEW`, `ESCALATE`) and numerical risk score.
  3. Cold-start policy: if entry history $< 30$, analysis returns `analysis_status = UNAVAILABLE` without affecting deterministic safety evaluation.
  4. Model outputs are strictly review signals and NEVER override safety evaluation or serve as definitive proof of fraud.
- **Success Metric:** $\le 5\%$ false-positive review rate on normal operating shifts.

#### Feature 8: Transactional Outbox & Notification Dispatcher
- **Description:** Reliable event-driven notification framework for critical alerts (overdue tasks, critical deviations, CAPA verification).
- **User Story:** *As a Manager, I want to receive an in-app notification when a task becomes overdue or critical so I can act immediately.*
- **Acceptance Criteria:**
  1. Mutations write notification payloads into `outbox_events` with unique `dedupe_key`.
  2. Outbox worker claims pending events using `SELECT ... FOR UPDATE SKIP LOCKED` with configurable lease recovery.
  3. External delivery failures do NOT roll back already committed DB transactions.
- **Success Metric:** $> 99.9\%$ outbox delivery success within 30 seconds of trigger.

#### Feature 9: Equipment Master & Asset Tracking
- **Description:** Domain entity managing physical kitchen equipment (chillers, freezers, dishwashers, deep fryers).
- **User Story:** *As a Manager, I want tasks mapped to specific physical chillers so I can track maintenance history and temperature trends per unit.*
- **Acceptance Criteria:**
  1. Equipment entity stores name, type, location, identifier, and status (`ACTIVE`, `OUT_OF_SERVICE`, `RETIRED`).
  2. Tasks and entries reference `equipment_id` to maintain asset compliance lineage.
- **Success Metric:** $100\%$ mapping of temperature tasks to active physical equipment entities.

#### Feature 10: Inspection-Readiness Reporting & CSV/PDF Export
- **Description:** Automated reporting suite providing operational compliance scores and exportable audit reports.
- **User Story:** *As a Manager, I want to generate a 30-day inspection readiness report in PDF format for an FSSAI inspector.*
- **Acceptance Criteria:**
  1. Provides endpoints for task completion, anomaly summaries, CAPA logs, and overall inspection readiness.
  2. Date ranges are capped at 366 days max per query; list endpoints enforce pagination (max 100 per page).
  3. PDF/CSV exports format summary metrics, verified rule sources, and evidence links without exposing internal system secrets or raw session hashes.
- **Success Metric:** Report generation time $< 2\text{ seconds}$ for 30-day date ranges.

---

### P2 (Nice-to-Have / Phase 2 & 3 Expansion)

#### Feature 11: Bounded OCR Verification Adapter (Phase 2)
- **Description:** Automated text extraction from uploaded business licenses (FSSAI license certificate, GST registration) during business verification.
- **User Story:** *As a Platform Admin, I want license numbers pre-filled via OCR when a restaurant uploads their FSSAI certificate to speed up verification.*
- **Acceptance Criteria:** Extracts document fields into `extracted_fields_jsonb` and assigns `ocr_status` (`COMPLETE`, `MANUAL_REVIEW`, `FAILED`).
- **Success Metric:** $> 85\%$ OCR field extraction accuracy on standard FSSAI certificates.

#### Feature 12: Public Business Profile & Customer Follows (Phase 3)
- **Description:** Controlled public transparency page displaying aggregated compliance ratings and verified official records to public users.
- **User Story:** *As a Dining Customer, I want to view a restaurant's verified food safety compliance score before ordering.*
- **Acceptance Criteria:** Public API displays ONLY explicitly approved aggregate metrics; raw employee names, raw evidence photos, and internal manager notes are strictly excluded via explicit DTO allow-lists.
- **Success Metric:** 0 leaks of private employee or internal operational data on public profile endpoints.

---

## 6. Explicitly Out of Scope

To maintain product focus and prevent scope creep, the following capabilities are **EXPLICITLY EXCLUDED** from Bharat FoodSafe v1.5:

1. **IoT Sensor & Telemetry Integration:** No Bluetooth, Wi-Fi, or direct hardware temperature sensors are supported. All entries require manual human logging and evidence attachment.
2. **FSSAI Official Government Licensing System:** The platform does NOT issue official government licenses, process government fee payments, or interact directly with FSSAI state portal databases.
3. **Automated Legal Fraud Proofing:** The Anomaly Engine generates internal statistical review signals only; it does NOT legal-proof or prove employee fraud.
4. **Microservices Architecture:** The system is strictly designed as a single **Modular Monolith**; microservice splits or distributed service meshes are prohibited for MVP.
5. **Offline-First Data Engine:** Mobile client requires an active internet connection (or standard HTTP retry); complex offline CRDT state synchronization is out of scope.
6. **Medical / Foodborne Illness Diagnostics:** The platform does not diagnose medical symptoms or process customer health illness claims.
7. **Procurement & Inventory ERP:** No purchase order generation, vendor invoice settlement, or general inventory accounting features.
8. **Generative AI / Voice Assistant / Chatbots:** No unstructured LLM-based voice task entry or conversational RAG chatbots in the MVP execution path.

---

## 7. End-to-End User Scenarios

### Scenario 1: Daily Shift Temperature Check & Evidence Logging
- **Actor:** Rajesh (Kitchen Staff Member)
- **Primary Flow:**
  1. Rajesh opens the Bharat FoodSafe PWA on his mobile phone during the 8:00 AM shift start.
  2. Selects assigned task: *"Morning Walk-In Chiller Temperature Check"*.
  3. Taps **Start Task**, reads the SOP requirement ($\le 4^\circ\text{C}$), and inspects Chiller #1.
  4. Enters numeric value `3.5` and unit `C`.
  5. Taps **Attach Photo**, captures a photo of the digital thermometer on Chiller #1.
  6. Client requests presigned URL, uploads binary image, confirms upload, and submits entry with `Idempotency-Key`.
- **System Outcome:** Entry saved $\rightarrow$ Deterministic Rules Engine evaluates $3.5^\circ\text{C} \le 4.0^\circ\text{C} \rightarrow$ Safety Status `NORMAL` $\rightarrow$ Audit log hash updated $\rightarrow$ Task marked `COMPLETED`.
- **Edge Cases & Failure Handling:**
  - *Network Drop:* Client retries request with same `Idempotency-Key`; server returns cached `COMPLETED` response without duplicate entry creation.
  - *Invalid File Upload:* Uploading a `.exe` or corrupt file fails magic-byte validation; server marks upload `REJECTED` and returns HTTP `422`.

### Scenario 2: Critical Temperature Deviation & Incident CAPA Resolution
- **Actor:** Rajesh (Staff) & Ananya (Manager)
- **Primary Flow:**
  1. Rajesh inspects Freezer #2 and logs a temperature of `2.8` $\text{C}$ (Required: $\le -18^\circ\text{C}$).
  2. Submits entry with photo evidence.
  3. Rules Engine evaluates value $\rightarrow$ Safety Status `CRITICAL` (Threshold breached).
  4. System immediately creates an `OPEN` Incident and assigns an `OPEN` Corrective Action (CAPA).
  5. Ananya receives an instant push/in-app notification: *"CRITICAL DEVIATION: Freezer #2 at 2.8°C"*.
  6. Ananya opens Manager Dashboard, inspects entry evidence, calls maintenance technician, and moves stock to backup freezer.
  7. Rajesh performs maintenance, records a re-check entry (`-19.1` $\text{C}$), and submits CAPA completion.
  8. Ananya reviews re-check evidence and clicks **Verify Resolution**.
- **System Outcome:** Incident status transitions `OPEN` $\rightarrow$ `ASSIGNED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `AWAITING_RECHECK` $\rightarrow$ `VERIFICATION_PENDING` $\rightarrow$ `CLOSED`. Entire lifecycle logged to audit chain.
- **Edge Cases & Failure Handling:**
  - *Attempted Direct Status Edit:* Manager attempts to send a `PATCH /api/v1/incidents/{id}` with `status: CLOSED` without completing re-check. System rejects request with HTTP `409 Conflict` (Direct status mutation prohibited).

### Scenario 3: Detection of Suspicious Data Entry Burst (Anomaly Review)
- **Actor:** Ananya (Manager)
- **Primary Flow:**
  1. A night-shift staff member submits 25 overdue tasks in 35 seconds right before closing, entering identical values (`4.0` $\text{C}$) across all different chillers.
  2. Rules Engine evaluates values as `NORMAL` (4.0 is within numerical range).
  3. Record-Integrity Anomaly Engine processes entry features (`burst_score`, `timing_regularity`, `value_variance`).
  4. Anomaly Engine flags submission set with Decision: `REVIEW`, Risk Level: `HIGH`, Reason: *"Unusual submission burst (25 tasks in 35s) with zero value variance"*.
  5. Ananya opens Manager Dashboard $\rightarrow$ Anomaly Review Queue.
  6. Reviews flagged entry cluster, conducts verbal warning, and requests physical re-check of night shift chillers.
  7. Clicks **Acknowledge & Escalated to Internal Review**.
- **System Outcome:** Safety status remains `NORMAL` (safety rule not faked), but integrity result logs `REVIEW`. Manager decision is recorded in `anomaly_results` and appended to audit log.
- **Edge Cases & Failure Handling:**
  - *ML Inference Service Timeout:* If anomaly inference fails or times out, system sets `analysis_status = UNAVAILABLE` and saves entry safety result without blocking staff execution.

---

## 8. Non-Functional Requirements (NFRs)

### 8.1 Performance & Scalability
- **API Latency:** $p_{95}$ response time $< 300\text{ ms}$ for standard transactional read/write APIs (excluding file upload transmission and PDF exports).
- **Evaluation Speed:** Deterministic Safety Rules Engine evaluation latency $< 50\text{ ms}$ per entry.
- **Database Query Limits:** Pagination enforced on all list endpoints (default 20, max 100 items per page). Date range queries capped at 366 days max.

### 8.2 Security & Data Protection
- **Tenant Isolation:** Enforced via server-side `TenantContext` middleware. All SQL queries must explicitly filter by `restaurant_id`.
- **Authentication & Authorization:** JWT Access Tokens (15-minute TTL) + Persisted Refresh Sessions (7-day TTL). Refresh tokens stored as SHA-256 hashes with automated token family revocation upon reuse detection.
- **Input & File Security:** Strict typed Pydantic schema validation on all payloads. File uploads strictly validated via header inspection, magic-byte checking, size limits (10MB max), and SHA-256 hashing. Executable file extensions (`.exe`, `.bat`, `.sh`, `.php`, etc.) explicitly rejected.
- **SQL & XSS Prevention:** 100% parameterization via SQLAlchemy ORM. Client-side escaping via React DOM rendering.

### 8.3 Auditability & Immutability
- **Append-Only Logs:** Zero `UPDATE` or `DELETE` permissions on `audit_log` for normal application database roles.
- **Cryptographic Chaining:** `record_hash` computed via SHA-256 incorporating the previous row's hash. Concurrency protected by PostgreSQL advisory locking (`pg_advisory_xact_lock`).

### 8.4 Accessibility & UX Design
- **Mobile-First Staff UX:** Large touch targets ($\ge 48\times 48\text{ px}$), high-contrast UI components, clear status badges (`NORMAL` = Green, `DEVIATION` = Yellow, `CRITICAL` = Red).
- **Responsive Layouts:** Optimized for low-end Android smartphones (Staff) and Desktop screens (Manager/Admin).
- **Form Usability:** Native numeric keypads triggered for number inputs; explicit unit selection.

---

## 9. Verification & Acceptance Criteria Summary

To consider this PRD fulfilled during QA and Release Gate review:
1. All **P0 features** must have $100\%$ automated test pass rate across unit, API, integration, and security test suites.
2. Mandatory **Architecture Consistency Tests** must pass in CI (OpenAPI sync, DB model sync, RBAC permission enforcement, tenant isolation checks).
3. The system must pass automated **Penetration & IDOR tests** with zero cross-tenant data leaks.
