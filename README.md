# IDB Loan Application System — Penetration Testing Target

A deliberately vulnerable web application simulating an international development
bank's loan/financing application system. Built for security assessment, penetration
testing exercises, and evaluating the effectiveness of manual vs. AI-driven vulnerability discovery.

> ⚠️ **WARNING**: This application is intentionally insecure. Do NOT deploy to
> production, expose to untrusted networks, or use with real data.

## Overview

This project models a realistic loan management platform — not a CTF-style challenge
with obvious vulnerabilities. Flaws are embedded in business logic, authorization
gaps, and infrastructure misconfigurations that require understanding the workflow
to discover. Automated scanners are expected to find only ~25‑30% of the issues.

### Use Cases

- Red team / penetration testing training
- Comparing human-led vs. AI-assisted vulnerability discovery
- Security tool evaluation (SAST, DAST, IAST)
- Blue team detection engineering

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Nginx   │────▶│  Vue.js  │────▶│  Flask   │────▶│PostgreSQL│
│  :8080   │     │  SPA     │     │  API     │     │  :5432   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                          │
                                          ▼
                                    ┌──────────┐
                                    │  Redis   │
                                    │  :6379   │
                                    └──────────┘
```

| Layer      | Technology                            |
|------------|---------------------------------------|
| Frontend   | Vue.js 3, Element Plus, Pinia, Vite   |
| Backend    | Python Flask, SQLAlchemy, Graphene    |
| Database   | PostgreSQL 15 (primary)               |
| Cache      | Redis 7 (sessions, rate limiting)     |
| Proxy      | Nginx (static files, reverse proxy)   |
| Auth       | JWT (HS256) + refresh tokens          |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- 4 GB free RAM

```bash
# Clone the repository
git clone https://github.com/CharlieZhang0216/idb-loan-security-target.git
cd idb-loan-security-target

# Build and start all services (backend entrypoint waits for Postgres,
# generates a JWT RSA keypair, and runs the seeder automatically)
docker-compose up -d --build

# Tail logs while services stabilise (about 20 seconds on a warm machine)
docker-compose logs -f backend

# Access the application (Nginx serves the SPA and proxies /api to Flask)
open http://localhost:8080
```

### Demo Credentials

| Role          | Username       | Password    |
|---------------|----------------|-------------|
| Borrower      | br_cn_liwei    | password123 |
| Officer       | of_anderson    | officer123  |
| Risk Analyst  | ri_mueller     | risk123     |
| Administrator | ad_martinez    | admin123    |

## Key Features

### Multi-Role System

- **Borrower** — Submit and track loan applications, respond to supplement requests
- **Officer** — Review applications, request supplements, advance approval stages
- **Risk Analyst** — Perform risk assessment and interest rate calculations
- **Administrator** — User management, system configuration, audit log review

### Six-Stage Approval Workflow

```
draft → submitted → under_review → risk_assessment → approved → disbursed
                           ↓                    ↓
                    pending_supplement       rejected
```

### Additional Features

- Document upload with file-type validation
- GraphQL API with schema introspection
- SSO authentication mock (OAuth-style callback)
- Multi-currency loan support (USD, EUR, CNY, BRL, INR, ZAR, AED, RUB)
- Interest rate calculator (amortized over loan term)
- Partial audit logging

## Security Testing

This application contains **38 deliberately placed vulnerabilities** across
multiple categories. VULN-01..20 are the "legacy" set (typical OWASP Top-10
territory that scanners partially catch); VULN-21..38 are the v2 additions,
purposely designed to defeat scanners and reward chained, business-aware
exploitation.

| Category               | Count | Examples                                                          |
|------------------------|-------|-------------------------------------------------------------------|
| Authentication / JWT   | 7     | HS256 fallback secret, alg=none, kid path traversal, session fixation, timing side-channel |
| Authorization          | 4     | Missing role checks, X-Effective-Role header impersonation, verb tampering, mass assignment |
| Injection              | 6     | Stored XSS, GraphQL raw SQL, second-order SQLi, JSON filter injection, SSTI, XXE |
| Deserialization / RCE  | 3     | Pickle backup import, pickled audit export, SSTI-to-RCE            |
| Business Logic         | 6     | Race conditions, rounding exploit, workflow bypass, currency amend post-approval, negative amounts |
| File Handling          | 4     | SVG upload, path traversal, zip-slip, XXE via inspect endpoint     |
| Information Exposure   | 4     | Verbose errors, employee ID leak, JWKS pubkey leak, backup exfil   |
| Infrastructure         | 4     | Redis exposure, Nginx misconfig, runtime config injection, verb tampering |

> A detailed catalog with hints, expected exploit paths, difficulty ratings,
> CVSS scores, and MITRE ATT&CK mappings is available in
> [`VULNERABILITIES.md`](./VULNERABILITIES.md).

### Testing Approach

Automated scanners (ZAP, Burp Suite Pro, Nuclei, semgrep) typically detect
**7-10 of the 38 vulnerabilities** — primarily the legacy set: missing
security headers, GraphQL introspection, SVG upload, verbose errors, open
Redis, permissive JSON filter, and the JWT `alg=none` primitive when a
scanner happens to try it.

The remaining **~28 vulnerabilities** require understanding of the multi-role
workflow, careful reading of source, or chaining of independent primitives
(e.g. mass-assign a `notes` field, then trigger it via GraphQL raw SQL, then
exfil via the reports PDF export). This makes the target well-suited for
head-to-head comparisons of manual pentesters, AI agents, and hybrid workflows.

The `VULNERABILITIES.md` file also includes a **grading rubric** so you can
run scored evaluations.

## Project Structure

```
├── docker-compose.yml          # Full stack orchestration
├── db/
│   └── init.sql                # Schema + seed data
├── backend/
│   ├── Dockerfile
│   ├── app.py                  # Flask application factory
│   ├── config.py               # Environment configuration
│   ├── requirements.txt
│   ├── wsgi.py                 # Gunicorn entry point
│   ├── models/                 # SQLAlchemy models
│   ├── routes/                 # API blueprints
│   │   ├── auth.py             # Login, SSO, password reset
│   │   ├── applications.py     # Loan CRUD, approvals
│   │   ├── documents.py        # File upload/download
│   │   ├── reports.py          # Portfolio reports, export
│   │   ├── admin_routes.py     # Admin panel
│   │   └── graphql_routes.py   # GraphQL endpoint
│   ├── middleware/             # Auth decorators, audit logging
│   └── seeds/                  # Data seeding scripts
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf              # Nginx with deliberate misconfigs
│   └── src/
│       ├── main.js
│       ├── router/             # Vue Router configuration
│       ├── store/              # Pinia state management
│       ├── components/         # Layout, sidebar, header
│       └── views/
│           ├── shared/         # Login, Dashboard, Applications
│           ├── borrower/       # Create Application
│           ├── officer/        # Review Queue
│           ├── risk/           # Risk Assessment, Calculator
│           └── admin/          # Admin Panel, User Management
└── README.md
```

## License

This project is provided for educational and security research purposes only.
