"""
tester.py — Network testing logic
Bug fixes:
  - conn.type handled safely (int or enum)
  - run_multi_ping has per-thread timeout guard
  - get_live_bandwidth uses short 0.5s sample
"""

import socket, subprocess, platform, threading, time
import psutil
from ping3 import ping as ping3_ping
from datetime import datetime


def _now(): return datetime.now().isoformat()

def _quality_score(avg_ms, loss_pct):
    if avg_ms is None:
        return {"score": 0, "grade": "F", "label": "No signal"}
    latency_score = max(0, 100 - (avg_ms / 3))
    loss_score    = max(0, 100 - (loss_pct * 10))
    score = round(latency_score * 0.6 + loss_score * 0.4)
    if score >= 90: return {"score": score, "grade": "A", "label": "Excellent"}
    if score >= 75: return {"score": score, "grade": "B", "label": "Good"}
    if score >= 55: return {"score": score, "grade": "C", "label": "Fair"}
    if score >= 30: return {"score": score, "grade": "D", "label": "Poor"}
    return {"score": score, "grade": "F", "label": "Critical"}


def run_ping_test(host="8.8.8.8", count=4):
    latencies, failed = [], 0
    try:
        for _ in range(count):
            r = ping3_ping(host, timeout=2, unit="ms")
            if r is None or r is False: failed += 1
            else: latencies.append(round(float(r), 2))
    except Exception:
        return _system_ping_fallback(host, count)

    loss = round((failed / count) * 100, 1)
    avg  = round(sum(latencies) / len(latencies), 2) if latencies else None

    if latencies:
        return {
            "timestamp": _now(), "host": host,
            "packets_sent": count, "packets_received": len(latencies),
            "packet_loss_percent": loss,
            "latency_min_ms": min(latencies),
            "latency_avg_ms": avg,
            "latency_max_ms": max(latencies),
            "latency_jitter_ms": round(max(latencies) - min(latencies), 2),
            "quality": _quality_score(avg, loss),
            "status": "success",
        }
    return {
        "timestamp": _now(), "host": host,
        "packets_sent": count, "packets_received": 0,
        "packet_loss_percent": 100.0,
        "latency_min_ms": None, "latency_avg_ms": None,
        "latency_max_ms": None, "latency_jitter_ms": None,
        "quality": _quality_score(None, 100),
        "status": "unreachable",
    }


def _system_ping_fallback(host, count):
    cmd = ["ping", "-n" if platform.system().lower() == "windows" else "-c", str(count), host]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=20).decode(errors="ignore")
        avg_ms = None
        for line in out.splitlines():
            ll = line.lower()
            if "average" in ll or "avg" in ll:
                for part in line.replace("=", "/").replace("ms", "").split("/"):
                    try: avg_ms = float(part.strip()); break
                    except ValueError: continue
        return {
            "timestamp": _now(), "host": host,
            "packets_sent": count, "packets_received": count,
            "packet_loss_percent": 0.0,
            "latency_min_ms": None, "latency_avg_ms": avg_ms,
            "latency_max_ms": None, "latency_jitter_ms": None,
            "quality": _quality_score(avg_ms, 0.0),
            "status": "success (system fallback)",
        }
    except subprocess.CalledProcessError:
        return {
            "timestamp": _now(), "host": host,
            "packets_sent": count, "packets_received": 0,
            "packet_loss_percent": 100.0,
            "latency_min_ms": None, "latency_avg_ms": None,
            "latency_max_ms": None, "latency_jitter_ms": None,
            "quality": _quality_score(None, 100),
            "status": "unreachable",
        }
    except Exception as e:
        return {"timestamp": _now(), "host": host, "status": "error", "error": str(e)}


def run_multi_ping(hosts, count=4):
    """Ping multiple hosts in parallel. BUG FIX: each thread has a 15s timeout guard."""
    results  = [None] * len(hosts)
    TIMEOUT  = 15

    def _ping(idx, host):
        try:
            results[idx] = run_ping_test(host=host, count=count)
        except Exception as e:
            results[idx] = {"timestamp": _now(), "host": host, "status": "error", "error": str(e)}

    threads = [threading.Thread(target=_ping, args=(i, h), daemon=True) for i, h in enumerate(hosts)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=TIMEOUT)

    # Fill in any threads that timed out
    for i, r in enumerate(results):
        if r is None:
            results[i] = {"timestamp": _now(), "host": hosts[i], "status": "timeout", "latency_avg_ms": None, "quality": _quality_score(None, 100)}

    def sort_key(r):
        lat = r.get("latency_avg_ms")
        return (0, lat) if lat is not None else (1, 0)

    return {"timestamp": _now(), "hosts_tested": len(hosts), "results": sorted(results, key=sort_key)}


