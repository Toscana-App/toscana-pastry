# Code Style Rules

## General
- Use English for all code (variables, functions, classes, comments).
- Directory/File names: snake_case.

## Python (Backend)
- Follow PEP8.
- **Strict Typing:** Use type hints for every function signature.
- **Async/Await:** All I/O operations (DB, API, File System) MUST be `async/await`.
- No magic numbers; use constants or configuration.

## TypeScript (Frontend)
- Use strict typing. Avoid `any`.
- Functional components with hooks.
- Tailwind/Chakra UI patterns.

## Architecture Enforcement
- Domain models MUST NOT depend on the database layer.
- Repositories in `data` layer handle SQL/ORM details.
- Services in `domain` handle business rules.
