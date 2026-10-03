# Bharat FoodSafe — Digital Food-Safety Assurance Platform

**Status:** Initial Project Foundation (Step 1.1 Complete)  
**Architecture:** Single Modular Monolith  
**Tech Stack:** FastAPI + Python 3.13 | React 19 + TypeScript + Vite 6 | PostgreSQL 18  

---

## 1. Project Overview

**Bharat FoodSafe** is a multi-tenant digital food-safety operational assurance and compliance platform for commercial Indian kitchens (restaurants, cloud kitchens, canteens, and caterers). It converts food safety requirements (FSSAI guidelines & SOPs) into versioned recurring tasks, captures verified digital evidence, performs deterministic safety rule evaluations, flags statistical record-integrity anomalies using machine learning (`scikit-learn`), tracks incidents & CAPA, and maintains a cryptographically verified audit hash chain.

---

## 2. Technology Stack

- **Backend:** FastAPI `0.115.6`, Python `3.13.1`, Uvicorn `0.34.0`, SQLAlchemy `2.0.36`, Alembic `1.14.0`, PostgreSQL `18.0`
- **Frontend:** React `19.2.0`, TypeScript `5.7.2`, Vite `6.0.7`, React Router `7.1.1`, Tailwind CSS `4.0.0`, TanStack Query `5.62.7`, Axios `1.7.9`, React Hook Form `7.54.2`, Zod `3.24.1`
- **Machine Learning:** scikit-learn `1.6.0`, pandas `2.2.3`, numpy `2.2.1`

---

## 3. Directory Structure

```
bharat-foodsafe/
├── backend/                # FastAPI backend modular monolith
│   ├── app/                # Application modules, core, jobs, api v1
│   ├── migrations/         # Alembic database migrations
│   ├── tests/              # Pytest test suites
│   ├── pyproject.toml      # Backend package configuration
│   └── requirements.txt    # Exact locked dependencies
├── frontend/               # React 19 + Vite SPA frontend
│   ├── src/                # Application components, layouts, features, services
│   ├── package.json        # Exact locked dependencies
│   ├── tsconfig.json       # TypeScript configuration
│   └── vite.config.ts      # Vite build configuration
├── docs/                   # Authoritative build-locked engineering specifications
│   ├── PRD_Bharat_FoodSafe.md
│   ├── APP_FLOW.md
│   ├── TECH_STACK.md
│   ├── FRONTEND_GUIDELINES.md
│   ├── BACKEND_STRUCTURE.md
│   └── IMPLEMENTATION_PLAN.md
├── ml/                     # Machine learning feature extraction & Isolation Forest artifacts
├── database/               # Database seed scripts
├── .gitignore              # Project Git ignore rules
└── README.md               # Project documentation
```

---

## 4. Development Setup Instructions

### Prerequisites
- Python 3.13+
- Node.js 22+
- PostgreSQL 18

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

### Frontend Setup
```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

---

## 5. Git Branching Strategy

- `main` → Production releases
- `develop` → Integration branch
- `feature/<issue-id>-short-description` → Feature branches
- `hotfix/<issue-id>-short-description` → Emergency hotfix patches
