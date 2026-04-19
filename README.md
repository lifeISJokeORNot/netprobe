# NetProbe — Automated Network Connection Tester

> Automated testing of network connections and performance monitoring, with a live web dashboard.

---

## Project Structure

```
project/
├── backend/
│   ├── main.py          # FastAPI server & API routes
│   ├── tester.py        # Network testing logic (ping, speed, connections)
│   ├── database.py      # SQLite storage for test history
│   └── results.db       # Auto-created on first run
├── frontend/
│   ├── index.html       # Dashboard UI
│   ├── style.css        # Styling
│   └── app.js           # API calls, tables, charts
├── requirements.txt     # Python dependencies
└── README.md
```

---

## Requirements

- Python 3.10 or higher
- A working internet connection (for speed tests and ping to external hosts)
- A modern browser (Chrome, Firefox, Edge)

---

## Installation & Setup

### 1. Clone or download the project

```bash
git clone https://github.com/yourname/netprobe.git
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

```bash
pip install -r requirements.txt
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

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/ping?host=8.8.8.8&count=4` | Run a ping test |
| GET | `/speed` | Run a download/upload speed test |
| GET | `/connections` | List active network connections |
| GET | `/interfaces` | List network interfaces |
| GET | `/history?test_type=ping&limit=50` | Retrieve saved test results |

You can also explore the API interactively at:
```
http://localhost:8000/docs
```
FastAPI generates a Swagger UI automatically — great for testing and demos.

---

## Features

- **Ping Test** — measures latency (min/avg/max) and packet loss to any host
- **Speed Test** — measures download and upload speed via speedtest.net
- **Active Connections** — lists all TCP/UDP connections with process names
- **Network Interfaces** — shows all network cards, IPs, MAC addresses, and traffic stats
- **History** — all test results are saved locally in SQLite and shown as charts
- **Live Status** — API health is checked every 10 seconds

---

## Linux Note — Ping Permissions

On Linux, `ping3` may require root privileges to send ICMP packets. If the ping test fails, either:

**Option A — Run with sudo:**
```bash
sudo python main.py
```

**Option B — Give Python permission (recommended):**
```bash
sudo setcap cap_net_raw+ep $(which python3)
```

The app will automatically fall back to the system `ping` command if `ping3` fails.

---

## Windows Note

No extra setup needed. Run everything normally. Make sure your firewall allows Python to access the network.

---

## Database

Test results are stored in `backend/results.db` (SQLite).  
This file is created automatically on first run. You can open it with any SQLite viewer such as [DB Browser for SQLite](https://sqlitebrowser.org/).

To clear all history, delete `results.db` and restart the server — it will be recreated empty.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework for the API |
| `uvicorn` | ASGI server to run FastAPI |
| `psutil` | System & network info (connections, interfaces) |
| `ping3` | Pure Python ping (ICMP) |
| `speedtest-cli` | Download/upload speed measurement |
| `sqlite3` | Built into Python — no install needed |

---

## 📄 License

For academic use only.
