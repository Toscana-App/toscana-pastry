# Toscana Pastry - Agent context

Project: Toscana Pastry (SaaS para reposteras)
Architecture: Domain-Driven Design (DDD) with Hexagonal influence.
Layers: `domain`, `data`, `presentation`, `web/modules`.
Tech Stack: Next.js 15 (App Router), Chakra UI v3, FastAPI, SQLAlchemy (Async), PostgreSQL, Redis (rate limiting).
Philosophy: TDD, Clean Code, Security-first, Async-first.

## Core Rules
- **TDD Mandatory:** No implementation without a passing test.
- **Code Style:** Python (PEP8, type hints), TypeScript (strict mode, functional).
- **Security:** Strict adherence to `specs/security.md`.
- **Naming:** snake_case for files/dirs, English only.
- **Exploration:** Explore the project with CodeGraph (`codegraph_explore`, or the `codegraph` CLI). Never use `grep`, `rg`, or the Grep tool.
- **Gaps:** When something is unclear, check the code and the conversation first. If still unclear, ask the user. Never invent requirements or make changes outside the requested specifications.

## Agent guide
Working rules, personas, and the installed skills catalog:
@AGENTS.md
