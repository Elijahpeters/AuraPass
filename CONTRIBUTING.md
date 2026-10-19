# Contributing to AuraPass

Thanks for your interest in AuraPass, an **experimental offline examination-access prototype** maintained by **Peters Elijah Temidayo, professionally known as Elijah Peters**.

## Before you contribute

- Read [README.md](README.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/SECURITY_AND_PRIVACY.md](docs/SECURITY_AND_PRIVACY.md).
- Do not submit real student names, matriculation records, exam attendance logs, private course forms, real face images, facial embeddings, or proprietary biometric datasets.
- Do not imply the system has passed liveness, fairness, biometric accuracy, electrical safety, or deployment testing. It has not.
- Check the licenses of external models, datasets and dependencies before adding them. Vendor models are downloaded separately.
- For a suspected security/privacy vulnerability, contact the maintainer privately at **peterselijah11@gmail.com**, rather than posting exploitable details in a public issue.

## Development setup

Use Python 3.10 or later, then from the repository root:

```bash
python -m venv .venv
# Activate .venv with the command for your operating system.
python -m pip install -e ".[dev]"
python tools/create_synthetic_course_form.py
python -m ruff check aurapass app tools tests
python -m pytest -q
python -m compileall -q aurapass app tools tests
```

Tests use fictional identity records and synthetic numeric vectors. Full GUI enrolment requires an operator-supplied face sample, and gate co-simulation additionally requires Proteus/serial setup.

## Pull requests

1. Open an issue before large changes, especially architecture, facial recognition, storage, or hardware protocol changes.
2. Keep changes focused and explain the problem they solve.
3. Include tests or reproducible instructions for behavioral changes.
4. Update README and technical documentation when user-facing behavior changes.
5. Avoid committing model binaries, generated databases, cache files and runtime material.

Contributions are expected to be offered under the repository's **MIT License**, except separately licensed third-party content. Contributors should submit only materials they have rights to distribute under those terms.
