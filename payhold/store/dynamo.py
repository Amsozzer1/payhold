"""DynamoDB store. Tested against DynamoDB Local (`-sharedDb -inMemory`), not AWS.

Tables:
  paid_bills  pk = payout key (load_key#linehaul)
  seen_loads  pk = load_key or invoice key, sk = factor#request_id
  audit_log   pk = request_id, sk = ts#seq  (append-only: every put is conditional on the item not existing)
"""

from __future__ import annotations

import itertools
import json
import os
import threading

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from payhold.store.base import PayoutItem, Seen

CLAIM_CONDITION = "attribute_not_exists(pk) OR (request_id = :rid AND #s = :pending AND lease_until < :now)"


def client(endpoint: str | None = None, session: boto3.session.Session | None = None):
    session = session or boto3.session.Session()
    return session.client(
        "dynamodb",
        endpoint_url=endpoint or os.environ.get("PAYHOLD_DDB_ENDPOINT", "http://localhost:8000"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(retries={"max_attempts": 3, "mode": "standard"}, max_pool_connections=4),
    )


def failed_condition(e: ClientError) -> bool:
    return e.response["Error"]["Code"] == "ConditionalCheckFailedException"


class DynamoStore:
    def __init__(self, ddb, prefix: str = "payhold_"):
        self.ddb = ddb
        self.paid = f"{prefix}paid_bills"
        self.seen_t = f"{prefix}seen_loads"
        self.audit_t = f"{prefix}audit_log"
        self._seq = itertools.count(1)
        self._seq_lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "DynamoStore":
        return cls(client(), os.environ.get("PAYHOLD_DDB_PREFIX", "payhold_"))

    # ---- tables ------------------------------------------------------------------------

    def create_tables(self) -> None:
        specs = [
            (self.paid, [("pk", "HASH")]),
            (self.seen_t, [("pk", "HASH"), ("sk", "RANGE")]),
            (self.audit_t, [("pk", "HASH"), ("sk", "RANGE")]),
        ]
        existing = set(self.ddb.list_tables()["TableNames"])
        for name, keys in specs:
            if name in existing:
                continue
            self.ddb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": k, "KeyType": t} for k, t in keys],
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k, _ in keys],
                BillingMode="PAY_PER_REQUEST",
            )
            self.ddb.get_waiter("table_exists").wait(TableName=name)

    # ---- seen_loads --------------------------------------------------------------------

    def put_seen(self, item: Seen) -> None:
        self.ddb.put_item(
            TableName=self.seen_t,
            Item={
                "pk": {"S": item.pk},
                "sk": {"S": item.sk},
                "factor_id": {"S": item.factor_id},
                "request_id": {"S": item.request_id},
                "status": {"S": item.status},
                "at": {"S": item.at},
                "label": {"S": item.label},
            },
        )

    def seen(self, pk: str) -> list[Seen]:
        out, kwargs = [], {}
        while True:
            r = self.ddb.query(
                TableName=self.seen_t,
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": {"S": pk}},
                ConsistentRead=True,
                **kwargs,
            )
            for it in r["Items"]:
                out.append(Seen(pk, it["factor_id"]["S"], it["request_id"]["S"], it["status"]["S"], it["at"]["S"], it["label"]["S"]))
            if "LastEvaluatedKey" not in r:
                break
            kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        return sorted(out, key=lambda s: (s.at, s.request_id))

    def set_status(self, pk: str, factor_id: str, request_id: str, status: str) -> None:
        self.ddb.update_item(
            TableName=self.seen_t,
            Key={"pk": {"S": pk}, "sk": {"S": f"{factor_id}#{request_id}"}},
            UpdateExpression="SET #s = :s",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": {"S": status}},
        )

    # ---- paid_bills --------------------------------------------------------------------

    def claim_payout(self, pk: str, request_id: str, token: str, lease_until: str, now: str) -> bool:
        try:
            self.ddb.put_item(
                TableName=self.paid,
                Item={
                    "pk": {"S": pk},
                    "request_id": {"S": request_id},
                    "attempt_token": {"S": token},
                    "status": {"S": "pending"},
                    "lease_until": {"S": lease_until},
                },
                ConditionExpression=CLAIM_CONDITION,
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":rid": {"S": request_id}, ":pending": {"S": "pending"}, ":now": {"S": now}},
            )
            return True
        except ClientError as e:
            if failed_condition(e):
                return False
            raise

    def mark_sent(self, pk: str, token: str) -> bool:
        try:
            self.ddb.update_item(
                TableName=self.paid,
                Key={"pk": {"S": pk}},
                UpdateExpression="SET #s = :sent",
                ConditionExpression="attempt_token = :tok",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":sent": {"S": "sent"}, ":tok": {"S": token}},
            )
            return True
        except ClientError as e:
            if failed_condition(e):
                return False
            raise

    def get_payout(self, pk: str) -> PayoutItem | None:
        it = self.ddb.get_item(TableName=self.paid, Key={"pk": {"S": pk}}, ConsistentRead=True).get("Item")
        if not it:
            return None
        return PayoutItem(pk, it["request_id"]["S"], it["attempt_token"]["S"], it["status"]["S"], it["lease_until"]["S"])

    # ---- audit_log ---------------------------------------------------------------------

    def append_audit(self, request_id: str, ts: str, record: dict) -> None:
        while True:
            with self._seq_lock:
                seq = next(self._seq)
            try:
                self.ddb.put_item(
                    TableName=self.audit_t,
                    Item={"pk": {"S": request_id}, "sk": {"S": f"{ts}#{seq:08d}"}, "record": {"S": json.dumps(record, sort_keys=True)}},
                    ConditionExpression="attribute_not_exists(pk)",
                )
                return
            except ClientError as e:
                if not failed_condition(e):
                    raise

    def audit(self, request_id: str) -> list[dict]:
        r = self.ddb.query(
            TableName=self.audit_t,
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": {"S": request_id}},
            ConsistentRead=True,
        )
        return [{"sk": it["sk"]["S"], **json.loads(it["record"]["S"])} for it in r["Items"]]
