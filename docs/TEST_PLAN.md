# NetProbe — Test Plan

| Field | Value |
|---|---|
| Project | NetProbe — Automated Network Connection Tester |
| Document version | 1.0 |
| Author | NetProbe team |
| Course | Software Quality Assurance and Testing |
| Status | Active |

---

## 1. Introduction

### 1.1 Purpose
This document defines the testing strategy, scope, methodology, and acceptance criteria for the NetProbe project. It is the contract between the development effort and the QA effort: it specifies *what* is tested, *how* it is tested, *why* those choices were made, and *when* testing is considered complete.

### 1.2 Scope
NetProbe is a full-stack network monitoring application consisting of a Python/FastAPI backend, a SQLite persistence layer, a rule-based anomaly detection module, and a vanilla-JS dashboard frontend. This plan covers all four layers, with emphasis weighted toward the backend where the core logic lives.

### 1.3 References
- Source repository: this folder
- README.md — installation and usage
- DEFECTS.md — defects discovered during the testing effort
- MANUAL_TEST_CASES.md — UI/system test cases
- IEEE 829 — Standard for Software Test Documentation (structural reference)

---

## 2. Test Items

The following components are subject to testing:

| Component | Path | Notes |
|---|---|---|
| Anomaly detection logic | `backend/analyzer.py` | Pure functions — highest test coverage |
| Network testing logic | `backend/tester.py` | External I/O — heavily mocked |
| Persistence layer | `backend/database.py` | SQLite, isolated tmp DB per test |
| API layer | `backend/main.py` | Tested via FastAPI TestClient |
| Frontend dashboard | `frontend/*` | Tested manually (see MANUAL_TEST_CASES.md) |

---

## 3. Features To Be Tested

- **Ping testing** — latency aggregation, packet loss calculation, quality scoring
- **Speed testing** — download/upload measurement (mocked in automated tests; verified manually)
- **Multi-host comparison** — parallel execution, timeout handling, ranking
- **DNS resolution** — IPv4/IPv6 separation, error handling
- **Network introspection** — interfaces, active connections, live bandwidth
- **Anomaly detection** — baseline calculation, severity classification, persistence
- **Persistence** — save/retrieve roundtrips, filtering, statistics aggregation
- **REST API** — every endpoint, valid and invalid inputs, response shapes, status codes

## 4. Features Not To Be Tested

- **Real internet bandwidth** during automated runs — speed tests are mocked because (a) results are non-deterministic, (b) CI environments may have throttled network access. The real speedtest path is verified manually before each release.
- **Operating-system-specific raw socket behaviour** in `ping3` — this is library code; we trust its own test suite and verify our integration via the fallback path instead.
- **Browser compatibility** beyond Chromium and Firefox — the dashboard targets evergreen browsers only.
- **Performance under load** — out of scope for an academic project; left for future work.

---

## 5. Test Strategy & Approach

NetProbe applies a **layered testing pyramid**: many fast unit tests at the base, fewer integration tests in the middle, manual system tests at the top. This is a deliberate choice because the bulk of the application's logic is deterministic and pure — perfect for unit testing — while the I/O-heavy parts (real network calls) are better verified manually or with mocks.

### 5.1 Unit Testing (lowest level)
- **Framework:** `pytest` 8.x
- **Scope:** Individual functions and classes in `analyzer.py`, `database.py`, and the parsing/scoring helpers in `tester.py`.
- **Isolation:** Database tests use a per-test temporary SQLite file via the `tmp_db` fixture; subprocess and ping3 calls are mocked with `unittest.mock.patch`.
- **Outcome:** ~50 fast deterministic tests that complete in under 5 seconds.

### 5.2 Integration Testing (middle level)
- **Framework:** `pytest` + `fastapi.testclient.TestClient`.
- **Scope:** Every HTTP endpoint of `main.py` is exercised with valid and invalid inputs, with the database isolated and the slow network calls (ping, speed) replaced by deterministic fakes via `monkeypatch`.
- **Outcome:** End-to-end coverage of the API surface without flakiness from the network.

### 5.3 Property-Based Testing (cross-cutting)
- **Framework:** `Hypothesis` 6.x.
- **Scope:** Invariants of the quality-score function. Rather than picking example inputs, Hypothesis generates ~100 random latency/loss combinations per run and checks that the score always lies in [0, 100] and the grade is one of the five defined letters.
- **Rationale:** Property testing catches edge cases that example-based tests miss (e.g. extreme inputs that cause the formula to produce negatives without the `max(0, ...)` guard).

### 5.4 System Testing (manual, frontend)
- **Approach:** Documented test cases in `MANUAL_TEST_CASES.md`, executed by a tester walking through the dashboard before each release.
- **Why manual:** The frontend is small enough that automated UI testing (Selenium, Playwright) carries more setup cost than benefit at this project's scale.

### 5.5 Regression Testing
- Every defect documented in `DEFECTS.md` has a corresponding regression test in the suite that fails on the buggy version and passes on the fixed version. Test names include the defect ID for traceability (e.g., `test_critical_latency_is_not_downgraded_by_minor_loss`).
- The full suite runs in CI on every push and pull request.

