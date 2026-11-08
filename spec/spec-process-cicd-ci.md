---
title: CI/CD Workflow Specification - CI
version: 1.0
date_created: 2026-11-07
last_updated: 2026-11-07
owner: DevOps Team
tags: [process, cicd, github-actions, automation, ci, nextjs, fastapi, postgres]
---

## Workflow Overview

**Purpose**: Validate frontend and backend on every change reaching `main` or any pull request, so a broken commit never lands in the stacked phase branches.
**Trigger Events**: `push` to `main`; `pull_request` (all branches, including stacked bases).
**Target Environments**: ephemeral CI runners only. No deployment, no publishing, no secrets.

## Execution Flow Diagram

```mermaid
graph TD
    T[Trigger: push to main / pull_request] --> F[Frontend job]
    T --> B[Backend job]
    F --> F1[Install locked deps]
    F1 --> F2[Lint] --> F3[Typecheck] --> F4[Unit tests] --> F5[Build]
    B --> B0[Postgres 16 service (toscana_test)]
    B0 --> B1[Install locked deps] --> B2[Full pytest suite]
    F5 --> E[Run complete]
    B2 --> E

    style T fill:#e1f5fe
    style E fill:#e8f5e8
```

## Jobs & Dependencies

| Job Name | Purpose | Dependencies | Execution Context |
|----------|---------|--------------|-------------------|
| frontend | Lint, typecheck, unit tests, production build of the Next.js app | none | ubuntu-latest, Node 22 |
| backend | Full pytest suite (unit + integration) against a real Postgres | none | ubuntu-latest, Python 3.12, Postgres 16 service |

Jobs run in parallel; a failure in either job fails the run. There is no dependency between them.

## Requirements Matrix

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| REQ-001 | Frontend lint passes with zero errors | High | Lint step exits 0 on the `src/` tree |
| REQ-002 | Frontend typecheck passes | High | Strict TypeScript check exits 0, no emit |
| REQ-003 | Frontend unit tests pass | High | Entire Vitest suite green |
| REQ-004 | Frontend production build succeeds | High | `next build` exits 0 (no backend required) |
| REQ-005 | Backend suite runs against a dedicated Postgres | High | Every test in the suite executes; suite exits 0 |
| REQ-006 | Backend test database is isolated and rebuilt | High | Dedicated `*_test` database; schema rebuilt once per session; every integration test starts from empty tables |
| REQ-007 | Dependency installs are reproducible | High | Frontend installs strictly from the committed lockfile; backend installs strictly from the committed lockfile (frozen) |

### Security Requirements

| ID | Requirement | Implementation Constraint |
|----|-------------|---------------------------|
| SEC-001 | Read-only access to repository contents | Workflow declares minimal permissions (contents: read) |
| SEC-002 | No secrets consumed | The workflow reads no secrets and never prints credentials |
| SEC-003 | Supply-chain containment | Third-party actions pinned to major versions; dependency trees come from committed lockfiles only, never from registry ranges |
| SEC-004 | Test database safety | The backend refuses to run against any database whose name does not end in `_test` (enforced in test code, not in CI) |

### Performance Requirements

| ID | Metric | Target | Measurement Method |
|----|--------|--------|--------------------|
| PERF-001 | Frontend job duration | ≤ 10 min | Run duration on the Actions page |
| PERF-002 | Backend job duration | ≤ 15 min | Run duration on the Actions page |
| PERF-003 | Whole-run wall time | ≤ 20 min | Jobs run in parallel; wall time ≈ max(job times) |

## Input/Output Contracts

### Inputs

```yaml
# Triggers
branches: [main]          # push trigger scope
events: [push, pull_request]

# Job environment (backend only, job-scoped, not repository secrets)
TEST_DATABASE_URL: string  # Purpose: asyncpg DSN of the isolated *_test database
```

No user-facing inputs, no workflow_dispatch parameters, no required repository variables.

### Outputs

```yaml
# Per-run
ci_status: success | failure   # The only output; consumed as the PR check gate
```

No artifacts are produced or consumed (build output is disposable).

### Secrets & Variables

| Type | Name | Purpose | Scope |
|------|------|---------|-------|
| — | — | none | — |

## Execution Constraints

### Runtime Constraints

- **Timeout**: 15 min (frontend), 20 min (backend); a hung step fails the job.
- **Concurrency**: one run per branch; a newer run on the same branch cancels the in-progress one.
- **Resource Limits**: default 2-vCPU runner; no self-hosted runners.

### Environmental Constraints

- **Runner Requirements**: `ubuntu-latest` hosted runner.
- **Network Access**: npm registry, PyPI, Docker Hub (Postgres image), GitHub. No access to internal services.
- **Permissions**: contents read only.
- **System dependencies (backend)**: PDF-rendering native libraries (Pango stack, Cairo, GDK-Pixbuf, libffi) and text fonts, installed at job start because the hosted runner image does not guarantee them.

## Error Handling Strategy

