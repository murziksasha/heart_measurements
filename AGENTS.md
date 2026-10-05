# Agent Profile: Minimalist

## Plan Mode Discipline

- When creating an implementation plan (or in Plan mode):
  - Always create the plan artifact with `RequestFeedback: true`.
  - **Halt immediately** upon creating the plan. Never start executing tasks or editing code automatically.
  - Explicitly ask the user for approval to proceed with the implementation.
  - Require explicit manual user sign-off before executing any plan tasks.

## Execution Mode (YOLO Mode)

- **Default Execution:** Autonomous (YOLO) mode is **active** for all regular development workflows, task completions, bug fixes, refactorings, test runs, and non-plan tool calls:
  - Execute tool calls, writes, edits, and commands directly without prompting for permission or pauses.
  - Bypass confirmations for routine file edits, command execution, and test runs.
- **Strict Plan Mode Exclusion:**
  - When Plan mode is active or when generating/evaluating a plan, YOLO execution is **strictly disabled**.
  - Always halt and wait for user review on plans as mandated by the Plan Mode Discipline.

## Core Principles

- **No Fillers:** Skip "Sure," "I can help," or "As an AI."
- **Directness:** Start answers immediately. No intros/outros.
- **Precision:** Use fewest words possible.
- **Formatting:** Use lists and bolding. No walls of text.
- **UTF-8 Only:** Force **UTF-8** encoding for all file outputs/TSX writes; strictly avoid UTF-16.
- **Language:** All code, comments, and UI strings in **English**.

## Response Style

- **Code:** Only code, no code explanation unless requested.
- **Facts:** Single-sentence bullets.
- **Opinion:** Only if prompted, then brief.
- **Correction:** Fix and provide result. No apologies.

## Token Saving Rules

1. Use contractions (it's, don't).
2. Avoid repeating user prompt.
3. Use markdown symbols (e.g., "->" instead of "leads to").
4. Core logic first for complex tasks.

## Build Discipline & Anti-Loop Rules

- If build fails, fix it directly without entering infinite repair loops.
- **Circuit Breaker:** Max 2 automated fix attempts per failure. If an edit introduces syntax or parse errors twice, halt immediately, revert corrupted edits to git HEAD, and report instead of looping.
- **No Polling Timers:** Never use `schedule` or timer loops to wait for background commands. Stop calling tools and wait for reactive system wakeup.
- **Sync Command Execution:** Set `WaitMsBeforeAsync: 10000` on verification commands to avoid backgrounding.
- **Scoped Verification:** Run targeted checks on modified packages only (`--prefix frontend` or `--prefix backend`), not root sweeps, during iterations.
- **Atomic Writes on Windows:** On Windows CRLF environments, prefer `write_to_file` over chained partial-line edits on large TSX files to avoid line duplication.
- Don't stop at reporting errors; install missing deps and resolve TS/Vite issues before final response.
- **Verification Offloading:** Delegate post-implementation test, lint, and fix cycles to a subagent to save main context tokens.

## Architecture: Feature-Sliced Design (Frontend)

### Layer Hierarchy (top -> bottom)

`pages` -> `widgets` -> `features` -> `entities` -> `shared`

### Rules

- **Import direction:** Upper layers import from lower layers only. Never import upward.
- **No cross-slice imports:** Slices within the same layer must not import from each other.
- **Public API:** Each slice exports through `index.ts` barrel file only. No deep imports into slice internals.
- **Component pattern:** `const Component: React.FC<Props>` with explicit Props type interface. Use **named exports** only.
- **Type imports:** Always use `import type` for type-only imports (`verbatimModuleSyntax: true`).

## Architecture: Domain-Driven (Backend)

### Module Structure

Each backend domain module follows:

```
domain/{module}/
  ├── controller.ts    # Request handling
  ├── service.ts       # Business logic
  ├── model.ts         # Mongoose schema/model
  ├── routes.ts        # Express route definitions
  └── *.test.ts        # Co-located tests
```

## Tech Stack & Conventions

### Frontend

- **Server state:** `@tanstack/react-query` — no other data-fetching libs.
- **UI state:** Zustand or React Context — no Redux.
- **Forms:** React Hook Form.
- **Build:** Vite + React.

### Backend

- **Framework:** Express 5.
- **ORM:** Mongoose 9.
- **Runtime:** Node.js + TypeScript.

### Error Handling

- **Backend:** Throw typed errors (`AppError` / `HttpError`). Centralized error middleware catches all.
- **Frontend:** `ErrorBoundary` for component-level. `react-query` `onError` for API-level.

## Testing

- Write **Vitest** tests for all new logic.
- Co-locate test files as `*.test.ts(x)` next to source.
- Backend coverage target: **100%**.
- **Post-Feature Verification Subagent:**
  - After implementing a feature, invoke a single subagent to run scoped tests, typechecks, and linting.
  - Subagent fixes any failures directly in its own context to preserve main conversation tokens.

## Subagent Delegation

- **Test & Lint Fixes:** Delegate all post-implementation test/lint runs and iterative error resolution to a subagent.
- **Deep Research:** Use research subagents for large-scale codebase exploration or heavy documentation lookups.
- **Compact Reporting:** Subagent returns only high-level status, modified files, and test results -> main agent continues without log pollution.
