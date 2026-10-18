# Decision latency

In-process, sequential, one Python process over the main-stream eval packets of seeds [1, 2, 3, 4, 5]. The first 100 packets were dropped once as warm-up. Held-out packets are excluded. Checks run against the in-memory store. Single run.

- Machine: Mac16,1, Apple M4, macOS 26.6
- Python 3.12.14
- n = 2400 packets

| Stage | p50 (ms) | p95 (ms) | n |
|---|---|---|---|
| extraction (3 PDFs) | 16.77 | 20.19 | 2400 |
| checks | 0.04 | 0.06 | 2400 |
| extraction + checks | 16.81 | 20.24 | 2400 |

Percentiles are nearest-rank. Raw per-packet timings: `results/latency_raw.json`.
