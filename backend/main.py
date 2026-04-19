from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from tester import (
    run_ping_test,
    run_speed_test,
    get_active_connections,
    get_network_interfaces,
)
from database import init_db, save_result, get_history

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Network Connection Tester",
    description="Automated tester for network connections and performance.",
    version="1.0.0",
)

# Allow the frontend (any origin during development) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise the database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health-check endpoint."""
    return {"status": "ok", "message": "Network Tester API is running."}


@app.get("/ping")
def ping(host: str = "8.8.8.8", count: int = 4):
    """
    Ping a host and return latency statistics.

    - **host**: target IP or hostname (default: Google DNS 8.8.8.8)
    - **count**: number of ping packets to send (default: 4)
    """
    result = run_ping_test(host=host, count=count)
    save_result("ping", result)
    return JSONResponse(content=result)


@app.get("/speed")
def speed():
    """
    Run a download/upload speed test.
    This may take 10–30 seconds — call it asynchronously from the frontend.
    """
    result = run_speed_test()
    save_result("speed", result)
    return JSONResponse(content=result)


@app.get("/connections")
def connections():
    """
    List all active network connections on this machine.
    Returns local/remote address, status, and the owning process (if available).
    """
    result = get_active_connections()
    return JSONResponse(content=result)


@app.get("/interfaces")
def interfaces():
    """
    List all network interfaces and their IP addresses.
    """
    result = get_network_interfaces()
    return JSONResponse(content=result)


@app.get("/history")
def history(test_type: str = None, limit: int = 50):
    """
    Retrieve past test results from the local database.

    - **test_type**: filter by 'ping' or 'speed' (omit for all)
    - **limit**: max number of records to return (default: 50)
    """
    records = get_history(test_type=test_type, limit=limit)
    return JSONResponse(content={"records": records})


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run with:  python main.py
    # Or:        uvicorn main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
