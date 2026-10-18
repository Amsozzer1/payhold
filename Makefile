SEED ?= 1
N ?= 500
DDB_IMAGE := amazon/dynamodb-local:3.3.1
DDB_ENV := AWS_ACCESS_KEY_ID=dummy AWS_SECRET_ACCESS_KEY=dummy AWS_DEFAULT_REGION=us-east-1

.PHONY: hooks sync test gen gen-heldout roundtrip dev eval ddb-up ddb-down test-integration payout-trials

hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/*

sync: hooks
	uv sync --frozen

test:
	uv run pytest -q

gen:
	uv run python -m generator gen --seed $(SEED) --n $(N)

# Held-out look-alikes for an existing seed (separate files; the main stream is untouched), then validate them.
gen-heldout:
	[ -f data/seed-$(SEED)/truth.json ] || uv run python -m generator gen --seed $(SEED) --n $(N)
	uv run python -m generator gen-heldout --seed $(SEED)
	uv run python -m generator.validate_heldout data/seed-$(SEED)

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

# DynamoDB Local, pinned, in memory. Dummy credentials: nothing here talks to AWS.
ddb-up:
	docker rm -f payhold-ddb >/dev/null 2>&1 || true
	docker run -d --rm --name payhold-ddb -p 8000:8000 $(DDB_IMAGE) -jar DynamoDBLocal.jar -sharedDb -inMemory

ddb-down:
	docker rm -f payhold-ddb >/dev/null 2>&1 || true

test-integration: ddb-up
	$(DDB_ENV) uv run pytest -q -m integration; status=$$?; $(MAKE) ddb-down; exit $$status

# Duplicate-payout trials (100 per scenario) plus the read-then-write control, raw output in results/.
payout-trials: ddb-up
	$(DDB_ENV) uv run python -m eval.payout_trials --trials 100 --out results/payout_trials.json \
	  && $(DDB_ENV) uv run python -m eval.payout_trials --control --trials 100 --out results/payout_naive_control.json; \
	  status=$$?; $(MAKE) ddb-down; exit $$status

# Report seeds 1-5 through both deciders. Local only: refuses a dirty tree or decision code that moved since the freeze.
eval:
	for s in 1 2 3 4 5; do $(MAKE) --no-print-directory gen-heldout SEED=$$s || exit 1; done
	uv run python -m eval.run --seeds 1 2 3 4 5 --n $(N)
