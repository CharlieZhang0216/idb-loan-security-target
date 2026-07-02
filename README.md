# IDB Loan Application System — Penetration Testing Target

A deliberately vulnerable web application simulating an International Development Bank's
loan/financing application system for security assessment and penetration testing.

## Architecture

```
Frontend: Vue.js 3 + Element Plus (SPA, JWT auth)
Backend:  Python Flask + SQLAlchemy + PostgreSQL
Cache:    Redis
Proxy:    Nginx
```

## Quick Start

```bash
# Build and start all services
docker-compose up -d --build

# Access the application
http://localhost:8080

# API (direct)
http://localhost:5000/api/
```

## Demo Credentials

| Role     | Username         | Password       |
|----------|------------------|----------------|
| Borrower | br_cn_liwei      | password123    |
| Officer  | of_anderson      | officer123     |
| Risk     | ri_mueller       | risk123        |
| Admin    | ad_martinez      | admin123       |

## Services

| Service    | Port  | URL                    |
|------------|-------|------------------------|
| Frontend   | 8080  | http://localhost:8080  |
| Backend    | 5000  | http://localhost:5000  |
| PostgreSQL | 5432  | localhost:5432         |
| Redis      | 6379  | localhost:6379         |

## Key Features

- 4 user roles: Borrower, Officer, Risk Analyst, Admin
- 6-stage loan approval workflow
- Document upload with file type validation
- GraphQL API with introspection
- SSO authentication mock
- Interest rate calculator
- Audit logging (partial)

## Security Testing

This application contains deliberately included vulnerabilities for educational
and assessment purposes. See `VULNERABILITIES.md` for the complete list.

⚠️ **WARNING**: This application is intentionally insecure. Do NOT deploy to
production or expose to untrusted networks.

## Project Structure

```
idb-loan-target/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── app.py
│   ├── config.py
│   ├── models/
│   ├── routes/
│   ├── middleware/
│   └── seeds/
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
├── db/
│   └── init.sql
└── README.md
```
