/**
 * app.js — NetProbe Dashboard
 * All bugs fixed. New features: anomaly detection display,
 * health timeline chart, section navigation, trend indicators.
 * CircularQueue declared at top (fixes class hoisting crash).
 */

const API = "http://localhost:8000";

// ── Circular Queue (MUST be at top — classes are not hoisted) ─────────────────

class CircularQueue {
  constructor(maxSize = 31) { this.maxSize = maxSize; this.queue = []; }
  enqueue(r)   { if (this.queue.length >= this.maxSize) this.queue.shift(); this.queue.push(r); }
  loadAll(arr) { this.queue = arr.slice(-this.maxSize); }
  toArray()    { return [...this.queue].reverse(); }
  get size()   { return this.queue.length; }
}

const historyQueue = new CircularQueue(31);

// ── State ──────────────────────────────────────────────────────────────────────

let chartPing = null, chartSpeed = null, chartHealth = null;
let autoPingTimer = null, bwTimer = null, bwRunning = false;
let allConnections = [];

// ── DOM ────────────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

const el = {
  // Header
  apiDot:   $("api-status-dot"),
  apiLabel: $("api-status-label"),
  ringProgress: $("ring-progress"),
  ringGrade:    $("ring-grade"),
  btnTheme:     $("btn-theme"),
  anomalyBadge: $("anomaly-badge"),

  // Anomaly banner
  anomalyBanner:     $("anomaly-banner"),
  anomalyBannerText: $("anomaly-banner-text"),
  btnDismissBanner:  $("btn-dismiss-banner"),

  // Stats
  statPing:      $("stat-ping"),
  statDownload:  $("stat-download"),
  statUpload:    $("stat-upload"),
  statQuality:   $("stat-quality"),
  statBestDl:    $("stat-best-dl"),
  statBestPing:  $("stat-best-ping"),
  trendPing:     $("trend-ping"),
  trendDl:       $("trend-dl"),
  trendUl:       $("trend-ul"),
  trendQuality:  $("trend-quality"),

  // Tests
  pingHost:  $("ping-host"),  pingCount: $("ping-count"),
  btnPing:   $("btn-ping"),   resultPing: $("result-ping"),
  autoPingToggle: $("auto-ping-toggle"), autoPingInterval: $("auto-ping-interval"),
  btnSpeed:  $("btn-speed"),  resultSpeed: $("result-speed"),
  multiHosts:   $("multi-hosts"),   btnMultiPing: $("btn-multi-ping"), multiResults: $("multi-results"),
  dnsHost:      $("dns-host"),      btnDns: $("btn-dns"),  resultDns: $("result-dns"),

  // Network
  btnBwToggle:  $("btn-bw-toggle"),  bwGrid: $("bw-grid"), bwStatusLabel: $("bw-status-label"),
  btnInterfaces: $("btn-interfaces"), tableInterfaces: $("table-interfaces"),
  btnConnections: $("btn-connections"), tableConns: $("table-connections"), connSearch: $("conn-search"),

  // Overview charts
  btnRefreshHealth: $("btn-refresh-health"),
  chartHealth: $("chart-health"),

  // History
  btnRefreshPingChart:  $("btn-refresh-ping-chart"),
  btnRefreshSpeedChart: $("btn-refresh-speed-chart"),
  chartPingCanvas:  $("chart-ping"),
  chartSpeedCanvas: $("chart-speed"),
  historyFilter: $("history-filter"),
  historyCount:  $("history-count"),
  historyTable:  $("history-table"),
  btnExportCsv:    $("btn-export-csv"),
  btnClearHistory: $("btn-clear-history"),

  // Anomalies
  anomalyList:          $("anomaly-list"),
  btnRefreshAnomalies:  $("btn-refresh-anomalies"),

  // Overview
  btnReset: $("btn-reset"),

  // Overlay / Toast
  overlay: $("loading-overlay"), loadingMsg: $("loading-msg"),
  toastContainer: $("toast-container"),
  footerTime: $("footer-time"),
};

// ── Utilities ──────────────────────────────────────────────────────────────────

const showLoading = msg => { el.loadingMsg.textContent = msg || "Running…"; el.overlay.classList.add("active"); };
const hideLoading = ()  => el.overlay.classList.remove("active");

