/* ==========================================================================
   SIMP Dashboard — Frontend Logic
   Pure vanilla JS. No frameworks. No build tools.
   ========================================================================== */

(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Config
  // -----------------------------------------------------------------------

  const REFRESH_INTERVAL = 5000; // ms
  const API_BASE = "";           // same origin

  // -----------------------------------------------------------------------
  // DOM refs
  // -----------------------------------------------------------------------

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const dom = {
    brokerDot:       $("#broker-dot"),
    brokerLabel:     $("#broker-label"),
    refreshBtn:      $("#refresh-btn"),
    countdown:       $("#countdown"),
    unreachable:     $("#unreachable-banner"),

    // Overview cards
    valBrokerStatus: $("#val-broker-status"),
    valBrokerState:  $("#val-broker-state"),
    valAgentsOnline: $("#val-agents-online"),
    valPending:      $("#val-pending"),
    valReceived:     $("#val-received"),
    valRouted:       $("#val-routed"),
    valFailed:       $("#val-failed"),
    valAvgRoute:     $("#val-avg-route"),

    // Tables / grids
    agentsTbody:     $("#agents-tbody"),
    capGrid:         $("#cap-grid"),
    activityFeed:    $("#activity-feed"),

    // Protocol
    valUptime:       $("#val-uptime"),
    valLastRefresh:  $("#val-last-refresh"),
  };

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  let brokerReachable = false;
  let countdownValue = REFRESH_INTERVAL / 1000;
  let countdownTimer = null;
  let dashboardStartedAt = null;

  // -----------------------------------------------------------------------
  // Fetch helpers
  // -----------------------------------------------------------------------

  async function apiFetch(path) {
    try {
      const res = await fetch(API_BASE + path);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  // -----------------------------------------------------------------------
  // Render: Overview
  // -----------------------------------------------------------------------

  function renderHealth(data) {
    if (!data || data.status === "unreachable") {
      setBrokerUnreachable();
      return;
    }
    setBrokerReachable(data.status);
    dom.valBrokerStatus.textContent = data.status || "--";
    dom.valBrokerStatus.className = "card-value status-" + statusClass(data.status);
    dom.valBrokerState.textContent = data.state || "--";
    dom.valAgentsOnline.textContent = data.agents_online ?? "--";
    dom.valPending.textContent = data.pending_intents ?? "--";
  }

  function renderStats(data) {
    if (!data || data.status === "unreachable") return;
    const broker = data.broker || {};
    const stats = broker.stats || {};
    dom.valReceived.textContent = stats.intents_received ?? "--";
    dom.valRouted.textContent = stats.intents_routed ?? "--";
    dom.valFailed.textContent = stats.intents_failed ?? "--";

    const avg = stats.avg_route_time_ms;
    dom.valAvgRoute.textContent = avg != null ? avg.toFixed(1) + " ms" : "--";

    // Update cards that may also appear in stats
    if (stats.agents_online != null) {
      dom.valAgentsOnline.textContent = stats.agents_online;
    }
    if (stats.pending_intents != null) {
      dom.valPending.textContent = stats.pending_intents;
    }
    if (broker.state) {
      dom.valBrokerState.textContent = broker.state;
    }

    // Color the failed card red if > 0
    if ((stats.intents_failed || 0) > 0) {
      dom.valFailed.className = "card-value mono status-error";
    } else {
      dom.valFailed.className = "card-value mono";
    }

    if (!dashboardStartedAt && data.dashboard_started_at) {
      dashboardStartedAt = data.dashboard_started_at;
    }
  }

  // -----------------------------------------------------------------------
  // Render: Agents Table
  // -----------------------------------------------------------------------

  function renderAgents(data) {
    if (!data || data.status === "unreachable") {
      dom.agentsTbody.innerHTML = '<tr><td colspan="8" class="empty-row">Broker unreachable</td></tr>';
      return;
    }
    const agents = data.agents || {};
    const keys = Object.keys(agents);
    if (keys.length === 0) {
      dom.agentsTbody.innerHTML = '<tr><td colspan="8" class="empty-row">No agents registered</td></tr>';
      return;
    }

    // Sort alphabetically
    keys.sort();
    let html = "";
    for (const id of keys) {
      const a = agents[id];
      const meta = a.metadata || {};
      const mode = detectMode(a.endpoint);
      const caps = meta.capabilities || [];
      const status = a.status || "unknown";

      html += "<tr>";
      html += td(mono(escHtml(a.agent_id || id)));
      html += td(escHtml(meta.name || a.agent_type || id));
      html += td(modeBadge(mode));
      html += td(statusBadge(status));
      html += td(caps.map(capPill).join(" ") || '<span class="text-muted">none</span>');
      html += td(mono(a.intents_received ?? "--"), "col-num");
      html += td(mono(a.intents_completed ?? "--"), "col-num");
      html += td('<span class="mono" style="font-size:0.75rem">' + formatDate(a.registered_at) + "</span>");
      html += "</tr>";
    }
    dom.agentsTbody.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Capability Map
  // -----------------------------------------------------------------------

  function renderCapabilities(data) {
    if (!data || data.status === "unreachable") {
      dom.capGrid.innerHTML = '<div class="empty-state">Broker unreachable</div>';
      return;
    }
    const caps = data.capabilities || {};
    const entries = Object.entries(caps);
    if (entries.length === 0) {
      dom.capGrid.innerHTML = '<div class="empty-state">No capabilities found</div>';
      return;
    }
    entries.sort((a, b) => a[0].localeCompare(b[0]));
    let html = "";
    for (const [cap, agentIds] of entries) {
      html += '<div class="cap-card">';
      html += '<div class="cap-card-name">' + escHtml(cap) + "</div>";
      html += '<div class="cap-card-agents">';
      for (const aid of agentIds) {
        html += '<span class="cap-agent-tag">' + escHtml(aid) + "</span>";
      }
      html += "</div></div>";
    }
    dom.capGrid.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Activity Feed
  // -----------------------------------------------------------------------

  function renderActivity(data) {
    if (!data) return;
    const events = data.events || [];
    if (events.length === 0) {
      dom.activityFeed.innerHTML =
        '<div class="empty-state">No activity recorded yet. Events appear when broker state changes.</div>';
      return;
    }
    // Show newest first
    const sorted = [...events].reverse();
    let html = "";
    for (const ev of sorted) {
      const statusCls = ev.delivery_status === "delivered"
        ? "delivered"
        : ev.delivery_status === "failed"
          ? "failed"
          : "queued";
      html += '<div class="activity-item">';
      html += '<span class="activity-ts">' + formatDate(ev.timestamp) + "</span>";
      html += '<span class="activity-type">' + escHtml(ev.event_type || ev.intent_type || "--") + "</span>";
      html += '<span class="activity-result">' + escHtml(ev.result || "--") + "</span>";
      html += '<span class="activity-status ' + statusCls + '">' + escHtml(ev.delivery_status || "--") + "</span>";
      html += "</div>";
    }
    dom.activityFeed.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Broker status helpers
  // -----------------------------------------------------------------------

  function setBrokerUnreachable() {
    brokerReachable = false;
    dom.brokerDot.className = "status-dot red";
    dom.brokerLabel.textContent = "Unreachable";
    dom.unreachable.style.display = "flex";

    // Set all card values to show unreachable state
    dom.valBrokerStatus.textContent = "Unreachable";
    dom.valBrokerStatus.className = "card-value status-error";
    dom.valBrokerState.textContent = "--";
    dom.valAgentsOnline.textContent = "--";
    dom.valPending.textContent = "--";
    dom.valReceived.textContent = "--";
    dom.valRouted.textContent = "--";
    dom.valFailed.textContent = "--";
    dom.valAvgRoute.textContent = "--";
  }

  function setBrokerReachable(status) {
    brokerReachable = true;
    dom.unreachable.style.display = "none";
    const cls = statusClass(status);
    dom.brokerDot.className = "status-dot " + (cls === "healthy" ? "green" : cls === "degraded" ? "amber" : "gray");
    dom.brokerLabel.textContent = capitalize(status || "Connected");
  }

  function statusClass(status) {
    if (!status) return "unknown";
    const s = status.toLowerCase();
    if (s === "healthy" || s === "online" || s === "running") return "healthy";
    if (s === "degraded" || s === "paused") return "degraded";
    if (s === "error" || s === "unreachable" || s === "stopped") return "error";
    return "unknown";
  }

  // -----------------------------------------------------------------------
  // HTML helpers
  // -----------------------------------------------------------------------

  function escHtml(str) {
    if (str == null) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function td(content, cls) {
    return '<td' + (cls ? ' class="' + cls + '"' : '') + '>' + content + '</td>';
  }

  function mono(val) {
    return '<span class="mono">' + val + "</span>";
  }

  function detectMode(endpoint) {
    if (!endpoint) return "unknown";
    if (endpoint === "http" || (typeof endpoint === "string" && endpoint.startsWith("http"))) return "http";
    if (endpoint === "file-based" || (typeof endpoint === "string" && (endpoint.startsWith("/") || endpoint.startsWith("file")))) return "file-based";
    return "unknown";
  }

  function modeBadge(mode) {
    return '<span class="mode-badge ' + escHtml(mode) + '">' + escHtml(mode) + "</span>";
  }

  function statusBadge(status) {
    const cls = statusClass(status);
    const mapped = cls === "healthy" ? "online" : cls === "error" ? "offline" : cls === "degraded" ? "degraded" : "unknown";
    return '<span class="status-badge ' + mapped + '">' + escHtml(capitalize(status)) + "</span>";
  }

  function capPill(cap) {
    return '<span class="cap-pill">' + escHtml(cap) + "</span>";
  }

  function capitalize(s) {
    if (!s) return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function formatDate(iso) {
    if (!iso) return "--";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch {
      return iso;
    }
  }

  function formatUptime(isoStart) {
    if (!isoStart) return "--";
    try {
      const start = new Date(isoStart);
      const now = new Date();
      const diff = Math.floor((now - start) / 1000);
      if (diff < 60) return diff + "s";
      if (diff < 3600) return Math.floor(diff / 60) + "m " + (diff % 60) + "s";
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      return h + "h " + m + "m";
    } catch {
      return "--";
    }
  }

  // -----------------------------------------------------------------------
  // Main refresh cycle
  // -----------------------------------------------------------------------

  async function refreshAll() {
    // Fetch all endpoints in parallel
    const [health, stats, agents, activity, capabilities] = await Promise.all([
      apiFetch("/api/health"),
      apiFetch("/api/stats"),
      apiFetch("/api/agents"),
      apiFetch("/api/activity"),
      apiFetch("/api/capabilities"),
    ]);

    renderHealth(health);
    renderStats(stats);
    renderAgents(agents);
    renderActivity(activity);
    renderCapabilities(capabilities);

    // Capture dashboard start time from health response
    if (!dashboardStartedAt && health && health.dashboard_started_at) {
      dashboardStartedAt = health.dashboard_started_at;
    }

    // Update protocol info
    dom.valUptime.textContent = formatUptime(dashboardStartedAt);
    dom.valLastRefresh.textContent = new Date().toLocaleTimeString("en-US", { hour12: false });

    // Reset countdown
    resetCountdown();
  }

  // -----------------------------------------------------------------------
  // Countdown timer
  // -----------------------------------------------------------------------

  function resetCountdown() {
    countdownValue = REFRESH_INTERVAL / 1000;
    dom.countdown.textContent = countdownValue;
  }

  function startCountdown() {
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      countdownValue = Math.max(0, countdownValue - 1);
      dom.countdown.textContent = countdownValue;
    }, 1000);
  }

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  dom.refreshBtn.addEventListener("click", () => {
    refreshAll();
  });

  // Initial load
  refreshAll();
  startCountdown();
  setInterval(refreshAll, REFRESH_INTERVAL);

})();
