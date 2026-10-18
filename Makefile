SEED ?= 1
N ?= 500

.PHONY: hooks sync test gen

hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/*

sync: hooks
	uv sync --frozen

test:
	uv run pytest -q

gen:
	uv run python -m generator gen --seed $(SEED) --n $(N)
