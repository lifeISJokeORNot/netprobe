"""
tester.py — All network testing logic.
Called by main.py endpoints.

Dependencies:
    pip install psutil ping3 speedtest-cli
"""

import socket
import subprocess
import platform
import psutil
import speedtest
from ping3 import ping as ping3_ping
from datetime import datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    """Return current timestamp as an ISO string."""
    return datetime.now().isoformat()


def _ms(seconds) -> float | None:
    """Convert seconds to milliseconds, rounded to 2 decimal places."""
    if seconds is None:
        return None
    return round(seconds * 1000, 2)


# ── Ping Test ─────────────────────────────────────────────────────────────────

def run_ping_test(host: str = "8.8.8.8", count: int = 4) -> dict:
    """
    Ping a host `count` times using ping3.
    Returns min / avg / max latency in milliseconds, and packet loss %.

    Falls back to subprocess (system ping) if ping3 fails (e.g. permission error on Linux).
    """
    latencies = []
    failed = 0

    # --- ping3 attempt ---
    try:
        for _ in range(count):
            result = ping3_ping(host, timeout=2, unit="ms")
            if result is None or result is False:
                failed += 1
            else:
                latencies.append(round(result, 2))
    except Exception:
        # ping3 may need root on Linux; fall back to system ping
        return _system_ping_fallback(host, count)

    packet_loss = round((failed / count) * 100, 1)

    if latencies:
        return {
            "timestamp": _now(),
            "host": host,
            "packets_sent": count,
            "packets_received": len(latencies),
            "packet_loss_percent": packet_loss,
            "latency_min_ms": min(latencies),
            "latency_avg_ms": round(sum(latencies) / len(latencies), 2),
            "latency_max_ms": max(latencies),
            "status": "success",
        }
    else:
        return {
            "timestamp": _now(),
            "host": host,
            "packets_sent": count,
            "packets_received": 0,
            "packet_loss_percent": 100.0,
            "latency_min_ms": None,
            "latency_avg_ms": None,
            "latency_max_ms": None,
            "status": "unreachable",
        }


def _system_ping_fallback(host: str, count: int) -> dict:
    """
    Use the OS ping command as a fallback.
    Works on both Windows and Linux/macOS.
    """
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), host]

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=15)
        output = output.decode(errors="ignore")

        # Parse avg latency from output (works for most OS ping formats)
        avg_ms = None
        for line in output.splitlines():
            line_lower = line.lower()
            # Linux:   rtt min/avg/max/mdev = 10.1/12.3/14.5/1.2 ms
            # Windows: Average = 12ms
            if "average" in line_lower or "avg" in line_lower:
                parts = line.replace("=", "/").replace("ms", "").split("/")
                for part in parts:
                    part = part.strip()
                    try:
                        avg_ms = float(part)
                        break
                    except ValueError:
                        continue

        return {
            "timestamp": _now(),
            "host": host,
            "packets_sent": count,
            "packets_received": count,   # approximate — hard to parse cross-platform
            "packet_loss_percent": 0.0,
            "latency_min_ms": None,
            "latency_avg_ms": avg_ms,
            "latency_max_ms": None,
            "status": "success (system ping fallback)",
        }

    except subprocess.CalledProcessError:
        return {
            "timestamp": _now(),
            "host": host,
            "packets_sent": count,
            "packets_received": 0,
            "packet_loss_percent": 100.0,
            "latency_min_ms": None,
            "latency_avg_ms": None,
            "latency_max_ms": None,
            "status": "unreachable",
        }
    except Exception as e:
        return {
            "timestamp": _now(),
            "host": host,
            "status": "error",
            "error": str(e),
        }


# ── Speed Test ────────────────────────────────────────────────────────────────

def run_speed_test() -> dict:
    """
    Measure download speed, upload speed, and ping to the best speedtest.net server.
    This takes 10–30 seconds depending on connection quality.
    """
    try:
        st = speedtest.Speedtest()
        st.get_best_server()          # finds the closest/fastest server

        download_bps = st.download()  # bits per second
        upload_bps = st.upload()

        results = st.results.dict()
        server = results.get("server", {})

        return {
            "timestamp": _now(),
            "download_mbps": round(download_bps / 1_000_000, 2),
            "upload_mbps": round(upload_bps / 1_000_000, 2),
            "ping_ms": results.get("ping"),
            "server_name": server.get("name"),
            "server_country": server.get("country"),
            "server_sponsor": server.get("sponsor"),
            "status": "success",
        }

    except speedtest.ConfigRetrievalError:
        return {
            "timestamp": _now(),
            "status": "error",
            "error": "Could not reach speedtest.net — check your internet connection.",
        }
    except Exception as e:
        return {
            "timestamp": _now(),
            "status": "error",
            "error": str(e),
        }


# ── Active Connections ────────────────────────────────────────────────────────

def get_active_connections() -> dict:
    """
    List all active TCP/UDP connections on this machine.
    Uses psutil to get local addr, remote addr, status, and owning process name.
    """
    connections = []

    for conn in psutil.net_connections(kind="inet"):
        # Get owning process name safely
        process_name = None
        try:
            if conn.pid:
                process_name = psutil.Process(conn.pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"

        local_addr = (
            f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None
        )
        remote_addr = (
            f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None
        )

        connections.append({
            "local_address": local_addr,
            "remote_address": remote_addr,
            "status": conn.status,
            "pid": conn.pid,
            "process": process_name,
            "type": "TCP" if conn.type.name == "SOCK_STREAM" else "UDP",
        })

    return {
        "timestamp": _now(),
        "total": len(connections),
        "connections": connections,
    }


# ── Network Interfaces ────────────────────────────────────────────────────────

def get_network_interfaces() -> dict:
    """
    List all network interfaces (Wi-Fi, Ethernet, loopback, etc.)
    and their assigned IP addresses + stats.
    """
    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io = psutil.net_io_counters(pernic=True)

    for name, addr_list in addrs.items():
        ipv4 = None
        ipv6 = None
        mac  = None

        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ipv4 = addr.address
            elif addr.family == socket.AF_INET6:
                ipv6 = addr.address
            elif addr.family == psutil.AF_LINK:
                mac = addr.address

        stat = stats.get(name)
        nic_io = io.get(name)

        interfaces.append({
            "name": name,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "mac": mac,
            "is_up": stat.isup if stat else None,
            "speed_mbps": stat.speed if stat else None,
            "bytes_sent": nic_io.bytes_sent if nic_io else None,
            "bytes_recv": nic_io.bytes_recv if nic_io else None,
        })

    return {
        "timestamp": _now(),
        "interfaces": interfaces,
    }
