# F3/P01 — Exact Core quota readback (22/10/2026)

## Internal security closure
The existing HTTPS Core quota reader already rejected missing/mis-scoped, stale, malformed and unreachable data. This WP fixes one remaining trust-boundary vulnerability in the reader: equality comparisons could silently treat JSON `true` as integer revision 1, or floating-point `2000.0` as integer plan limit 2000. The consumer read port now requires *exact* JSON strings and integers, checks nonnegative counters and that consumed + reserved + remaining equals the licensed Core limit **before** accepting the balance, and requires a timezone-aware caller clock. It does not bypass the existing validation in `PlanConsumptionView`.

The regression tests cover booleans, floats, negative and inconsistent consumption, mismatched unit/resource, stale observations and naive timestamps; no provider connections, credentials, real billing, real data or migrations.

## Certification
PR targets Assistant F3 candidate `feat/saas-foundation-v1`, not `main`. Run all applicable SaaS/test, PostgreSQL bridge and signed bridge E2E checks on exact HEAD. Review source and diff, then merge only if green, and validate post-merge candidate SHA. Command Foundation then repins the actual final Assistant candidate SHA. Main PR #1 still Draft until F3/P01 global audit/closure.

## Still open
Persistent provider billing evidence reconciliation and alert thresholds, final commercial lifecycle and adversarial matrix, Core and Assistant monolithic audits, plus deferred external homologation.
