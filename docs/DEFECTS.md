# NetProbe — Defect Log

This document records all defects discovered during the testing of NetProbe, in the order they were found. Each entry follows a consistent format adapted from IEEE 829: ID, severity, status, reporter, reproduction steps, expected vs. actual behaviour, root cause analysis, fix details, and the regression test that prevents reintroduction.

| ID | Severity | Status | Component | One-line summary |
|---|---|---|---|---|
| [DEF-001](#def-001) | Critical | Fixed | `main.py` | Anomaly detection module never invoked by the API |
| [DEF-002](#def-002) | High | Fixed | `analyzer.py` | Severity downgraded from `critical` to `warning` when packet loss is also present |
| [DEF-003](#def-003) | Medium | Fixed | `tester.py` | System-ping fallback parser returns the minimum latency instead of the average |

---

## DEF-001

**Title:** Anomaly detection feature is fully disconnected from the API layer.

| Field | Value |
|---|---|
| **Severity** | Critical |
| **Priority** | P1 |
| **Status** | Fixed |
| **Component** | `backend/main.py` |
| **Found by** | Code review (cross-referenced frontend calls against backend routes) |
| **Affects version** | v2.0.0 (initial submission) |
| **Fixed in** | v2.0.1 |

### Description
Although the project ships an entire anomaly detection module (`analyzer.py`), an `anomalies` table in `database.py`, persistence helpers (`save_anomaly`, `get_anomaly_log`), and a complete frontend UI for displaying anomalies (banner, badge, dedicated tab), none of these components are wired up in `main.py`. The feature appears to work because the UI loads, but no anomaly is ever detected, persisted, or returned.

### Steps to Reproduce
1. Start the backend: `python backend/main.py`.
2. Open the frontend dashboard.
3. Run several ping tests against `8.8.8.8` to build a baseline (≥ 5 results).
4. Run a ping test against a slow or unreachable host to trigger an anomaly.
5. Click the **Anomalies** tab in the navigation.

### Expected Behaviour
- The backend's `/ping` response includes an `anomaly` object when one is detected.
- The frontend banner displays the warning.
- The Anomalies tab shows a list of detected events.
- `GET /anomalies?limit=20` returns the anomaly log.

### Actual Behaviour
- The `anomaly` field is never present in any API response.
- The warning banner never appears.
- The Anomalies tab issues a request to `GET /anomalies?limit=20` which returns **HTTP 404 Not Found** (route does not exist).
- The badge counter on the navigation tab stays at zero forever.

### Root Cause
`main.py` does not import `analyze_result` from `analyzer.py`, does not import `save_anomaly` or `get_anomaly_log` from `database.py`, does not invoke any analysis after saving a result, and does not register a `/anomalies` route. The implementation of every supporting component exists but is unreachable from the HTTP layer.

### Fix
Imports added to `main.py`:
```python
from database import (..., save_anomaly, get_anomaly_log)
from analyzer import analyze_result
```
The `/ping` and `/speed` handlers were modified to fetch recent history, run the analyzer, persist any detected anomaly, and attach it to the response payload. A new route `GET /anomalies?limit=N` was added, calling `get_anomaly_log()`.

### Regression Tests
- `tests/integration/test_api.py::test_anomalies_endpoint_exists`
- `tests/integration/test_api.py::test_anomalies_endpoint_returns_anomalies_key`
- `tests/integration/test_api.py::test_anomalies_empty_initially`
- `tests/integration/test_api.py::test_anomalies_limit_validated`

### Lessons Learned
The bug was invisible from a casual smoke test because the UI silently swallows the 404 (the empty-state message is shown instead of an error). It was caught only by methodically cross-referencing every endpoint the frontend calls against every route the backend exposes. A simple linter or contract test could have caught this earlier; this is a future improvement.

---

## DEF-002

**Title:** Anomaly severity is downgraded from `critical` to `warning` when packet loss accompanies high latency.

| Field | Value |
|---|---|
| **Severity** | High |
| **Priority** | P1 |
| **Status** | Fixed |
| **Component** | `backend/analyzer.py`, function `_analyze_ping` |
| **Found by** | Test development (writing `test_critical_latency_is_not_downgraded_by_minor_loss`) |
| **Affects version** | v2.0.0 |
| **Fixed in** | v2.0.1 |

### Description
When a ping result triggers both a critical latency spike *and* moderate packet loss (e.g. 15%), the final severity reported is `warning` rather than `critical`. The packet-loss handling block reassigns the `severity` variable unconditionally, overwriting any prior assignment.

### Steps to Reproduce
With a baseline of five ping results at 20 ms latency and 0% loss:
1. Submit a new ping result with `latency_avg_ms = 60.0` and `packet_loss_percent = 15.0`.
2. Call `analyze_result("ping", result, history)`.

### Expected Behaviour
- `severity == "critical"` (because latency alone is 200% above baseline, well above the 150% threshold).
- Both reasons listed: latency spike and packet loss.

### Actual Behaviour
- `severity == "warning"` — the latency-derived `critical` was overwritten by the loss-derived `warning`.
- Both reasons are correctly listed, but the severity badge on the dashboard misrepresents the event.

### Root Cause
Original code in `_analyze_ping`:

```python
if current_loss > LOSS_THRESHOLD:
    reasons.append(f"Packet loss {current_loss}% (threshold: {LOSS_THRESHOLD}%)")
    severity = "critical" if current_loss >= 50 else "warning"   # ← clobbers prior
```

The assignment is unconditional. Any earlier `critical` from latency analysis is silently downgraded if loss is moderate. This violates the principle that severity should be **monotonic — escalating only**.

### Fix
Replaced the unconditional assignment with a guarded escalation:

```python
if current_loss > LOSS_THRESHOLD:
    reasons.append(...)
    new_sev = "critical" if current_loss >= 50 else "warning"
    if severity != "critical":
        severity = new_sev
```

The same pattern was applied to `_analyze_speed` for consistency (the upload branch had a similar but milder version of this bug).

### Regression Test
`tests/unit/test_analyzer.py::test_critical_latency_is_not_downgraded_by_minor_loss`

### Lessons Learned
This is a textbook case of why pure functions should be tested with combinations of inputs, not just one variable at a time. Testing high latency alone, and packet loss alone, both produced the correct severity. Only the combination revealed the bug. Future test development should systematically exercise input combinations for any function with multiple severity-bearing inputs.

---

## DEF-003

**Title:** System-ping fallback parser returns the minimum latency instead of the average.

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Priority** | P2 |
| **Status** | Fixed |
| **Component** | `backend/tester.py`, function `_system_ping_fallback` |
| **Found by** | Test development (`test_linux_parser_returns_avg_not_min`) |
| **Affects version** | v2.0.0 |
| **Fixed in** | v2.0.1 |

### Description
The fallback parser used when the `ping3` library fails (typically on Linux without raw-socket capability) extracts the wrong number from the system `ping` output. On Linux, the line `rtt min/avg/max/mdev = 12.345/15.678/19.012/2.345 ms` results in `latency_avg_ms = 12.345` (the minimum) instead of `15.678` (the average). The same problem exists on Windows.

### Steps to Reproduce
1. On Linux, run NetProbe without granting raw-socket capabilities to Python.
2. Trigger a ping test from the dashboard.
3. The fallback path activates because `ping3` raises a `PermissionError`.

### Expected Behaviour
The reported average latency matches the value labelled `avg` in the system ping output.

### Actual Behaviour
The reported average is the *minimum* value from the output. All downstream calculations (quality score, anomaly detection baselines) are biased toward optimism by this same amount.

### Root Cause
Original parsing code split on `/` and accepted the first numeric token. On Linux, after replacing `=` with `/` and stripping `ms`, the first numeric token in the rtt line is the minimum, not the average:

```python
for part in line.replace("=", "/").replace("ms", "").split("/"):
    try: avg_ms = float(part.strip()); break    # picks first number, which is min
    except ValueError: continue
```

### Fix
Replaced with platform-specific anchored regular expressions:

```python
# Linux/macOS
m = re.search(r"min/avg/max[^=]*=\s*[\d.]+/([\d.]+)", out)
if m:
    avg_ms = float(m.group(1))
else:
    # Windows
    m = re.search(r"Average\s*=\s*(\d+)", out, re.IGNORECASE)
    if m:
        avg_ms = float(m.group(1))
```

### Regression Tests
- `tests/unit/test_tester_parsers.py::test_linux_parser_returns_avg_not_min`
- `tests/unit/test_tester_parsers.py::test_windows_parser_extracts_average`
- `tests/unit/test_tester_parsers.py::test_garbage_output_yields_none_avg`
- `tests/unit/test_tester_parsers.py::test_decimal_avg_preserved`

### Lessons Learned
"Best-effort" parsers that try to be format-agnostic are dangerous. When a known input format exists, an anchored regex that matches that format precisely is more reliable than a flexible split-and-pick approach. Test fixtures with **real** sample output (`tests/fixtures/ping_*.txt`) catch these bugs immediately; synthetic inputs would not.

---

## Summary Statistics

| Metric | Value |
|---|---|
| Total defects logged | 3 |
| Critical | 1 |
| High | 1 |
| Medium | 1 |
| All fixed and verified | ✓ |
| Defects with regression tests | 3 / 3 (100%) |
| Defects found by automated tests | 2 |
| Defects found by code review | 1 |
