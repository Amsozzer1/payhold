import os
import time

import pytest

from eval import payout_trials as pt


def check(result: dict, trials: int, clients: int) -> None:
    a, b, c = result["a"], result["b"], result["c"]
    assert a["attempts_per_trial"] == [1] * trials
    assert a["results_total"] == {"duplicate": (clients - 1) * trials, "sent": trials}
    assert b["attempts_per_trial"] == [1] * trials
    assert b["results_total"].get("sent", 0) >= trials
    assert set(b["results_total"]) <= {"sent", "in_progress"}
    assert sum(b["results_total"].values()) == clients * trials
    assert c["attempts_per_trial"] == [2] * trials
    assert c["sends_per_trial"] == [1] * trials
    assert c["retry_during_lease"] == {"in_progress": trials}
    assert c["retry_after_lease"] == {"sent": trials}
    assert c["final_status"] == {"sent": trials}


def test_payout_smoke_in_memory():
    check(pt.run(pt.memory_stores(), trials=1), 1, pt.CLIENTS)


@pytest.fixture(scope="module")
def dynamo():
    """Polls until DynamoDB Local answers, then builds the 50 clients."""
    from payhold.store.dynamo import client

    os.environ.setdefault("AWS_ACCESS_KEY_ID", "dummy")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "dummy")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    deadline = time.monotonic() + 60
    while True:
        try:
            client().list_tables()
            break
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)
    return pt.dynamo_stores()


@pytest.mark.integration
def test_payout_100_trials_dynamodb_local(dynamo):
    check(pt.run(dynamo, trials=100), 100, pt.CLIENTS)


@pytest.mark.integration
def test_dynamo_store_seen_and_audit(dynamo):
    from payhold.store.base import Seen

    store = dynamo[0]
    pk = pt.fresh_key("seen", 0)
    store.put_seen(Seen(pk, "F1", "R1", "requested", "2026-03-02T06:00:00Z", "4820157"))
    store.put_seen(Seen(pk, "F2", "R2", "requested", "2026-03-02T06:10:00Z", "4820157"))
    store.set_status(pk, "F1", "R1", "paid")
    assert [(s.request_id, s.status) for s in store.seen(pk)] == [("R1", "paid"), ("R2", "requested")]
    store.append_audit(pk, "2026-03-02T06:00:00Z", {"event": "decision", "decision": "pay"})
    store.append_audit(pk, "2026-03-02T06:00:00Z", {"event": "decision", "decision": "hold"})
    assert [e["decision"] for e in store.audit(pk)] == ["pay", "hold"]


@pytest.mark.integration
def test_pipeline_on_dynamodb_matches_memory(dynamo, seed1):
    import json
    import uuid

    from payhold.engine import Payhold
    from payhold.extract.pdf import extract_packet
    from payhold.store.dynamo import DynamoStore, client

    world = json.loads((seed1 / "world.json").read_text())
    requests = json.loads((seed1 / "requests.json").read_text())[:60]
    store = DynamoStore(client(), prefix=f"pipe{uuid.uuid4().hex[:8]}_")
    store.create_tables()
    on_ddb, in_mem = Payhold.from_world(world, store), Payhold.from_world(world)
    for req in requests:
        p = extract_packet(req, seed1)
        a, b = on_ddb.process(p), in_mem.process(p)
        assert (a.decision, [r.code for r in a.reasons]) == (b.decision, [r.code for r in b.reasons])
