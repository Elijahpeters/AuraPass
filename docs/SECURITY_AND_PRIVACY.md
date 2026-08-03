# Security and privacy notes

AuraPass handles identity records, course registrations, face images, embeddings, attendance decisions and controller commands. Treat each of these as sensitive even though this public repository contains only fictional records and synthetic numeric fixtures.

## Data created at runtime

By default, AuraPass writes beneath `runtime/`:

- `database/aurapass.db`
- normalized enrollment images under `data/face_images/`
- temporary captures under `data/captures/`
- bridge logs under `logs/`

These paths, database files, images, logs, model binaries, caches and common private benchmark directories are excluded by `.gitignore`. Database image references are runtime-relative so a copied database does not expose a workstation username through an absolute path.

## Current controls

- SQLite foreign keys and uniqueness constraints.
- Transaction rollback on enrollment failure.
- Duplicate matric rejection during enrollment.
- Cross-template collision check for compatible embedding models.
- Same-session repeat denial.
- Loopback-only UDP defaults.
- Vendor-model checksum verification.
- No secrets or API credentials are required.

## Controls not implemented

- Encryption at rest or field-level encryption.
- Operator authentication and roles.
- Consent capture, retention scheduling, or automated deletion.
- Signed audit logs or tamper-evident storage.
- Liveness/presentation-attack detection.
- Controller authentication, encrypted transport, acknowledgements, or replay protection.
- Central university-system integration.

## Responsible evaluation

Before collecting real biometric data, define a lawful purpose, obtain informed consent where applicable, minimize collection, restrict workstation access, encrypt the host disk, document retention/deletion, and obtain institutional approval. Do not commit or share runtime folders. Do not use public face datasets unless their licence and the intended biometric use have been reviewed.

The included tests intentionally use fictional names, fictional identifiers and synthetic vectors. No real face images, captured frames, databases, matric numbers, LFW/RandomUser datasets, benchmark reports, logs, pickles, or templates are part of the sanitized repository.
