# Agent Guide

Toscana Pastry agent rules. Project context and stack live in `CLAUDE.md` and `.claude/rules/`.

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

## Personas

- **Code Reviewer:** Expert in DDD and Clean Code.
- **Security Auditor:** Specialist in OWASP and the 20 security items defined for Toscana Pastry.

## Skills

Installed in `.claude/skills/<name>/SKILL.md`. Load the matching skill before starting a task it covers. Unsure which fits? Use `ask-matt`.

### Planning and specs
- `grill-me` / `grilling`: relentless interview to stress-test a plan or idea.
- `grill-with-docs`: grilling that also writes ADRs and glossary.
- `loop-me`: grill the user about specs for workflows to build.
- `to-spec`: turn the conversation into a spec on the issue tracker.
- `to-tickets`: break a plan or spec into tracer-bullet tickets with blocking edges.
- `to-questionnaire`: turn an open decision into a questionnaire for someone else.
- `wayfinder`: plan work larger than one session as a map of decision tickets.
- `technical-project-kickoff`: technical plan from specs, stack, TDD and skills.
- `triage`: move issues and external PRs through triage roles into agent-ready briefs.
- `setup-matt-pocock-skills`: configure issue tracker, triage labels and domain docs; run once before the engineering skills.

### Implementation
- `implement` / `implement-spec`: build from a spec or tickets (`implement-spec` follows `to-spec` + `to-tickets`).
- `tdd`: red-green-refactor for features and bug fixes.
- `prototype`: throwaway prototype to answer a design question.
- `senior-backend`: API design, DB optimization, auth, backend business logic.
- `nextjs-app-router-patterns`: App Router, Server Components, streaming, data fetching.
- `vercel-react-best-practices`: React/Next.js performance patterns.
- `design-by-contract`: preconditions, postconditions and invariants.
- `pick-ui-library`: pick a frontend library from a curated list (explicit invocation only).

### Architecture and domain
- `codebase-design`: deep-module vocabulary, interfaces, seams, testability.
- `improve-codebase-architecture`: scan for deepening opportunities, HTML report, then grill one.
- `domain-modeling`: domain terminology, `GLOSSARY.md`, ADRs.
- `setup-ts-deep-modules`: dependency-cruiser deep-module boundaries for TypeScript (user-invoked).

### Debugging, testing and review
- `diagnosing-bugs`: diagnosis loop for hard bugs and performance regressions.
- `code-review`: two-axis review (standards + spec) of the diff since a fixed point.
- `e2e-testing-patterns`: Playwright/Cypress E2E suites, flaky tests.
- `webapp-testing`: drive the local web app with Playwright, screenshots, browser logs.
- `break-ui`: stress-test UI with worst-case data and report breakage.
- `migrate-to-shoehorn`: replace `as` assertions in tests with shoehorn.

### UI and motion
- `emil-design-eng`: UI polish and component design details.
- `animate`: build an animation from scratch.
- `animation-performance`: fix janky animations, frame budget.
- `animation-vocabulary`: name a described motion effect.
- `find-animation-opportunities`: propose where motion belongs (read-only).
- `improve-animations`: audit motion code into a prioritized plan (read-only).

### Delivery and tooling
- `pr`: write a PR body.
- `setup-pre-commit`: Husky + lint-staged, typecheck and tests on commit.
- `git-guardrails-claude-code`: hooks that block destructive git commands.
- `wizard`: interactive bash wizard for steps only a human can perform.
- `find-skills`: discover and install new skills.

### Research, writing and docs
- `research`: investigate primary sources, save findings as Markdown.
- `writing-for-agents`: write skills, `AGENTS.md` or `CLAUDE.md`.
- `writing-fragments` / `writing-shape` / `writing-beats`: article writing (explore, shape, beats).
- `teach`: teach the user a concept within this workspace.

### Session flow
- `handoff`: compact the conversation into a handoff doc.
- `claude-handoff`: hand the conversation to a fresh background agent.
- `chief-of-staff`: pursue a long goal in one session by coordinating subagents.
- `retro`: retrospective on a coding session.
- `wait-what`: re-pitch a message that did not land.
- `scaffold-exercises`: exercise directory structures for courses.
