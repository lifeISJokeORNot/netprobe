/**
 * app.js — NetProbe Dashboard Logic
 * Fetches data from the FastAPI backend and renders everything.
 */

const API = "http://localhost:8000";

// ── DOM References ────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

const els = {
  apiDot:       $("api-status-dot"),
  apiLabel:     $("api-status-label"),

  // Stat cards
  statPing:     $("stat-ping"),
  statDownload: $("stat-download"),
  statUpload:   $("stat-upload"),
  statTests:    $("stat-tests"),

  // Ping test
  pingHost:     $("ping-host"),
  pingCount:    $("ping-count"),
  btnPing:      $("btn-ping"),
  resultPing:   $("result-ping"),

  // Speed test
  btnSpeed:     $("btn-speed"),
  resultSpeed:  $("result-speed"),

  // Tables
  btnInterfaces:   $("btn-interfaces"),
  btnConnections:  $("btn-connections"),
  tableInterfaces: $("table-interfaces"),
  tableConns:      $("table-connections"),

  // Charts
  btnRefreshPingChart:  $("btn-refresh-ping-chart"),
  btnRefreshSpeedChart: $("btn-refresh-speed-chart"),
  chartPingCanvas:      $("chart-ping"),
  chartSpeedCanvas:     $("chart-speed"),

  // Loading overlay
  overlay:    $("loading-overlay"),
  loadingMsg: $("loading-msg"),

  // Footer clock
  footerTime: $("footer-time"),

  // Overview actions
  btnReset:        $("btn-reset"),
  btnHistoryModal: $("btn-history-modal"),

  // History modal
  modalBackdrop: $("modal-backdrop"),
  btnModalClose: $("btn-modal-close"),
  modalFilter:   $("modal-filter"),
  modalTable:    $("modal-table"),
  modalCount:    $("modal-count"),
};

// ── Chart instances (kept so we can destroy & redraw) ─────────────────────────

let chartPing  = null;
let chartSpeed = null;

// ── Utilities ─────────────────────────────────────────────────────────────────

function showLoading(msg = "Running test…") {
  els.loadingMsg.textContent = msg;
  els.overlay.classList.add("active");
  els.overlay.setAttribute("aria-hidden", "false");
}

function hideLoading() {
  els.overlay.classList.remove("active");
  els.overlay.setAttribute("aria-hidden", "true");
}

/**
 * Generic fetch wrapper — returns parsed JSON or throws.
 */
async function apiFetch(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Build a result-box row (key → value).
 * valueClass: 'ok' | 'err' | 'warn' | '' (default cyan)
 */
function resultRow(key, value, valueClass = "") {
  return `
    <div class="result-row">
      <span class="result-key">${key}</span>
      <span class="result-val ${valueClass}">${value ?? "—"}</span>
    </div>`;
}

/**
 * Show an error message inside a result box.
 */
function showError(el, message) {
  el.innerHTML = resultRow("error", message, "err");
}

/**
 * Format bytes → KB / MB / GB string.
 */
function formatBytes(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1_073_741_824) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  return `${(bytes / 1_073_741_824).toFixed(2)} GB`;
}

/**
 * Short timestamp label for charts (HH:MM:SS).
 */
function shortTime(isoString) {
  try {
    return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return isoString;
  }
}

// ── API Health Check ──────────────────────────────────────────────────────────

async function checkApiStatus() {
  try {
    await apiFetch("/");
    els.apiDot.className   = "status-dot online";
    els.apiLabel.textContent = "API online";
  } catch {
    els.apiDot.className   = "status-dot offline";
    els.apiLabel.textContent = "API offline";
  }
}

// ── Summary Cards ─────────────────────────────────────────────────────────────