def run_dns_lookup(host):
    import time as _time
    start = _time.perf_counter()
    try:
        info    = socket.getaddrinfo(host, None)
        elapsed = round((_time.perf_counter() - start) * 1000, 2)
        seen, addresses = set(), []
        for item in info:
            ip     = item[4][0]
            family = "IPv4" if item[0] == socket.AF_INET else "IPv6"
            if (ip, family) not in seen:
                seen.add((ip, family))
                addresses.append({"ip": ip, "family": family})
        return {"timestamp": _now(), "host": host, "resolved_in_ms": elapsed, "addresses": addresses, "status": "success"}
    except socket.gaierror as e:
        return {"timestamp": _now(), "host": host, "status": "error", "error": str(e)}


def run_speed_test():
    try:
        import speedtest as st_mod
        st = st_mod.Speedtest()
        st.get_best_server()
        dl  = st.download()
        ul  = st.upload()
        res = st.results.dict()
        srv = res.get("server", {})
        return {
            "timestamp": _now(),
            "download_mbps": round(dl / 1_000_000, 2),
            "upload_mbps":   round(ul / 1_000_000, 2),
            "ping_ms": res.get("ping"),
            "server_name": srv.get("name"),
            "server_country": srv.get("country"),
            "server_sponsor": srv.get("sponsor"),
            "status": "success",
        }
    except Exception as e:
        return {"timestamp": _now(), "status": "error", "error": str(e)}


def get_active_connections():
    SOCK_STREAM = socket.SOCK_STREAM
    conns = []
    for conn in psutil.net_connections(kind="inet"):
        process_name = None
        try:
            if conn.pid: process_name = psutil.Process(conn.pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"
        try:
            conn_type = "TCP" if int(conn.type) == int(SOCK_STREAM) else "UDP"
        except Exception:
            conn_type = "unknown"
        conns.append({
            "local_address":  f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
            "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
            "status":  conn.status,
            "pid":     conn.pid,
            "process": process_name,
            "type":    conn_type,
        })
    return {"timestamp": _now(), "total": len(conns), "connections": conns}


def get_network_interfaces():
    addrs, stats, io = psutil.net_if_addrs(), psutil.net_if_stats(), psutil.net_io_counters(pernic=True)
    ifaces = []
    for name, addr_list in addrs.items():
        ipv4 = ipv6 = mac = None
        for addr in addr_list:
            if addr.family == socket.AF_INET:    ipv4 = addr.address
            elif addr.family == socket.AF_INET6: ipv6 = addr.address
            elif addr.family == psutil.AF_LINK:  mac  = addr.address
        s, n = stats.get(name), io.get(name)
        ifaces.append({
            "name": name, "ipv4": ipv4, "ipv6": ipv6, "mac": mac,
            "is_up": s.isup if s else None,
            "speed_mbps": s.speed if s else None,
            "bytes_sent": n.bytes_sent if n else None,
            "bytes_recv": n.bytes_recv if n else None,
            "packets_sent": n.packets_sent if n else None,
            "packets_recv": n.packets_recv if n else None,
            "errors_in":  n.errin  if n else None,
            "errors_out": n.errout if n else None,
        })
    return {"timestamp": _now(), "interfaces": ifaces}


def get_live_bandwidth(sample_interval=0.5):
    """BUG FIX: Reduced default sample to 0.5s to avoid blocking the server for 1s."""
    before = psutil.net_io_counters(pernic=True)
    time.sleep(sample_interval)
    after  = psutil.net_io_counters(pernic=True)
    rates  = []
    for name in before:
        if name not in after: continue
        b, a = before[name], after[name]
        sent_kbps = max(0, round((a.bytes_sent - b.bytes_sent) / sample_interval / 1024, 2))
        recv_kbps = max(0, round((a.bytes_recv - b.bytes_recv) / sample_interval / 1024, 2))
        s = psutil.net_if_stats().get(name)
        if sent_kbps > 0 or recv_kbps > 0 or (s and s.isup):
            rates.append({"interface": name, "send_kbps": sent_kbps, "recv_kbps": recv_kbps, "is_up": s.isup if s else False})
    return {"timestamp": _now(), "interfaces": rates}
