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

# Build and start all services
docker-compose up -d --build

# Initialize demo passwords
docker-compose exec backend python seeds/hash_passwords.py

# Access the application
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

This application contains **20 deliberately placed vulnerabilities** across multiple
categories:

| Category            | Count | Examples                                        |
|---------------------|-------|-------------------------------------------------|
| Authentication      | 3     | Weak password reset, open redirect, no rate limit |
| Authorization       | 3     | Missing role checks, status transition bypass   |
| Injection           | 3     | Stored XSS, JSON injection, GraphQL introspection |
| Business Logic      | 4     | Race condition, rounding exploit, workflow bypass |
| File Handling       | 2     | SVG upload, path traversal                      |
| Information Exposure| 3     | Verbose errors, employee ID leak, config exposure |
| Infrastructure      | 2     | Redis exposure, Nginx misconfigurations         |

> 📋 A detailed vulnerability catalog is available in `VULNERABILITIES.md`.

### Testing Approach

Automated scanners (ZAP, Burp Suite, Nuclei) typically detect **5-7 vulnerabilities**
— primarily the low-hanging fruit like missing security headers, open Swagger docs,
and GraphQL introspection.

The remaining **13-15 vulnerabilities** require understanding of the business
logic, multi-step exploitation, or chaining of weaknesses — making this an ideal
target for comparing automated tools against skilled human or AI-assisted testing.

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