async function loadSummary() {
  try {
    const data = await apiFetch("/history?limit=100");
    const records = data.records || [];

    const pings  = records.filter(r => r.test_type === "ping"  && r.latency_avg_ms != null);
    const speeds = records.filter(r => r.test_type === "speed" && r.download_mbps  != null);

    const avg = arr => arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1) : "—";

    els.statPing.textContent     = avg(pings.map(r => r.latency_avg_ms));
    els.statDownload.textContent = avg(speeds.map(r => r.download_mbps));
    els.statUpload.textContent   = avg(speeds.map(r => r.upload_mbps));
    els.statTests.textContent    = records.length;
  } catch {
    // Silently fail — API may not be up yet
  }
}

// ── Ping Test ─────────────────────────────────────────────────────────────────

async function runPingTest() {
  const host  = els.pingHost.value.trim()  || "8.8.8.8";
  const count = parseInt(els.pingCount.value) || 4;

  els.btnPing.disabled = true;
  els.resultPing.innerHTML = `<span class="result-placeholder">Pinging ${host}…</span>`;

  try {
    const data = await apiFetch(`/ping?host=${encodeURIComponent(host)}&count=${count}`);

    // Pick colour class based on avg latency
    let latClass = "ok";
    if (data.latency_avg_ms == null)    latClass = "err";
    else if (data.latency_avg_ms > 150) latClass = "warn";
    else if (data.latency_avg_ms > 300) latClass = "err";

    let lossClass = "ok";
    if (data.packet_loss_percent > 0  && data.packet_loss_percent < 20) lossClass = "warn";
    if (data.packet_loss_percent >= 20) lossClass = "err";

    els.resultPing.innerHTML = [
      resultRow("host",         data.host),
      resultRow("status",       data.status, data.status === "success" ? "ok" : "err"),
      resultRow("packets sent", data.packets_sent),
      resultRow("packets recv", data.packets_received),
      resultRow("packet loss",  data.packet_loss_percent != null ? `${data.packet_loss_percent}%` : "—", lossClass),
      resultRow("latency min",  data.latency_min_ms != null ? `${data.latency_min_ms} ms` : "—"),
      resultRow("latency avg",  data.latency_avg_ms != null ? `${data.latency_avg_ms} ms` : "—", latClass),
      resultRow("latency max",  data.latency_max_ms != null ? `${data.latency_max_ms} ms` : "—"),
    ].join("");

    // Refresh summary + chart
    await loadSummary();
    await loadPingChart();

  } catch (err) {
    showError(els.resultPing, err.message);
  } finally {
    els.btnPing.disabled = false;
  }
}

// ── Speed Test ────────────────────────────────────────────────────────────────

async function runSpeedTest() {
  els.btnSpeed.disabled = true;
  showLoading("Running speed test — this may take up to 30 seconds…");

  try {
    const data = await apiFetch("/speed");

    let dlClass = "ok";
    if (data.download_mbps != null && data.download_mbps < 10) dlClass = "warn";
    if (data.download_mbps != null && data.download_mbps < 2)  dlClass = "err";

    els.resultSpeed.innerHTML = [
      resultRow("status",       data.status, data.status === "success" ? "ok" : "err"),
      resultRow("download",     data.download_mbps != null ? `${data.download_mbps} Mbps` : "—", dlClass),
      resultRow("upload",       data.upload_mbps   != null ? `${data.upload_mbps} Mbps`   : "—"),
      resultRow("ping",         data.ping_ms       != null ? `${data.ping_ms} ms`         : "—"),
      resultRow("server",       data.server_name   ?? "—"),
      resultRow("country",      data.server_country ?? "—"),
      resultRow("sponsor",      data.server_sponsor ?? "—"),
    ].join("");

    // Refresh summary + chart
    await loadSummary();
    await loadSpeedChart();

  } catch (err) {
    showError(els.resultSpeed, err.message);
  } finally {
    hideLoading();
    els.btnSpeed.disabled = false;
  }
}

// ── Interfaces Table ──────────────────────────────────────────────────────────

