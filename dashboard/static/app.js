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

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // -----------------------------------------------------------------------
  // Safe DOM access & loading states (Sprint 21 — KP-002)
  // -----------------------------------------------------------------------

  function safeGetEl(id) {
    return document.getElementById(id);
  }

  function setLoading(sectionId, loading) {
    var el = safeGetEl(sectionId);
    if (!el) return;
    if (loading) {
      el.classList.add('loading');
    } else {
      el.classList.remove('loading');
    }
  }

  var lastUpdate = {};

  function markUpdated(section) {
    lastUpdate[section] = Date.now();
  }

  function checkStaleness() {
    var STALE_THRESHOLD = 30000;
    Object.keys(lastUpdate).forEach(function(section) {
      var time = lastUpdate[section];
      var el = safeGetEl(section + '-stale');
      if (el) {
        var isStale = (Date.now() - time) > STALE_THRESHOLD;
        el.style.display = isStale ? 'inline' : 'none';
      }
    });
  }
  setInterval(checkStaleness, 5000);

  function showError(sectionId, message) {
    var el = safeGetEl(sectionId);
    if (!el) return;
    el.innerHTML = '<div class="error-message">' + escapeHtml(message) + '</div>';
  }

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
    valProjectXStatus: $("#val-projectx-status"),
    valGemma4Status: $("#val-gemma4-status"),
    valDashboardStatus: $("#val-dashboard-status"),
    valProtocolUpdate: $("#val-protocol-update"),

    // Tables / grids
    agentsTbody:     $("#agents-tbody"),
    capGrid:         $("#cap-grid"),
    activityFeed:    $("#activity-feed"),
    projectxProcessesTbody: $("#projectx-processes-tbody"),
    projectxActionsFeed: $("#projectx-actions-feed"),
    stackStartCommand: $("#stack-start-command"),
    stackRestartCommand: $("#stack-restart-command"),
    valProjectxProtocolVersion: $("#val-projectx-protocol-version"),
    valProjectxIntentCount: $("#val-projectx-intent-count"),
    valProjectxAgentCount: $("#val-projectx-agent-count"),
    valProjectxPolicyCount: $("#val-projectx-policy-count"),
    projectxProtocolSummary: $("#projectx-protocol-summary"),
    projectxChatFeed: $("#projectx-chat-feed"),
    projectxChatForm: $("#projectx-chat-form"),
    projectxChatInput: $("#projectx-chat-input"),

    // Delivery status
    valDelivered:         $("#val-delivered"),
    valQueued:            $("#val-queued"),
    valQueuedNoEndpoint:  $("#val-queued-no-endpoint"),
    valDeliveryFailed:    $("#val-delivery-failed"),
    valConnectionRefused: $("#val-connection-refused"),
    valTimeout:           $("#val-timeout"),
    valRateLimited:       $("#val-rate-limited"),
    deliveryTbody:        $("#delivery-tbody"),

    // Failed intent diagnostics
    valFailedIntentsCount: $("#val-failed-intents-count"),
    valFailedIntentsLatest: $("#val-failed-intents-latest"),
    valFailedIntentsTargets: $("#val-failed-intents-targets"),
    valFailedIntentsFilter: $("#val-failed-intents-filter"),
    failedStatusBreakdown: $("#failed-status-breakdown"),
    failedTargetBreakdown: $("#failed-target-breakdown"),
    failedIntentsTbody: $("#failed-intents-tbody"),
    intentDrawer: $("#intent-drawer"),
    intentDrawerBackdrop: $("#intent-drawer-backdrop"),
    intentDrawerTitle: $("#intent-drawer-title"),
    intentDrawerSummary: $("#intent-drawer-summary"),
    intentDrawerCorrelation: $("#intent-drawer-correlation"),
    intentDrawerAttempts: $("#intent-drawer-attempts"),
    intentDrawerLifecycle: $("#intent-drawer-lifecycle"),
    intentDrawerClose: $("#intent-drawer-close"),

    // Task queue
    valTasksQueued:     $("#val-tasks-queued"),
    valTasksClaimed:    $("#val-tasks-claimed"),
    valTasksInProgress: $("#val-tasks-in-progress"),
    valTasksCompleted:  $("#val-tasks-completed"),
    valTasksFailed:     $("#val-tasks-failed"),
    valTasksDeferred:   $("#val-tasks-deferred"),
    taskQueueTbody:     $("#task-queue-tbody"),

    // Failure stats & routing
    failureGrid:     $("#failure-grid"),
    routingGrid:     $("#routing-grid"),

    // Memory
    memoryTasksTbody:  $("#memory-tasks-tbody"),
    memoryConvosTbody: $("#memory-convos-tbody"),

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
  let unreachableCount = 0;
  const UNREACHABLE_THRESHOLD = 3;
  let failedIntentData = { intents: [], summary: {} };
  let failedIntentFilter = { type: "all", value: null };

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

  async function apiPost(path, payload) {
    try {
      const res = await fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
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
    if (!data || data.status === "unreachable" || data.status === "degraded") {
      if (!data || data.status === "unreachable") {
        setBrokerUnreachable();
        return;
      }
      // degraded — broker not reachable but dashboard is running
      setBrokerReachable(data.status);
    } else {
      setBrokerReachable(data.status);
    }
    dom.valBrokerStatus.textContent = data.status || "--";
    dom.valBrokerStatus.className = "card-value status-" + statusClass(data.status);
    dom.valBrokerState.textContent = data.broker_state || "--";
    dom.valAgentsOnline.textContent = data.agents_registered ?? "--";

    // Update version display
    if (data.dashboard_version) {
      var versionEl = document.getElementById('dashboard-version');
      if (versionEl) versionEl.textContent = 'v' + data.dashboard_version;
    }
  }

  function renderStats(data) {
    if (!data || data.status === "unreachable") return;
    // Handle both nested {broker:{stats:{...}}} and flat structures
    const broker = data.broker || data;
    const stats = broker.stats || broker;
    dom.valReceived.textContent = stats.intents_received ?? "--";
    dom.valRouted.textContent = stats.intents_routed ?? "--";
    dom.valFailed.textContent = stats.intents_failed ?? "--";

    const avg = stats.avg_route_time_ms;
    dom.valAvgRoute.textContent = avg != null ? Number(avg).toFixed(1) + " ms" : "--";

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
    if (dom.valDashboardStatus) {
      dom.valDashboardStatus.textContent = "Healthy";
      dom.valDashboardStatus.className = "card-value status-healthy";
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
    // Broker returns {"agents": [list of agent objects]}
    let agents = data.agents || [];
    // Defensive: if agents is a dict (legacy), convert to array
    if (!Array.isArray(agents)) {
      agents = Object.values(agents);
    }
    if (agents.length === 0) {
      dom.agentsTbody.innerHTML = '<tr><td colspan="8" class="empty-row">No agents registered</td></tr>';
      return;
    }

    // Sort by agent_id alphabetically
    agents.sort((a, b) => (a.agent_id || "").localeCompare(b.agent_id || ""));
    let html = "";
    for (const a of agents) {
      const mode = detectMode(a.endpoint);
      const caps = a.capabilities || [];
      const status = a.status || "unknown";

      html += "<tr>";
      html += td(mono(escHtml(a.agent_id || "--")));
      html += td(escHtml(a.name || a.agent_id || "--"));
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
        '<div class="empty-state">No broker intents recorded yet.</div>';
      return;
    }
    // Show newest first
    const sorted = [...events].reverse();
    let html = "";
    for (const ev of sorted) {
      const ds = ev.delivery_status || "--";
      const deliveryCls = deliveryStatusClass(ds);
      const statusCls = deliveryCls === "online" ? "delivered"
        : deliveryCls === "offline" ? "failed"
        : "queued";
      const result = ev.result || [ev.source_agent || "unknown", ev.target_agent || "unknown"].join(" -> ");
      html += '<div class="activity-item">';
      html += '<span class="activity-ts">' + formatDate(ev.timestamp) + "</span>";
      html += '<span class="activity-type">' + escHtml(ev.event_type || ev.intent_type || "--") + "</span>";
      if (ev.intent_id) {
        html += '<span class="activity-result"><button type="button" class="intent-row-button" data-intent-id="' + escHtml(ev.intent_id) + '">' + escHtml(result) + "</button></span>";
      } else {
        html += '<span class="activity-result">' + escHtml(result) + "</span>";
      }
      html += '<span class="activity-status ' + statusCls + '">' + escHtml(ds) + "</span>";
      if (ev.delivery_latency_ms != null) {
        html += '<span class="activity-latency mono">' + Number(ev.delivery_latency_ms).toFixed(1) + " ms</span>";
      }
      if (ev.retry_count && ev.retry_count > 0) {
        html += '<span class="activity-retries mono">retries: ' + ev.retry_count + "</span>";
      }
      if (ev.fallback_agent) {
        html += '<span class="activity-fallback mono">fallback: ' + escHtml(ev.fallback_agent) + "</span>";
      }
      html += "</div>";
    }
    dom.activityFeed.innerHTML = html;
    dom.activityFeed.querySelectorAll("[data-intent-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openIntentDrawer(button.getAttribute("data-intent-id"));
      });
    });
  }

  // -----------------------------------------------------------------------
  // Render: Structured Logs
  // -----------------------------------------------------------------------

  function renderLogs(data) {
    const tbody = document.getElementById("logs-tbody");
    if (!tbody) return;
    if (!data || !data.logs || data.logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No structured logs yet</td></tr>';
      return;
    }
    tbody.innerHTML = data.logs.slice(0, 50).map(e => {
      const ts = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : "--";
      const levelClass = e.level === "error" ? "status-badge offline"
                       : e.level === "warning" ? "status-badge degraded"
                       : "status-badge online";
      return `<tr>
        <td class="mono">${escapeHtml(ts)}</td>
        <td><span class="${escapeHtml(levelClass)}">${escapeHtml(e.level || "info")}</span></td>
        <td>${escapeHtml(e.event_type || "--")}</td>
        <td class="mono">${escapeHtml(e.agent_id || "--")}</td>
        <td>${escapeHtml(e.message || "--")}</td>
      </tr>`;
    }).join("");
  }

  // -----------------------------------------------------------------------
  // Render: Network Topology
  // -----------------------------------------------------------------------

  function renderTopology(data) {
    const container = document.getElementById("topology-container");
    if (!container) return;
    if (!data || !data.nodes || data.nodes.length === 0) {
      container.innerHTML = '<p class="empty-row">No topology data</p>';
      return;
    }
    const nodes = data.nodes || [];
    const html = nodes.map(n => {
      const mode = n.connection_mode || "unknown";
      const statusClass = n.status === "online" ? "online"
                        : n.status === "degraded" ? "degraded"
                        : "offline";
      return `<div class="topology-node">
        <span class="status-dot ${escapeHtml(statusClass)}"></span>
        <strong>${escapeHtml(n.agent_id || "unknown")}</strong>
        <span class="topology-mode">${escapeHtml(mode)}</span>
        <span class="topology-type">${escapeHtml(n.agent_type || "")}</span>
      </div>`;
    }).join("");
    container.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Task Queue (from /api/tasks/queue)
  // -----------------------------------------------------------------------

  function renderTaskQueue(data) {
    const container = document.getElementById("task-queue-tbody");
    if (!container) return;
    if (!data || !data.queue || data.queue.length === 0) {
      container.innerHTML = '<tr><td colspan="4" class="empty-row">Task queue empty</td></tr>';
      return;
    }
    container.innerHTML = data.queue.slice(0, 20).map(t => {
      const statusClass = t.status === "completed" ? "online"
                        : t.status === "in_progress" ? "degraded"
                        : "offline";
      return `<tr>
        <td class="mono">${escapeHtml(t.task_id || "--")}</td>
        <td>${escapeHtml(t.task_type || "--")}</td>
        <td><span class="status-badge ${escapeHtml(statusClass)}">${escapeHtml(t.status || "--")}</span></td>
        <td class="mono">${escapeHtml(t.claimed_by || "unclaimed")}</td>
      </tr>`;
    }).join("");
  }

  // -----------------------------------------------------------------------
  // Broker status helpers
  // -----------------------------------------------------------------------

  function setBrokerUnreachable() {
    brokerReachable = false;
    unreachableCount++;
    dom.brokerDot.className = "status-dot red";
    dom.brokerLabel.textContent = "Unreachable";

    // Only show banner after UNREACHABLE_THRESHOLD consecutive failures
    if (unreachableCount >= UNREACHABLE_THRESHOLD) {
      dom.unreachable.style.display = "flex";
    }

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
    unreachableCount = 0;
    dom.unreachable.style.display = "none";
    const cls = statusClass(status);
    dom.brokerDot.className = "status-dot " + (cls === "healthy" ? "green" : cls === "degraded" ? "amber" : "gray");
    dom.brokerLabel.textContent = capitalize(status || "Connected");
  }

  function statusClass(status) {
    if (!status) return "unknown";
    const s = status.toLowerCase();
    if (s === "healthy" || s === "online" || s === "running" || s === "ok" || s === "active") return "healthy";
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

  function setInteractiveDiagnostic(el, enabled, handler) {
    if (!el) return;
    el.classList.toggle("interactive", Boolean(enabled));
    el.onclick = enabled ? handler : null;
  }

  function currentFailedIntentRows() {
    var intents = (failedIntentData && failedIntentData.intents) || [];
    if (failedIntentFilter.type === "status" && failedIntentFilter.value) {
      return intents.filter(function(intent) {
        return (intent.delivery_status || "unknown") === failedIntentFilter.value;
      });
    }
    if (failedIntentFilter.type === "target" && failedIntentFilter.value) {
      return intents.filter(function(intent) {
        return (intent.target_agent || "unknown") === failedIntentFilter.value;
      });
    }
    return intents;
  }

  function updateFailedIntentFilterLabel() {
    if (!dom.valFailedIntentsFilter) return;
    if (failedIntentFilter.type === "status") {
      dom.valFailedIntentsFilter.textContent = "status:" + failedIntentFilter.value;
      return;
    }
    if (failedIntentFilter.type === "target") {
      dom.valFailedIntentsFilter.textContent = "target:" + failedIntentFilter.value;
      return;
    }
    dom.valFailedIntentsFilter.textContent = "all";
  }

  function focusFailedIntentPanel(openFirst) {
    var section = safeGetEl("failed-intents-section");
    if (section) {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    var rows = currentFailedIntentRows();
    if (openFirst && rows.length > 0) {
      openIntentDrawer(rows[0].intent_id);
    }
  }

  function applyFailedIntentFilter(type, value, options) {
    options = options || {};
    failedIntentFilter = { type: type || "all", value: value || null };
    updateFailedIntentFilterLabel();
    renderFailedIntentRows();
    if (options.focus) {
      focusFailedIntentPanel(Boolean(options.openFirst));
    }
  }

  function renderDiagnosticPairs(el, pairs) {
    if (!el) return;
    if (!pairs.length) {
      el.innerHTML = '<div class="empty-state">No diagnostic metadata.</div>';
      return;
    }
    el.innerHTML = pairs.map(function(pair) {
      return '<div class="diagnostic-pair"><span class="card-label">' + escHtml(pair.label) + '</span><span class="mono">' + escHtml(pair.value) + '</span></div>';
    }).join("");
  }

  function renderDiagnosticList(el, rows, formatter) {
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = '<div class="empty-state">No records.</div>';
      return;
    }
    el.innerHTML = rows.map(formatter).join("");
  }

  async function openIntentDrawer(intentId) {
    if (!intentId) return;
    var payload = await apiFetch("/api/intents/" + encodeURIComponent(intentId));
    var detail = (payload && payload.detail) || { intent_id: intentId, failure_reason: "unknown", route_attempts: [], lifecycle: [], correlation_ids: {}, fallback_behavior: {} };

    if (dom.intentDrawerTitle) {
      dom.intentDrawerTitle.textContent = detail.intent_id || intentId;
    }
    renderDiagnosticPairs(dom.intentDrawerSummary, [
      { label: "Source", value: detail.source_agent || "--" },
      { label: "Target", value: detail.target_agent || "--" },
      { label: "Type", value: detail.intent_type || "--" },
      { label: "Status", value: detail.delivery_status || "--" },
      { label: "Reason", value: detail.failure_reason || "unknown" },
      { label: "Fallback", value: (detail.fallback_behavior && detail.fallback_behavior.mode) || "unknown" },
    ]);
    renderDiagnosticPairs(dom.intentDrawerCorrelation, Object.entries(detail.correlation_ids || {}).filter(function(entry) {
      return entry[1];
    }).map(function(entry) {
      return { label: entry[0], value: String(entry[1]) };
    }));
    renderDiagnosticList(dom.intentDrawerAttempts, detail.route_attempts || [], function(attempt) {
      return '<div class="diagnostic-row">'
        + '<span class="mono">' + escHtml(formatDate(attempt.timestamp)) + '</span>'
        + '<span>' + escHtml((attempt.transport || "route") + " -> " + (attempt.status || "unknown")) + '</span>'
        + '<span class="mono">' + escHtml(attempt.endpoint || "--") + '</span>'
        + '<span>' + escHtml(attempt.error || "--") + '</span>'
        + '</div>';
    });
    renderDiagnosticList(dom.intentDrawerLifecycle, detail.lifecycle || [], function(event) {
      return '<div class="diagnostic-row">'
        + '<span class="mono">' + escHtml(formatDate(event.timestamp)) + '</span>'
        + '<span>' + escHtml(event.event || "--") + '</span>'
        + '<span class="mono">' + escHtml(event.status || "--") + '</span>'
        + '<span>' + escHtml(event.reason || event.note || event.failure_reason || "--") + '</span>'
        + '</div>';
    });

    if (dom.intentDrawerBackdrop) dom.intentDrawerBackdrop.hidden = false;
    if (dom.intentDrawer) dom.intentDrawer.hidden = false;
  }

  function closeIntentDrawer() {
    if (dom.intentDrawerBackdrop) dom.intentDrawerBackdrop.hidden = true;
    if (dom.intentDrawer) dom.intentDrawer.hidden = true;
  }

  // -----------------------------------------------------------------------
  // Render: Delivery Status
  // -----------------------------------------------------------------------

  function renderDeliveryStatus(statsData) {
    if (!statsData || statsData.status === "unreachable") return;
    var broker = statsData.broker || statsData;
    var stats = broker.stats || broker;

    // Delivery counts from broker stats
    var dc = stats.delivery_counts || {};
    if (dom.valDelivered) dom.valDelivered.textContent = dc.delivered || 0;
    if (dom.valQueued) dom.valQueued.textContent = dc.queued || 0;
    if (dom.valQueuedNoEndpoint) dom.valQueuedNoEndpoint.textContent = dc.queued_no_endpoint || 0;
    if (dom.valDeliveryFailed) dom.valDeliveryFailed.textContent = dc.failed || 0;
    if (dom.valConnectionRefused) dom.valConnectionRefused.textContent = dc.connection_refused || 0;
    if (dom.valTimeout) dom.valTimeout.textContent = dc.timeout || 0;
    if (dom.valRateLimited) dom.valRateLimited.textContent = dc.rate_limited || 0;

    // Color failed/timeout/rate_limited red if > 0
    if (dom.valDeliveryFailed) {
      dom.valDeliveryFailed.className = (dc.failed || 0) > 0 ? "card-value mono status-error" : "card-value mono";
    }
    if (dom.valConnectionRefused) {
      dom.valConnectionRefused.className = (dc.connection_refused || 0) > 0 ? "card-value mono status-error" : "card-value mono";
    }
    if (dom.valTimeout) {
      dom.valTimeout.className = (dc.timeout || 0) > 0 ? "card-value mono status-error" : "card-value mono";
    }
    if (dom.valRateLimited) {
      dom.valRateLimited.className = (dc.rate_limited || 0) > 0 ? "card-value mono status-error" : "card-value mono";
    }

    setInteractiveDiagnostic(safeGetEl("card-failed"), (stats.intents_failed || 0) > 0, function() {
      applyFailedIntentFilter("all", null, { focus: true });
    });
    setInteractiveDiagnostic(safeGetEl("card-delivery-failed"), (dc.failed || 0) > 0, function() {
      applyFailedIntentFilter("all", null, { focus: true });
    });
    setInteractiveDiagnostic(safeGetEl("card-connection-refused"), (dc.connection_refused || 0) > 0, function() {
      applyFailedIntentFilter("status", "connection_refused", { focus: true });
    });
    setInteractiveDiagnostic(safeGetEl("card-timeout"), (dc.timeout || 0) > 0, function() {
      applyFailedIntentFilter("status", "timeout", { focus: true });
    });
    setInteractiveDiagnostic(safeGetEl("card-rate-limited"), (dc.rate_limited || 0) > 0, function() {
      applyFailedIntentFilter("status", "rate_limited", { focus: true });
    });

    // Delivery detail table from recent intents
    var intents = stats.recent_deliveries || [];
    if (intents.length === 0) {
      dom.deliveryTbody.innerHTML = '<tr><td colspan="6" class="empty-row">No delivery data yet</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < intents.length; i++) {
      var d = intents[i];
      var dsCls = deliveryStatusClass(d.delivery_status);
      html += "<tr>";
      if (d.intent_id) {
        html += td('<button type="button" class="intent-row-button mono" data-intent-id="' + escHtml(d.intent_id) + '">' + escHtml((d.intent_id || "").substring(0, 12)) + "</button>");
      } else {
        html += td('<span class="mono" style="font-size:0.7rem">' + escHtml((d.intent_id || "").substring(0, 12)) + "</span>");
      }
      html += td(mono(escHtml(d.target_agent || "--")));
      html += td('<span class="status-badge ' + dsCls + '">' + escHtml(d.delivery_status || "--") + "</span>");
      html += td(mono(d.delivery_latency_ms != null ? Number(d.delivery_latency_ms).toFixed(1) + " ms" : "--"));
      html += td(mono(d.retry_count != null ? String(d.retry_count) : "--"));
      html += td(mono(escHtml(d.fallback_agent || "--")));
      html += "</tr>";
    }
    dom.deliveryTbody.innerHTML = html;
    dom.deliveryTbody.querySelectorAll("[data-intent-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openIntentDrawer(button.getAttribute("data-intent-id"));
      });
    });
  }

  function deliveryStatusClass(status) {
    if (!status) return "unknown";
    if (status === "delivered" || status === "ok" || status === "healthy" || status === "clean" || status === "ready" || status === "success") return "online";
    if (status === "queued" || status === "queued_no_endpoint" || status === "pending" || status === "requested" || status === "degraded" || status === "dry_run") return "degraded";
    if (status === "failed" || status === "connection_refused" || status === "timeout" || status === "rate_limited" || status === "error" || status === "blocked" || status === "unreachable") return "offline";
    if (String(status).startsWith("http_") || String(status).startsWith("error_")) return "offline";
    return "unknown";
  }

  function renderFailedIntentRows() {
    if (!dom.failedIntentsTbody) return;
    var intents = currentFailedIntentRows();
    if (!intents.length) {
      dom.failedIntentsTbody.innerHTML = '<tr><td colspan="6" class="empty-row">No failed intents captured.</td></tr>';
      return;
    }
    dom.failedIntentsTbody.innerHTML = intents.map(function(intent) {
      var correlation = (((intent.correlation_ids || {}).correlation_id) || ((intent.correlation_ids || {}).request_id) || "--");
      return "<tr>"
        + td('<button type="button" class="intent-row-button mono" data-intent-id="' + escHtml(intent.intent_id || "") + '">' + escHtml((intent.intent_id || "").substring(0, 12)) + "</button>")
        + td('<span class="mono">' + escHtml(formatDate(intent.delivered_at || intent.timestamp)) + "</span>")
        + td(mono(escHtml(intent.target_agent || "--")))
        + td('<span class="status-badge ' + deliveryStatusClass(intent.delivery_status || "") + '">' + escHtml(intent.delivery_status || "--") + "</span>")
        + td(escHtml(intent.failure_reason || "unknown"))
        + td('<span class="mono">' + escHtml(String(correlation).substring(0, 18)) + "</span>")
        + "</tr>";
    }).join("");
    dom.failedIntentsTbody.querySelectorAll("[data-intent-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openIntentDrawer(button.getAttribute("data-intent-id"));
      });
    });
  }

  function renderFailedIntents(data) {
    failedIntentData = data || { intents: [], summary: {} };
    var summary = failedIntentData.summary || {};
    var intents = failedIntentData.intents || [];
    if (dom.valFailedIntentsCount) dom.valFailedIntentsCount.textContent = String(summary.count != null ? summary.count : intents.length);
    if (dom.valFailedIntentsLatest) dom.valFailedIntentsLatest.textContent = formatDate(summary.latest_failure_at);
    if (dom.valFailedIntentsTargets) dom.valFailedIntentsTargets.textContent = String(Object.keys(summary.by_target_agent || {}).length);
    updateFailedIntentFilterLabel();

    if (dom.failedStatusBreakdown) {
      var statusEntries = Object.entries(summary.by_status || {});
      dom.failedStatusBreakdown.innerHTML = statusEntries.length ? statusEntries.map(function(entry) {
        return '<button type="button" class="diagnostic-chip" data-filter-type="status" data-filter-value="' + escHtml(entry[0]) + '"><span>' + escHtml(entry[0]) + '</span><span class="diagnostic-chip-value">' + escHtml(String(entry[1])) + '</span></button>';
      }).join("") : '<div class="empty-state">No failed intents.</div>';
      dom.failedStatusBreakdown.querySelectorAll("[data-filter-type]").forEach(function(button) {
        button.addEventListener("click", function() {
          applyFailedIntentFilter(button.getAttribute("data-filter-type"), button.getAttribute("data-filter-value"));
        });
      });
    }

    if (dom.failedTargetBreakdown) {
      var targetEntries = Object.entries(summary.by_target_agent || {});
      dom.failedTargetBreakdown.innerHTML = targetEntries.length ? targetEntries.map(function(entry) {
        return '<button type="button" class="diagnostic-chip" data-filter-type="target" data-filter-value="' + escHtml(entry[0]) + '"><span>' + escHtml(entry[0]) + '</span><span class="diagnostic-chip-value">' + escHtml(String(entry[1])) + '</span></button>';
      }).join("") : '<div class="empty-state">No failed intents.</div>';
      dom.failedTargetBreakdown.querySelectorAll("[data-filter-type]").forEach(function(button) {
        button.addEventListener("click", function() {
          applyFailedIntentFilter(button.getAttribute("data-filter-type"), button.getAttribute("data-filter-value"));
        });
      });
    }

    renderFailedIntentRows();
    setInteractiveDiagnostic(dom.unreachable, intents.length > 0, function() {
      applyFailedIntentFilter("all", null, { focus: true, openFirst: true });
    });
  }

  // -----------------------------------------------------------------------
  // Render: Task Queue
  // -----------------------------------------------------------------------

  function renderTasks(data) {
    if (!data || data.status === "unreachable") {
      dom.taskQueueTbody.innerHTML = '<tr><td colspan="7" class="empty-row">Broker unreachable</td></tr>';
      return;
    }
    // Status counts
    var counts = data.status_counts || {};
    dom.valTasksQueued.textContent = counts.queued || 0;
    dom.valTasksClaimed.textContent = counts.claimed || 0;
    dom.valTasksInProgress.textContent = counts.in_progress || 0;
    dom.valTasksCompleted.textContent = counts.completed || 0;
    dom.valTasksFailed.textContent = counts.failed || 0;
    dom.valTasksDeferred.textContent = counts.deferred_by_capacity || 0;

    if ((counts.failed || 0) > 0) {
      dom.valTasksFailed.className = "card-value mono status-error";
    } else {
      dom.valTasksFailed.className = "card-value mono";
    }

    // Task table — show most recent 50
    var tasks = data.tasks || [];
    if (tasks.length === 0) {
      dom.taskQueueTbody.innerHTML = '<tr><td colspan="7" class="empty-row">No tasks recorded</td></tr>';
      return;
    }
    tasks = tasks.slice(-50).reverse();
    var html = "";
    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i];
      var prioClass = t.priority === "critical" ? "status-error" : t.priority === "high" ? "status-degraded" : "";
      html += "<tr>";
      html += td('<span class="mono" style="font-size:0.7rem">' + escHtml((t.task_id || "").substring(0, 8)) + "</span>");
      html += td(escHtml(t.title || "--"));
      html += td(capPill(t.task_type || "--"));
      html += td('<span class="' + prioClass + '">' + escHtml(t.priority || "--") + "</span>");
      html += td(statusBadge(t.status || "unknown"));
      html += td(mono(escHtml(t.assigned_agent || t.claimed_by || "--")));
      html += td('<span class="mono" style="font-size:0.75rem">' + formatDate(t.created_at) + "</span>");
      html += "</tr>";
    }
    dom.taskQueueTbody.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Failure Stats
  // -----------------------------------------------------------------------

  function renderFailureStats(data) {
    if (!data || data.status === "unreachable") {
      dom.failureGrid.innerHTML = '<div class="empty-state">Broker unreachable</div>';
      return;
    }
    var stats = data.failure_stats || {};
    var entries = Object.entries(stats);
    if (entries.length === 0) {
      dom.failureGrid.innerHTML = '<div class="empty-state">No failures recorded</div>';
      return;
    }
    entries.sort(function(a, b) { return b[1] - a[1]; });
    var html = "";
    for (var i = 0; i < entries.length; i++) {
      var cls = entries[i][0];
      var count = entries[i][1];
      html += '<div class="cap-card">';
      html += '<div class="cap-card-name">' + escHtml(cls) + "</div>";
      html += '<div class="cap-card-agents"><span class="cap-agent-tag status-error">' + count + " occurrence" + (count !== 1 ? "s" : "") + "</span></div>";
      html += "</div>";
    }
    dom.failureGrid.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Routing Policy
  // -----------------------------------------------------------------------

  function renderRouting(data) {
    if (!data || data.status === "unreachable") {
      dom.routingGrid.innerHTML = '<div class="empty-state">Broker unreachable</div>';
      return;
    }
    var policy = data.policy || {};
    var taskRouting = policy.task_routing || {};
    var entries = Object.entries(taskRouting);
    if (entries.length === 0) {
      dom.routingGrid.innerHTML = '<div class="empty-state">No routing policy configured</div>';
      return;
    }
    entries.sort(function(a, b) { return a[0].localeCompare(b[0]); });
    var html = "";
    // Show builder pool summary
    var pool = policy.builder_pool || {};
    if (pool.primary) {
      html += '<div class="cap-card">';
      html += '<div class="cap-card-name">Builder Pool</div>';
      html += '<div class="cap-card-agents">';
      html += '<span class="cap-agent-tag" style="background:#2a6f2a">Primary: ' + escHtml(pool.primary) + "</span>";
      if (pool.secondary) html += '<span class="cap-agent-tag" style="background:#6f6f2a">Secondary: ' + escHtml(pool.secondary) + "</span>";
      var support = pool.support || [];
      for (var s = 0; s < support.length; s++) {
        html += '<span class="cap-agent-tag">Support: ' + escHtml(support[s]) + "</span>";
      }
      html += "</div></div>";
    }
    // Show task routing
    for (var i = 0; i < entries.length; i++) {
      var taskType = entries[i][0];
      var agents = entries[i][1];
      html += '<div class="cap-card">';
      html += '<div class="cap-card-name">' + escHtml(taskType) + "</div>";
      html += '<div class="cap-card-agents">';
      for (var j = 0; j < agents.length; j++) {
        html += '<span class="cap-agent-tag">' + escHtml(agents[j]) + "</span>";
      }
      html += "</div></div>";
    }
    dom.routingGrid.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Memory — Task Memory
  // -----------------------------------------------------------------------

  function renderMemoryTasks(data) {
    if (!data || data.status === "unreachable") {
      dom.memoryTasksTbody.innerHTML = '<tr><td colspan="3" class="empty-row">Broker unreachable</td></tr>';
      return;
    }
    var tasks = data.tasks || [];
    if (tasks.length === 0) {
      dom.memoryTasksTbody.innerHTML = '<tr><td colspan="3" class="empty-row">No task memory files</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i];
      var st = (t.status || "unknown").toLowerCase();
      var badgeCls = st === "completed" ? "online" : st === "active" ? "degraded" : "unknown";
      html += "<tr>";
      html += td(mono(escHtml(t.slug || "--")));
      html += td(escHtml(t.title || "--"));
      html += td('<span class="status-badge ' + badgeCls + '">' + escHtml(capitalize(t.status || "unknown")) + "</span>");
      html += "</tr>";
    }
    dom.memoryTasksTbody.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Memory — Recent Conversations
  // -----------------------------------------------------------------------

  function renderMemoryConversations(data) {
    if (!data || data.status === "unreachable") {
      dom.memoryConvosTbody.innerHTML = '<tr><td colspan="4" class="empty-row">Broker unreachable</td></tr>';
      return;
    }
    var convos = data.conversations || [];
    if (convos.length === 0) {
      dom.memoryConvosTbody.innerHTML = '<tr><td colspan="4" class="empty-row">No conversations archived</td></tr>';
      return;
    }
    // Show newest first
    var sorted = convos.slice().reverse();
    var html = "";
    for (var i = 0; i < Math.min(sorted.length, 20); i++) {
      var c = sorted[i];
      var participants = (c.participants || []).map(escHtml).join(", ") || "--";
      html += "<tr>";
      html += td('<span class="mono" style="font-size:0.7rem">' + escHtml((c.id || "").substring(0, 20)) + "</span>");
      html += td(escHtml(c.topic || "--"));
      html += td(participants);
      html += td('<span class="mono" style="font-size:0.75rem">' + formatDate(c.created_at) + "</span>");
      html += "</tr>";
    }
    dom.memoryConvosTbody.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Render: Orchestration Status
  // -----------------------------------------------------------------------

  function renderOrchestration(data) {
    const el = document.getElementById("orchestration-status");
    if (!el) return;
    if (!data || !data.orchestration_active) {
      el.innerHTML = '<span class="status-badge offline">Inactive</span>';
      return;
    }
    const summary = data.task_summary || {};
    const parts = Object.entries(summary).map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(v)}`).join(" · ");
    el.innerHTML = `<span class="status-badge online">Active</span> <span class="mono">${parts || "no tasks"}</span>`;
  }

  // -----------------------------------------------------------------------
  // Render: Computer Use (ProjectX)
  // -----------------------------------------------------------------------

  function renderComputerUse(data) {
    const el = document.getElementById("computer-use-status");
    if (!el) return;
    if (!data || !data.projectx_available) {
      el.innerHTML = '<span class="status-badge offline">Unavailable</span>';
      return;
    }
    const tiers = data.action_tiers || {};
    const total = Object.values(tiers).reduce((sum, arr) => sum + arr.length, 0);
    el.innerHTML = `<span class="status-badge online">Active</span> <span class="mono">${escapeHtml(total)} actions available</span>`;
  }

  function renderProjectXSystem(data) {
    if (!data || data.status === "unreachable") {
      if (dom.valProjectXStatus) {
        dom.valProjectXStatus.textContent = "Down";
        dom.valProjectXStatus.className = "card-value status-error";
      }
      if (dom.valGemma4Status) {
        dom.valGemma4Status.textContent = "Down";
        dom.valGemma4Status.className = "card-value status-error";
      }
      return;
    }
    const services = ((data.stack || {}).services || []);
    const byName = {};
    services.forEach(function(service) { byName[service.name] = service; });
    var projectx = byName.projectx_guard;
    var gemma = byName.gemma4_local;
    if (dom.valProjectXStatus) {
      dom.valProjectXStatus.textContent = capitalize((projectx && projectx.status) || "unknown");
      dom.valProjectXStatus.className = "card-value status-" + statusClass((projectx && projectx.status) || "unknown");
    }
    if (dom.valGemma4Status) {
      dom.valGemma4Status.textContent = capitalize((gemma && gemma.status) || "unknown");
      dom.valGemma4Status.className = "card-value status-" + statusClass((gemma && gemma.status) || "unknown");
    }
    if (dom.valProtocolUpdate && data.protocol_facts) {
      dom.valProtocolUpdate.textContent = formatDate(data.protocol_facts.last_updated);
    }
  }

  function renderProjectXProcesses(data) {
    if (!dom.projectxProcessesTbody) return;
    if (!data || data.status === "unreachable") {
      dom.projectxProcessesTbody.innerHTML = '<tr><td colspan="6" class="empty-row">ProjectX guard unreachable</td></tr>';
      return;
    }
    const services = data.services || [];
    if (!services.length) {
      dom.projectxProcessesTbody.innerHTML = '<tr><td colspan="6" class="empty-row">No services discovered</td></tr>';
      return;
    }
    dom.stackStartCommand.textContent = data.startup_command || "--";
    dom.stackRestartCommand.textContent = data.restart_command || "--";
    dom.projectxProcessesTbody.innerHTML = services.map(function(service) {
      var port = "--";
      if (service.health_url) {
        var match = String(service.health_url).match(/:(\d+)\//);
        if (match) port = match[1];
      }
      return "<tr>"
        + td(escHtml(service.name))
        + td(capPill(service.category || "--"))
        + td(statusBadge(service.status || "unknown"))
        + td(mono(escHtml(service.health_url || "--")))
        + td(mono(port))
        + td('<span class="mono" style="font-size:0.72rem">' + escHtml(service.log_path || "--") + "</span>")
        + "</tr>";
    }).join("");
  }

  function renderProjectXActions(data) {
    if (!dom.projectxActionsFeed) return;
    var actions = (data && data.actions) || [];
    if (!actions.length) {
      dom.projectxActionsFeed.innerHTML = '<div class="empty-state">No ProjectX actions recorded yet.</div>';
      return;
    }
    dom.projectxActionsFeed.innerHTML = actions.map(function(action) {
      return '<div class="activity-item">'
        + '<span class="activity-ts">' + formatDate(action.timestamp) + "</span>"
        + '<span class="activity-type">' + escHtml(action.action_type || "--") + "</span>"
        + '<span class="activity-result">' + escHtml(action.summary || "--") + "</span>"
        + '<span class="activity-status ' + deliveryStatusClass(action.status || "") + '">' + escHtml(action.status || "--") + "</span>"
        + '<span class="activity-latency mono">' + (action.latency_ms != null ? escapeHtml(Number(action.latency_ms).toFixed(1) + " ms") : "--") + "</span>"
        + '</div>';
    }).join("");
  }

  function renderProjectXProtocolFacts(data) {
    var facts = (data && data.protocol_facts) || null;
    if (!facts) return;
    dom.valProjectxProtocolVersion.textContent = facts.version != null ? String(facts.version) : "--";
    dom.valProjectxIntentCount.textContent = facts.intent_count != null ? String(facts.intent_count) : "--";
    dom.valProjectxAgentCount.textContent = facts.agent_count != null ? String(facts.agent_count) : "--";
    dom.valProjectxPolicyCount.textContent = facts.policy_count != null ? String(facts.policy_count) : "--";
    var summaryHtml = "";
    summaryHtml += '<div class="protocol-summary-row"><span class="card-label">Last Updated</span><span class="mono">' + escHtml(formatDate(facts.last_updated)) + '</span></div>';
    summaryHtml += '<div class="protocol-summary-row"><span class="card-label">Schema Path</span><span class="mono">' + escHtml(facts.path || "--") + '</span></div>';
    var drifts = facts.drift_indicators || [];
    summaryHtml += '<div class="protocol-summary-row"><span class="card-label">Drift Indicators</span><span>' + escHtml(String(drifts.length)) + '</span></div>';
    dom.projectxProtocolSummary.innerHTML = summaryHtml;
  }

  function appendChatMessage(role, text, meta) {
    if (!dom.projectxChatFeed) return;
    var wrapper = document.createElement("div");
    wrapper.className = "chat-message " + role;
    wrapper.innerHTML = '<div class="chat-role">' + escHtml(role === "user" ? "Operator" : "ProjectX") + '</div>'
      + '<div class="chat-text">' + escHtml(text || "--") + '</div>'
      + (meta ? '<div class="chat-meta mono">' + escHtml(meta) + '</div>' : '');
    dom.projectxChatFeed.prepend(wrapper);
  }

  async function submitProjectXChat(payload, previewText) {
    appendChatMessage("user", previewText, null);
    const response = await apiPost("/api/projectx/chat", payload);
    if (!response || !response.response) {
      appendChatMessage("assistant", "ProjectX guard unreachable.", "dashboard proxy error");
      return;
    }
    var body = response.response.response || response.response;
    var answer = body.answer || body.summary || JSON.stringify(body, null, 2);
    appendChatMessage("assistant", typeof answer === "string" ? answer : JSON.stringify(answer), body.intent_type || response.mode);
    refreshAll();
  }

  // -----------------------------------------------------------------------
  // Task search/filter with pagination (Sprint 21 — KP-003)
  // -----------------------------------------------------------------------

  var _lastTasksData = null;

  function renderTasksWithFilter(tasks) {
    var container = safeGetEl('tasks-container');
    if (!container) return;
    if (!tasks || !Array.isArray(tasks)) {
      container.innerHTML = '<div class="empty-state">No tasks</div>';
      return;
    }

    var searchEl = safeGetEl('task-search');
    var statusEl = safeGetEl('task-status-filter');
    var searchTerm = searchEl ? searchEl.value.toLowerCase() : '';
    var statusFilter = statusEl ? statusEl.value : 'all';

    var filtered = tasks;
    if (searchTerm) {
      filtered = filtered.filter(function(t) {
        return (t.description || '').toLowerCase().indexOf(searchTerm) !== -1 ||
          (t.task_type || '').toLowerCase().indexOf(searchTerm) !== -1 ||
          (t.source_agent || '').toLowerCase().indexOf(searchTerm) !== -1 ||
          (t.task_id || '').toLowerCase().indexOf(searchTerm) !== -1;
      });
    }
    if (statusFilter !== 'all') {
      filtered = filtered.filter(function(t) { return t.status === statusFilter; });
    }

    var PAGE_SIZE = 50;
    var pageEl = safeGetEl('task-page');
    var page = parseInt((pageEl && pageEl.value) || '1');
    var start = (page - 1) * PAGE_SIZE;
    var paged = filtered.slice(start, start + PAGE_SIZE);

    var html = '<div class="filter-bar"><span class="mono">' + filtered.length + ' tasks</span></div>';
    html += '<div class="task-list">';
    paged.forEach(function(t) {
      var statusClass = t.status === 'completed' ? 'success' : t.status === 'failed' ? 'error' : 'pending';
      html += '<div class="task-item ' + statusClass + '">';
      html += '<span class="task-type">' + escapeHtml(t.task_type || '') + '</span>';
      html += '<span class="task-status status-badge ' + statusClass + '">' + escapeHtml(t.status || '') + '</span>';
      html += '<span class="task-desc">' + escapeHtml(t.description || '').substring(0, 100) + '</span>';
      html += '<span class="task-agent mono">' + escapeHtml(t.source_agent || '') + '</span>';
      html += '</div>';
    });
    html += '</div>';

    var totalPages = Math.ceil(filtered.length / PAGE_SIZE);
    if (totalPages > 1) {
      html += '<div class="pagination">Page ' + page + ' of ' + totalPages + '</div>';
    }

    container.innerHTML = html;
  }

  // -----------------------------------------------------------------------
  // Activity Charts (Sprint 21 — KP-004)
  // -----------------------------------------------------------------------

  var intentChart = null;
  var taskChart = null;

  function initCharts() {
    var intentCtx = safeGetEl('intent-chart');
    var taskCtx = safeGetEl('task-chart');

    if (intentCtx && typeof Chart !== 'undefined') {
      intentChart = new Chart(intentCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Intents Routed',
            data: [],
            borderColor: '#6366f1',
            tension: 0.3,
            fill: false,
          }]
        },
        options: {
          responsive: true,
          scales: { y: { beginAtZero: true } },
          plugins: { legend: { display: false } },
          animation: false,
        }
      });
    }

    if (taskCtx && typeof Chart !== 'undefined') {
      taskChart = new Chart(taskCtx, {
        type: 'doughnut',
        data: {
          labels: ['Queued', 'In Progress', 'Completed', 'Failed', 'Blocked'],
          datasets: [{
            data: [0, 0, 0, 0, 0],
            backgroundColor: ['#f59e0b', '#3b82f6', '#22c55e', '#ef4444', '#6b7280'],
          }]
        },
        options: {
          responsive: true,
          animation: false,
        }
      });
    }
  }

  var intentHistory = [];
  var MAX_HISTORY = 60;

  function updateIntentChart(stats) {
    if (!intentChart || !stats) return;
    var now = new Date().toLocaleTimeString();
    intentHistory.push({ time: now, count: stats.intents_routed || 0 });
    if (intentHistory.length > MAX_HISTORY) intentHistory.shift();

    intentChart.data.labels = intentHistory.map(function(h) { return h.time; });
    intentChart.data.datasets[0].data = intentHistory.map(function(h) { return h.count; });
    intentChart.update();
  }

  function updateTaskChart(tasks) {
    if (!taskChart || !tasks) return;
    var counts = { queued: 0, in_progress: 0, completed: 0, failed: 0, blocked: 0 };
    if (Array.isArray(tasks)) {
      tasks.forEach(function(t) {
        if (counts.hasOwnProperty(t.status)) counts[t.status]++;
      });
    }
    taskChart.data.datasets[0].data = [counts.queued, counts.in_progress, counts.completed, counts.failed, counts.blocked];
    taskChart.update();
  }

  // -----------------------------------------------------------------------
  // Main refresh cycle
  // -----------------------------------------------------------------------

  async function refreshAll() {
    setLoading('overview-section', true);

    // Fetch all endpoints in parallel
    const [health, stats, agents, activity, failedIntents, capabilities, tasks, routing, memTasks, memConvos, logsData, topologyData, taskQueueData, orchestrationData, computerUseData, projectxSystem, projectxProcesses, projectxActions, projectxProtocolFacts] = await Promise.all([
      apiFetch("/api/health"),
      apiFetch("/api/stats"),
      apiFetch("/api/agents"),
      apiFetch("/api/activity"),
      apiFetch("/api/intents/failed"),
      apiFetch("/api/capabilities"),
      apiFetch("/api/tasks"),
      apiFetch("/api/routing"),
      apiFetch("/api/memory/tasks"),
      apiFetch("/api/memory/conversations"),
      apiFetch("/api/logs"),
      apiFetch("/api/topology"),
      apiFetch("/api/tasks/queue"),
      apiFetch("/api/orchestration"),
      apiFetch("/api/computer-use"),
      apiFetch("/api/projectx/system"),
      apiFetch("/api/projectx/processes"),
      apiFetch("/api/projectx/actions"),
      apiFetch("/api/projectx/protocol-facts"),
    ]);

    setLoading('overview-section', false);

    renderHealth(health);
    renderStats(stats);
    renderAgents(agents);
    renderActivity(activity);
    renderFailedIntents(failedIntents);
    renderCapabilities(capabilities);
    renderDeliveryStatus(stats);
    renderTasks(tasks);
    renderFailureStats(tasks);
    renderRouting(routing);
    renderMemoryTasks(memTasks);
    renderMemoryConversations(memConvos);
    renderLogs(logsData);
    renderTopology(topologyData);
    renderTaskQueue(taskQueueData);
    renderOrchestration(orchestrationData);
    renderComputerUse(computerUseData);
    renderProjectXSystem(projectxSystem);
    renderProjectXProcesses(projectxProcesses);
    renderProjectXActions(projectxActions);
    renderProjectXProtocolFacts(projectxProtocolFacts);

    // Sprint 21 — update charts
    if (stats) {
      var broker = stats.broker || stats;
      var chartStats = broker.stats || broker;
      updateIntentChart(chartStats);
    }
    if (tasks && tasks.tasks) {
      _lastTasksData = tasks.tasks;
      updateTaskChart(tasks.tasks);
      renderTasksWithFilter(tasks.tasks);
    }

    markUpdated('overview');
    markUpdated('agents');
    markUpdated('tasks');

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
  // WebSocket connection
  // -----------------------------------------------------------------------

  var ws = null;
  var wsRetryCount = 0;
  var MAX_WS_RETRIES = 10;
  var WS_RETRY_DELAY = 3000;
  var wsPingInterval = null;

  function connectWebSocket() {
    var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + location.host + '/ws';

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = function() {
        wsRetryCount = 0;
        updateConnectionStatus('connected');
        if (wsPingInterval) clearInterval(wsPingInterval);
        wsPingInterval = setInterval(function() {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
      };

      ws.onmessage = function(event) {
        try {
          var msg = JSON.parse(event.data);
          handleWsMessage(msg);
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = function() {
        updateConnectionStatus('disconnected');
        if (wsPingInterval) clearInterval(wsPingInterval);
        if (wsRetryCount < MAX_WS_RETRIES) {
          wsRetryCount++;
          setTimeout(connectWebSocket, WS_RETRY_DELAY);
        } else {
          startPollingFallback();
        }
      };

      ws.onerror = function() {
        updateConnectionStatus('error');
      };
    } catch (e) {
      startPollingFallback();
    }
  }

  function handleWsMessage(msg) {
    switch (msg.type) {
      case 'stats':
        renderStats(msg.data);
        renderDeliveryStatus(msg.data);
        break;
      case 'agents':
        renderAgents(msg.data);
        break;
      case 'tasks':
        renderTasks(msg.data);
        renderFailureStats(msg.data);
        break;
      case 'logs':
        renderLogs(msg.data);
        break;
      case 'activity':
        renderActivity(msg.data);
        break;
      case 'heartbeat':
      case 'pong':
        break;
      default:
        refreshAll();
    }
  }

  function updateConnectionStatus(status) {
    var el = document.getElementById('ws-status');
    if (!el) return;
    el.className = 'ws-status ' + status;
    el.textContent = status === 'connected' ? 'Live' : status === 'disconnected' ? 'Reconnecting...' : 'Polling';
  }

  function startPollingFallback() {
    updateConnectionStatus('error');
    setInterval(refreshAll, REFRESH_INTERVAL);
  }

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  dom.refreshBtn.addEventListener("click", function() {
    refreshAll();
  });

  if (dom.intentDrawerClose) {
    dom.intentDrawerClose.addEventListener("click", closeIntentDrawer);
  }
  if (dom.intentDrawerBackdrop) {
    dom.intentDrawerBackdrop.addEventListener("click", closeIntentDrawer);
  }

  if (dom.projectxChatForm) {
    dom.projectxChatForm.addEventListener("submit", function(event) {
      event.preventDefault();
      var message = (dom.projectxChatInput.value || "").trim();
      if (!message) return;
      dom.projectxChatInput.value = "";
      submitProjectXChat({ message: message }, message);
    });
  }

  $$(".projectx-job-btn").forEach(function(btn) {
    btn.addEventListener("click", function() {
      var job = btn.getAttribute("data-job");
      submitProjectXChat({ job: job }, "Run " + job);
    });
  });

  // Sprint 21 — filter event listeners
  var taskSearchEl = safeGetEl('task-search');
  var taskStatusFilterEl = safeGetEl('task-status-filter');
  if (taskSearchEl) {
    taskSearchEl.addEventListener('input', function() {
      if (_lastTasksData) renderTasksWithFilter(_lastTasksData);
    });
  }
  if (taskStatusFilterEl) {
    taskStatusFilterEl.addEventListener('change', function() {
      if (_lastTasksData) renderTasksWithFilter(_lastTasksData);
    });
  }

  // Sprint 21 — initialize charts
  initCharts();

  // Try WebSocket first, fall back to polling
  connectWebSocket();
  // Initial fetch + countdown
  refreshAll();
  startCountdown();

})();
