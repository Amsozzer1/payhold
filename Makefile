.PHONY: hooks sync test

hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/*

sync: hooks
	uv sync --frozen

test:
	uv run pytest -q