async function loadInterfaces() {
  els.tableInterfaces.innerHTML = `<span class="result-placeholder">Loading…</span>`;

  try {
    const data = await apiFetch("/interfaces");
    const ifaces = data.interfaces || [];

    if (!ifaces.length) {
      els.tableInterfaces.innerHTML = `<span class="result-placeholder">No interfaces found.</span>`;
      return;
    }

    const rows = ifaces.map(i => `
      <tr>
        <td>${i.name}</td>
        <td>${i.ipv4 ?? "—"}</td>
        <td>${i.mac  ?? "—"}</td>
        <td class="${i.is_up ? "td-up" : "td-down"}">${i.is_up ? "UP" : "DOWN"}</td>
        <td>${i.speed_mbps ? `${i.speed_mbps} Mbps` : "—"}</td>
        <td>${formatBytes(i.bytes_sent)}</td>
        <td>${formatBytes(i.bytes_recv)}</td>
      </tr>`).join("");

    els.tableInterfaces.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Name</th><th>IPv4</th><th>MAC</th>
            <th>Status</th><th>Speed</th><th>Sent</th><th>Received</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    els.tableInterfaces.innerHTML = `<span class="result-placeholder" style="color:var(--red)">Error: ${err.message}</span>`;
  }
}

// ── Connections Table ─────────────────────────────────────────────────────────

async function loadConnections() {
  els.tableConns.innerHTML = `<span class="result-placeholder">Loading…</span>`;

  try {
    const data = await apiFetch("/connections");
    const conns = data.connections || [];

    if (!conns.length) {
      els.tableConns.innerHTML = `<span class="result-placeholder">No active connections.</span>`;
      return;
    }

    const statusClass = s => {
      if (!s) return "td-status-other";
      if (s === "ESTABLISHED") return "td-status-established";
      if (s === "LISTEN")      return "td-status-listen";
      return "td-status-other";
    };

    const rows = conns.map(c => `
      <tr>
        <td>${c.type}</td>
        <td>${c.local_address  ?? "—"}</td>
        <td>${c.remote_address ?? "—"}</td>
        <td class="${statusClass(c.status)}">${c.status ?? "—"}</td>
        <td>${c.process ?? "—"}</td>
      </tr>`).join("");

    els.tableConns.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Type</th><th>Local</th><th>Remote</th>
            <th>Status</th><th>Process</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    els.tableConns.innerHTML = `<span class="result-placeholder" style="color:var(--red)">Error: ${err.message}</span>`;
  }
}

// ── Chart helpers ─────────────────────────────────────────────────────────────

const CHART_DEFAULTS = {
  responsive: true,
  animation: { duration: 400 },
  plugins: {
    legend: {
      labels: {
        color: "#6b7c93",
        font: { family: "'DM Mono', monospace", size: 11 },
        boxWidth: 12,
      }
    },
    tooltip: {
      backgroundColor: "#0f1217",
      borderColor: "#1e2530",
      borderWidth: 1,
      titleColor: "#e8edf3",
      bodyColor:  "#a8c0d6",
      titleFont:  { family: "'DM Mono', monospace", size: 11 },
      bodyFont:   { family: "'DM Mono', monospace", size: 11 },
    }
  },
  scales: {
    x: {
      ticks: { color: "#6b7c93", font: { family: "'DM Mono', monospace", size: 10 }, maxTicksLimit: 8 },
      grid:  { color: "#1e2530" },
    },
    y: {
      ticks: { color: "#6b7c93", font: { family: "'DM Mono', monospace", size: 10 } },
      grid:  { color: "#1e2530" },
    }
  }
};

// ── Ping History Chart ────────────────────────────────────────────────────────

