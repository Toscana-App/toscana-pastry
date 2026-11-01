---
name: technical-project-kickoff
description: Prepares technical plans from specs, stack, TDD and skills.
---

# Technical Project Kickoff

This skill provides a structured procedure to transition from abstract specifications to a concrete, test-driven technical implementation plan.

## When to Use This Skill

Use this skill when starting a new feature, a new project, or a significant phase transition where high-level requirements need to be converted into a technical roadmap.

## Procedure

### 1. Specification Audit
- Read all files in the current `specs/` directory.
- Build a comprehensive technical context: requirements, business rules, and security constraints.
- **Pitfall:** Do not rely on memory or previous turn summaries alone; re-read the files to ensure the plan accounts for the latest changes.

### 2. Stack and Architecture Mapping
- Validate that the chosen tech stack (e.g., Next.js, FastAPI, Postgres) supports all functional and non-functional requirements.
- Map requirements to the defined architecture (e.g., Domain-Driven Design layers: `domain`, `data`, `presentation`).
- Identify potential architectural mismatches early.

### 3. TDD (Test-Driven Development) Strategy
- Define the testing scope for each technical layer:
  - **Domain Layer:** Unit tests (business logic, pure functions).
  - **Data/Infrastructure Layer:** Integration tests (repository implementations, DB constraints).
  - **Presentation/Web Layer:** Contract testing (API endpoints) and UI/E2E tests (user flows).
- Specify the testing framework for each layer (e.g., `pytest`, `Vitest`).

### 4. Agentic Skill Curation
- Use `find-skills` to discover specialized agent capabilities needed for implementation (e.g., design, testing, debugging).
- **Vetting Protocol:**
  - **Reputation:** Prioritize skills with high install counts (1K+).
  - **Authority:** Prefer official sources (e.g., `vercel-labs`, `anthropics`).
  - **Security:** Verify the skill's purpose aligns with the project's security standards.
- Present the vetted list to the user for approval.

### 5. Implementation Briefing
- Deliver a consolidated briefing containing:
  - The technical implementation roadmap.
  - The confirmed TDD strategy.
  - The proposed skillset for the execution.

## Pitfalls

- **Hallucinated Capabilities:** Do not recommend a skill based on its name alone; always verify existence and reputation using `find-skills`.
- **Ignoring Security:** Security constraints are not optional; they must be integrated into the technical design from Step 1.
- **Ignoring the User's Specifics:** Always respect user-defined naming conventions (e.g., project branding) and specific technology preferences throughout the plan.
