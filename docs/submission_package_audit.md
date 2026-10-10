# Submission Package Audit

Audit date: 2026-10-08

## Decision

`SUBMISSION_PACKAGE_AUDIT = PASS`

Package: `submission/agentic-marketing-final`

## Inventory

- Manifest-reported files: 558 (557 hashed payload files plus the manifest)
- Every payload file has a SHA-256 entry; the stable aggregate content digest is recorded in `SUBMISSION_CONTENTS.json`.
- Included project areas: agent, benchmark, data, database, docs, frontend, guardrail, marketing, metadata, query_plan, scripts, SQL, tests, and webapp.
- Included root material: README, dependency/configuration templates, stage documentation, schema, and required entity-resolution CSV files.

## Exclusion and privacy checks

- `.env` in package: no
- Forbidden directories (`node_modules`, `__pycache__`, `.pytest_cache`, `.firecrawl`, `dist`): 0
- Known local database-password occurrences: 0
- API/access-key pattern findings: 0
- Absolute Windows user-path findings: 0
- Log, archive, local-database, and debug-image artifacts: 0
- Package-builder privacy findings: 0
- Package-builder forbidden entries: 0

## Reproducibility boundary

- The four customer fact CSVs are controlled external competition data and are not redistributed.
- Their exact filenames, sizes and SHA-256 values are frozen in `EXTERNAL_DATA_REQUIREMENTS.json`.
- `python scripts/verify_external_data.py` verifies them before database import.
- Import SQL uses project-root-relative filenames and contains no developer-machine path.
- `python scripts/final_verify.py` now verifies every packaged file against the manifest before declaring release integrity.

The local `.env` remains outside the submission package. `.env.example` is retained with an empty password value.
