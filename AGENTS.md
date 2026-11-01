# Agent Guide

Toscana Pastry agent context and rules. Single source of truth for every agent: Pi reads this file directly, Claude Code imports it from `CLAUDE.md`.

## Project

Project: Toscana Pastry (SaaS para reposteras)
Architecture: Domain-Driven Design (DDD) with Hexagonal influence.
Layers: `domain`, `data`, `presentation`, `web/modules`.
Tech Stack: Next.js 15 (App Router), Chakra UI v3, FastAPI, SQLAlchemy (Async), PostgreSQL, Redis (rate limiting).
Philosophy: TDD, Clean Code, Security-first, Async-first.

## Core rules

- **TDD Mandatory:** No implementation without a passing test.
- **Code Style:** Python (PEP8, type hints), TypeScript (strict mode, functional).
- **Security:** Strict adherence to `docs/specs/security.md`.
- **Naming:** snake_case for files/dirs, English only.
- **Exploration:** Explore the project with CodeGraph (`codegraph_explore`, or the `codegraph` CLI). Never use `grep`, `rg`, or the Grep tool.
- **Gaps:** When something is unclear, check the code and the conversation first. If still unclear, ask the user. Never invent requirements or make changes outside the requested specifications.

## Working rules

### Explore with CodeGraph

Explore the project through CodeGraph: the `codegraph_explore` MCP tool first, the `codegraph` CLI (`query`, `explore`, `callers`, `callees`, `impact`) when MCP is unavailable. Run `codegraph sync -q .` before CLI reads.
Hard guardrail: never search with `grep`, `rg`, or the Grep tool. Open a known path with a file read; every search goes through CodeGraph.

### Resolve gaps before acting

A request rarely carries every detail: part is in the message, part in the code, part still in the user's head. Fill each gap in this order:

1. **Code and conversation**: look for the answer in the codebase and in what was already discussed.
2. **Ask**: if the gap remains, ask the user one focused question and wait for the answer.
3. **Stay in scope**: change only what was requested. Keep requirements to what the user specified; a plausible assumption is still an assumption.

The more work is delegated, the more this boundary matters.

## Code style

### General
- Use English for all code (variables, functions, classes, comments).
- Directory/File names: snake_case.

### Python (Backend)
- Follow PEP8.
- **Strict Typing:** Use type hints for every function signature.
- **Async/Await:** All I/O operations (DB, API, File System) MUST be `async/await`.
- No magic numbers; use constants or configuration.

### TypeScript (Frontend)
- Use strict typing. Avoid `any`.
- Functional components with hooks.
- Tailwind/Chakra UI patterns.

### Architecture enforcement
- Domain models MUST NOT depend on the database layer.
- Repositories in `data` layer handle SQL/ORM details.
- Services in `domain` handle business rules.

## API conventions

### General
- **Protocol:** RESTful.
- **Version:** `/api/v1/...`
- **Format:** `application/json`.
- **Error Handling:** Use `problem+json` (RFC 7807).

### Standards
- **Pagination:** `?page={number}&page_size={size}` (Default 50, Max 200).
- **Rate Limiting:** Enforced via middleware (headers: `X-RateLimit-*`).
- **Authentication:** JWT in `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
- **Concurrency:** All endpoints must be `async`.

## Testing (TDD)

### Core philosophy
- **Red-Green-Refactor:** Write the failing test first, then the minimum code to pass, then refactor.

### Frameworks
- **Backend:** `pytest` + `pytest-asyncio` + `httpx` (for integration).
- **Frontend:** `Vitest` + `React Testing Library`.

### Requirements
- **Unit Tests:** Every logic in the `domain` layer must have >90% coverage.
- **Integration Tests:** All API endpoints in `web/modules/*` must be tested against an async DB session.
- **Mocks:** Use `unittest.mock` or `pytest-mock` for external services (WhatsApp, Email) in tests.

## Personas

- **Code Reviewer:** Expert in DDD and Clean Code.
- **Security Auditor:** Specialist in OWASP and the 20 security items defined for Toscana Pastry.

## Skills

Project skills live in `.claude/skills/<name>/SKILL.md` (Claude Code reads it natively; Pi loads it through `.pi/settings.json`). Load the matching skill before starting a task it covers. Unsure which fits? Use `ask-matt`.
