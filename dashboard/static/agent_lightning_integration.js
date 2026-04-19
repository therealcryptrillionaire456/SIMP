
// Agent Lightning Dashboard Integration
document.addEventListener('DOMContentLoaded', function() {
    // Wait for dashboard to load
    setTimeout(function() {
        addAgentLightningWidget();
        startAgentLightningUpdates();
    }, 2000);
});

function addAgentLightningWidget() {
    // Check if widget already exists
    if (document.getElementById('agent-lightning-widget')) {
        return;
    }
    
    // Create widget container
    const widget = document.createElement('div');
    widget.id = 'agent-lightning-widget';
    widget.className = 'card mb-3';
    widget.innerHTML = \`
        <div class="card-header">
            <h5 class="mb-0">
                <i class="bi bi-lightning-charge"></i> Agent Lightning
                <span class="badge bg-success float-end" id="lightning-status">Loading...</span>
            </h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <h6>System Performance</h6>
                    <div class="mb-2">
                        <small>Total Calls:</small>
                        <div class="fw-bold" id="total-calls">0</div>
                    </div>
                    <div class="mb-2">
                        <small>Success Rate:</small>
                        <div class="fw-bold" id="success-rate">0%</div>
                    </div>
                </div>
                <div class="col-md-6">
                    <h6>Resource Usage</h6>
                    <div class="mb-2">
                        <small>Avg Response Time:</small>
                        <div class="fw-bold" id="avg-response-time">0ms</div>
                    </div>
                    <div class="mb-2">
                        <small>Total Tokens:</small>
                        <div class="fw-bold" id="total-tokens">0</div>
                    </div>
                </div>
            </div>
            <div class="mt-3">
                <a href="/agent-lightning-ui" class="btn btn-sm btn-outline-primary">
                    <i class="bi bi-graph-up"></i> Detailed Dashboard
                </a>
                <button class="btn btn-sm btn-outline-secondary" onclick="refreshAgentLightning()">
                    <i class="bi bi-arrow-clockwise"></i> Refresh
                </button>
            </div>
        </div>
    \`;
    
    // Add to dashboard
    const dashboardContent = document.querySelector('.container-fluid, #dashboard-content, .dashboard-container');
    if (dashboardContent) {
        dashboardContent.prepend(widget);
    } else {
        document.body.prepend(widget);
    }
}

function refreshAgentLightning() {
    loadAgentLightningData();
}

function loadAgentLightningData() {
    fetch('/agent-lightning/health')
        .then(response => response.json())
        .then(healthData => {
            updateHealthStatus(healthData);
        })
        .catch(error => {
            console.error('Failed to load Agent Lightning health:', error);
            document.getElementById('lightning-status').className = 'badge bg-danger';
            document.getElementById('lightning-status').textContent = 'Error';
        });
    
    fetch('/agent-lightning/performance?hours=1')
        .then(response => response.json())
        .then(performanceData => {
            updatePerformanceMetrics(performanceData);
        })
        .catch(error => {
            console.error('Failed to load Agent Lightning performance:', error);
        });
}

function updateHealthStatus(healthData) {
    const statusElement = document.getElementById('lightning-status');
    
    if (!healthData.enabled) {
        statusElement.className = 'badge bg-secondary';
        statusElement.textContent = 'Disabled';
        return;
    }
    
    if (healthData.proxy_healthy && healthData.store_healthy) {
        statusElement.className = 'badge bg-success';
        statusElement.textContent = 'Healthy';
    } else {
        statusElement.className = 'badge bg-warning';
        statusElement.textContent = 'Unhealthy';
    }
}

function updatePerformanceMetrics(performanceData) {
    if (performanceData.error) {
        return;
    }
    
    document.getElementById('total-calls').textContent = 
        (performanceData.total_traces || 0).toLocaleString();
    
    document.getElementById('success-rate').textContent = 
        (performanceData.success_rate || 0).toFixed(1) + '%';
    
    document.getElementById('avg-response-time').textContent = 
        (performanceData.avg_response_time_ms || 0).toFixed(0) + 'ms';
    
    document.getElementById('total-tokens').textContent = 
        (performanceData.total_tokens || 0).toLocaleString();
}

function startAgentLightningUpdates() {
    // Load initial data
    loadAgentLightningData();
    
    // Update every 30 seconds
    setInterval(loadAgentLightningData, 30000);
}
