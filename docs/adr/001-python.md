# ADR-001: Python with typed domain boundaries

Status: accepted for design, 2026-09-09.

Context: quantitative research and asynchronous provider integration must share tested rules.

Decision: Python 3.12+, uv, FastAPI/Pydantic transport and SQLAlchemy persistence; pure typed domain values and injected ports. Use a dedicated React/TypeScript frontend.

Alternatives: a TypeScript-only backend reduces languages but complicates reuse of the requested quantitative stack. Not selected.

Consequences: CPU-heavy research runs outside the API/trading loop. Lock dependency versions and validate reference math. Framework objects must not leak into strategies.
