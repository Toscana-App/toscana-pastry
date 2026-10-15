# Testing Rules (TDD)

## Core Philosophy
- **Red-Green-Refactor:** Write the failing test first, then the minimum code to pass, then refactor.

## Frameworks
- **Backend:** `pytest` + `pytest-asyncio` + `httpx` (for integration).
- **Frontend:** `Vitest` + `React Testing Library`.

## Requirements
- **Unit Tests:** Every logic in the `domain` layer must have >90% coverage.
- **Integration Tests:** All API endpoints in `web/modules/*` must be tested against an async DB session.
- **Mocks:** Use `unittest.mock` or `pytest-mock` for external services (WhatsApp, Email) in tests.
