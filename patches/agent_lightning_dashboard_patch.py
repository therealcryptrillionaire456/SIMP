"""
Agent Lightning Dashboard Patch

This patch integrates Agent Lightning with the SIMP dashboard,
adding real-time metrics, performance monitoring, and trace visualization.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def patch_dashboard_for_agent_lightning(dashboard_app):
    """Patch the SIMP dashboard to integrate Agent Lightning"""
    
    try:
        from simp.integrations.agent_lightning import (
            agent_lightning_manager,
            integrate_with_dashboard
        )
        
        logger.info("Patching SIMP dashboard for Agent Lightning integration")
        
        if not agent_lightning_manager.config.enabled:
            logger.info("Agent Lightning integration disabled in configuration")
            return dashboard_app
        
        # Integrate Agent Lightning with dashboard
        integrate_with_dashboard(dashboard_app)
        
        # Add additional dashboard endpoints
        from fastapi import APIRouter, HTTPException
        from fastapi.responses import HTMLResponse
        
        router = APIRouter(prefix="/agent-lightning-ui", tags=["agent-lightning-ui"])
        
        @router.get("/", response_class=HTMLResponse)
        async def agent_lightning_ui():
            """Agent Lightning dashboard UI"""
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Agent Lightning Dashboard - SIMP Ecosystem</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                        margin: 0;
                        padding: 20px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                    }
                    .container {
                        max-width: 1400px;
                        margin: 0 auto;
                    }
                    .header {
                        text-align: center;
                        margin-bottom: 40px;
                        color: white;
                    }
                    .header h1 {
                        font-size: 2.5rem;
                        margin-bottom: 10px;
                    }
                    .header .subtitle {
                        font-size: 1.2rem;
                        opacity: 0.9;
                    }
                    .dashboard-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }
                    .card {
                        background: rgba(255, 255, 255, 0.95);
                        border-radius: 15px;
                        padding: 20px;
                        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                        backdrop-filter: blur(10px);
                    }
                    .card h2 {
                        margin-top: 0;
                        color: #333;
                        border-bottom: 2px solid #667eea;
                        padding-bottom: 10px;
                    }
                    .health-status {
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        margin-bottom: 15px;
                    }
                    .status-indicator {
                        width: 12px;
                        height: 12px;
                        border-radius: 50%;
                    }
                    .status-healthy {
                        background: #4ade80;
                        box-shadow: 0 0 10px #4ade80;
                    }
                    .status-unhealthy {
                        background: #f87171;
                        box-shadow: 0 0 10px #f87171;
                    }
                    .status-unknown {
                        background: #fbbf24;
                        box-shadow: 0 0 10px #fbbf24;
                    }
                    .metric {
                        margin: 10px 0;
                        padding: 10px;
                        background: rgba(102, 126, 234, 0.1);
                        border-radius: 8px;
                    }
                    .metric-label {
                        font-weight: bold;
                        color: #667eea;
                    }
                    .metric-value {
                        font-size: 1.5rem;
                        color: #333;
                    }
                    .chart-container {
                        height: 300px;
                        margin-top: 20px;
                    }
                    .trace-list {
                        max-height: 400px;
                        overflow-y: auto;
                        margin-top: 20px;
                    }
                    .trace-item {
                        padding: 10px;
                        margin: 5px 0;
                        background: rgba(102, 126, 234, 0.05);
                        border-radius: 8px;
                        border-left: 4px solid #4ade80;
                    }
                    .trace-item.error {
                        border-left-color: #f87171;
                    }
                    .agent-selector {
                        display: flex;
                        gap: 10px;
                        margin-bottom: 20px;
                    }
                    .agent-selector select {
                        flex: 1;
                        padding: 10px;
                        border-radius: 8px;
                        border: 2px solid #667eea;
                        background: white;
                        font-size: 1rem;
                    }
                    .refresh-btn {
                        padding: 10px 20px;
                        background: #667eea;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 1rem;
                        transition: background 0.3s;
                    }
                    .refresh-btn:hover {
                        background: #5a67d8;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>⚡ Agent Lightning Dashboard</h1>
                        <div class="subtitle">Real-time LLM call tracing and optimization across SIMP ecosystem</div>
                    </div>
                    
                    <div class="agent-selector">
                        <select id="agentSelect">
                            <option value="all">All Agents</option>
                            <option value="quantumarb">QuantumArb</option>
                            <option value="kashclaw_gemma">KashClaw Gemma</option>
                            <option value="kloutbot">KloutBot</option>
                            <option value="projectx_native">ProjectX</option>
                            <option value="perplexity_research">Perplexity Research</option>
                        </select>
                        <select id="timeRange">
                            <option value="1">Last hour</option>
                            <option value="24" selected>Last 24 hours</option>
                            <option value="168">Last week</option>
                            <option value="720">Last month</option>
                        </select>
                        <button class="refresh-btn" onclick="loadData()">Refresh</button>
                    </div>
                    
                    <div class="dashboard-grid">
                        <div class="card">
                            <h2>System Health</h2>
                            <div class="health-status">
                                <div class="status-indicator" id="healthIndicator"></div>
                                <span id="healthText">Loading...</span>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Agent Lightning Proxy</div>
                                <div class="metric-value" id="proxyStatus">Checking...</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">LightningStore</div>
                                <div class="metric-value" id="storeStatus">Checking...</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Total Agents Tracked</div>
                                <div class="metric-value" id="totalAgents">0</div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h2>Performance Overview</h2>
                            <div class="metric">
                                <div class="metric-label">Total LLM Calls</div>
                                <div class="metric-value" id="totalCalls">0</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Success Rate</div>
                                <div class="metric-value" id="successRate">0%</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Avg Response Time</div>
                                <div class="metric-value" id="avgResponseTime">0ms</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Total Tokens</div>
                                <div class="metric-value" id="totalTokens">0</div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h2>Cost Analysis</h2>
                            <div class="metric">
                                <div class="metric-label">Estimated Cost</div>
                                <div class="metric-value" id="estimatedCost">$0.00</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Cost per 1K Tokens</div>
                                <div class="metric-value" id="costPer1K">$0.00</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Daily Cost Trend</div>
                                <div class="metric-value" id="dailyTrend">→ Stable</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Optimization Savings</div>
                                <div class="metric-value" id="optimizationSavings">$0.00</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Performance Trends</h2>
                        <div class="chart-container">
                            <canvas id="performanceChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Recent Traces</h2>
                        <div class="trace-list" id="traceList">
                            <div class="trace-item">Loading traces...</div>
                        </div>
                    </div>
                </div>
                
                <script>
                    let performanceChart = null;
                    
                    async function loadData() {
                        const agentId = document.getElementById('agentSelect').value;
                        const hours = document.getElementById('timeRange').value;
                        
                        // Load health data
                        try {
                            const healthResponse = await fetch('/agent-lightning/health');
                            const healthData = await healthResponse.json();
                            updateHealthUI(healthData);
                        } catch (error) {
                            console.error('Failed to load health data:', error);
                        }
                        
                        // Load performance data
                        try {
                            let url = '/agent-lightning/performance';
                            if (agentId !== 'all') {
                                url = `/agent-lightning/agents/${agentId}/performance`;
                            }
                            url += `?hours=${hours}`;
                            
                            const perfResponse = await fetch(url);
                            const perfData = await perfResponse.json();
                            updatePerformanceUI(perfData);
                            
                            // Update chart if data is available
                            if (perfData.trends) {
                                updateChart(perfData.trends);
                            }
                        } catch (error) {
                            console.error('Failed to load performance data:', error);
                        }
                        
                        // Load recent traces
                        try {
                            const tracesResponse = await fetch(`/agent-lightning/agents/${agentId}/traces?limit=10`);
                            const tracesData = await tracesResponse.json();
                            updateTracesUI(tracesData);
                        } catch (error) {
                            console.error('Failed to load traces:', error);
                        }
                    }
                    
                    function updateHealthUI(healthData) {
                        const indicator = document.getElementById('healthIndicator');
                        const healthText = document.getElementById('healthText');
                        const proxyStatus = document.getElementById('proxyStatus');
                        const storeStatus = document.getElementById('storeStatus');
                        const totalAgents = document.getElementById('totalAgents');
                        
                        if (!healthData.enabled) {
                            indicator.className = 'status-indicator status-unknown';
                            healthText.textContent = 'Disabled';
                            proxyStatus.textContent = 'N/A';
                            storeStatus.textContent = 'N/A';
                            totalAgents.textContent = '0';
                            return;
                        }
                        
                        if (healthData.proxy_healthy && healthData.store_healthy) {
                            indicator.className = 'status-indicator status-healthy';
                            healthText.textContent = 'Healthy';
                        } else {
                            indicator.className = 'status-indicator status-unhealthy';
                            healthText.textContent = 'Unhealthy';
                        }
                        
                        proxyStatus.textContent = healthData.proxy_healthy ? '✅ Running' : '❌ Stopped';
                        storeStatus.textContent = healthData.store_healthy ? '✅ Running' : '❌ Stopped';
                        totalAgents.textContent = healthData.config?.trace_specific_agents?.length || 'All';
                    }
                    
                    function updatePerformanceUI(perfData) {
                        if (perfData.error) {
                            document.getElementById('totalCalls').textContent = 'Error';
                            document.getElementById('successRate').textContent = 'Error';
                            document.getElementById('avgResponseTime').textContent = 'Error';
                            document.getElementById('totalTokens').textContent = 'Error';
                            return;
                        }
                        
                        document.getElementById('totalCalls').textContent = perfData.total_traces?.toLocaleString() || '0';
                        document.getElementById('successRate').textContent = 
                            (perfData.success_rate || 0).toFixed(1) + '%';
                        document.getElementById('avgResponseTime').textContent = 
                            (perfData.avg_response_time_ms || 0).toFixed(0) + 'ms';
                        document.getElementById('totalTokens').textContent = 
                            (perfData.total_tokens || 0).toLocaleString();
                        
                        // Calculate estimated cost (assuming $0.10 per 1K tokens)
                        const costPer1K = 0.10;
                        const totalCost = ((perfData.total_tokens || 0) / 1000) * costPer1K;
                        document.getElementById('estimatedCost').textContent = '$' + totalCost.toFixed(2);
                        document.getElementById('costPer1K').textContent = '$' + costPer1K.toFixed(2);
                        
                        // Simple trend analysis
                        if (perfData.daily_trend) {
                            const trend = perfData.daily_trend > 0 ? '↗ Increasing' : 
                                         perfData.daily_trend < 0 ? '↘ Decreasing' : '→ Stable';
                            document.getElementById('dailyTrend').textContent = trend;
                        }
                        
                        // Estimate optimization savings (assuming 15% savings from APO)
                        const optimizationRate = 0.15;
                        const savings = totalCost * optimizationRate;
                        document.getElementById('optimizationSavings').textContent = '$' + savings.toFixed(2);
                    }
                    
                    function updateChart(trendsData) {
                        const ctx = document.getElementById('performanceChart').getContext('2d');
                        
                        if (performanceChart) {
                            performanceChart.destroy();
                        }
                        
                        const labels = trendsData.labels || [];
                        const successRates = trendsData.success_rates || [];
                        const responseTimes = trendsData.response_times || [];
                        
                        performanceChart = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: labels,
                                datasets: [
                                    {
                                        label: 'Success Rate (%)',
                                        data: successRates,
                                        borderColor: '#4ade80',
                                        backgroundColor: 'rgba(74, 222, 128, 0.1)',
                                        yAxisID: 'y',
                                        tension: 0.4
                                    },
                                    {
                                        label: 'Response Time (ms)',
                                        data: responseTimes,
                                        borderColor: '#667eea',
                                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                        yAxisID: 'y1',
                                        tension: 0.4
                                    }
                                ]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                interaction: {
                                    mode: 'index',
                                    intersect: false,
                                },
                                scales: {
                                    x: {
                                        grid: {
                                            color: 'rgba(255, 255, 255, 0.1)'
                                        },
                                        ticks: {
                                            color: '#666'
                                        }
                                    },
                                    y: {
                                        type: 'linear',
                                        display: true,
                                        position: 'left',
                                        grid: {
                                            color: 'rgba(255, 255, 255, 0.1)'
                                        },
                                        ticks: {
                                            color: '#666'
                                        },
                                        title: {
                                            display: true,
                                            text: 'Success Rate (%)',
                                            color: '#666'
                                        }
                                    },
                                    y1: {
                                        type: 'linear',
                                        display: true,
                                        position: 'right',
                                        grid: {
                                            drawOnChartArea: false,
                                        },
                                        ticks: {
                                            color: '#666'
                                        },
                                        title: {
                                            display: true,
                                            text: 'Response Time (ms)',
                                            color: '#666'
                                        }
                                    }
                                },
                                plugins: {
                                    legend: {
                                        labels: {
                                            color: '#666'
                                        }
                                    },
                                    tooltip: {
                                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                                        titleColor: '#fff',
                                        bodyColor: '#fff'
                                    }
                                }
                            }
                        });
                    }
                    
                    function updateTracesUI(tracesData) {
                        const traceList = document.getElementById('traceList');
                        
                        if (!tracesData || !tracesData.traces || tracesData.traces.length === 0) {
                            traceList.innerHTML = '<div class="trace-item">No traces found for selected time period</div>';
                            return;
                        }
                        
                        let html = '';
                        tracesData.traces.forEach(trace => {
                            const time = new Date(trace.timestamp).toLocaleTimeString();
                            const successClass = trace.success ? '' : 'error';
                            const statusIcon = trace.success ? '✅' : '❌';
                            const tokens = trace.total_tokens?.toLocaleString() || '0';
                            
                            html += \`
                                <div class="trace-item \${successClass}">
                                    <div style="display: flex; justify-content: space-between;">
                                        <strong>\${trace.agent_id}</strong>
                                        <span>\${time}</span>
                                    </div>
                                    <div style="margin: 5px 0;">
                                        <span>\${statusIcon} \${trace.intent_type}</span>
                                        <span style="float: right;">\${trace.response_time_ms}ms</span>
                                    </div>
                                    <div style="font-size: 0.9em; color: #666;">
                                        Tokens: \${tokens} | Model: \${trace.model}
                                        \${trace.error_message ? '<br>Error: ' + trace.error_message : ''}
                                    </div>
                                </div>
                            \`;
                        });
                        
                        traceList.innerHTML = html;
                    }
                    
                    // Load data on page load
                    document.addEventListener('DOMContentLoaded', loadData);
                    
                    // Auto-refresh every 30 seconds
                    setInterval(loadData, 30000);
                </script>
            </body>
            </html>
            """
        
        # Add router to dashboard app
        dashboard_app.include_router(router)
        
        logger.info("✅ SIMP dashboard patched for Agent Lightning integration")
        
        return dashboard_app
        
    except ImportError as e:
        logger.warning(f"Agent Lightning integration not available: {e}")
        return dashboard_app
    except Exception as e:
        logger.error(f"Failed to patch dashboard for Agent Lightning: {e}")
        return dashboard_app


def add_agent_lightning_to_main_dashboard():
    """Add Agent Lightning widget to main SIMP dashboard"""
    
    try:
        # This would modify the main dashboard HTML/JS
        # For now, we'll create a separate endpoint
        
        logger.info("Agent Lightning dashboard UI available at: /agent-lightning-ui")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to add Agent Lightning to main dashboard: {e}")
        return False