# Technology Stack Specifications (TECH_STACK.md) — Bharat FoodSafe

**App Name:** Bharat FoodSafe  
**Specification Version:** 1.5.0  
**Document Status:** Build-Locked Specification  
**App Type:** Mobile-First Web Application (Staff PWA) + Responsive Desktop Web Dashboard (Manager/Admin) + REST API Monolith  
**Scale Target:** Production-Ready Modular Monolith (Multi-tenant)  

---

## 1. Executive Summary & Tech Selection Rationale

The architecture of **Bharat FoodSafe** is locked as a single **Modular Monolith** using **FastAPI (Python 3.13.1)** on the backend, **React 19.2.0 + Vite 8.0.0** on the frontend, and **PostgreSQL 18.0** as the primary relational database. This stack was selected for high asynchronous throughput, strict type safety across Python DTOs and TypeScript client interfaces, seamless machine learning integration (`scikit-learn`), and zero reliance on heavy microservice infrastructure (no Kubernetes or Redis required for MVP).

---

## 2. Technology Stack & Decision Matrix

### 2.1 Frontend Stack

| Category | Technology & Exact Version | Documentation URL | Selection Rationale | Alternatives Considered & Rejected |
| :--- | :--- | :--- | :--- | :--- |
| **Framework** | **React 19.2.0** | [react.dev](https://react.dev/) | Industry-standard component model, excellent PWA support, optimized concurrent rendering. | **Vue 3.5** (smaller ecosystem for enterprise PWA plugins); **Next.js 15** (unnecessary SSR complexity for authenticated kitchen SPA). |
| **Language** | **TypeScript 5.7.2** | [typescriptlang.org](https://www.typescriptlang.org/) | Enforces strict compile-time type safety across DTO interfaces, preventing runtime property access bugs. | **Plain JavaScript** (high risk of runtime type errors during complex entry data handling). |
| **Build Tool** | **Vite 6.0.7** | [vite.dev](https://vite.dev/) | Sub-second HMR and instant dev server startup; fast Rollup-based production bundling. | **Webpack 5** (slow build times, complex configuration boilerplate); **Create React App** (deprecated). |
| **Styling** | **Tailwind CSS 4.0.0** | [tailwindcss.com](https://tailwindcss.com/) | Utility-first CSS engine enabling rapid custom mobile UI development with zero runtime CSS-in-JS overhead. | **Bootstrap 5** (generic aesthetic); **Styled Components 6** (runtime CSS extraction performance cost on mobile). |
| **Routing** | **React Router 7.1.1** | [reactrouter.com](https://reactrouter.com/) | Robust, type-safe route matching, layout inheritance, and role-gated navigation guards. | **TanStack Router 1.90** (higher learning curve for initial release). |
| **Server State** | **TanStack Query 5.62.7** | [tanstack.com/query](https://tanstack.com/query/latest) | Automatic caching, background revalidation, optimistic updates, and built-in offline query retries. | **Redux Toolkit 2.5** (excessive boilerplate for managing server response state). |
| **Form Handling** | **React Hook Form 7.54.2** | [react-hook-form.com](https://react-hook-form.com/) | Uncontrolled form inputs minimizing re-renders on mobile devices during fast numerical entry. | **Formik 2.4** (causes heavy full-form re-renders on every keystroke). |
| **Validation** | **Zod 3.24.1** | [zod.dev](https://zod.dev/) | Schema validation with automated TypeScript type inference; aligns directly with FastAPI Pydantic DTOs. | **Yup 1.6** (inferior TypeScript integration). |
| **HTTP Client** | **Axios 1.8.2** | [axios-http.com](https://axios-http.com/) | Interceptors for seamless JWT access token refresh and global idempotency key injection. | **Native Fetch** (requires manual wrapper for interceptors and response envelope handling). |
| **Icons** | **Lucide React 0.469.0** | [lucide.dev](https://lucide.dev/) | Lightweight, accessible SVG icon package supporting clean UI state indicators. | **FontAwesome 6** (large bundle footprint). |

---

### 2.2 Backend & Infrastructure Stack

| Category | Technology & Exact Version | Documentation URL | Selection Rationale | Alternatives Considered & Rejected |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime** | **Python 3.13.1** | [python.org](https://www.python.org/) | Modern Python with improved GIL performance, JIT compilation enhancements, and native ML library support. | **Node.js 22.x** (weaker native integration with `scikit-learn` and statistical data pipelines). |
| **Framework** | **FastAPI 0.115.6** | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) | High-performance async ASGI web framework with automatic OpenAPI spec generation and Pydantic validation. | **Django 5.1** (heavy ORM overhead and sync legacy); **Flask 3.1** (lacks native async ASGI and auto OpenAPI). |
| **Server Engine**| **Uvicorn 0.34.0** | [uvicorn.org](https://www.uvicorn.org/) | Lightning-fast ASGI server implementation powered by `uvloop` and `httptools`. | **Gunicorn + gevent** (unnecessary for pure async FastAPI ASGI deployments). |
| **Database** | **PostgreSQL 18.0** | [postgresql.org](https://www.postgresql.org/) | Industrial system of record supporting ACID transactions, JSONB indexing, advisory locks, and UUID PKs. | **MySQL 8.4** (inferior JSONB query capabilities and lack of transaction-level advisory locks); **MongoDB** (lacks transactional safety guarantees). |
| **ORM** | **SQLAlchemy 2.0.36** | [sqlalchemy.org](https://www.sqlalchemy.org/) | Explicit session transaction management, strict unit-of-work pattern, and full PostgreSQL feature support. | **Tortoise ORM 0.21** (less mature ecosystem); **Peewee** (lacks complex migration and advisory lock capabilities). |
| **Migrations** | **Alembic 1.14.0** | [alembic.sqlalchemy.org](https://alembic.sqlalchemy.org/) | Official SQLAlchemy database migration tool ensuring version-controlled DDL schema evolution. | **Raw SQL scripts** (error-prone across team environments). |
| **ML Engine** | **scikit-learn 1.6.0** | [scikit-learn.org](https://scikit-learn.org/) | Robust, production-tested Isolation Forest algorithm for statistical record-integrity anomaly analysis. | **PyTorch / TensorFlow** (excessive resource overhead for tabular statistical anomaly detection). |
| **Data Science** | **pandas 2.2.3 / numpy 2.2.1** | [pandas.pydata.org](https://pandas.pydata.org/) | High-performance feature engineering matrix processing for entry timing and variance scoring. | **Pure Python loops** (slow vector processing). |
| **Auth Hashing**| **Passlib 1.7.4 + bcrypt 4.2.1** | [passlib.readthedocs.io](https://passlib.readthedocs.io/) | Cryptographically secure password and PIN hashing using salted bcrypt algorithms. | **SHA-256 / MD5** (insecure, vulnerable to rainbow table attacks). |
| **JWT Library** | **PyJWT 2.10.1** | [pyjwt.readthedocs.io](https://pyjwt.readthedocs.io/) | Lightweight, secure RFC 7519 compliant JSON Web Token encoding and decoding. | **python-jose** (unmaintained maintenance status). |
| **Object Storage**| **Boto3 1.35.84** | [boto3.amazonaws.com](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) | AWS SDK for Python powering presigned S3 upload URL generation and object lifecycle management. | **Custom upload handlers** (loads application server memory and network bandwidth). |

---

## 3. Complete Environment Variables Specification

Below is the complete list of environment variables required for application runtime across development and production environments.

### 3.1 Backend Configuration (`backend/.env.example`)

```ini
# ==============================================================================
# BHARAT FOODSAFE - BACKEND ENVIRONMENT CONFIGURATION
# ==============================================================================

# Application Metadata
APP_ENV=development                           # Options: development, staging, production
APP_NAME=BharatFoodSafe
APP_VERSION=0.1.0
DEBUG=true

# Database Connection
DATABASE_URL=postgresql+psycopg://foodsafety:foodsafe_pass_2026@localhost:5432/bharat_foodsafe
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30

# Security & Authentication
JWT_SECRET=super_secret_jwt_key_bharat_foodsafe_2026_change_in_prod_min_32_chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
BCRYPT_ROUNDS=12

# CORS Policy
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# Object Storage Configuration
STORAGE_PROVIDER=local                         # Options: local, s3
LOCAL_STORAGE_PATH=./uploads
S3_ENDPOINT=https://s3.ap-south-1.amazonaws.com
S3_BUCKET=bharat-foodsafe-evidence-prod
S3_REGION=ap-south-1
S3_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
S3_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
MAX_UPLOAD_MB=10

# Security Rate Limits
RATE_LIMIT_LOGIN_PER_MINUTE=5
RATE_LIMIT_UPLOAD_PER_MINUTE=20
RATE_LIMIT_API_PER_MINUTE=100

# Anomaly Engine & Operational Parameters
TASK_GENERATION_LOOKAHEAD_DAYS=1
ANOMALY_MIN_HISTORY=30
ANOMALY_REVIEW_THRESHOLD=0.70
AUDIT_RETENTION_DAYS=2555                      # 7 Years retention policy

# Logging & Observability
LOG_LEVEL=INFO                                 # Options: DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json
```

### 3.2 Frontend Configuration (`frontend/.env.example`)

```ini
# ==============================================================================
# BHARAT FOODSAFE - FRONTEND ENVIRONMENT CONFIGURATION
# ==============================================================================

VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=BharatFoodSafe
VITE_APP_VERSION=0.1.0
VITE_ENABLE_ANALYTICS=false
```

---

## 4. Build Scripts & Command Registry

### 4.1 Frontend Package Scripts (`frontend/package.json`)

```json
{
  "name": "bharat-foodsafe-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "e2e": "playwright test"
  }
}
```

### 4.2 Backend Execution Scripts (`backend/pyproject.toml`)

```toml
[project.scripts]
dev = "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start = "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"
migrate = "alembic upgrade head"
rollback = "alembic downgrade -1"
seed = "python -m database.seeds.run_all"
test = "pytest tests/ -v"
test-cov = "pytest --cov=app tests/"
lint = "ruff check app/ tests/"
format = "ruff format app/ tests/"
```

---

## 5. Dependency Lock Manifests

### 5.1 Frontend Exact Version Lock (`frontend/package.json`)

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.62.7",
    "axios": "^1.8.2",
    "clsx": "^2.1.1",
    "lucide-react": "^0.469.0",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "react-hook-form": "^7.54.2",
    "react-router-dom": "^7.3.0",
    "tailwind-merge": "^2.6.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@testing-library/react": "^16.3.3",
    "@types/node": "^22.10.2",
    "@types/react": "^19.0.2",
    "@types/react-dom": "^19.0.2",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.17.0",
    "jsdom": "^30.1.2",
    "postcss": "^8.5.3",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.2",
    "vite": "^6.0.7",
    "vitest": "^2.1.9"
  }
}
```

### 5.2 Backend Exact Version Lock (`backend/requirements.txt`)

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.0
sqlalchemy==2.0.36
psycopg[binary]==3.2.3
alembic==1.14.0
scikit-learn==1.6.0
pandas==2.2.3
numpy==2.2.1
passlib[bcrypt]==1.7.4
bcrypt==4.2.1
pyjwt==2.10.1
boto3==1.35.84
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.25.0
pytest-cov==6.0.0
ruff==0.8.4
python-multipart==0.0.20
```

---

## 6. Security Parameters & Configuration Matrix

```mermaid
flowchart LR
    Request["Incoming HTTP Request"] --> RateLimit{"Check Rate Limits (5/min login, 20/min upload)"}
    RateLimit -- Exceeded --> R429["429 Too Many Requests"]
    RateLimit -- Pass --> CorsCheck{"Validate Origin against CORS_ORIGINS"}
    CorsCheck -- Unauthorized --> R403["403 Origin Denied"]
    CorsCheck -- Valid --> JwtCheck{"Validate Bearer Access Token (15m TTL)"}
    JwtCheck -- Expired/Invalid --> R401["401 Unauthorized"]
    JwtCheck -- Valid Token --> ScopeCheck{"Verify TenantContext (restaurant_id)"}
    ScopeCheck -- Pass --> Handler["Execute Fast API Handler"]
```

| Security Aspect | Policy / Standard | Technical Implementation Parameter |
| :--- | :--- | :--- |
| **Password / PIN Hashing** | salted `bcrypt` | `Passlib 1.7.4` with `rounds=12` |
| **Access Token TTL** | Short-lived JWT | `15 Minutes` (`JWT_ACCESS_TTL_MINUTES=15`) |
| **Refresh Session TTL** | Persisted rotated sessions | `7 Days` (`JWT_REFRESH_TTL_DAYS=7`), stored as SHA-256 hash |
| **Token Family Revocation** | Reuse Detection | On duplicate refresh attempt, revokes all tokens for `token_family_id` |
| **CORS Policy** | Explicit Allow-list | Strict origin matching from `CORS_ORIGINS`; `allow_credentials=True` |
| **Login Rate Limit** | Sliding Window Counter | Max `5 attempts per minute` per IP/Phone |
| **Upload Rate Limit** | Presign Request Limit | Max `20 presign requests per minute` per user |
| **Evidence Validation** | Magic-Byte Inspection | Validates JPEG (`FF D8 FF`), PNG (`89 50 4E 47`), WebP (`52 49 46 46`) |
| **File Size Limit** | Hard Binary Cap | Max `10 MB` (`MAX_UPLOAD_MB=10`) |
| **Idempotency Key Window** | TTL Retention | Keys retained for `24 Hours` before job cleanup |

---

## 7. Git Branching & CI/CD Pipeline Specification

### 7.1 Git Branching Model
- **`main`**: Production code. Direct commits prohibited; requires pull request with 2 approved reviews + passing CI.
- **`develop`**: Integration branch for upcoming release features.
- **`feature/<issue-id>-short-description`**: Feature branches created from `develop`.
- **`hotfix/<issue-id>-short-description`**: Emergency production patches created directly from `main`.

### 7.2 GitHub Actions CI Workflow (`.github/workflows/ci.yml`)

```yaml
name: Bharat FoodSafe CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  backend-checks:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:18-alpine
        env:
          POSTGRES_USER: foodsafety
          POSTGRES_PASSWORD: foodsafe_pass_2026
          POSTGRES_DB: bharat_foodsafe_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          cd backend
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Ruff Linter & Formatter Check
        run: |
          cd backend
          ruff check app/ tests/
          ruff format --check app/ tests/

      - name: Run Database Migrations
        env:
          DATABASE_URL: postgresql+psycopg://foodsafety:foodsafe_pass_2026@localhost:5432/bharat_foodsafe_test
        run: |
          cd backend
          alembic upgrade head

      - name: Run Pytest Suite
        env:
          DATABASE_URL: postgresql+psycopg://foodsafety:foodsafe_pass_2026@localhost:5432/bharat_foodsafe_test
          JWT_SECRET: ci_test_jwt_secret_key_32_characters_minimum
        run: |
          cd backend
          pytest --cov=app tests/

  frontend-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package.json

      - name: Install Dependencies
        run: |
          cd frontend
          npm ci

      - name: TypeScript Typecheck & Linting
        run: |
          cd frontend
          npm run typecheck
          npm run lint

      - name: Run Vitest Unit Tests
        run: |
          cd frontend
          npm run test

      - name: Build Production Frontend Assets
        run: |
          cd frontend
          npm run build
```

---

## 8. Dependency Version Upgrade Policy

1. **Lock Integrity:** `package.json` and `requirements.txt` MUST specify exact version numbers without wildcards (`*`), tildes (`~`), or carets (`^`).
2. **Feature Freeze:** Dependency versions are strictly frozen during active feature implementation sprints.
3. **Scheduled Maintenance:** Dependency security updates are evaluated monthly during dedicated dependency review sprints.
4. **Upgrade Protocol:**
   - Create a dedicated branch `chore/dependency-update-<date>`.
   - Update lock manifest with exact pinned versions.
   - Run full regression testing (Unit, API, Integration, E2E) in local environment.
   - Run Alembic migration verification if database drivers or ORM libraries are changed.
   - Merge only after successful CI validation.
