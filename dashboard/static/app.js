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
    systemOverviewSummary: $("#system-overview-summary"),
    systemOverviewCards: $("#system-overview-cards"),
    systemOverviewActions: $("#system-overview-actions"),
    agentObservabilityCards: $("#agent-observability-cards"),
    valBrpResponses: $("#val-brp-responses"),
    valBrpActiveRules: $("#val-brp-active-rules"),
    valBrpElevated: $("#val-brp-elevated"),
    valBrpAvgThreat: $("#val-brp-avg-threat"),
    valBrpLastEval: $("#val-brp-last-eval"),
    valBrpTopTag: $("#val-brp-top-tag"),
    valBrpOpenAlerts: $("#val-brp-open-alerts"),
    valBrpAckedAlerts: $("#val-brp-acked-alerts"),
    brpPostureSummary: $("#brp-posture-summary"),
    brpThreatTags: $("#brp-threat-tags"),
    brpSignalSummary: $("#brp-signal-summary"),
    brpPlaybooksFeed: $("#brp-playbooks-feed"),
    brpEvaluationsTbody: $("#brp-evaluations-tbody"),
    brpRulesTbody: $("#brp-rules-tbody"),
    brpAlertsFeed: $("#brp-alerts-feed"),
    brpRemediationsFeed: $("#brp-remediations-feed"),
    brpDecisionFilter: $("#brp-decision-filter"),
    brpSeverityFilter: $("#brp-severity-filter"),
    brpSourceFilter: $("#brp-source-filter"),
    brpExportBtn: $("#brp-export-btn"),
    brpDrawer: $("#brp-drawer"),
    brpDrawerBackdrop: $("#brp-drawer-backdrop"),
    brpDrawerTitle: $("#brp-drawer-title"),
    brpDrawerSummary: $("#brp-drawer-summary"),
    brpDrawerSource: $("#brp-drawer-source"),
    brpDrawerSignals: $("#brp-drawer-signals"),
    brpDrawerTags: $("#brp-drawer-tags"),
    brpDrawerObservations: $("#brp-drawer-observations"),
    brpDrawerRules: $("#brp-drawer-rules"),
    brpDrawerClose: $("#brp-drawer-close"),
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
    intentDrawerActions: $("#intent-drawer-actions"),
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
    smokeTbody:      $("#smoke-tbody"),
    flowsTbody:      $("#flows-tbody"),

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
  let brpFilterTimer = null;

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

  function buildBrpEvaluationQuery() {
    var params = new URLSearchParams();
    params.set("limit", "12");
    if (dom.brpDecisionFilter && dom.brpDecisionFilter.value) params.set("decision", dom.brpDecisionFilter.value);
    if (dom.brpSeverityFilter && dom.brpSeverityFilter.value) params.set("severity", dom.brpSeverityFilter.value);
    if (dom.brpSourceFilter && dom.brpSourceFilter.value.trim()) {
      params.set("query", dom.brpSourceFilter.value.trim());
    }
    return params.toString();
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
      const status = a.heartbeat_stale ? "stale" : (a.status || "unknown");
      const heartbeatHint = a.last_heartbeat
        ? '<div class="text-muted" style="font-size:0.72rem">heartbeat ' + escHtml(formatDate(a.last_heartbeat)) + "</div>"
        : "";

      html += "<tr>";
      html += td(mono(escHtml(a.agent_id || "--")));
      html += td(escHtml(a.name || a.agent_id || "--"));
      html += td(modeBadge(mode));
      html += td(statusBadge(status) + heartbeatHint);
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
      container.innerHTML = '<tr><td colspan="7" class="empty-row">Task queue empty</td></tr>';
      return;
    }
    container.innerHTML = data.queue.slice(0, 20).map(t => {
      const statusClass = t.status === "completed" ? "online"
                        : t.status === "in_progress" ? "degraded"
                        : t.status === "queued" ? "unknown"
                        : "offline";
      return `<tr>
        <td class="mono">${escapeHtml(t.task_id || "--")}</td>
        <td>${escapeHtml(t.title || "--")}</td>
        <td>${escapeHtml(t.task_type || "--")}</td>
        <td class="mono">${escapeHtml(t.priority || "--")}</td>
        <td><span class="status-badge ${escapeHtml(statusClass)}">${escapeHtml(t.status || "--")}</span></td>
        <td class="mono">${escapeHtml(t.assigned_agent || t.claimed_by || "unclaimed")}</td>
        <td class="mono">${escapeHtml(formatDate(t.created_at))}</td>
      </tr>`;
    }).join("");
  }

  function renderSmoke(data) {
    if (!dom.smokeTbody) return;
    if (!data || !data.results || data.results.length === 0) {
      dom.smokeTbody.innerHTML = '<tr><td colspan="5" class="empty-row">No smoke probes available</td></tr>';
      return;
    }
    dom.smokeTbody.innerHTML = data.results.slice(0, 20).map(function(row) {
      var statusClass = deliveryStatusClass(row.status || (row.reachable ? "ok" : "failed"));
      var probeLabel = row.delivery_path ? String(row.delivery_path) : (row.health_url || row.endpoint || "--");
      if (row.degraded) {
        probeLabel += " • degraded";
      }
      return "<tr>"
        + td(mono(escHtml(row.agent_id || "--")))
        + td('<span class="status-badge ' + statusClass + '">' + escHtml(row.status || (row.reachable ? "reachable" : "unreachable")) + "</span>")
        + td(mono(escHtml(probeLabel)))
        + td(mono(escHtml(formatDuration(row.response_ms))))
        + td(escHtml(row.error || "--"))
        + "</tr>";
    }).join("");
  }

  function renderFlows(data) {
    if (!dom.flowsTbody) return;
    var flows = (data && data.flows) || [];
    if (!flows.length) {
      dom.flowsTbody.innerHTML = '<tr><td colspan="6" class="empty-row">No linked flows recorded yet</td></tr>';
      return;
    }
    dom.flowsTbody.innerHTML = flows.slice(0, 20).map(function(flow) {
      var planner = flow.planner_intent || {};
      var executors = flow.executor_intents || [];
      var timeline = (flow.timeline && flow.timeline.steps) || [];
      var plannerCell = planner.intent_id
        ? '<button type="button" class="intent-row-button" data-intent-id="' + escHtml(planner.intent_id) + '">' + escHtml((planner.target_agent || "--") + " • " + (planner.intent_type || "--")) + "</button>"
        : '<span class="text-muted">--</span>';
      var executorCell = executors.length ? executors.map(function(item) {
        if (!item.intent_id) return '<span class="text-muted">--</span>';
        return '<button type="button" class="intent-row-button" data-intent-id="' + escHtml(item.intent_id) + '">' + escHtml((item.target_agent || "--") + " • " + (item.intent_type || "--")) + "</button>";
      }).join("<br>") : '<span class="text-muted">No executor intents</span>';
      var timelineCell = timeline.length ? '<div class="flow-timeline">'
        + timeline.map(function(step) {
          var label = (step.phase || "--") + " • " + (step.target_agent || "--");
          var meta = [];
          if (step.duration_ms != null) meta.push(formatDuration(step.duration_ms));
          if (step.retry_count) meta.push("retry " + step.retry_count);
          if (step.failure_reason) meta.push(step.failure_reason);
          return '<div class="flow-step">'
            + '<div class="flow-step-header"><span class="status-badge ' + escHtml(deliveryStatusClass(step.delivery_status || "unknown")) + '">' + escHtml(step.delivery_status || "--") + '</span>'
            + '<span class="flow-step-label">' + escHtml(label) + '</span></div>'
            + '<div class="flow-step-meta mono">' + escHtml(meta.join(" • ") || "--") + '</div>'
            + '</div>';
        }).join("")
        + '<div class="flow-timeline-summary mono">total ' + escHtml(formatDuration(flow.timeline.total_duration_ms)) + ' • retries ' + escHtml(String(flow.timeline.total_retry_count || 0)) + '</div>'
        + '</div>'
        : '<span class="text-muted">No timing yet</span>';
      var statuses = (flow.statuses || []).join(", ") || "--";
      return "<tr>"
        + td(mono(escHtml(flow.flow_id || "--")))
        + td(plannerCell)
        + td(executorCell)
        + td(timelineCell)
        + td(escHtml(statuses))
        + td(mono(escHtml(formatDate(flow.last_updated))))
        + "</tr>";
    }).join("");
    dom.flowsTbody.querySelectorAll("[data-intent-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openIntentDrawer(button.getAttribute("data-intent-id"));
      });
    });
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
    if (s === "degraded" || s === "paused" || s === "stale") return "degraded";
    if (s === "error" || s === "unreachable" || s === "stopped" || s === "offline") return "error";
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

  function formatDuration(ms) {
    if (ms == null || ms === "") return "--";
    var value = Number(ms);
    if (!isFinite(value)) return "--";
    if (value < 1000) return value.toFixed(0) + " ms";
    return (value / 1000).toFixed(value >= 10000 ? 0 : 1) + " s";
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

  function remediationActionsForIntent(detail) {
    var actions = [];
    var status = String(detail.delivery_status || "unknown");
    var target = String(detail.target_agent || "");

    if (status === "connection_refused" || status === "timeout") {
      actions.push({
        label: "Check broker health",
        job: "native_agent_health_check",
        note: "Validate the control plane before retrying delivery."
      });
    }
    if (status === "queued_no_endpoint" || target === "projectx_native") {
      actions.push({
        label: "Run task audit",
        job: "native_agent_task_audit",
        note: "Inspect recent task and registration state for this target."
      });
    }
    if (status !== "delivered") {
      actions.push({
        label: "Run repo scan",
        job: "native_agent_repo_scan",
        note: "Use a bounded ProjectX inspection before deeper repair work."
      });
    }

    var deduped = [];
    var seen = {};
    actions.forEach(function(action) {
      if (!seen[action.job]) {
        deduped.push(action);
        seen[action.job] = true;
      }
    });
    return deduped;
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
    renderDiagnosticList(dom.intentDrawerActions, remediationActionsForIntent(detail), function(action) {
      return '<div class="intent-action-row">'
        + '<button type="button" class="refresh-btn intent-remediation-btn" data-job="' + escHtml(action.job) + '">' + escHtml(action.label) + '</button>'
        + '<span class="intent-action-note">' + escHtml(action.note || "") + '</span>'
        + '</div>';
    });
    if (dom.intentDrawerActions) {
      dom.intentDrawerActions.querySelectorAll("[data-job]").forEach(function(button) {
        button.addEventListener("click", function() {
          var job = button.getAttribute("data-job");
          submitProjectXChat({ job: job, source_intent_id: detail.intent_id }, "Run " + job);
        });
      });
    }

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
    if (data.supported === false || data.status === "not_supported") {
      dom.memoryTasksTbody.innerHTML = '<tr><td colspan="3" class="empty-row">' + escHtml(data.reason || "Task memory is not supported by the broker") + '</td></tr>';
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
    if (data.supported === false || data.status === "not_supported") {
      dom.memoryConvosTbody.innerHTML = '<tr><td colspan="4" class="empty-row">' + escHtml(data.reason || "Conversation memory is not supported by the broker") + '</td></tr>';
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
    summaryHtml += '<div class="protocol-summary-row"><span class="card-label">Docs Path</span><span class="mono">' + escHtml(facts.protocol_docs_path || "--") + '</span></div>';
    dom.projectxProtocolSummary.innerHTML = summaryHtml;
    renderSystemOverview(facts.protocol_docs || null);
  }

  function brpDecisionBadge(decision) {
    var value = String(decision || "--");
    var normalized = value.toUpperCase();
    var cls = "unknown";
    if (normalized === "ALLOW" || normalized === "SHADOW_ALLOW") cls = "online";
    else if (normalized === "ELEVATE" || normalized === "DENY") cls = "offline";
    else if (normalized === "LOG_ONLY") cls = "degraded";
    return '<span class="status-badge ' + cls + '">' + escHtml(value) + "</span>";
  }

  function brpSeverityBadge(severity) {
    var value = String(severity || "--");
    var normalized = value.toLowerCase();
    var cls = "unknown";
    if (normalized === "critical" || normalized === "high") cls = "offline";
    else if (normalized === "medium" || normalized === "low") cls = "degraded";
    else if (normalized === "info") cls = "online";
    return '<span class="status-badge ' + cls + '">' + escHtml(value) + "</span>";
  }

  function renderBrpStatus(data) {
    if (!dom.valBrpResponses) return;
    if (!data || data.status !== "success" || !data.has_data) {
      dom.valBrpResponses.textContent = "--";
      dom.valBrpActiveRules.textContent = "--";
      dom.valBrpElevated.textContent = "--";
      dom.valBrpAvgThreat.textContent = "--";
      dom.valBrpLastEval.textContent = "--";
      dom.valBrpTopTag.textContent = "--";
      if (dom.brpPostureSummary) {
        dom.brpPostureSummary.innerHTML = '<div class="empty-state">BRP status not loaded.</div>';
      }
      if (dom.brpThreatTags) {
        dom.brpThreatTags.innerHTML = '<div class="empty-state">No threat tags observed.</div>';
      }
      return;
    }

    var counts = data.counts || {};
    var recent = data.recent || {};
    var decisionCounts = recent.decision_counts || {};
    var elevated = Number(decisionCounts.ELEVATE || 0) + Number(decisionCounts.DENY || 0);
    var topTags = recent.top_threat_tags || [];

    dom.valBrpResponses.textContent = counts.responses != null ? String(counts.responses) : "--";
    dom.valBrpActiveRules.textContent = recent.active_adaptive_rules != null ? String(recent.active_adaptive_rules) : "--";
    dom.valBrpElevated.textContent = String(elevated);
    dom.valBrpElevated.className = elevated > 0 ? "card-value mono status-error" : "card-value mono";
    dom.valBrpAvgThreat.textContent = recent.average_threat_score != null ? Number(recent.average_threat_score).toFixed(2) : "--";
    dom.valBrpAvgThreat.className = "card-value mono " + ((recent.average_threat_score || 0) >= 0.6 ? "status-error" : (recent.average_threat_score || 0) >= 0.3 ? "status-degraded" : "");
    dom.valBrpLastEval.textContent = formatDate(recent.last_evaluation_at);
    dom.valBrpTopTag.textContent = topTags.length ? String(topTags[0].tag || "--") : "--";

    renderDiagnosticPairs(dom.brpPostureSummary, [
      { label: "Events", value: String(counts.events != null ? counts.events : "--") },
      { label: "Plans", value: String(counts.plans != null ? counts.plans : "--") },
      { label: "Observations", value: String(counts.observations != null ? counts.observations : "--") },
      { label: "Max Threat", value: recent.max_threat_score != null ? Number(recent.max_threat_score).toFixed(2) : "--" },
      { label: "Last Observation", value: formatDate(recent.last_observation_at) },
    ]);

    if (dom.brpThreatTags) {
      dom.brpThreatTags.innerHTML = topTags.length ? topTags.map(function(item) {
        return '<div class="brp-chip"><span>' + escHtml(item.tag || "--") + '</span><span class="brp-chip-count">' + escHtml(String(item.count || 0)) + '</span></div>';
      }).join("") : '<div class="empty-state">No threat tags observed.</div>';
    }
  }

  function renderBrpIncidents(data) {
    if (!data) return;
    var openAlerts = Number(data.open_alerts || 0);
    var ackedAlerts = Number(data.acknowledged_alerts || 0);
    if (dom.valBrpOpenAlerts) {
      dom.valBrpOpenAlerts.textContent = String(openAlerts);
      dom.valBrpOpenAlerts.className = openAlerts > 0 ? "card-value mono status-error" : "card-value mono";
    }
    if (dom.valBrpAckedAlerts) {
      dom.valBrpAckedAlerts.textContent = String(ackedAlerts);
      dom.valBrpAckedAlerts.className = ackedAlerts > 0 ? "card-value mono status-healthy" : "card-value mono";
    }
  }

  function renderBrpInsights(data) {
    if (!dom.brpSignalSummary) return;
    if (!data || data.status !== "success") {
      dom.brpSignalSummary.innerHTML = '<div class="empty-state">BRP insights not loaded.</div>';
      return;
    }
    var summary = data.summary || {};
    var signals = data.signals || {};
    renderDiagnosticPairs(dom.brpSignalSummary, [
      { label: "Window", value: String(summary.window_size != null ? summary.window_size : "--") },
      { label: "Elevated / Denied", value: String(summary.elevated_or_denied != null ? summary.elevated_or_denied : "--") },
      { label: "High Severity", value: String(summary.high_severity != null ? summary.high_severity : "--") },
      { label: "Predictive Boost", value: signals.predictive_score_boost != null ? Number(signals.predictive_score_boost).toFixed(2) : "--" },
      { label: "Multimodal Detections", value: String(signals.multimodal_detections != null ? signals.multimodal_detections : "--") },
    ]);
  }

  function renderBrpEvaluations(data) {
    if (!dom.brpEvaluationsTbody) return;
    var evaluations = (data && data.evaluations) || [];
    if (!evaluations.length) {
      dom.brpEvaluationsTbody.innerHTML = '<tr><td colspan="7" class="empty-row">No BRP evaluations recorded yet.</td></tr>';
      return;
    }
    dom.brpEvaluationsTbody.innerHTML = evaluations.slice(0, 12).map(function(row) {
      var source = [row.source_agent || "--", row.record_type || "--"].join(" • ");
      var threat = row.threat_score != null ? Number(row.threat_score).toFixed(2) : "--";
      var signalLines = [];
      if ((row.predictive_score_boost || 0) > 0) signalLines.push("predictive +" + Number(row.predictive_score_boost).toFixed(2));
      if ((row.multimodal_score_boost || 0) > 0) signalLines.push("multimodal +" + Number(row.multimodal_score_boost).toFixed(2));
      if ((row.multimodal_detections || 0) > 0) signalLines.push(String(row.multimodal_detections) + " detections");
      return "<tr>"
        + td('<button type="button" class="intent-row-button mono brp-row-button" data-brp-event-id="' + escHtml(row.event_id || "") + '">' + escHtml(formatDate(row.timestamp)) + "</button>")
        + td(escHtml(source))
        + td('<div>' + escHtml(row.action || row.event_type || "--") + '</div><div class="brp-inline-tags">' + ((row.threat_tags || []).slice(0, 3).map(capPill).join("") || "") + '</div>')
        + td(brpDecisionBadge(row.decision))
        + td(brpSeverityBadge(row.severity))
        + td(mono(escHtml(threat)))
        + td('<div class="brp-signal-stack">' + (signalLines.length ? signalLines.map(function(line) { return '<div class="brp-signal-line">' + escHtml(line) + '</div>'; }).join("") : '<div class="brp-signal-line">no extra signals</div>') + '</div>')
        + "</tr>";
    }).join("");
    dom.brpEvaluationsTbody.querySelectorAll("[data-brp-event-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openBrpDrawer(button.getAttribute("data-brp-event-id"));
      });
    });
  }

  function renderBrpAdaptiveRules(data) {
    if (!dom.brpRulesTbody) return;
    var rules = (data && data.rules) || [];
    if (!rules.length) {
      dom.brpRulesTbody.innerHTML = '<tr><td colspan="6" class="empty-row">No adaptive BRP rules learned yet.</td></tr>';
      return;
    }
    dom.brpRulesTbody.innerHTML = rules.slice(0, 12).map(function(rule) {
      return "<tr>"
        + td('<span class="mono" style="font-size:0.74rem">' + escHtml(rule.key || "--") + "</span>")
        + td(brpSeverityBadge(rule.severity))
        + td(mono(escHtml(rule.boost != null ? Number(rule.boost).toFixed(2) : "--")))
        + td(mono(escHtml(rule.count != null ? String(rule.count) : "--")))
        + td(statusBadge(rule.active ? "active" : "inactive"))
        + td(mono(escHtml(formatDate(rule.last_seen))))
        + "</tr>";
    }).join("");
  }

  function renderBrpPlaybooks(data) {
    if (!dom.brpPlaybooksFeed) return;
    var playbooks = (data && data.playbooks) || [];
    if (!playbooks.length) {
      dom.brpPlaybooksFeed.innerHTML = '<div class="empty-state">No BRP playbooks derived yet.</div>';
      return;
    }
    dom.brpPlaybooksFeed.innerHTML = playbooks.slice(0, 8).map(function(playbook) {
      var automation = playbook.automation || {};
      var inspectButton = playbook.event_id
        ? '<button type="button" class="intent-row-button" data-brp-event-id="' + escHtml(playbook.event_id) + '">inspect</button>'
        : '<span class="text-muted">playbook</span>';
      var executeButton = automation.job
        ? '<button type="button" class="intent-row-button" data-brp-playbook-id="' + escHtml(playbook.playbook_id || "") + '" data-brp-job="' + escHtml(automation.job) + '">run ' + escHtml(automation.job) + '</button>'
        : '<span class="text-muted">manual</span>';
      var remediationLine = playbook.last_remediation
        ? 'last remediation: ' + String(playbook.last_remediation.status || "--") + ' via ' + String(playbook.last_remediation.job || "--")
        : (automation.reason || "--");
      return '<div class="activity-item">'
        + '<span class="activity-ts">' + escHtml(formatDate(playbook.timestamp)) + '</span>'
        + '<span class="activity-type">' + brpSeverityBadge(playbook.priority || playbook.severity || "medium") + '</span>'
        + '<span class="activity-result">' + escHtml(playbook.title || "--") + '<div class="brp-signal-line">' + escHtml(playbook.primary_action || "--") + '</div><div class="brp-signal-line">' + escHtml(remediationLine) + '</div><div class="brp-signal-line">' + inspectButton + ' ' + executeButton + '</div></span>'
        + '<span class="activity-status ' + (playbook.status === "acknowledged" ? "online" : "queued") + '">' + escHtml(playbook.status || "--") + '</span>'
        + '</div>';
    }).join("");
    dom.brpPlaybooksFeed.querySelectorAll("[data-brp-event-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openBrpDrawer(button.getAttribute("data-brp-event-id"));
      });
    });
    dom.brpPlaybooksFeed.querySelectorAll("[data-brp-playbook-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        executeBrpPlaybook(button.getAttribute("data-brp-playbook-id"), button.getAttribute("data-brp-job"));
      });
    });
  }

  async function acknowledgeBrpAlert(alertId) {
    if (!alertId) return;
    var response = await apiPost("/api/brp/alerts/" + encodeURIComponent(alertId) + "/acknowledge", {
      actor: "dashboard_ui",
      note: "triaged via dashboard"
    });
    if (!response || response.status !== "success") return;
    await refreshAll();
  }

  async function executeBrpPlaybook(playbookId, job) {
    if (!playbookId || !job) return;
    var response = await apiPost("/api/brp/playbooks/" + encodeURIComponent(playbookId) + "/execute", {
      actor: "dashboard_ui",
      job: job
    });
    if (!response || (response.status !== "success" && response.status !== "unreachable")) return;
    await refreshAll();
  }

  function renderBrpRemediations(data) {
    if (!dom.brpRemediationsFeed) return;
    var remediations = (data && data.remediations) || [];
    if (!remediations.length) {
      dom.brpRemediationsFeed.innerHTML = '<div class="empty-state">No BRP remediations executed yet.</div>';
      return;
    }
    dom.brpRemediationsFeed.innerHTML = remediations.slice(0, 8).map(function(item) {
      var inspectButton = item.event_id
        ? '<button type="button" class="intent-row-button" data-brp-event-id="' + escHtml(item.event_id) + '">inspect</button>'
        : '<span class="text-muted">history</span>';
      return '<div class="activity-item">'
        + '<span class="activity-ts">' + escHtml(formatDate(item.timestamp)) + '</span>'
        + '<span class="activity-type">' + statusBadge(item.status || "unknown") + '</span>'
        + '<span class="activity-result">' + escHtml(item.summary || "--") + '<div class="brp-signal-line">' + escHtml((item.job || "--") + " • " + (item.routing_mode || "--")) + '</div><div class="brp-signal-line">' + inspectButton + '</div></span>'
        + '<span class="activity-status ' + (item.status === "completed" ? "online" : item.status === "failed" ? "failed" : "queued") + '">' + escHtml(item.delivery_status || item.status || "--") + '</span>'
        + '</div>';
    }).join("");
    dom.brpRemediationsFeed.querySelectorAll("[data-brp-event-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openBrpDrawer(button.getAttribute("data-brp-event-id"));
      });
    });
  }

  function renderBrpAlerts(data) {
    if (!dom.brpAlertsFeed) return;
    var alerts = (data && data.alerts) || [];
    if (!alerts.length) {
      dom.brpAlertsFeed.innerHTML = '<div class="empty-state">No BRP alerts derived yet.</div>';
      return;
    }
    dom.brpAlertsFeed.innerHTML = alerts.slice(0, 8).map(function(alert) {
      var statusClass = String(alert.severity || "").toLowerCase();
      var severityBadge = brpSeverityBadge(alert.severity || "medium");
      var openButton = alert.event_id
        ? '<button type="button" class="intent-row-button" data-brp-event-id="' + escHtml(alert.event_id) + '">inspect</button>'
        : '<span class="text-muted">summary</span>';
      var ackButton = alert.acknowledged
        ? '<span class="text-muted">acked by ' + escHtml(alert.acknowledged_by || "operator") + '</span>'
        : '<button type="button" class="intent-row-button" data-brp-alert-id="' + escHtml(alert.alert_id || "") + '">acknowledge</button>';
      var stateText = alert.state || (alert.acknowledged ? "acknowledged" : "open");
      var lifecycleLabel = stateText + (alert.decision ? " • " + alert.decision : "");
      return '<div class="activity-item">'
        + '<span class="activity-ts">' + escHtml(formatDate(alert.timestamp)) + '</span>'
        + '<span class="activity-type">' + severityBadge + '</span>'
        + '<span class="activity-result">' + escHtml(alert.summary || "--") + '<div class="brp-signal-line">' + escHtml(alert.recommendation || "--") + '</div><div class="brp-signal-line">' + openButton + ' ' + ackButton + '</div></span>'
        + '<span class="activity-status ' + (alert.acknowledged ? "online" : (statusClass === "critical" || statusClass === "high" ? "failed" : "queued")) + '">' + escHtml(lifecycleLabel) + '</span>'
        + '</div>';
    }).join("");
    dom.brpAlertsFeed.querySelectorAll("[data-brp-event-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        openBrpDrawer(button.getAttribute("data-brp-event-id"));
      });
    });
    dom.brpAlertsFeed.querySelectorAll("[data-brp-alert-id]").forEach(function(button) {
      button.addEventListener("click", function() {
        acknowledgeBrpAlert(button.getAttribute("data-brp-alert-id"));
      });
    });
  }

  async function openBrpDrawer(eventId) {
    if (!eventId) return;
    var payload = await apiFetch("/api/brp/evaluations/" + encodeURIComponent(eventId));
    var detail = payload && payload.detail;
    if (!detail || !detail.evaluation) {
      if (dom.brpDrawerTitle) dom.brpDrawerTitle.textContent = eventId;
      renderDiagnosticPairs(dom.brpDrawerSummary, [{ label: "Status", value: "not found" }]);
      renderDiagnosticPairs(dom.brpDrawerSource, []);
      renderDiagnosticPairs(dom.brpDrawerSignals, []);
      if (dom.brpDrawerTags) dom.brpDrawerTags.innerHTML = '<div class="empty-state">No threat tags.</div>';
      renderDiagnosticList(dom.brpDrawerObservations, [], function() { return ""; });
      renderDiagnosticList(dom.brpDrawerRules, [], function() { return ""; });
    } else {
      var evaluation = detail.evaluation || {};
      var sourceRecord = detail.source_record || {};
      var predictive = (evaluation.metadata || {}).predictive_assessment || {};
      var multimodal = (evaluation.metadata || {}).multimodal_assessment || {};
      var predictiveSteps = (evaluation.metadata || {}).predictive_steps || [];
      var multimodalSteps = (evaluation.metadata || {}).multimodal_steps || [];
      if (dom.brpDrawerTitle) dom.brpDrawerTitle.textContent = evaluation.event_id || eventId;
      renderDiagnosticPairs(dom.brpDrawerSummary, [
        { label: "Decision", value: evaluation.decision || "--" },
        { label: "Severity", value: evaluation.severity || "--" },
        { label: "Threat", value: evaluation.threat_score != null ? Number(evaluation.threat_score).toFixed(2) : "--" },
        { label: "Confidence", value: evaluation.confidence != null ? Number(evaluation.confidence).toFixed(2) : "--" },
        { label: "Mode", value: evaluation.mode || "--" },
        { label: "Timestamp", value: formatDate(evaluation.timestamp) },
      ]);
      renderDiagnosticPairs(dom.brpDrawerSource, [
        { label: "Source Agent", value: sourceRecord.source_agent || evaluation.source_agent || "--" },
        { label: "Event Type", value: sourceRecord.event_type || evaluation.event_type || "--" },
        { label: "Action", value: sourceRecord.action || evaluation.action || "--" },
        { label: "Step Count", value: sourceRecord.steps ? String(sourceRecord.steps.length) : (evaluation.step_count != null ? String(evaluation.step_count) : "--") },
      ]);
      renderDiagnosticPairs(dom.brpDrawerSignals, [
        { label: "Predictive Boost", value: evaluation.predictive_score_boost != null ? Number(evaluation.predictive_score_boost).toFixed(2) : "--" },
        { label: "Multimodal Boost", value: evaluation.multimodal_score_boost != null ? Number(evaluation.multimodal_score_boost).toFixed(2) : "--" },
        { label: "Multimodal Detections", value: evaluation.multimodal_detections != null ? String(evaluation.multimodal_detections) : "--" },
        { label: "Predictive Domains", value: (predictive.domains || []).join(", ") || (predictiveSteps.length ? "step-derived" : "--") },
        { label: "Predictive Matches", value: predictive.adaptive_rule_matches ? String(predictive.adaptive_rule_matches.length) : (predictiveSteps.length ? String(predictiveSteps.length) : "--") },
        { label: "Multimodal Channels", value: ((multimodal.summary || {}).detection_breakdown ? Object.keys(multimodal.summary.detection_breakdown).filter(function(key) { return multimodal.summary.detection_breakdown[key]; }).join(", ") : (multimodalSteps.length ? "step-derived" : "--")) || "--" },
        { label: "Incident State", value: ((detail.alert || {}).state) || "--" },
        { label: "Primary Playbook", value: ((detail.playbook || {}).primary_action) || "--" },
        { label: "Last Remediation", value: (((detail.remediations || [])[0] || {}).job) || "--" },
      ]);
      if (dom.brpDrawerTags) {
        var tags = evaluation.threat_tags || [];
        dom.brpDrawerTags.innerHTML = tags.length ? tags.map(function(tag) {
          return '<div class="brp-chip"><span>' + escHtml(tag) + '</span></div>';
        }).join("") : '<div class="empty-state">No threat tags.</div>';
      }
      renderDiagnosticList(dom.brpDrawerObservations, detail.related_observations || [], function(obs) {
        return '<div class="diagnostic-row">'
          + '<span class="mono">' + escHtml(formatDate(obs.timestamp)) + '</span>'
          + '<span>' + escHtml(obs.outcome || "--") + '</span>'
          + '<span class="mono">' + escHtml(obs.action || "--") + '</span>'
          + '<span>' + escHtml(((obs.result_data || {}).error_message) || (((obs.result_data || {}).success) === true ? "success" : "--")) + '</span>'
          + '</div>';
      });
      renderDiagnosticList(dom.brpDrawerRules, detail.related_rules || [], function(rule) {
        return '<div class="diagnostic-row">'
          + '<span class="mono">' + escHtml(rule.key || "--") + '</span>'
          + '<span>' + escHtml(rule.severity || "--") + '</span>'
          + '<span class="mono">' + escHtml(rule.boost != null ? Number(rule.boost).toFixed(2) : "--") + '</span>'
          + '<span>' + escHtml(rule.active ? "active" : "inactive") + '</span>'
          + '</div>';
      });
    }

    if (dom.brpDrawerBackdrop) dom.brpDrawerBackdrop.hidden = false;
    if (dom.brpDrawer) dom.brpDrawer.hidden = false;
  }

  function closeBrpDrawer() {
    if (dom.brpDrawerBackdrop) dom.brpDrawerBackdrop.hidden = true;
    if (dom.brpDrawer) dom.brpDrawer.hidden = true;
  }

  function renderAgentObservability(activityData, agentsData, capabilitiesData, failedIntentsData, smokeData) {
    if (!activityData || !activityData.events || !agentsData || !agentsData.agents) {
      dom.agentObservabilityCards.innerHTML =
        '<div class="empty-state">Agent activity data unavailable.</div>';
      return;
    }

    const events = activityData.events || [];
    
    // Count intents by source agent
    const agentCounts = {};
    const agentStatus = {};
    const agentFailureCounts = {};
    
    // Initialize with all known agents
    agentsData.agents.forEach(agent => {
      const agentId = agent.id || agent.agent_id;
      if (agentId) {
        agentCounts[agentId] = 0;
        agentStatus[agentId] = agent.status || "unknown";
        agentFailureCounts[agentId] = 0;
      }
    });
    
    // Count recent intents by source agent
    events.forEach(event => {
      const sourceAgent = event.source_agent;
      if (sourceAgent && agentCounts.hasOwnProperty(sourceAgent)) {
        agentCounts[sourceAgent]++;
      }
    });
    
    // Count failures by target agent from failed intents data
    if (failedIntentsData && failedIntentsData.summary && failedIntentsData.summary.by_target_agent) {
      const byTargetAgent = failedIntentsData.summary.by_target_agent;
      Object.keys(byTargetAgent).forEach(agentId => {
        if (agentFailureCounts.hasOwnProperty(agentId)) {
          agentFailureCounts[agentId] = byTargetAgent[agentId];
        }
      });
    }
    
    // Enhance agent status with smoke test data if available
    if (smokeData && smokeData.results) {
      smokeData.results.forEach(result => {
        const agentId = result.agent_id;
        if (agentId && agentStatus.hasOwnProperty(agentId)) {
          // Use smoke test reachability to improve status accuracy
          if (result.reachable === true) {
            agentStatus[agentId] = "online";
          } else if (result.reachable === false) {
            agentStatus[agentId] = "offline";
          }
        }
      });
    }
    
    // Sort agents by count (descending)
    const sortedAgents = Object.keys(agentCounts)
      .sort((a, b) => agentCounts[b] - agentCounts[a])
      .slice(0, 8); // Show top 8 agents
    
    if (sortedAgents.length === 0) {
      dom.agentObservabilityCards.innerHTML =
        '<div class="empty-state">No agent activity recorded.</div>';
      return;
    }
    
    let html = "";
    
    // Special focus agents
    const focusAgents = ["quantumarb", "kashclaw", "kloutbot"];
    
    // Check for TimesFM availability in capabilities
    let timesfmAvailable = false;
    let timesfmAgents = [];
    // Check for A2A readiness in capabilities
    let a2aReady = false;
    let a2aAgents = [];
    
    if (capabilitiesData && capabilitiesData.capabilities) {
      // Check for forecasting-related capabilities
      const forecastingCaps = ["forecasting", "timeseries_forecast", "timesfm", "prediction"];
      for (const cap of forecastingCaps) {
        if (capabilitiesData.capabilities[cap]) {
          timesfmAvailable = true;
          timesfmAgents = capabilitiesData.capabilities[cap];
          break;
        }
      }
      
      // Check for A2A-related capabilities
      const a2aCaps = ["a2a", "financial_ops", "payment", "trade_execution", "simulation"];
      for (const cap of a2aCaps) {
        if (capabilitiesData.capabilities[cap]) {
          a2aReady = true;
          a2aAgents = capabilitiesData.capabilities[cap];
          break;
        }
      }
    }
    
    // Infrastructure readiness cards with tooltips
    html += '<div class="card" title="Timeseries forecasting engine availability">';
    html += '<div class="card-label">TimesFM</div>';
    if (timesfmAvailable) {
      html += '<div class="card-value">Available</div>';
      html += '<div class="card-status online">via ' + escHtml(timesfmAgents.join(", ")) + '</div>';
    } else {
      html += '<div class="card-value">Not detected</div>';
      html += '<div class="card-status unknown">no forecast agent</div>';
    }
    html += '</div>';
    
    html += '<div class="card" title="Agent-to-Agent financial operations layer">';
    html += '<div class="card-label">A2A Layer</div>';
    if (a2aReady) {
      html += '<div class="card-value">Ready</div>';
      html += '<div class="card-status online">via ' + escHtml(a2aAgents.join(", ")) + '</div>';
    } else {
      html += '<div class="card-value">Not detected</div>';
      html += '<div class="card-status unknown">no A2A agent</div>';
    }
    html += '</div>';
    
    // Group 1: Infrastructure readiness cards
    html += '<div class="agent-group">';
    html += '<div class="group-label">Infrastructure</div>';
    html += '<div class="group-cards">';
    
    // TimesFM card
    html += '<div class="card" title="Timeseries forecasting engine availability">';
    html += '<div class="card-label">TimesFM</div>';
    if (timesfmAvailable) {
      html += '<div class="card-value">Available</div>';
      html += '<div class="card-status online">via ' + escHtml(timesfmAgents.join(", ")) + '</div>';
    } else {
      html += '<div class="card-value">Not detected</div>';
      html += '<div class="card-status unknown">no forecast agent</div>';
    }
    html += '</div>';
    
    // A2A Layer card
    html += '<div class="card" title="Agent-to-Agent financial operations layer">';
    html += '<div class="card-label">A2A Layer</div>';
    if (a2aReady) {
      html += '<div class="card-value">Ready</div>';
      html += '<div class="card-status online">via ' + escHtml(a2aAgents.join(", ")) + '</div>';
    } else {
      html += '<div class="card-value">Not detected</div>';
      html += '<div class="card-status unknown">no A2A agent</div>';
    }
    html += '</div>';
    html += '</div></div>'; // Close group-cards and agent-group
    
    // Group 2: Focus agents
    const focusAgentsWithData = focusAgents.filter(agentId => agentCounts[agentId] !== undefined);
    if (focusAgentsWithData.length > 0) {
      html += '<div class="agent-group">';
      html += '<div class="group-label">Focus Agents</div>';
      html += '<div class="group-cards">';
      
      focusAgentsWithData.forEach(agentId => {
        const count = agentCounts[agentId];
        const failures = agentFailureCounts[agentId] || 0;
        const status = agentStatus[agentId] || "unknown";
        const statusClass = status === "online" ? "online" : 
                          status === "offline" ? "offline" : "unknown";
        
        html += '<div class="card" title="Recent activity for ' + escHtml(agentId) + ' agent">';
        html += '<div class="card-label">' + escHtml(agentId) + '</div>';
        html += '<div class="card-value">' + count + ' intents</div>';
        if (failures > 0) {
          html += '<div class="card-subvalue" style="color: var(--red);" title="Failed deliveries to this agent">' + failures + ' failed</div>';
        } else {
          html += '<div class="card-subvalue" style="color: var(--green);" title="No failed deliveries">0 failed</div>';
        }
        html += '<div class="card-status ' + statusClass + '" title="Agent connectivity status">' + escHtml(status) + '</div>';
        html += '</div>';
      });
      html += '</div></div>'; // Close group-cards and agent-group
    }
    
    // Group 3: Other active agents
    const otherAgents = sortedAgents.filter(agentId => 
      !focusAgents.includes(agentId) && 
      agentId !== "timesfm" && 
      agentCounts[agentId] !== undefined
    );
    
    if (otherAgents.length > 0) {
      html += '<div class="agent-group">';
      html += '<div class="group-label">Other Active Agents</div>';
      html += '<div class="group-cards">';
      
      otherAgents.forEach(agentId => {
        const count = agentCounts[agentId];
        const failures = agentFailureCounts[agentId] || 0;
        const status = agentStatus[agentId] || "unknown";
        const statusClass = status === "online" ? "online" : 
                          status === "offline" ? "offline" : "unknown";
        
        html += '<div class="card" title="Recent activity for ' + escHtml(agentId) + ' agent">';
        html += '<div class="card-label">' + escHtml(agentId) + '</div>';
        html += '<div class="card-value">' + count + ' intents</div>';
        if (failures > 0) {
          html += '<div class="card-subvalue" style="color: var(--red);" title="Failed deliveries to this agent">' + failures + ' failed</div>';
        }
        html += '<div class="card-status ' + statusClass + '" title="Agent connectivity status">' + escHtml(status) + '</div>';
        html += '</div>';
      });
      html += '</div></div>'; // Close group-cards and agent-group
    }
    
    dom.agentObservabilityCards.innerHTML = html;
  }

  function renderSystemOverview(docs) {
    if (!dom.systemOverviewSummary || !dom.systemOverviewCards || !dom.systemOverviewActions) return;
    if (!docs || !docs.system_identity) {
      dom.systemOverviewSummary.innerHTML = '<div class="empty-state">Protocol docs not loaded.</div>';
      dom.systemOverviewCards.innerHTML = '<div class="empty-state">Component summaries unavailable.</div>';
      dom.systemOverviewActions.innerHTML = '<div class="empty-state">No operator recommendations loaded.</div>';
      return;
    }

    var systemIdentity = docs.system_identity || {};
    var nonGoals = Array.isArray(systemIdentity.non_goals) ? systemIdentity.non_goals : [];
    dom.systemOverviewSummary.innerHTML =
      '<div class="system-overview-summary-card">'
      + '<div class="system-overview-header">'
      + '<div class="system-overview-title">' + escHtml(systemIdentity.full_name || systemIdentity.name || "SIMP") + '</div>'
      + '<div class="system-overview-version mono">Docs v' + escHtml(docs.version || "--") + '</div>'
      + '</div>'
      + '<div class="system-overview-line">' + escHtml(systemIdentity.one_line_summary || "--") + '</div>'
      + '<div class="system-overview-operator">' + escHtml(systemIdentity.operator_summary || "--") + '</div>'
      + '<div class="system-overview-non-goals">'
      + nonGoals.slice(0, 3).map(function(goal) {
        return '<div>' + escHtml(goal) + '</div>';
      }).join("")
      + '</div>'
      + '</div>';

    var preferredOrder = ["projectx", "kashclaw", "dashboard", "broker", "a2a", "financial_ops"];
    var components = docs.component_summaries || {};
    var componentKeys = preferredOrder.filter(function(key) { return components[key]; });
    dom.systemOverviewCards.innerHTML = componentKeys.map(function(key) {
      var item = components[key] || {};
      return '<div class="system-overview-card">'
        + '<div class="system-overview-card-title">' + escHtml(item.name || key) + '</div>'
        + '<div class="system-overview-card-copy">' + escHtml(item.one_line_summary || "--") + '</div>'
        + '<div class="system-overview-card-copy">' + escHtml(item.operator_summary || "--") + '</div>'
        + '</div>';
    }).join("") || '<div class="empty-state">Component summaries unavailable.</div>';

    var actions = ((docs.operator_actions || {}).recommended_first_steps) || [];
    dom.systemOverviewActions.innerHTML = actions.map(function(action) {
      return '<div class="operator-action-card">'
        + '<div class="operator-action-label">' + escHtml(action.label || "--") + '</div>'
        + '<div class="operator-action-intent mono">' + escHtml(action.intent_type || "--") + '</div>'
        + '<div class="operator-action-description">' + escHtml(action.description || "--") + '</div>'
        + '</div>';
    }).join("") || '<div class="empty-state">No operator recommendations loaded.</div>';
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
    
    // Build query string from payload
    const params = new URLSearchParams();
    if (payload.message) params.set("message", payload.message);
    if (payload.job) params.set("job", payload.job);
    if (payload.request_id) params.set("request_id", payload.request_id);
    if (payload.source_intent_id) params.set("source_intent_id", payload.source_intent_id);
    if (payload.plan_id) params.set("plan_id", payload.plan_id);
    
    const queryString = params.toString();
    const url = "/api/projectx/chat" + (queryString ? "?" + queryString : "");
    
    const response = await apiFetch(url);
    if (!response || !response.response) {
      appendChatMessage("assistant", "ProjectX guard unreachable.", "dashboard proxy error");
      return;
    }
    var body = response.response.response || response.response;
    var answer = body.answer || body.summary || JSON.stringify(body, null, 2);
    var meta = body.answer_source_path || body.intent_type || response.mode;
    if (body.matched_faq_id) {
      meta = body.matched_faq_id + " • " + meta;
    }
    if (response.broker_intent_id) {
      meta = (meta ? meta + " • " : "") + "broker:" + response.broker_intent_id.substring(0, 8);
    }
    if (response.delivery_status) {
      meta = (meta ? meta + " • " : "") + response.delivery_status;
    }
    appendChatMessage("assistant", typeof answer === "string" ? answer : JSON.stringify(answer), meta);
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
    var brpQuery = buildBrpEvaluationQuery();
    const [health, stats, agents, activity, failedIntents, capabilities, tasks, routing, smokeData, flowData, memTasks, memConvos, logsData, topologyData, taskQueueData, orchestrationData, computerUseData, projectxSystem, projectxProcesses, projectxActions, projectxProtocolFacts, brpStatus, brpIncidents, brpAlerts, brpPlaybooks, brpRemediations, brpEvaluations, brpRules, brpInsights] = await Promise.all([
      apiFetch("/api/health"),
      apiFetch("/api/stats"),
      apiFetch("/api/agents"),
      apiFetch("/api/activity"),
      apiFetch("/api/intents/failed"),
      apiFetch("/api/capabilities"),
      apiFetch("/api/tasks"),
      apiFetch("/api/routing"),
      apiFetch("/api/agents/smoke"),
      apiFetch("/api/flows"),
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
      apiFetch("/api/brp/status"),
      apiFetch("/api/brp/incidents?limit=12"),
      apiFetch("/api/brp/alerts?limit=8"),
      apiFetch("/api/brp/playbooks?limit=8"),
      apiFetch("/api/brp/remediations?limit=8"),
      apiFetch("/api/brp/evaluations?" + brpQuery),
      apiFetch("/api/brp/adaptive-rules?limit=12"),
      apiFetch("/api/brp/insights?limit=12"),
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
    renderSmoke(smokeData);
    renderFlows(flowData);
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
    renderBrpStatus(brpStatus);
    renderBrpIncidents(brpIncidents);
    renderBrpAlerts(brpAlerts);
    renderBrpPlaybooks(brpPlaybooks);
    renderBrpRemediations(brpRemediations);
    renderBrpEvaluations(brpEvaluations);
    renderBrpAdaptiveRules(brpRules);
    renderBrpInsights(brpInsights);
    
    // Agent observability - show intent counts by agent
    renderAgentObservability(activity, agents, capabilities, failedIntents, smokeData);

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
  var MAX_RETRY_DELAY = 30000; // 30 seconds max
  var wsPingInterval = null;
  var wsConnectionStartTime = null;
  var wsMessageCount = 0;
  var wsLastPongTime = null;

  function connectWebSocket() {
    var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + location.host + '/ws';

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = function() {
        wsRetryCount = 0;
        wsConnectionStartTime = Date.now();
        wsMessageCount = 0;
        updateConnectionStatus('connected', 'WebSocket connection established');
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
          // Validate message structure
          if (msg && typeof msg === 'object' && msg.type) {
            wsMessageCount++;
            
            // Handle pong response for latency measurement
            if (msg.type === 'pong') {
              wsLastPongTime = Date.now();
              updateConnectionQuality();
            } else {
              handleWsMessage(msg);
            }
          } else {
            console.warn('Invalid WebSocket message format:', msg);
          }
        } catch (e) {
          console.warn('Failed to parse WebSocket message:', e, 'Data:', event.data);
        }
      };

      ws.onclose = function(event) {
        updateConnectionStatus('disconnected');
        if (wsPingInterval) clearInterval(wsPingInterval);
        
        if (wsRetryCount < MAX_WS_RETRIES) {
          wsRetryCount++;
          // Exponential backoff with jitter
          var delay = Math.min(WS_RETRY_DELAY * Math.pow(1.5, wsRetryCount - 1), MAX_RETRY_DELAY);
          // Add jitter (±20%) to prevent thundering herd
          delay = delay * (0.8 + Math.random() * 0.4);
          console.log('WebSocket closed. Reconnecting in ' + Math.round(delay) + 'ms (attempt ' + wsRetryCount + ')');
          setTimeout(connectWebSocket, Math.round(delay));
        } else {
          console.log('WebSocket max retries reached. Switching to polling fallback.');
          startPollingFallback();
        }
      };

      ws.onerror = function(error) {
        updateConnectionStatus('error', 'WebSocket error occurred');
        console.error('WebSocket error:', error);
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
      case 'brp':
        if (msg.data) {
          renderBrpStatus(msg.data.status);
          renderBrpIncidents(msg.data.incidents);
          renderBrpAlerts(msg.data.alerts);
          renderBrpPlaybooks(msg.data.playbooks);
          renderBrpRemediations(msg.data.remediations);
          renderBrpEvaluations(msg.data.evaluations);
          renderBrpAdaptiveRules(msg.data.adaptive_rules);
          renderBrpInsights(msg.data.insights);
        }
        break;
      case 'heartbeat':
      case 'pong':
        break;
      default:
        refreshAll();
    }
  }

  function updateConnectionStatus(status, details) {
    var el = document.getElementById('ws-status');
    if (!el) return;
    el.className = 'ws-status ' + status;
    
    var statusText = '';
    switch(status) {
      case 'connected':
        statusText = 'Live WebSocket';
        break;
      case 'disconnected':
        statusText = 'Reconnecting' + (wsRetryCount > 0 ? ' (' + wsRetryCount + ')' : '') + '...';
        break;
      case 'error':
        statusText = 'Polling Fallback';
        break;
      default:
        statusText = status;
    }
    
    el.textContent = statusText;
    
    // Add connection quality info to tooltip
    var tooltip = details || statusText;
    if (status === 'connected' && wsConnectionStartTime) {
      var uptime = Math.floor((Date.now() - wsConnectionStartTime) / 1000);
      tooltip += '\\nUptime: ' + formatDuration(uptime);
      tooltip += '\\nMessages: ' + wsMessageCount;
      if (wsLastPongTime) {
        var latency = Date.now() - wsLastPongTime;
        tooltip += '\\nLatency: ' + latency + 'ms';
      }
    }
    
    el.title = tooltip;
  }
  
  function updateConnectionQuality() {
    // Update connection status with current quality info
    if (ws && ws.readyState === WebSocket.OPEN) {
      updateConnectionStatus('connected', 'WebSocket connection active');
    }
  }
  
  function formatDuration(seconds) {
    if (seconds < 60) return seconds + 's';
    var minutes = Math.floor(seconds / 60);
    var remainingSeconds = seconds % 60;
    if (minutes < 60) return minutes + 'm ' + remainingSeconds + 's';
    var hours = Math.floor(minutes / 60);
    var remainingMinutes = minutes % 60;
    return hours + 'h ' + remainingMinutes + 'm';
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
  if (dom.brpDrawerClose) {
    dom.brpDrawerClose.addEventListener("click", closeBrpDrawer);
  }
  if (dom.brpDrawerBackdrop) {
    dom.brpDrawerBackdrop.addEventListener("click", closeBrpDrawer);
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

  [dom.brpDecisionFilter, dom.brpSeverityFilter].forEach(function(el) {
    if (!el) return;
    el.addEventListener("change", function() {
      refreshAll();
    });
  });
  if (dom.brpSourceFilter) {
    dom.brpSourceFilter.addEventListener("input", function() {
      if (brpFilterTimer) clearTimeout(brpFilterTimer);
      brpFilterTimer = setTimeout(refreshAll, 250);
    });
  }
  if (dom.brpExportBtn) {
    dom.brpExportBtn.addEventListener("click", function() {
      window.open("/api/brp/report?limit=25", "_blank");
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

// Agent Lightning Integration
const agentLightningScript = document.createElement('script');
agentLightningScript.src = '/static/agent_lightning_integration.js';
document.head.appendChild(agentLightningScript);
