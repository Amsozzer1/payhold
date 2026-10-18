SEED ?= 1
N ?= 500

.PHONY: hooks sync test gen roundtrip dev

hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/*

sync: hooks
	uv sync --frozen

test:
	uv run pytest -q

gen:
	uv run python -m generator gen --seed $(SEED) --n $(N)

# Extraction round-trip on seed 1 and the dev seeds, every field, failures listed by field.
roundtrip:
	for s in 1 101 102; do [ -f data/seed-$$s/truth.json ] || uv run python -m generator gen --seed $$s --n $(N); done
	uv run python -m eval.roundtrip data/seed-1 data/seed-101 data/seed-102 | tee results/roundtrip.txt

# Who catches what on the dev seeds (101, 102). Thresholds are tuned here, never on report seeds.
dev:
	for s in 101 102; do [ -f data/seed-$$s/truth.json ] || uv run python -m generator gen --seed $$s --n $(N); done
	{ echo "# Dev seeds 101-102: who catches what"; echo; echo "Synthetic packets with planted issues. Counts are packets held, out of n."; echo; \
	  uv run python -m eval.whocatches data/seed-101 data/seed-102; } > results/dev_who_catches.md
	cat results/dev_who_catches.md
