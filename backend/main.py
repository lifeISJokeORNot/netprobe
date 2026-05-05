"""
main.py — NetProbe API Server (v2)
FastAPI backend for the Network Connection Tester dashboard.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from tester import (
    run_ping_test,
    run_speed_test,
    get_active_connections,
    get_network_interfaces,
    run_dns_lookup,
    run_multi_ping,
    get_live_bandwidth,
)
from database import init_db, save_result, get_history, get_stats_summary, delete_history


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield   # server runs here


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NetProbe — Network Connection Tester",
    description="Automated tester for network connections and performance.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "NetProbe API v2 is running."}


# ── Tests ─────────────────────────────────────────────────────────────────────

@app.get("/ping", tags=["Tests"])
def ping(
    host: str = Query("8.8.8.8", description="Target IP or hostname"),
    count: int = Query(4, ge=1, le=20, description="Number of packets"),
):
    """Ping a host — returns min/avg/max latency + packet loss + quality score."""
    result = run_ping_test(host=host, count=count)
    save_result("ping", result)
    return JSONResponse(content=result)


@app.get("/ping/multi", tags=["Tests"])
def ping_multi(
    hosts: str = Query(..., description="Comma-separated hosts, max 4"),
    count: int = Query(4, ge=1, le=10),
):
    """Ping up to 4 hosts in parallel and compare results."""
    host_list = [h.strip() for h in hosts.split(",") if h.strip()][:4]
    if not host_list:
        raise HTTPException(status_code=400, detail="No valid hosts provided.")
    return JSONResponse(content=run_multi_ping(host_list, count))


@app.get("/speed", tags=["Tests"])
def speed():
    """Download/upload speed test via speedtest.net (10–30 seconds)."""
    result = run_speed_test()
    save_result("speed", result)
    return JSONResponse(content=result)


@app.get("/dns", tags=["Tests"])
def dns(host: str = Query(..., description="Domain to resolve")):
    """Resolve a domain name to its IP addresses."""
    return JSONResponse(content=run_dns_lookup(host))


# ── Network Info ──────────────────────────────────────────────────────────────

@app.get("/connections", tags=["Network"])
def connections():
    """All active TCP/UDP connections with process names."""
    return JSONResponse(content=get_active_connections())


@app.get("/interfaces", tags=["Network"])
def interfaces():
    """All network interfaces with IPs, MACs, and traffic counters."""
    return JSONResponse(content=get_network_interfaces())


@app.get("/bandwidth", tags=["Network"])
def bandwidth():
    """Live bytes/sec per interface — samples over 1 second."""
    return JSONResponse(content=get_live_bandwidth())


# ── History & Stats ───────────────────────────────────────────────────────────

@app.get("/history", tags=["History"])
def history(
    test_type: str = Query(None, description="'ping' or 'speed'"),
    limit: int = Query(50, ge=1, le=500),
):
    """Retrieve saved test results."""
    records = get_history(test_type=test_type, limit=limit)
    return JSONResponse(content={"records": records})


@app.get("/stats", tags=["History"])
def stats():
    """Aggregate statistics across all saved tests."""
    return JSONResponse(content=get_stats_summary())


@app.delete("/history", tags=["History"])
def clear_history(test_type: str = Query(None)):
    """Delete history. Omit test_type to delete everything."""
    delete_history(test_type=test_type)
    return {"status": "ok", "message": f"Cleared {'all' if not test_type else test_type} history."}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
