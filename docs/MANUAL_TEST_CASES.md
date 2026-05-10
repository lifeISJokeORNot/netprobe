# NetProbe — Manual UI Test Cases

These are the system-level test cases for the NetProbe dashboard (`frontend/index.html`). They exist because the frontend is small enough that a manual checklist is more cost-effective than a Selenium/Playwright suite, but still requires structured verification before any release.

## How to use this document
- Execute every test case before tagging a release.
- Fill in the **Result** column with **Pass / Fail / Blocked** and any notes.
- Failed cases must be logged in `DEFECTS.md` with reproduction steps.

## Test environment
| Item | Value |
|---|---|
| Browser | Chromium ≥ 120, Firefox ≥ 120 |
| Backend | Started via `python backend/main.py` |
| Frontend | `frontend/index.html` opened directly |
| Network | Internet access required for speed/DNS tests |
| Database | Cleared (`rm backend/results.db`) before the run |

---

## TC-01 — API status indicator

| | |
|---|---|
| **Pre-condition** | Backend not yet started |
| **Steps** | 1. Open `frontend/index.html`. 2. Observe the status dot (top-right). 3. Start `python backend/main.py`. 4. Wait 10 seconds. |
| **Expected** | Dot is red and label reads "offline" before backend starts; turns green and reads "online" within 10 s of backend starting. |
| **Result** | |

## TC-02 — Theme toggle persistence

| | |
|---|---|
| **Pre-condition** | App loaded in dark mode (default) |
| **Steps** | 1. Click the theme button (☾). 2. Reload the page. |
| **Expected** | UI switches to light mode immediately on click; light mode is still active after reload (persisted in localStorage). |
| **Result** | |

## TC-03 — Section navigation

| | |
|---|---|
| **Steps** | Click each top-nav button in order: Overview → Tests → Network → Anomalies → History. |
| **Expected** | Only the corresponding section becomes visible; the active button has the highlighted style; the navigated-to section's data loads (e.g. interfaces appear when Network is opened for the first time). |
| **Result** | |

## TC-04 — Run a ping test (happy path)

| | |
|---|---|
| **Pre-condition** | Network → Tests tab |
| **Steps** | 1. Enter `8.8.8.8` and 4 packets. 2. Click **Run**. |
| **Expected** | Result panel populates within ~5 s with status, packet loss, min/avg/max latency, jitter, and quality grade. The header health-ring updates with the grade letter. A toast notification appears. |
| **Result** | |

## TC-05 — Run a ping test against an unreachable host

| | |
|---|---|
| **Steps** | Enter `10.255.255.1` (RFC 5737 unreachable) and click **Run**. |
| **Expected** | Result panel shows status "unreachable", 100% packet loss, latency fields shown as "—", and grade F. No JS error in the console. |
| **Result** | |

## TC-06 — Ping input validation

| | |
|---|---|
| **Steps** | Enter packet count of 0, then 99. Click **Run** in each case. |
| **Expected** | Backend returns HTTP 422 in both cases; frontend displays a clear error in the result panel; toast notification reads "Ping failed". |
| **Result** | |

## TC-07 — Auto-ping toggle

| | |
|---|---|
| **Steps** | 1. Enable the Auto switch with interval 5 s. 2. Wait 15 s. 3. Disable the switch. |
| **Expected** | Three ping tests fire automatically. After disabling, no further automatic pings occur. A "Auto-ping every 5s" toast appears on enable; "Auto-ping stopped" on disable. |
| **Result** | |

## TC-08 — Speed test

| | |
|---|---|
| **Steps** | Click **Run Speed Test** in the Tests section. |
| **Expected** | Loading overlay appears with "Running speed test — up to 30 seconds…". Within 30 s, result panel shows download Mbps, upload Mbps, ping ms, server name, country. |
| **Result** | |

## TC-09 — Multi-host comparison

| | |
|---|---|
| **Steps** | Use the default `8.8.8.8, 1.1.1.1, 9.9.9.9, 208.67.222.222`; click **Compare**. |
| **Expected** | Within ~20 s, four cards appear ranked by latency (lowest first); each shows host, latency, loss percentage, grade. |
| **Result** | |

