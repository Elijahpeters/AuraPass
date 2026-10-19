# Testing AuraPass

Install the test dependencies and run:

```powershell
python -m pip install -e ".[dev]"
python tools\create_synthetic_course_form.py
python -m ruff check aurapass app tools tests
python -m pytest -q
python -m compileall -q aurapass app tools tests
```

## Synthetic exam-access demo

With Python 3.10 or later, run the policy demonstration from the repository root:

```powershell
py -3 tools\synthetic_exam_demo.py
```

Use `python tools\synthetic_exam_demo.py` if the Windows Python launcher is unavailable. The script needs only the Python standard library. It calls the existing `ExamService` using fictional records and injected synthetic match outcomes in a temporary SQLite database. It prints grant and denial outcomes and the controller command strings, then removes the temporary database. It does not run recognition, access a camera, load models, write to the normal runtime database, or send commands to any hardware bridge.

## Public suite coverage

The checked-in suite covers:

- expected and rejected course-form parsing;
- extraction from the generated fictional PDF;
- empty-database initialization and foreign-key enforcement;
- course-code normalization;
- access grant and `V`/`O` controller encoding;
- same-session duplicate denial;
- course-ineligibility denial;
- hall-capacity denial and `F` encoding;
- unknown-face denial logging;
- the synthetic exam-access demo's grant, repeat-scan, course-eligibility, hall-capacity, and no-match decisions;
- cosine similarity;
- multi-template support;
- close-runner-up ambiguity rejection;
- enrollment sample consistency and collision rejection.

All identities are fictional. Recognition tests use small numeric vectors rather than photographs or generated faces.

## What the suite does not establish

Passing these tests demonstrates application logic, schema constraints, parser behaviour for the fixture, and protocol encoding. It does not establish biometric accuracy, liveness, demographic fairness, robustness to presentation attacks, controller actuation, electrical safety, or fitness for deployment.

Any future biometric evaluation should publish a lawful and reproducible protocol: dataset provenance/licence, consent basis, population, preprocessing, model checksums, threshold selection, positive and negative denominators, quality rejections, and uncertainty intervals. Raw biometric samples should remain outside the public repository.
