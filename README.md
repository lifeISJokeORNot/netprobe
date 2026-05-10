# NetProbe — Automated Network Connection Tester

[![Tests](https://github.com/YOUR_USERNAME/netprobe/actions/workflows/test.yml/badge.svg)](https://github.com/YOUR_USERNAME/netprobe/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-75%25-brightgreen)](docs/TEST_PLAN.md)
[![Tests](https://img.shields.io/badge/tests-68%20passing-brightgreen)](tests/)

> Automated testing of network connections and performance monitoring, with a live web dashboard and automatic anomaly detection against a historical baseline.

This repository accompanies a Software Quality Assurance and Testing course project. The application is the *subject under test* — the focus of the deliverable is the **testing process applied to it**: a structured test plan, a layered automated test suite, defect tracking with regression coverage, manual UI test cases, and continuous integration. See the **Quality Assurance** section below.

---

## Project Structure

```
netprobe/
├── .github/workflows/test.yml   # CI: pytest + coverage on every push
├── backend/
│   ├── main.py                  # FastAPI server & API routes
│   ├── tester.py                # Network testing logic (ping, speed, DNS, bandwidth)
│   ├── analyzer.py              # Anomaly detection vs. historical baseline
│   ├── database.py              # SQLite storage for results & anomalies
│   └── results.db               # Auto-created on first run
├── frontend/
│   ├── index.html               # Dashboard UI
│   ├── style.css                # Styling
│   └── app.js                   # API calls, tables, charts
├── tests/
│   ├── conftest.py              # Shared fixtures (tmp DB, FastAPI client)
│   ├── unit/                    # 50 unit tests (analyzer, parsers, scoring, db)
│   ├── integration/             # 18 integration tests (API surface)
│   └── fixtures/                # Real ping output samples for parser tests
├── docs/
│   ├── TEST_PLAN.md             # Test strategy, scope, coverage goals
│   ├── DEFECTS.md               # Defect log with regression-test references
│   └── MANUAL_TEST_CASES.md     # Manual UI test cases
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Test dependencies
├── pytest.ini                   # pytest configuration
└── README.md
```

---

## Requirements

- Python 3.10 or higher
- A working internet connection (for speed tests and ping to external hosts)
- A modern browser (Chrome, Firefox, Edge)

---

## Installation & Setup

### 1. Clone the project

```bash
git clone https://github.com/YOUR_USERNAME/netprobe.git
cd netprobe
```

### 2. (Optional but recommended) Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

For running the app:
```bash
pip install -r requirements.txt
```

For running the tests as well:
```bash
pip install -r requirements-dev.txt
```

### 4. Start the backend server

```bash
cd backend
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 5. Open the dashboard

Open `frontend/index.html` directly in your browser.
The status dot in the top-right corner will turn **green** when the frontend is connected to the API.

---

## Quality Assurance

This is a Software QA project, so the testing effort is documented as a first-class deliverable.

### Running the tests

```bash
# Full suite with coverage report
pytest --cov=backend --cov-report=term-missing

# Just unit tests (fast)
pytest tests/unit/

# Just integration tests
pytest tests/integration/

# Generate an HTML coverage report
pytest --cov=backend --cov-report=html
# open htmlcov/index.html in your browser
```

### Test suite summary

| Layer | Count | Purpose |
|---|---|---|
| Unit — analyzer | 16 | Severity logic for every ping/speed branch, including the DEF-002 regression |
| Unit — parsers | 11 | System-ping fallback parser on real Linux/Windows/garbage outputs (DEF-003) |
| Unit — quality score | 10 | Includes Hypothesis property tests over random latency/loss inputs |
| Unit — database | 13 | Save/retrieve/delete roundtrips on per-test isolated SQLite |
| Integration — API | 18 | Every endpoint via FastAPI TestClient (DEF-001 regression) |
| **Total** | **68** | All passing on Python 3.10, 3.11, 3.12 |

### Coverage achieved

| Module | Coverage |
|---|---|
| `analyzer.py` | 98% |
| `database.py` | 95% |
| `main.py`     | 85% |
| `tester.py` (parsers + scoring) | covered |
| **Overall**   | **75%** |

`tester.py`'s network I/O paths (real speedtest, psutil-based interface inspection) are intentionally tested manually rather than via heavy mocking — see `docs/MANUAL_TEST_CASES.md`.

### Documentation

- **[`docs/TEST_PLAN.md`](docs/TEST_PLAN.md)** — strategy, scope, levels, risk prioritization, entry/exit criteria.
- **[`docs/DEFECTS.md`](docs/DEFECTS.md)** — three real defects discovered during testing, each with a regression test:
  - **DEF-001** (Critical) — Anomaly detection module never invoked by the API.
  - **DEF-002** (High) — Severity downgraded from `critical` to `warning` when packet loss is also present.
  - **DEF-003** (Medium) — System-ping fallback parser returns the minimum latency instead of the average.
- **[`docs/MANUAL_TEST_CASES.md`](docs/MANUAL_TEST_CASES.md)** — 20 manual UI test cases covering every interactive element of the dashboard.

### Continuous Integration

`.github/workflows/test.yml` runs the full pytest suite with coverage on every push and pull request, across Python 3.10, 3.11, and 3.12. The build fails if any test fails or coverage drops below 70%.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/ping?host=8.8.8.8&count=4` | Run a ping test (auto-runs anomaly check) |
| GET | `/ping/multi?hosts=8.8.8.8,1.1.1.1` | Compare up to 4 hosts in parallel |
| GET | `/speed` | Download/upload speed test (auto-runs anomaly check) |
| GET | `/dns?host=google.com` | Resolve a domain to IPv4/IPv6 addresses |
| GET | `/connections` | List active TCP/UDP connections with process names |
| GET | `/interfaces` | List network interfaces with traffic counters |
| GET | `/bandwidth` | Live per-interface send/recv rates (sampled over 0.5 s) |
| GET | `/history?test_type=ping&limit=50` | Retrieve saved test results |
| GET | `/stats` | Aggregate statistics (averages, bests, anomaly count) |
| GET | `/anomalies?limit=20` | Detected anomalies (latency spikes, speed drops, packet loss) |
| DELETE | `/history?test_type=ping` | Clear history (omit param to clear all) |

Interactive Swagger UI is available at: `http://localhost:8000/docs`

---

## Features

- **Ping Test** — measures latency (min/avg/max/jitter) and packet loss to any host, with a quality score (A–F).
- **Speed Test** — measures download and upload speed via speedtest.net.
- **Multi-Host Comparison** — pings up to 4 hosts in parallel and ranks them.
- **DNS Lookup** — resolves a domain to its IPv4 and IPv6 addresses.
- **Active Connections** — lists all TCP/UDP connections with process names.
- **Network Interfaces** — shows all network cards, IPs, MAC addresses, and traffic stats.
- **Live Bandwidth Monitor** — real-time send/recv rates per interface.
- **Anomaly Detection** — every ping and speed result is automatically compared against a rolling baseline (last 50 / 20 results); latency spikes, speed drops, and packet-loss surges are flagged as `warning` or `critical` and saved to a separate anomaly log.
- **History & Charts** — all results saved locally in SQLite and visualised as time-series charts; CSV export available.
- **Live Status** — API health is polled every 10 seconds.

---

## Linux Note — Ping Permissions

On Linux, `ping3` may require root privileges to send ICMP packets. If the ping test fails:

**Option A — Run with sudo:**
```bash
sudo python main.py
```

**Option B — Give Python permission (recommended):**
```bash
sudo setcap cap_net_raw+ep $(which python3)
```

The app automatically falls back to the system `ping` command if `ping3` fails.

---

## Windows Note

No extra setup needed. Make sure your firewall allows Python to access the network.

---

## Database

Test results are stored in `backend/results.db` (SQLite), created automatically on first run. Open it with any SQLite viewer such as [DB Browser for SQLite](https://sqlitebrowser.org/).

To clear all history, either click **🗑 Clear All** in the dashboard's History section, or delete `results.db` and restart the server.

---

## License

For academic use only.