### 5.6 Continuous Integration
- **Platform:** GitHub Actions (`.github/workflows/test.yml`)
- **Triggers:** Push and pull-request events on `main`.
- **Matrix:** Python 3.10, 3.11, 3.12.
- **Failure threshold:** Build fails if any test fails or if coverage drops below 70%.

---

## 6. Risk-Based Prioritization

Test effort is concentrated where defects would have the greatest impact. Components are ranked by **risk = likelihood × impact**:

| Component | Likelihood of defect | Impact of defect | Priority | Coverage target |
|---|---|---|---|---|
| `analyzer.py` (severity logic) | Medium | High — incorrect alerts mislead user | **P1** | ≥ 95% |
| `database.py` (persistence) | Low | High — data loss is unacceptable | **P1** | ≥ 90% |
| `main.py` API surface | Medium | High — public contract | **P1** | ≥ 80% |
| `tester.py` parsers | Medium | Medium — wrong metric on rare fallback path | **P2** | ≥ 70% (parsers only) |
| `tester.py` network I/O | High | Low — failures are observable, not silent | **P3** | Manual verification |
| Frontend rendering | Medium | Low — cosmetic | **P3** | Manual checklist |

The original buggy code shipped with all three of the highest-impact components carrying real defects (see `DEFECTS.md`), validating this prioritization in retrospect.

---

## 7. Test Levels and Types

| Level | Type | Tool | Where |
|---|---|---|---|
| Unit | Functional | pytest | `tests/unit/` |
| Unit | Property-based | Hypothesis | `tests/unit/test_quality_score.py` |
| Integration | Functional (API) | pytest + TestClient | `tests/integration/` |
| Integration | Negative (input validation) | pytest + TestClient | `tests/integration/test_api.py` |
| System | Manual exploratory | Browser | `MANUAL_TEST_CASES.md` |
| Regression | Functional | pytest | All defect-related tests |

---

## 8. Test Environment & Tools

| Concern | Tool |
|---|---|
| Test framework | pytest 8.2.0 |
| Coverage | pytest-cov 5.0.0 |
| Property-based testing | Hypothesis 6.100.0 |
| HTTP test client | httpx 0.27.0 (FastAPI TestClient backend) |
| Mocking | unittest.mock (stdlib) |
| CI | GitHub Actions |
| Python versions | 3.10, 3.11, 3.12 |
| OS | Ubuntu (CI), Windows + Linux (manual) |

Reproducible install:
```bash
pip install -r requirements-dev.txt
pytest --cov=backend
```

---

## 9. Test Coverage Goals

| Module | Target | Achieved |
|---|---|---|
| `analyzer.py` | ≥ 95% | 98% |
| `database.py` | ≥ 90% | 95% |
| `main.py` | ≥ 80% | 85% |
| `tester.py` (parsers + scoring only) | ≥ 70% | covered |
| **Overall** | **≥ 70%** | **75%** |

Coverage on `tester.py` as a whole is intentionally lower (~50%) because the network I/O functions (`run_speed_test`, `get_active_connections`, `get_network_interfaces`, `get_live_bandwidth`) require extensive OS-level mocking that would test the mocks more than the code. These paths are verified manually instead — see `MANUAL_TEST_CASES.md`.

---

## 10. Entry & Exit Criteria

### 10.1 Entry Criteria — testing may begin when:
- All source files compile / parse without error.
- All declared dependencies install cleanly via `pip install -r requirements-dev.txt`.
- The application can be started locally without crashing on import.

### 10.2 Exit Criteria — testing is considered complete when:
- All automated tests pass on all three Python versions in CI.
- Coverage meets or exceeds the targets in §9.
- All P1 and P2 defects are either fixed or documented with a justified deferral.
- All manual test cases in `MANUAL_TEST_CASES.md` have been executed and recorded.
- This document and `DEFECTS.md` are up to date.

---

## 11. Defect Management

Defects discovered during testing are recorded in `DEFECTS.md` with a unique ID, severity, status, reproduction steps, root cause, and the commit that fixed them. Every fixed defect must have an associated automated regression test.

Severity scale:
- **Critical** — feature is non-functional or data corruption is possible.
- **High** — feature works incorrectly in a way the user would notice.
- **Medium** — feature works incorrectly only in a rare path or non-user-facing code.
- **Low** — cosmetic or documentation only.

---

## 12. Roles & Responsibilities

For an academic project:
- **Developer + Tester** (same person/team): writes code and the corresponding tests.
- **Reviewer** (peer or instructor): reviews this plan, the defect log, and a sample of tests for adequacy.

---

## 13. Schedule

| Phase | Duration | Output |
|---|---|---|
| Test plan drafting | 1 day | This document |
| Unit test development | 2 days | `tests/unit/` |
| Integration test development | 1 day | `tests/integration/` |
| Manual test pass | 1 day | Filled-in `MANUAL_TEST_CASES.md` |
| Defect logging & fix verification | rolling | `DEFECTS.md` |
| CI setup | 0.5 day | `.github/workflows/test.yml` |

---

## 14. Approval

By committing this document to the repository, the team confirms that this plan reflects the testing approach actually applied to NetProbe.