async function loadPingChart() {
  try {
    const data = await apiFetch("/history?test_type=ping&limit=30");
    const records = (data.records || [])
      .filter(r => r.latency_avg_ms != null)
      .reverse();   // oldest → newest left to right

    const labels = records.map(r => shortTime(r.timestamp));
    const avgMs  = records.map(r => r.latency_avg_ms);
    const minMs  = records.map(r => r.latency_min_ms);
    const maxMs  = records.map(r => r.latency_max_ms);

    if (chartPing) chartPing.destroy();

    chartPing = new Chart(els.chartPingCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Avg (ms)",
            data: avgMs,
            borderColor: "#00e5ff",
            backgroundColor: "rgba(0,229,255,0.08)",
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: "#00e5ff",
            tension: 0.3,
            fill: true,
          },
          {
            label: "Min (ms)",
            data: minMs,
            borderColor: "#00ff88",
            backgroundColor: "transparent",
            borderWidth: 1,
            pointRadius: 2,
            borderDash: [4, 3],
            tension: 0.3,
          },
          {
            label: "Max (ms)",
            data: maxMs,
            borderColor: "#ffd166",
            backgroundColor: "transparent",
            borderWidth: 1,
            pointRadius: 2,
            borderDash: [4, 3],
            tension: 0.3,
          },
        ]
      },
      options: {
        ...CHART_DEFAULTS,
        scales: {
          ...CHART_DEFAULTS.scales,
          y: {
            ...CHART_DEFAULTS.scales.y,
            title: {
              display: true,
              text: "ms",
              color: "#6b7c93",
              font: { family: "'DM Mono', monospace", size: 10 }
            }
          }
        }
      }
    });
  } catch {
    // Chart stays blank if no data yet
  }
}

// ── Speed History Chart ───────────────────────────────────────────────────────

async function loadSpeedChart() {
  try {
    const data = await apiFetch("/history?test_type=speed&limit=20");
    const records = (data.records || [])
      .filter(r => r.download_mbps != null)
      .reverse();

    const labels   = records.map(r => shortTime(r.timestamp));
    const download = records.map(r => r.download_mbps);
    const upload   = records.map(r => r.upload_mbps);

    if (chartSpeed) chartSpeed.destroy();

    chartSpeed = new Chart(els.chartSpeedCanvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Download (Mbps)",
            data: download,
            backgroundColor: "rgba(0,229,255,0.7)",
            borderColor: "#00e5ff",
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: "Upload (Mbps)",
            data: upload,
            backgroundColor: "rgba(0,255,136,0.5)",
            borderColor: "#00ff88",
            borderWidth: 1,
            borderRadius: 4,
          },
        ]
      },
      options: {
        ...CHART_DEFAULTS,
        scales: {
          ...CHART_DEFAULTS.scales,
          y: {
            ...CHART_DEFAULTS.scales.y,
            title: {
              display: true,
              text: "Mbps",
              color: "#6b7c93",
              font: { family: "'DM Mono', monospace", size: 10 }
            }
          }
        }
      }
    });
  } catch {
    // Chart stays blank if no data yet
  }
}

// ── Footer Clock ──────────────────────────────────────────────────────────────

function updateClock() {
  els.footerTime.textContent = new Date().toLocaleTimeString();
}

// ── Event Listeners ───────────────────────────────────────────────────────────

els.btnPing.addEventListener("click", runPingTest);
els.btnSpeed.addEventListener("click", runSpeedTest);

els.btnInterfaces.addEventListener("click", loadInterfaces);
els.btnConnections.addEventListener("click", loadConnections);

els.btnRefreshPingChart.addEventListener("click", loadPingChart);
els.btnRefreshSpeedChart.addEventListener("click", loadSpeedChart);

// Allow pressing Enter in ping inputs to trigger the test
els.pingHost.addEventListener("keydown",  e => { if (e.key === "Enter") runPingTest(); });
els.pingCount.addEventListener("keydown", e => { if (e.key === "Enter") runPingTest(); });

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  updateClock();
  setInterval(updateClock, 1000);

  // Check API health every 10 seconds
  await checkApiStatus();
  setInterval(checkApiStatus, 10_000);

  // Load initial data
  await loadSummary();
  await loadInterfaces();
  await loadConnections();
  await loadPingChart();
  await loadSpeedChart();
}

init();

// ── Circular Queue (size 31) ──────────────────────────────────────────────────

class CircularQueue {
  constructor(maxSize = 31) {
    this.maxSize = maxSize;
    this.queue   = [];
  }