async function apiFetch(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function apiDelete(path) {
  const r = await fetch(`${API}${path}`, { method: "DELETE", headers: { "Content-Type": "application/json" } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function rrow(key, val, cls = "") {
  return `<div class="result-row"><span class="rk">${key}</span><span class="rv ${cls}">${val ?? "—"}</span></div>`;
}
function showErr(el, msg) { el.innerHTML = rrow("error", msg, "err"); }

function formatBytes(b) {
  if (b == null) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1_048_576) return `${(b/1024).toFixed(1)} KB`;
  if (b < 1_073_741_824) return `${(b/1_048_576).toFixed(1)} MB`;
  return `${(b/1_073_741_824).toFixed(2)} GB`;
}

function shortTime(iso) {
  try { return new Date(iso).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}); }
  catch { return iso; }
}

// BUG FIX: latency class is now a standalone function (was broken inside else-if chain)
function latClass(ms) {
  if (ms == null) return "err";
  if (ms > 300)   return "err";
  if (ms > 150)   return "warn";
  return "ok";
}
function lossClass(p) { return p >= 20 ? "err" : p > 0 ? "warn" : "ok"; }

// ── Toast ──────────────────────────────────────────────────────────────────────

function toast(msg, type = "info", ms = 3500) {
  const icons = { success:"✓", error:"✕", info:"◈" };
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<span class="ti">${icons[type]}</span><span>${msg}</span>`;
  el.toastContainer.appendChild(t);
  setTimeout(() => { t.style.opacity="0"; t.style.transition="opacity .3s"; setTimeout(()=>t.remove(),300); }, ms);
}

// ── Theme ──────────────────────────────────────────────────────────────────────

function toggleTheme() {
  const d = document.documentElement;
  const now = d.getAttribute("data-theme") === "dark" ? "light" : "dark";
  d.setAttribute("data-theme", now);
  el.btnTheme.textContent = now === "dark" ? "☾" : "☀";
  localStorage.setItem("np-theme", now);
}
function loadTheme() {
  const t = localStorage.getItem("np-theme") || "dark";
  document.documentElement.setAttribute("data-theme", t);
  el.btnTheme.textContent = t === "dark" ? "☾" : "☀";
}

// ── Section Navigation ─────────────────────────────────────────────────────────

function initNav() {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const sec = btn.dataset.section;
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".page-section").forEach(s => s.classList.remove("active"));
      btn.classList.add("active");
      $(`section-${sec}`)?.classList.add("active");
      // Lazy-load section data
      if (sec === "anomalies") loadAnomalies();
      if (sec === "history")   { loadHistoryTable(); loadPingChart(); loadSpeedChart(); }
      if (sec === "network")   { loadInterfaces(); loadConnections(); }
    });
  });
}

// ── API Health ─────────────────────────────────────────────────────────────────

async function checkApiStatus() {
  try {
    await apiFetch("/");
    el.apiDot.className    = "status-dot online";
    el.apiLabel.textContent = "online";
  } catch {
    el.apiDot.className    = "status-dot offline";
    el.apiLabel.textContent = "offline";
  }
}

// ── Health Ring (SVG animated arc in logo) ─────────────────────────────────────

function updateHealthRing(score, grade) {
  if (!el.ringProgress) return;
  const circumference = 107;
  const offset = circumference - (score / 100) * circumference;
  el.ringProgress.style.strokeDashoffset = offset;
  el.ringGrade.textContent = grade ?? "—";
}

// ── Summary / Stats ────────────────────────────────────────────────────────────

async function loadSummary() {
  try {
    const d = await apiFetch("/stats");
    el.statPing.textContent     = d.avg_ping_ms       ?? "—";
    el.statDownload.textContent = d.avg_download_mbps ?? "—";
    el.statUpload.textContent   = d.avg_upload_mbps   ?? "—";
    el.statQuality.textContent  = d.avg_quality_score ?? "—";
    el.statBestDl.textContent   = d.best_download_mbps ?? "—";
    el.statBestPing.textContent = d.best_ping_ms       ?? "—";

    // Update anomaly badge count
    if (d.total_anomalies > 0) {
      el.anomalyBadge.textContent = d.total_anomalies;
      el.anomalyBadge.style.display = "inline-flex";
    }
  } catch { /* silent */ }
}

function resetOverview() {
  [el.statPing, el.statDownload, el.statUpload, el.statQuality, el.statBestDl, el.statBestPing]
    .forEach(e => { e.textContent = "—"; });
  updateHealthRing(0, "—");
  el.trendPing.textContent = el.trendDl.textContent = el.trendUl.textContent = el.trendQuality.textContent = "";
  toast("Overview reset", "info");
}

// ── Trend Indicators ───────────────────────────────────────────────────────────

function computeTrend(records, key) {
  const vals = records.map(r => r[key]).filter(v => v != null);
  if (vals.length < 3) return null;
  const first = vals.slice(0, Math.floor(vals.length / 2));
  const last  = vals.slice(Math.floor(vals.length / 2));
  const avgF  = first.reduce((a,b)=>a+b,0)/first.length;
  const avgL  = last.reduce((a,b)=>a+b,0)/last.length;
  const delta = ((avgL - avgF) / avgF) * 100;
  if (Math.abs(delta) < 5) return { arrow: "→", cls: "trend-flat", label: "Stable" };
  return delta > 0
    ? { arrow: "↑", cls: "trend-up",   label: `+${delta.toFixed(0)}%` }
    : { arrow: "↓", cls: "trend-down", label: `${delta.toFixed(0)}%` };
}

async function loadTrends() {
  try {
    const pd = await apiFetch("/history?test_type=ping&limit=20");
    const sd = await apiFetch("/history?test_type=speed&limit=10");
    const pr = pd.records || [], sr = sd.records || [];

    const applyTrend = (el, trend, invertGood) => {
      if (!trend) { el.textContent = ""; return; }
      const isGood = invertGood ? trend.arrow === "↓" : trend.arrow === "↑";
      el.className = `stat-trend ${isGood ? "trend-up" : trend.arrow === "→" ? "trend-flat" : "trend-down"}`;
      el.textContent = `${trend.arrow} ${trend.label}`;
    };

    applyTrend(el.trendPing,    computeTrend(pr, "latency_avg_ms"),  true);  // lower=better
    applyTrend(el.trendDl,      computeTrend(sr, "download_mbps"),   false);
    applyTrend(el.trendUl,      computeTrend(sr, "upload_mbps"),     false);
    applyTrend(el.trendQuality, computeTrend(pr.map(r => ({score: r.quality?.score})), "score"), false);
  } catch { /* silent */ }
}

// ── Anomaly Banner ─────────────────────────────────────────────────────────────

function showAnomalyBanner(anomaly) {
  if (!anomaly) return;
  const severity = anomaly.severity === "critical" ? "🔴 Critical" : "🟡 Warning";
  el.anomalyBannerText.textContent = `${severity}: ${anomaly.reasons?.join(" · ") ?? "Anomaly detected"}`;
  el.anomalyBanner.style.display = "flex";
}

// ── Ping ───────────────────────────────────────────────────────────────────────

async function runPingTest() {
  const host  = el.pingHost.value.trim() || "8.8.8.8";
  const count = parseInt(el.pingCount.value) || 4;

  el.btnPing.disabled = true;
  el.resultPing.innerHTML = `<span class="muted-text">Pinging ${host}…</span>`;

  try {
    const d = await apiFetch(`/ping?host=${encodeURIComponent(host)}&count=${count}`);
    const lc = latClass(d.latency_avg_ms);
    const ls = lossClass(d.packet_loss_percent);

    el.resultPing.innerHTML = [
      rrow("host",         d.host),
      rrow("status",       d.status, d.status?.startsWith("success") ? "ok" : "err"),
      rrow("sent/recv",    `${d.packets_sent} / ${d.packets_received}`),
      rrow("packet loss",  d.packet_loss_percent != null ? `${d.packet_loss_percent}%` : "—", ls),
      rrow("latency min",  d.latency_min_ms  != null ? `${d.latency_min_ms} ms`  : "—"),
      rrow("latency avg",  d.latency_avg_ms  != null ? `${d.latency_avg_ms} ms`  : "—", lc),
      rrow("latency max",  d.latency_max_ms  != null ? `${d.latency_max_ms} ms`  : "—"),
      rrow("jitter",       d.latency_jitter_ms != null ? `${d.latency_jitter_ms} ms` : "—"),
      rrow("quality",      d.quality ? `${d.quality.score}/100 — ${d.quality.grade} (${d.quality.label})` : "—",
           d.quality?.grade === "A" || d.quality?.grade === "B" ? "ok" : d.quality?.grade === "F" ? "err" : "warn"),
    ].join("");

    if (d.quality) updateHealthRing(d.quality.score, d.quality.grade);
    if (d.anomaly) showAnomalyBanner(d.anomaly);

    toast(`${host}: ${d.latency_avg_ms ?? "N/A"} ms — ${d.quality?.grade ?? "?"}`, "success");
    await loadSummary();
    await loadHealthChart();
    await loadTrends();

  } catch (err) {
    showErr(el.resultPing, err.message);
    toast(`Ping failed: ${err.message}`, "error");
  } finally {
    el.btnPing.disabled = false;
  }
}

function startAutoPing() {
  const s = Math.max(3, parseInt(el.autoPingInterval.value) || 10);
  autoPingTimer = setInterval(runPingTest, s * 1000);
  toast(`Auto-ping every ${s}s`, "info");
}
function stopAutoPing() {
  clearInterval(autoPingTimer); autoPingTimer = null;
  toast("Auto-ping stopped", "info");
}

// ── Speed ──────────────────────────────────────────────────────────────────────

async function runSpeedTest() {
  el.btnSpeed.disabled = true;
  showLoading("Running speed test — up to 30 seconds…");
  try {
    const d   = await apiFetch("/speed");
    const dlc = d.download_mbps == null ? "" : d.download_mbps < 2 ? "err" : d.download_mbps < 10 ? "warn" : "ok";

    el.resultSpeed.innerHTML = [
      rrow("status",   d.status, d.status === "success" ? "ok" : "err"),
      rrow("download", d.download_mbps != null ? `${d.download_mbps} Mbps` : "—", dlc),
      rrow("upload",   d.upload_mbps   != null ? `${d.upload_mbps} Mbps`   : "—"),
      rrow("ping",     d.ping_ms       != null ? `${d.ping_ms} ms`         : "—"),
      rrow("server",   d.server_name    ?? "—"),
      rrow("country",  d.server_country ?? "—"),
    ].join("");

    if (d.anomaly) showAnomalyBanner(d.anomaly);
    toast(`↓${d.download_mbps} ↑${d.upload_mbps} Mbps`, "success");
    await loadSummary();
    await loadTrends();

  } catch (err) {
    showErr(el.resultSpeed, err.message);
    toast(`Speed test failed: ${err.message}`, "error");
  } finally {
    hideLoading();
    el.btnSpeed.disabled = false;
  }
}

// ── Multi Ping ─────────────────────────────────────────────────────────────────

async function runMultiPing() {
  const hosts = el.multiHosts.value.split(",").map(h=>h.trim()).filter(Boolean).slice(0,4);
  if (!hosts.length) { toast("Enter at least one host", "error"); return; }
  el.btnMultiPing.disabled = true;
  el.multiResults.innerHTML = `<span class="muted-text">Testing ${hosts.length} hosts…</span>`;
  try {
    const d = await apiFetch(`/ping/multi?hosts=${encodeURIComponent(hosts.join(","))}&count=4`);
    const results = d.results || [];
    const rankClass = ["mc-1","mc-2","mc-3","mc-4"];
    el.multiResults.innerHTML = results.map((r,i) => `
      <div class="multi-card ${rankClass[i]||""}">
        <div class="mc-host">${r.host}</div>
        <div class="mc-lat">${r.latency_avg_ms != null ? r.latency_avg_ms+" ms" : "Unreachable"}</div>
        <div class="mc-loss">${r.packet_loss_percent != null ? r.packet_loss_percent+"% loss" : ""}</div>
        <div class="mc-grade grade-${r.quality?.grade??""}">${r.quality?.grade??""} — ${r.quality?.label??""}</div>
      </div>`).join("");
    toast(`Compared ${results.length} hosts`, "success");
  } catch (err) {
    el.multiResults.innerHTML = `<span class="muted-text" style="color:var(--red)">${err.message}</span>`;
    toast(`Multi-ping failed: ${err.message}`, "error");
  } finally {
    el.btnMultiPing.disabled = false;
  }
}

// ── DNS ────────────────────────────────────────────────────────────────────────

async function runDnsLookup() {
  const host = el.dnsHost.value.trim();
  if (!host) { toast("Enter a domain", "error"); return; }
  el.btnDns.disabled = true;
  el.resultDns.innerHTML = `<span class="muted-text">Resolving ${host}…</span>`;
  try {
    const d = await apiFetch(`/dns?host=${encodeURIComponent(host)}`);
    if (d.status === "error") { showErr(el.resultDns, d.error); toast(d.error, "error"); return; }
    el.resultDns.innerHTML =
      rrow("host", d.host) +
      rrow("resolved in", `${d.resolved_in_ms} ms`) +
      (d.addresses||[]).map(a => rrow(a.family, a.ip)).join("");
    toast(`${host} → ${d.addresses?.length} addresses`, "success");
  } catch (err) {
    showErr(el.resultDns, err.message);
    toast(err.message, "error");
  } finally {
    el.btnDns.disabled = false;
  }
}

// ── Bandwidth ──────────────────────────────────────────────────────────────────

async function fetchBandwidth() {
  try {
    const d = await apiFetch("/bandwidth");
    const ifaces = d.interfaces || [];
    if (!ifaces.length) { el.bwGrid.innerHTML = `<span class="muted-text">No active interfaces.</span>`; return; }
    const max = Math.max(1, ...ifaces.flatMap(i=>[i.recv_kbps, i.send_kbps]));
    el.bwGrid.innerHTML = ifaces.map(i => {
      const rw = Math.round((i.recv_kbps/max)*100);
      const sw = Math.round((i.send_kbps/max)*100);
      const fmtKb = v => v >= 1024 ? `${(v/1024).toFixed(1)} MB/s` : `${v} KB/s`;
      return `<div class="bw-card">
        <div class="bw-name">${i.interface}</div>
        <div class="bw-row"><span class="bw-lbl">↓</span><div class="bw-track"><div class="bw-fill bw-fill--r" style="width:${rw}%"></div></div><span class="bw-val">${fmtKb(i.recv_kbps)}</span></div>
        <div class="bw-row"><span class="bw-lbl">↑</span><div class="bw-track"><div class="bw-fill bw-fill--s" style="width:${sw}%"></div></div><span class="bw-val">${fmtKb(i.send_kbps)}</span></div>
        <div class="${i.is_up?"bw-up":"bw-down"}">${i.is_up?"● UP":"● DOWN"}</div>
      </div>`;
    }).join("");
  } catch (err) {
    el.bwGrid.innerHTML = `<span class="muted-text" style="color:var(--red)">${err.message}</span>`;
  }
}

function toggleBw() {
  if (bwRunning) {
    clearInterval(bwTimer); bwTimer = null; bwRunning = false;
    el.btnBwToggle.textContent = "▶ Live Bandwidth";
    el.bwStatusLabel.textContent = "Stopped";
    el.bwGrid.innerHTML = `<span class="muted-text">Monitor stopped.</span>`;
    toast("Bandwidth monitor stopped", "info");
  } else {
    bwRunning = true;
    el.btnBwToggle.textContent = "■ Stop";
    el.bwStatusLabel.textContent = "Live";
    fetchBandwidth();
    bwTimer = setInterval(fetchBandwidth, 2000);
    toast("Live bandwidth started", "info");
  }
}

// ── Interfaces ─────────────────────────────────────────────────────────────────

async function loadInterfaces() {
  el.tableInterfaces.innerHTML = `<span class="muted-text">Loading…</span>`;
  try {
    const d = await apiFetch("/interfaces");
    const rows = (d.interfaces||[]).map(i=>`<tr>
      <td>${i.name}</td><td>${i.ipv4??"—"}</td><td>${i.mac??"—"}</td>
      <td class="${i.is_up?"c-up":"c-down"}">${i.is_up?"UP":"DOWN"}</td>
      <td>${i.speed_mbps?`${i.speed_mbps} Mbps`:"—"}</td>
      <td>${formatBytes(i.bytes_sent)}</td><td>${formatBytes(i.bytes_recv)}</td>
    </tr>`).join("");
    el.tableInterfaces.innerHTML = `<table><thead><tr><th>Name</th><th>IPv4</th><th>MAC</th><th>Status</th><th>Speed</th><th>Sent</th><th>Recv</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (err) {
    el.tableInterfaces.innerHTML = `<span class="muted-text" style="color:var(--red)">${err.message}</span>`;
  }
}

// ── Connections ────────────────────────────────────────────────────────────────

async function loadConnections() {
  el.tableConns.innerHTML = `<span class="muted-text">Loading…</span>`;
  try {
    const d = await apiFetch("/connections");
    // BUG FIX: Store connections then render — was calling render before data loaded
    allConnections = d.connections || [];
    renderConnections(el.connSearch.value);
  } catch (err) {
    el.tableConns.innerHTML = `<span class="muted-text" style="color:var(--red)">${err.message}</span>`;
  }
}

function renderConnections(filter = "") {
  const fl = filter.toLowerCase();
  const list = fl
    ? allConnections.filter(c=>(c.process??"").toLowerCase().includes(fl)||(c.local_address??"").includes(fl))
    : allConnections;

  if (!list.length) { el.tableConns.innerHTML = `<span class="muted-text">No connections match "${filter}".</span>`; return; }

  const sc = s => s==="ESTABLISHED"?"c-estab":s==="LISTEN"?"c-listen":"c-other";
  const rows = list.map(c=>`<tr>
    <td>${c.type}</td><td>${c.local_address??"—"}</td><td>${c.remote_address??"—"}</td>
    <td class="${sc(c.status)}">${c.status??"—"}</td>
    <td>${c.process??"—"}</td><td>${c.pid??"—"}</td>
  </tr>`).join("");
  el.tableConns.innerHTML = `<table><thead><tr><th>Type</th><th>Local</th><th>Remote</th><th>Status</th><th>Process</th><th>PID</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ── Anomaly List ───────────────────────────────────────────────────────────────

async function loadAnomalies() {
  try {
    const d = await apiFetch("/anomalies?limit=20");
    const list = d.anomalies || [];
    if (!list.length) {
      el.anomalyList.innerHTML = `<span class="muted-text">No anomalies detected yet. Run some tests to build a baseline.</span>`;
      return;
    }
    el.anomalyList.innerHTML = list.map(a => `
      <div class="anomaly-card ${a.severity}">
        <div class="ac-header">
          <span class="ac-badge">${a.severity}</span>
          <span class="ac-type">${a.test_type} test${a.host ? " · "+a.host : ""}</span>
          <span class="ac-time">${shortTime(a.timestamp)}</span>
        </div>
        <div class="ac-reasons">
          ${(a.reasons||[]).map(r=>`<div class="ac-reason">${r}</div>`).join("")}
        </div>
      </div>`).join("");
  } catch (err) {
    el.anomalyList.innerHTML = `<span class="muted-text" style="color:var(--red)">${err.message}</span>`;
  }
}

// ── Health Timeline Chart ──────────────────────────────────────────────────────

async function loadHealthChart() {
  try {
    const d = await apiFetch("/history?test_type=ping&limit=30");
    const records = (d.records||[]).filter(r=>r.quality?.score!=null).reverse();
    if (!records.length) return;

    const labels = records.map(r=>shortTime(r.timestamp));
    const scores = records.map(r=>r.quality.score);

    if (chartHealth) chartHealth.destroy();

    chartHealth = new Chart(el.chartHealth, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Health Score",
          data: scores,
          borderColor: "url(#health-grad)",   // will fallback
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: scores.map(s => s>=75?"#22d78a":s>=55?"#f5c842":"#f05474"),
          tension: .35,
          fill: true,
          backgroundColor: (ctx) => {
            const g = ctx.chart.ctx.createLinearGradient(0,0,0,ctx.chart.height);
            g.addColorStop(0,"rgba(124,111,239,0.25)");
            g.addColorStop(1,"rgba(124,111,239,0)");
            return g;
          },
          segment: {
            borderColor: ctx => {
              const v = ctx.p1.parsed.y;
              return v>=75?"#22d78a":v>=55?"#f5c842":"#f05474";
            }
          }
        }]
      },
      options: {
        responsive:true, animation:{duration:400},
        plugins: {
          legend:{display:false},
          tooltip:{
            backgroundColor:"#0d1220",borderColor:"rgba(99,120,180,.3)",borderWidth:1,
            titleColor:"#e4eaf8",bodyColor:"#8fa4cc",
            callbacks:{
              label: ctx => ` ${ctx.parsed.y}/100 — ${ctx.parsed.y>=90?"Excellent":ctx.parsed.y>=75?"Good":ctx.parsed.y>=55?"Fair":ctx.parsed.y>=30?"Poor":"Critical"}`
            }
          }
        },
        scales:{
          x:{ticks:{color:"#5a6a8a",font:{family:"JetBrains Mono",size:9},maxTicksLimit:8},grid:{color:"rgba(99,120,180,.1)"}},
          y:{
            min:0,max:100,
            ticks:{color:"#5a6a8a",font:{family:"JetBrains Mono",size:9},stepSize:25},
            grid:{color:"rgba(99,120,180,.1)"},
            title:{display:true,text:"Score",color:"#5a6a8a",font:{family:"JetBrains Mono",size:9}},
          }
        }
      }
    });
  } catch { /* no data */ }
}

// ── Ping / Speed Charts ────────────────────────────────────────────────────────

const CHART_OPT = {
  responsive:true, animation:{duration:400},
  plugins:{
    legend:{labels:{color:"#5a6a8a",font:{family:"JetBrains Mono",size:10},boxWidth:10}},
    tooltip:{backgroundColor:"#0d1220",borderColor:"rgba(99,120,180,.3)",borderWidth:1,titleColor:"#e4eaf8",bodyColor:"#8fa4cc",titleFont:{family:"JetBrains Mono",size:10},bodyFont:{family:"JetBrains Mono",size:10}}
  },
  scales:{
    x:{ticks:{color:"#5a6a8a",font:{family:"JetBrains Mono",size:9},maxTicksLimit:8},grid:{color:"rgba(99,120,180,.1)"}},
    y:{ticks:{color:"#5a6a8a",font:{family:"JetBrains Mono",size:9}},grid:{color:"rgba(99,120,180,.1)"}}
  }
};

async function loadPingChart() {
  try {
    const d = await apiFetch("/history?test_type=ping&limit=30");
    const r = (d.records||[]).filter(x=>x.latency_avg_ms!=null).reverse();
    if (chartPing) chartPing.destroy();
    chartPing = new Chart(el.chartPingCanvas, {
      type:"line",
      data:{ labels:r.map(x=>shortTime(x.timestamp)), datasets:[
        {label:"Avg (ms)",data:r.map(x=>x.latency_avg_ms),borderColor:"#7c6fef",backgroundColor:"rgba(124,111,239,.08)",borderWidth:2,pointRadius:3,tension:.3,fill:true},
        {label:"Min (ms)",data:r.map(x=>x.latency_min_ms),borderColor:"#22d78a",borderWidth:1,pointRadius:2,borderDash:[4,3],tension:.3},
        {label:"Max (ms)",data:r.map(x=>x.latency_max_ms),borderColor:"#f5c842",borderWidth:1,pointRadius:2,borderDash:[4,3],tension:.3},
      ]},
      options:{...CHART_OPT,scales:{...CHART_OPT.scales,y:{...CHART_OPT.scales.y,title:{display:true,text:"ms",color:"#5a6a8a",font:{family:"JetBrains Mono",size:9}}}}}
    });
  } catch {}
}

async function loadSpeedChart() {
  try {
    const d = await apiFetch("/history?test_type=speed&limit=20");
    const r = (d.records||[]).filter(x=>x.download_mbps!=null).reverse();
    if (chartSpeed) chartSpeed.destroy();
    chartSpeed = new Chart(el.chartSpeedCanvas, {
      type:"bar",
      data:{ labels:r.map(x=>shortTime(x.timestamp)), datasets:[
        {label:"Download (Mbps)",data:r.map(x=>x.download_mbps),backgroundColor:"rgba(124,111,239,.7)",borderColor:"#7c6fef",borderWidth:1,borderRadius:4},
        {label:"Upload (Mbps)",  data:r.map(x=>x.upload_mbps),  backgroundColor:"rgba(63,184,240,.5)",borderColor:"#3fb8f0",borderWidth:1,borderRadius:4},
      ]},
      options:{...CHART_OPT,scales:{...CHART_OPT.scales,y:{...CHART_OPT.scales.y,title:{display:true,text:"Mbps",color:"#5a6a8a",font:{family:"JetBrains Mono",size:9}}}}}
    });
  } catch {}
}

// ── History Table ──────────────────────────────────────────────────────────────

async function loadHistoryTable(filter="all") {
  el.historyTable.innerHTML = `<span class="muted-text">Loading…</span>`;
  try {
    const d = await apiFetch(`/history?limit=100${filter!=="all"?"&test_type="+filter:""}`);
    const records = d.records||[];
    historyQueue.loadAll([...records].reverse());
    el.historyCount.textContent = `${records.length} records`;

    if (!records.length) { el.historyTable.innerHTML=`<span class="muted-text">No records yet.</span>`; return; }

    const rows = records.map(r => {
      const ip = r.test_type==="ping";
      const badge = ip?`<span class="badge badge--ping">ping</span>`:`<span class="badge badge--speed">speed</span>`;
      const primary   = ip?(r.latency_avg_ms!=null?`${r.latency_avg_ms} ms`:"—"):(r.download_mbps!=null?`↓${r.download_mbps} Mbps`:"—");
      const secondary = ip?(r.packet_loss_percent!=null?`${r.packet_loss_percent}% loss`:"—"):(r.upload_mbps!=null?`↑${r.upload_mbps} Mbps`:"—");
      const g = r.quality?.grade??"—";
      const sc = r.status?.startsWith("success")?"c-estab":"c-other";
      return `<tr><td>${badge}</td><td>${shortTime(r.timestamp)}</td><td>${r.host??r.server_name??"—"}</td><td>${primary}</td><td>${secondary}</td><td class="grade-${g}">${g}</td><td class="${sc}">${r.status??"—"}</td></tr>`;
    }).join("");

    el.historyTable.innerHTML = `<table><thead><tr><th>Type</th><th>Time</th><th>Host</th><th>Primary</th><th>Secondary</th><th>Grade</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (err) {
    el.historyTable.innerHTML = `<span class="muted-text" style="color:var(--red)">${err.message}</span>`;
  }
}

// ── CSV Export ─────────────────────────────────────────────────────────────────

function exportCsv() {
  const records = historyQueue.toArray();
  if (!records.length) { toast("No records to export", "error"); return; }
  const headers = ["id","test_type","timestamp","host","latency_avg_ms","packet_loss_percent","download_mbps","upload_mbps","quality_score","quality_grade","status"];
  const rows = records.map(r=>[r.id??"",r.test_type??"",r.timestamp??"",r.host??r.server_name??"",r.latency_avg_ms??"",r.packet_loss_percent??"",r.download_mbps??"",r.upload_mbps??"",r.quality?.score??"",r.quality?.grade??"",r.status??""]);
  const csv  = [headers, ...rows].map(r=>r.join(",")).join("\n");
  const a = Object.assign(document.createElement("a"), {href:URL.createObjectURL(new Blob([csv],{type:"text/csv"})),download:`netprobe-${Date.now()}.csv`});
  a.click(); URL.revokeObjectURL(a.href);
  toast("CSV exported!", "success");
}

// ── Clear History ──────────────────────────────────────────────────────────────

async function clearHistory() {
  if (!confirm("Delete all history? Cannot be undone.")) return;
  try {
    await apiDelete("/history");
    historyQueue.loadAll([]);
    el.historyTable.innerHTML = `<span class="muted-text">History cleared.</span>`;
    el.historyCount.textContent = "0 records";
    await loadSummary();
    if (chartPing)   { chartPing.destroy();   chartPing   = null; }
    if (chartSpeed)  { chartSpeed.destroy();  chartSpeed  = null; }
    if (chartHealth) { chartHealth.destroy(); chartHealth = null; }
    toast("History cleared", "success");
  } catch (err) { toast(err.message, "error"); }
}

// ── Clock ──────────────────────────────────────────────────────────────────────

function updateClock() { el.footerTime.textContent = new Date().toLocaleTimeString(); }

// ── Event Listeners ────────────────────────────────────────────────────────────

el.btnTheme.addEventListener("click", toggleTheme);

el.btnPing.addEventListener("click", runPingTest);
el.pingHost.addEventListener("keydown",  e => { if(e.key==="Enter") runPingTest(); });
el.pingCount.addEventListener("keydown", e => { if(e.key==="Enter") runPingTest(); });
el.autoPingToggle.addEventListener("change", e => e.target.checked ? startAutoPing() : stopAutoPing());

el.btnSpeed.addEventListener("click", runSpeedTest);
el.btnMultiPing.addEventListener("click", runMultiPing);
el.multiHosts.addEventListener("keydown", e => { if(e.key==="Enter") runMultiPing(); });
el.btnDns.addEventListener("click", runDnsLookup);
el.dnsHost.addEventListener("keydown", e => { if(e.key==="Enter") runDnsLookup(); });

el.btnBwToggle.addEventListener("click", toggleBw);
el.btnInterfaces.addEventListener("click", loadInterfaces);
el.btnConnections.addEventListener("click", loadConnections);
el.connSearch.addEventListener("input", e => renderConnections(e.target.value));

el.btnRefreshHealth.addEventListener("click", loadHealthChart);
el.btnRefreshPingChart.addEventListener("click", loadPingChart);
el.btnRefreshSpeedChart.addEventListener("click", loadSpeedChart);
el.btnRefreshAnomalies.addEventListener("click", loadAnomalies);

el.historyFilter.addEventListener("change", e => loadHistoryTable(e.target.value));
el.btnExportCsv.addEventListener("click", exportCsv);
el.btnClearHistory.addEventListener("click", clearHistory);

el.btnReset.addEventListener("click", resetOverview);
el.btnDismissBanner.addEventListener("click", () => { el.anomalyBanner.style.display = "none"; });

// Clean up timers on page unload (BUG FIX: prevents memory leak)
window.addEventListener("beforeunload", () => {
  clearInterval(autoPingTimer);
  clearInterval(bwTimer);
});

// ── Init ───────────────────────────────────────────────────────────────────────

async function init() {
  loadTheme();
  initNav();
  updateClock();
  setInterval(updateClock, 1000);
  await checkApiStatus();
  setInterval(checkApiStatus, 10_000);
  await loadSummary();
  await loadTrends();
  await loadHealthChart();
}

init();
