# Project Brief — [PROJECT NAME]
<!-- 
  This file is the shared briefing document for the Antigravity Swarm.
  Fill this out at the start of every new project BEFORE running the planner.
  All agents receive this document as part of their shared state injection.
-->

## 1. Project Overview
**Name:** [Project Name]
**Type:** [web app / API / CLI tool / library / etc.]
**Description:**
> Briefly describe what this project does in 2-3 sentences.

## 2. Technology Stack
| Layer | Technology |
|---|---|
| Language | [e.g., Python 3.11 / TypeScript / Go] |
| Framework | [e.g., FastAPI / Next.js / Gin] |
| Database | [e.g., PostgreSQL / SQLite / None] |
| Frontend | [e.g., React / Vue / HTML/CSS] |
| Testing | [e.g., PyTest / Jest / Vitest] |
| Deployment | [e.g., Docker / Vercel / Bare metal] |

## 3. Project Structure
```
project-root/
  src/          # Application source code
  tests/        # Automated tests
  docs/         # Documentation
  .env.example  # Environment variable template
  README.md     # Project readme
```

## 4. Coding Conventions
- **Indentation:** [2 spaces / 4 spaces / tabs]
- **Naming:** [camelCase / snake_case / PascalCase]
- **Comments:** [JSDoc / docstrings / inline]
- **Branch Strategy:** [main + feature branches / trunk-based]

## 5. Environment Variables
| Variable | Description | Required |
|---|---|---|
| `PORT` | Server port | No (default: 3000) |
| `DATABASE_URL` | Database connection string | Yes |

## 6. Key Constraints & Decisions
<!-- Document any hard rules agents must follow -->
- [ ] Must not introduce new dependencies without documenting them in findings.md
- [ ] All API endpoints must validate inputs before processing
- [ ] Secrets must never be hardcoded; always use environment variables
- [ ] Error messages shown to users must not expose internal stack traces

## 7. Out of Scope (For This Mission)
<!-- List explicitly what agents should NOT do -->
- Authentication system (handled separately)
- Payment processing
- Email notifications