  /** Add one record. If full, drop the oldest. */
  enqueue(record) {
    if (this.queue.length >= this.maxSize) this.queue.shift();
    this.queue.push(record);
  }

  /** Bulk-load an array, keeping only the last maxSize entries. */
  loadAll(records) {
    this.queue = records.slice(-this.maxSize);
  }

  /** Return all records newest-first (for display). */
  toArray() { return [...this.queue].reverse(); }

  get size() { return this.queue.length; }
}

const historyQueue = new CircularQueue(31);

// ── Reset Overview ────────────────────────────────────────────────────────────

function resetOverview() {
  els.statPing.textContent     = "—";
  els.statDownload.textContent = "—";
  els.statUpload.textContent   = "—";
  els.statTests.textContent    = "—";
}

// ── History Modal ─────────────────────────────────────────────────────────────

async function openHistoryModal() {
  try {
    const data = await apiFetch("/history?limit=31");
    // API returns newest-first; reverse so queue is oldest→newest
    historyQueue.loadAll((data.records || []).reverse());
  } catch { /* use whatever is already in the queue */ }

  renderModalTable(els.modalFilter.value);
  els.modalBackdrop.classList.add("active");
  els.modalBackdrop.setAttribute("aria-hidden", "false");
}

function closeHistoryModal() {
  els.modalBackdrop.classList.remove("active");
  els.modalBackdrop.setAttribute("aria-hidden", "true");
}

function renderModalTable(filter = "all") {
  let records = historyQueue.toArray();   // newest first
  if (filter === "ping")  records = records.filter(r => r.test_type === "ping");
  if (filter === "speed") records = records.filter(r => r.test_type === "speed");

  els.modalCount.textContent = records.length;

  if (!records.length) {
    els.modalTable.innerHTML = `<span class="result-placeholder">No records found.</span>`;
    return;
  }

  const rows = records.map(r => {
    const isPing  = r.test_type === "ping";
    const isSpeed = r.test_type === "speed";

    const badge = isPing
      ? `<span class="badge badge--ping">ping</span>`
      : `<span class="badge badge--speed">speed</span>`;

    let metric  = "—";
    let metric2 = "—";

    if (isPing) {
      if (r.latency_avg_ms     != null) metric  = `${r.latency_avg_ms} ms avg`;
      if (r.packet_loss_percent != null) metric2 = `${r.packet_loss_percent}% loss`;
    }
    if (isSpeed) {
      if (r.download_mbps != null) metric  = `↓ ${r.download_mbps} Mbps`;
      if (r.upload_mbps   != null) metric2 = `↑ ${r.upload_mbps} Mbps`;
    }

    const statusClass =
      r.status === "success"                               ? "td-status-established" :
      r.status === "unreachable" || r.status === "error"  ? "td-status-other"        : "";

    return `
      <tr>
        <td>${badge}</td>
        <td style="font-family:var(--font-mono);font-size:0.72rem">${shortTime(r.timestamp)}</td>
        <td>${r.host ?? r.server_name ?? "—"}</td>
        <td style="font-family:var(--font-mono)">${metric}</td>
        <td style="font-family:var(--font-mono)">${metric2}</td>
        <td class="${statusClass}">${r.status ?? "—"}</td>
      </tr>`;
  }).join("");

  els.modalTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Type</th><th>Time</th><th>Host / Server</th>
          <th>Primary</th><th>Secondary</th><th>Status</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── New Event Listeners ───────────────────────────────────────────────────────

// Reset overview cards
els.btnReset.addEventListener("click", resetOverview);

// Open history modal
els.btnHistoryModal.addEventListener("click", openHistoryModal);

// Close modal — button or clicking the dark backdrop
els.btnModalClose.addEventListener("click", closeHistoryModal);
els.modalBackdrop.addEventListener("click", e => {
  if (e.target === els.modalBackdrop) closeHistoryModal();
});

// Close modal with Escape key
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeHistoryModal();
});

// Filter dropdown inside modal — re-render without re-fetching
els.modalFilter.addEventListener("change", e => {
  renderModalTable(e.target.value);
});
