.PHONY: dev test test-unit test-risk test-integration test-e2e lint
dev:
	uv run python scripts/dev.py
test: test-unit test-integration test-e2e
test-unit:
	uv run pytest tests/unit tests/property
test-risk:
	uv run pytest tests/unit/test_control.py tests/property
test-integration:
	uv run pytest tests/integration
test-e2e:
	pnpm --dir apps/web test:e2e
lint:
	uv run ruff check apps wallybot migrations scripts tests
	uv run pyright
	pnpm --dir apps/web lint
