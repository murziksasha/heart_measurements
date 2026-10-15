---
name: decomposer
description: Break down complex requests into atomic executable tasks to save tokens.
---

# Skill: Project Decomposer
## Objective
Break down complex requests into atomic, executable tasks.

## Process
1. **Analyze:** Identify core modules and data flow.
2. **Layering:** Separate UI, Logic, and Data layers.
3. **Tasking:** Create tasks:
   - Must be < 50 lines of code change.
   - Must be independently testable.
   - List dependencies (Task A before Task B).
4. **Format:** Output as a numbered list of "Waves" (parallel steps).

## Token Saver
- No talk, only the task list.
- Use `[D]` for dependencies, `[T]` for tests.
