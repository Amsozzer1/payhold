"""Generator settings. Every rate here is a planting rate for synthetic data, not an industry rate."""

from datetime import datetime, timezone

# Synthetic clock: the stream starts here and nothing reads the wall clock.
STREAM_START = datetime(2026, 3, 2, 6, 0, tzinfo=timezone.utc)
MINUTES_BETWEEN_REQUESTS = (4, 18)
HISTORY_DAYS = 60

# Issue types, planted exactly round(N * rate) times each. At most one per packet.
ISSUE_RATES = {
    1: 0.04,  # padding
    2: 0.03,  # duplicate re-bill
    3: 0.04,  # double factoring (the later request through a second factor)
    4: 0.03,  # bank change / identity takeover
    5: 0.03,  # double brokering
}
ISSUE_NAMES = {
    0: "clean",
    1: "padding",
    2: "duplicate_rebill",
    3: "double_factoring",
    4: "bank_change",
    5: "double_brokering",
}

# Seen look-alikes: clean packets built to resemble an issue. About 15% of main-stream clean packets.
LOOKALIKE_RATES = {
    "bank_verified": 0.04,  # recent bank change, verified, requested from a contact on file
    "ratecon_revision": 0.04,  # rate con revision that adds the detention the invoice bills
    "rejected_rebill": 0.04,  # corrected re-bill of a request the same factor rejected
}

# World size. Bank-change carriers are dedicated so their changes touch no other packet.
GENERAL_CARRIERS = 120
BROKERS = 30
DBA_SHARE = 0.25  # at least 20% of carriers get a DBA
PRE_STREAM_PAID = 400
PRE_STREAM_REJECTED = 60
SHARE_WITH_AGREED_ACCESSORIAL = 0.25

# A recent remit-to change is planted 1-5 days before the request. Background changes are older.
RECENT_CHANGE_DAYS = (1, 5)
OLD_CHANGE_DAYS = (120, 700)

# Type-3 anchors are a plain clean packet within this many positions before the follower.
ANCHOR_WINDOW = 60

FACTORS = [
    ("F1", "Alder Funding"),
    ("F2", "Birchgate Capital"),
    ("F3", "Cobalt Receivables"),
    ("F4", "Driftwood Factoring"),
]

# Main-stream report seeds and dev seeds (thresholds are tuned on dev seeds only).
REPORT_SEEDS = [1, 2, 3, 4, 5]
DEV_SEEDS = [101, 102]

# Held-out look-alikes (written after the freeze commit): 25 per kind per seed.
HELDOUT_PER_KIND = 25
# Carriers with an unverified remit-to change this recent are left out of the held-out set, so a
# held-out packet can only be held for its own feature. Wider than any window the checks use.
HELDOUT_REMIT_EXCLUDE_DAYS = 60