| Error Type | Response | Recovery Action |
|------------|----------|-----------------|
| Lint / typecheck failure | Job fails, run red | Fix locally, re-push the branch (auto re-run on push) |
| Test failure | Job fails, suite output in logs | Fix locally; the run re-triggers on the next push |
| Build failure | Job fails | Fix locally; check for stale generated types before blaming the source |
| Dependency install failure | Job fails | Usually lockfile drift or registry issue; regenerate the lockfile locally and commit it |
| Postgres service not ready | Health check retries; job fails if it never becomes ready | Re-run the workflow (transient) |
| Lockfile out of sync with the manifest | Frozen install fails explicitly | Regenerate the lockfile locally, commit, re-push |

## Quality Gates

### Gate Definitions

| Gate | Criteria | Bypass Conditions |
|------|----------|-------------------|
| Code quality (frontend) | Lint 0 errors + strict typecheck 0 errors | none |
| Test coverage | 100% of committed tests green (no numeric coverage threshold) | none |
| Build integrity | Production build succeeds | none |
| Backend behavior | Full suite green against real Postgres | none |

The gate is binary: any red job blocks the PR. There is no override in the workflow itself.

## Monitoring & Observability

### Key Metrics

- **Success Rate**: share of green runs; investigate any run failing on a step that passed locally.
- **Execution Time**: trend of job durations; a sustained jump signals dependency bloat or a slow test.
- **Resource Usage**: runner minutes per run (visible on the Actions page).

### Alerting

| Condition | Severity | Notification Target |
|-----------|----------|---------------------|
| Run red on `main` (push trigger) | High | immediate — fix before further merges |
| Run red on a PR | Medium | author, via the PR check |
| Two consecutive red runs on the same branch | Medium | investigate runner/dependency drift, not the code |

## Integration Points

### External Systems

| System | Integration Type | Data Exchange | SLA Requirements |
|--------|------------------|---------------|------------------|
| npm registry | dependency source | lockfile-locked tree | availability at run time |
| PyPI | dependency source | lockfile-locked tree | availability at run time |
| Docker Hub | Postgres 16 service image | pull | availability at run time |

### Dependent Workflows

| Workflow | Relationship | Trigger Mechanism |
|----------|--------------|-------------------|
| (none) | standalone | — |

## Compliance & Governance

### Audit Requirements

- **Execution Logs**: retained with the run by the platform; no extra retention.
- **Approval Gates**: PR merge is the human gate; the CI check is required input to it.
- **Change Control**: update this spec first, then the workflow, in the same PR.

### Security Controls

- **Access Control**: workflow runs with read-only contents permission; no self-hosted runners, no checkout of external repositories.
- **Secret Management**: not applicable (no secrets).
- **Vulnerability Scanning**: out of scope for v1 (see Version History).

## Edge Cases & Exceptions

### Scenario Matrix

| Scenario | Expected Behavior | Validation Method |
|----------|-------------------|-------------------|
| PR stacked on a non-`main` branch (standard phase flow) | `pull_request` trigger fires; both jobs validate the head branch | Open a stacked PR, observe run |
| Multiple pushes to the same branch in quick succession | Older runs cancelled by concurrency group | Push twice rapidly, observe cancellation |
| Backend lockfile regenerated out of band | Frozen install fails until the new lockfile is committed | Corrupt lock locally, expect explicit failure |
| New backend model/table added | Schema rebuilt from ORM metadata per session — no migration step needed in CI | Add a model in a test, suite green |
| `pdfgenerator` service merged into `main` (PR #48) | Add a dedicated job (Python 3.12, uv, its own test suite); no Postgres needed unless its tests require it | Update this spec + workflow in the same PR |
| E2E suite (`frontend/e2e/`) | Out of scope for v1: needs a live app + live backend; manual script today | — |

## Validation Criteria

### Workflow Validation

- **VLD-001**: A push to `main` starts exactly one run with both jobs.
- **VLD-002**: A PR (including stacked bases) starts a run whose status becomes the PR check.
- **VLD-003**: A deliberately broken lint rule fails the frontend job at the Lint step.
- **VLD-004**: A deliberately failing test fails the backend job with the failing test named in the log.
- **VLD-005**: The backend job never touches a database that is not `*_test`.

### Performance Benchmarks

- **PERF-001/002/003**: as in the Performance Requirements matrix.

## Change Management

### Update Process

1. **Specification Update**: modify this document first.
2. **Review & Approval**: normal PR review (CI change = infra change).
3. **Implementation**: apply changes to the workflow in the same PR.
4. **Testing**: the PR's own run is the smoke test; add a scratch-branch red test for gate behavior changes (VLD-003/004).
5. **Deployment**: merge to `main`; the next push validates the new workflow in production.

### Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-11-07 | Initial specification: frontend + backend CI, no deploy, no e2e, no scanning | Hermes (for Gaspar) |

## Related Specifications

- `docs/specs/master_plan.md` — phase plan (CI validates the branches that deliver each phase)
- `AGENTS.md` — agent working rules (TDD, local gates that this pipeline mirrors)
