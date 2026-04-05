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

    // Delivery status
    valDelivered:         $("#val-delivered"),
    valQueued:            $("#val-queued"),
    valQueuedNoEndpoint:  $("#val-queued-no-endpoint"),
    valDeliveryFailed:    $("#val-delivery-failed"),
    valTimeout:           $("#val-timeout"),
    valRateLimited:       $("#val-rate-limited"),
    deliveryTbody:        $("#delivery-tbody"),

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
    // Broker returns paused/bullbear_watcher instead of a single "state" string
    const state = data.state || (data.paused ? "Paused" : "Running");
    dom.valBrokerState.textContent = state;
    dom.valAgentsOnline.textContent = data.agents_online ?? "--";
    dom.valPending.textContent = data.pending_intents ?? "--";
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
        '<div class="empty-state">No activity recorded yet. Events appear when broker state changes.</div>';
      return;
    }
    // Show newest first
    const sorted = [...events].reverse();
    let html = "";
    for (const ev of sorted) {
      const ds = ev.delivery_status || "--";
      const statusCls = ds === "delivered" ? "delivered"
        : (ds === "failed" || ds === "timeout" || ds === "rate_limited") ? "failed"
        : (ds === "queued" || ds === "queued_no_endpoint") ? "queued"
        : "queued";
      html += '<div class="activity-item">';
      html += '<span class="activity-ts">' + formatDate(ev.timestamp) + "</span>";
      html += '<span class="activity-type">' + escHtml(ev.event_type || ev.intent_type || "--") + "</span>";
      html += '<span class="activity-result">' + escHtml(ev.result || "--") + "</span>";
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

  // -----------------------------------------------------------------------
  // Render: Delivery Status
  // -----------------------------------------------------------------------

  function renderDeliveryStatus(statsData) {
    if (!statsData || statsData.status === "unreachable") return;
    var broker = statsData.broker || statsData;
    var stats = broker.stats || broker;

    // Delivery counts from broker stats
    var dc = stats.delivery_counts || {};
    dom.valDelivered.textContent = dc.delivered || 0;
    dom.valQueued.textContent = dc.queued || 0;
    dom.valQueuedNoEndpoint.textContent = dc.queued_no_endpoint || 0;
    dom.valDeliveryFailed.textContent = dc.failed || 0;
    dom.valTimeout.textContent = dc.timeout || 0;
    dom.valRateLimited.textContent = dc.rate_limited || 0;

    // Color failed/timeout/rate_limited red if > 0
    if ((dc.failed || 0) > 0) dom.valDeliveryFailed.className = "card-value mono status-error";
    else dom.valDeliveryFailed.className = "card-value mono";
    if ((dc.timeout || 0) > 0) dom.valTimeout.className = "card-value mono status-error";
    else dom.valTimeout.className = "card-value mono";
    if ((dc.rate_limited || 0) > 0) dom.valRateLimited.className = "card-value mono status-error";
    else dom.valRateLimited.className = "card-value mono";

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
      html += td('<span class="mono" style="font-size:0.7rem">' + escHtml((d.intent_id || "").substring(0, 12)) + "</span>");
      html += td(mono(escHtml(d.target_agent || "--")));
      html += td('<span class="status-badge ' + dsCls + '">' + escHtml(d.delivery_status || "--") + "</span>");
      html += td(mono(d.delivery_latency_ms != null ? Number(d.delivery_latency_ms).toFixed(1) + " ms" : "--"));
      html += td(mono(d.retry_count != null ? String(d.retry_count) : "--"));
      html += td(mono(escHtml(d.fallback_agent || "--")));
      html += "</tr>";
    }
    dom.deliveryTbody.innerHTML = html;
  }

  function deliveryStatusClass(status) {
    if (!status) return "unknown";
    if (status === "delivered") return "online";
    if (status === "queued" || status === "queued_no_endpoint") return "degraded";
    if (status === "failed" || status === "timeout" || status === "rate_limited") return "offline";
    return "unknown";
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
  // Main refresh cycle
  // -----------------------------------------------------------------------

  async function refreshAll() {
    // Fetch all endpoints in parallel
    const [health, stats, agents, activity, capabilities, tasks, routing, memTasks, memConvos] = await Promise.all([
      apiFetch("/api/health"),
      apiFetch("/api/stats"),
      apiFetch("/api/agents"),
      apiFetch("/api/activity"),
      apiFetch("/api/capabilities"),
      apiFetch("/api/tasks"),
      apiFetch("/api/routing"),
      apiFetch("/api/memory/tasks"),
      apiFetch("/api/memory/conversations"),
    ]);

    renderHealth(health);
    renderStats(stats);
    renderAgents(agents);
    renderActivity(activity);
    renderCapabilities(capabilities);
    renderDeliveryStatus(stats);
    renderTasks(tasks);
    renderFailureStats(tasks);
    renderRouting(routing);
    renderMemoryTasks(memTasks);
    renderMemoryConversations(memConvos);

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