## TC-10 — Multi-host with one unreachable host

| | |
|---|---|
| **Steps** | Enter `8.8.8.8, 10.255.255.1, 1.1.1.1`; click **Compare**. |
| **Expected** | Reachable hosts come first, ranked by latency; the unreachable host appears at the bottom with "Unreachable" label. |
| **Result** | |

## TC-11 — DNS lookup

| | |
|---|---|
| **Steps** | Enter `google.com`; click **Resolve**. |
| **Expected** | Result panel lists at least one IPv4 address and (typically) one IPv6 address; resolved-in time is shown in ms. |
| **Result** | |

## TC-12 — DNS lookup of nonexistent domain

| | |
|---|---|
| **Steps** | Enter `this-domain-definitely-does-not-exist-12345.invalid`; click **Resolve**. |
| **Expected** | Result panel shows the resolution error message; toast notification "error". No crash. |
| **Result** | |

## TC-13 — Live bandwidth monitor

| | |
|---|---|
| **Steps** | 1. Open Network section. 2. Click **▶ Live Bandwidth**. 3. Generate traffic (e.g. open a video in another tab). 4. Wait 5 s. 5. Click **■ Stop**. |
| **Expected** | Per-interface cards appear, with send/recv bars updating every ~2 s; the active interface's bars grow when video traffic flows; on stop, polling ceases and the panel shows "Monitor stopped". |
| **Result** | |

## TC-14 — Anomaly banner appears

| | |
|---|---|
| **Pre-condition** | At least 5 successful baseline ping tests against `8.8.8.8` |
| **Steps** | Run a ping test against a slow host or intentionally throttle network. |
| **Expected** | A red/yellow banner appears at the top of the page reading "Critical:" or "Warning:" followed by the reason(s). The banner can be dismissed with the ✕ button. |
| **Result** | |

## TC-15 — Anomalies tab populated

| | |
|---|---|
| **Pre-condition** | TC-14 has been executed at least once |
| **Steps** | Click **Anomalies** in the navigation. |
| **Expected** | Anomalies tab shows the detected event(s) with severity badge, test type, host, time, and reasons listed. |
| **Result** | |

## TC-16 — History table and filtering

| | |
|---|---|
| **Pre-condition** | At least 3 ping and 1 speed test have been run |
| **Steps** | 1. Open History. 2. Switch the filter dropdown between "All Tests", "Ping", "Speed". |
| **Expected** | Records appear newest-first; filter restricts to the selected type; record count updates accordingly. |
| **Result** | |

## TC-17 — CSV export

| | |
|---|---|
| **Steps** | Click **⬇ Export CSV** in History. |
| **Expected** | A `netprobe-<timestamp>.csv` file downloads. Opening it in a spreadsheet shows headers and one row per record with timestamps, latencies, etc. |
| **Result** | |

## TC-18 — Clear history with confirmation

| | |
|---|---|
| **Steps** | 1. Click **🗑 Clear All**. 2. In the confirmation dialog, click **Cancel**. 3. Click **🗑 Clear All** again. 4. Click **OK**. |
| **Expected** | First time: history is preserved. Second time: all records and charts are wiped, count goes to 0, toast confirms "History cleared". |
| **Result** | |

## TC-19 — Connections filter

| | |
|---|---|
| **Pre-condition** | A browser is connected to the dashboard |
| **Steps** | 1. Open Network. 2. Click **Refresh** under Active Connections. 3. Type `python` in the filter field. |
| **Expected** | Table shows only connections owned by Python processes; filter is case-insensitive; clearing the filter restores the full list. |
| **Result** | |

## TC-20 — Sustained run (smoke / soak)

| | |
|---|---|
| **Steps** | Leave the dashboard open with auto-ping at 10 s for 5 minutes. |
| **Expected** | No JavaScript errors in the browser console; memory usage stable (no leak); status indicator stays green; ping chart updates continuously. |
| **Result** | |

---

## Run Summary

| | |
|---|---|
| Date executed | _________ |
| Tester | _________ |
| Build / commit | _________ |
| Total cases | 20 |
| Passed | _________ |
| Failed | _________ |
| Blocked | _________ |
| Defects logged | _________ |
| Sign-off | _________ |
