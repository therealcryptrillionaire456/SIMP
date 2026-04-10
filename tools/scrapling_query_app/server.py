"""
FastAPI server for the Scrapling Query Tool.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .models import QueryRequest, QueryResponse, FetcherType
from .query_processor import query_processor
from .enhanced_processor import EnhancedQueryProcessor
from .config import config


# Create FastAPI app
app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="A local web app for query-driven web content extraction using Scrapling"
)

# Initialize processors
enhanced_processor = EnhancedQueryProcessor(search_provider_name='duckduckgo')

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Scrapling Query Tool</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            
            header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 2rem;
                text-align: center;
            }
            
            h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
            }
            
            .subtitle {
                opacity: 0.9;
                font-size: 1.1rem;
            }
            
            main {
                padding: 2rem;
            }
            
            .query-section {
                background: #f8fafc;
                border-radius: 8px;
                padding: 1.5rem;
                margin-bottom: 2rem;
                border: 1px solid #e2e8f0;
            }
            
            .form-group {
                margin-bottom: 1rem;
            }
            
            label {
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 600;
                color: #334155;
            }
            
            input, select, button {
                width: 100%;
                padding: 0.75rem;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 1rem;
            }
            
            input:focus, select:focus {
                outline: none;
                border-color: #4f46e5;
                box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
            }
            
            button {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                border: none;
                cursor: pointer;
                font-weight: 600;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(79, 70, 229, 0.2);
            }
            
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .results-section {
                display: none;
            }
            
            .results-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.5rem;
                padding-bottom: 1rem;
                border-bottom: 2px solid #e2e8f0;
            }
            
            .status-badge {
                padding: 0.5rem 1rem;
                border-radius: 20px;
                font-weight: 600;
                font-size: 0.875rem;
            }
            
            .status-queued { background: #fef3c7; color: #92400e; }
            .status-searching { background: #dbeafe; color: #1e40af; }
            .status-extracting { background: #f0f9ff; color: #0c4a6e; }
            .status-completed { background: #d1fae5; color: #065f46; }
            .status-failed { background: #fee2e2; color: #991b1b; }
            
            .results-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 1.5rem;
            }
            
            .result-card {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                overflow: hidden;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .result-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            }
            
            .card-header {
                padding: 1rem;
                background: #f8fafc;
                border-bottom: 1px solid #e2e8f0;
            }
            
            .card-title {
                font-size: 1.1rem;
                font-weight: 600;
                color: #1e293b;
                margin-bottom: 0.5rem;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
            
            .card-url {
                font-size: 0.875rem;
                color: #64748b;
                word-break: break-all;
            }
            
            .card-content {
                padding: 1rem;
            }
            
            .card-snippet {
                color: #475569;
                line-height: 1.6;
                display: -webkit-box;
                -webkit-line-clamp: 4;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
            
            .card-meta {
                display: flex;
                justify-content: space-between;
                margin-top: 1rem;
                padding-top: 1rem;
                border-top: 1px solid #f1f5f9;
                font-size: 0.875rem;
                color: #64748b;
            }
            
            .loading {
                text-align: center;
                padding: 3rem;
                color: #64748b;
            }
            
            .spinner {
                display: inline-block;
                width: 40px;
                height: 40px;
                border: 3px solid #e2e8f0;
                border-top-color: #4f46e5;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-bottom: 1rem;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .error {
                background: #fee2e2;
                color: #991b1b;
                padding: 1rem;
                border-radius: 6px;
                margin: 1rem 0;
            }
            
            .empty-state {
                text-align: center;
                padding: 3rem;
                color: #64748b;
            }
            
            @media (max-width: 768px) {
                .container {
                    margin: 10px;
                }
                
                .results-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Scrapling Query Tool</h1>
                <p class="subtitle">Enter a topic to search and extract content from public web pages</p>
            </header>
            
            <main>
                <section class="query-section">
                    <div class="form-group">
                        <label for="query">What would you like to search for?</label>
                        <input type="text" id="query" placeholder="Enter a topic, question, or subject..." autofocus>
                    </div>
                    
                    <div class="form-group">
                        <label for="maxResults">Number of results</label>
                        <select id="maxResults">
                            <option value="5">5 results</option>
                            <option value="10" selected>10 results</option>
                            <option value="15">15 results</option>
                            <option value="20">20 results</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="fetcherType">Extraction method</label>
                        <select id="fetcherType">
                            <option value="dynamic">Dynamic (JavaScript sites)</option>
                            <option value="static">Static (Simple sites)</option>
                            <option value="stealthy">Stealthy (Anti-bot sites)</option>
                        </select>
                    </div>
                    
                    <button id="submitBtn" onclick="submitQuery()">Search & Extract</button>
                </section>
                
                <section class="results-section" id="resultsSection">
                    <div class="results-header">
                        <h2 id="resultsTitle">Results</h2>
                        <div class="status-badge" id="statusBadge">Queued</div>
                    </div>
                    
                    <div class="loading" id="loading">
                        <div class="spinner"></div>
                        <p id="loadingText">Searching for relevant pages...</p>
                    </div>
                    
                    <div class="error" id="error" style="display: none;"></div>
                    
                    <div class="empty-state" id="emptyState" style="display: none;">
                        <p>No results yet. Submit a query to get started.</p>
                    </div>
                    
                    <div class="results-grid" id="resultsGrid"></div>
                </section>
            </main>
        </div>
        
        <script>
            let currentRequestId = null;
            let pollInterval = null;
            
            function submitQuery() {
                const query = document.getElementById('query').value.trim();
                const maxResults = parseInt(document.getElementById('maxResults').value);
                const fetcherType = document.getElementById('fetcherType').value;
                
                if (!query) {
                    alert('Please enter a search query');
                    return;
                }
                
                // Disable submit button
                const submitBtn = document.getElementById('submitBtn');
                submitBtn.disabled = true;
                submitBtn.textContent = 'Processing...';
                
                // Show results section
                document.getElementById('resultsSection').style.display = 'block';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('error').style.display = 'none';
                document.getElementById('emptyState').style.display = 'none';
                document.getElementById('resultsGrid').innerHTML = '';
                
                // Update title
                document.getElementById('resultsTitle').textContent = `Results for: "${query}"`;
                
                // Submit query
                fetch('/api/query/async', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: query,
                        max_results: maxResults,
                        fetcher_type: fetcherType,
                        use_cache: true
                    })
                })
                .then(response => response.json())
                .then(data => {
                    currentRequestId = data.request_id;
                    
                    // Start polling for status
                    pollInterval = setInterval(pollStatus, 1000);
                })
                .catch(error => {
                    showError('Failed to submit query: ' + error.message);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Search & Extract';
                });
            }
            
            function pollStatus() {
                if (!currentRequestId) return;
                
                fetch(`/api/query/${currentRequestId}`)
                    .then(response => response.json())
                    .then(data => {
                        updateStatus(data);
                        
                        if (data.status === 'completed' || data.status === 'failed') {
                            // Stop polling
                            clearInterval(pollInterval);
                            pollInterval = null;
                            
                            // Re-enable submit button
                            document.getElementById('submitBtn').disabled = false;
                            document.getElementById('submitBtn').textContent = 'Search & Extract';
                            
                            // Hide loading
                            document.getElementById('loading').style.display = 'none';
                            
                            if (data.status === 'completed') {
                                displayResults(data);
                            } else {
                                showError(data.error || 'Query failed');
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Polling error:', error);
                    });
            }
            
            function updateStatus(response) {
                const statusBadge = document.getElementById('statusBadge');
                const loadingText = document.getElementById('loadingText');
                
                // Update status badge
                statusBadge.textContent = response.status.charAt(0).toUpperCase() + response.status.slice(1);
                statusBadge.className = 'status-badge status-' + response.status;
                
                // Update loading text
                let statusText = 'Processing...';
                if (response.status === 'queued') statusText = 'Query queued...';
                else if (response.status === 'searching') statusText = 'Searching for relevant pages...';
                else if (response.status === 'extracting') statusText = 'Extracting content from pages...';
                else if (response.status === 'completed') statusText = 'Completed!';
                else if (response.status === 'failed') statusText = 'Failed';
                
                loadingText.textContent = statusText;
            }
            
            function displayResults(response) {
                const resultsGrid = document.getElementById('resultsGrid');
                const successfulResults = response.extracted_content.filter(c => c.status === 'success');
                
                if (successfulResults.length === 0) {
                    document.getElementById('emptyState').style.display = 'block';
                    return;
                }
                
                resultsGrid.innerHTML = '';
                
                successfulResults.forEach((result, index) => {
                    const card = document.createElement('div');
                    card.className = 'result-card';
                    
                    const snippet = result.text_content.length > 200 
                        ? result.text_content.substring(0, 200) + '...' 
                        : result.text_content;
                    
                    card.innerHTML = `
                        <div class="card-header">
                            <div class="card-title">${escapeHtml(result.title)}</div>
                            <div class="card-url">${escapeHtml(result.url)}</div>
                        </div>
                        <div class="card-content">
                            <div class="card-snippet">${escapeHtml(snippet)}</div>
                            <div class="card-meta">
                                <span>${new Date(result.extracted_at).toLocaleString()}</span>
                                <span>Score: ${result.metadata?.relevance_score?.toFixed(2) || 'N/A'}</span>
                            </div>
                        </div>
                    `;
                    
                    // Add click to show more
                    card.addEventListener('click', () => {
                        showResultDetail(result);
                    });
                    
                    resultsGrid.appendChild(card);
                });
            }
            
            function showResultDetail(result) {
                const detail = `
                    <h3>${escapeHtml(result.title)}</h3>
                    <p><strong>URL:</strong> <a href="${result.url}" target="_blank">${result.url}</a></p>
                    <p><strong>Extracted:</strong> ${new Date(result.extracted_at).toLocaleString()}</p>
                    ${result.author ? `<p><strong>Author:</strong> ${escapeHtml(result.author)}</p>` : ''}
                    ${result.published_date ? `<p><strong>Published:</strong> ${escapeHtml(result.published_date)}</p>` : ''}
                    <div style="margin-top: 1rem; padding: 1rem; background: #f8fafc; border-radius: 6px; max-height: 400px; overflow-y: auto;">
                        <p>${escapeHtml(result.text_content)}</p>
                    </div>
                `;
                
                alert(detail.replace(/<[^>]*>/g, '')); // Simple alert without HTML
            }
            
            function showError(message) {
                const errorDiv = document.getElementById('error');
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
                document.getElementById('loading').style.display = 'none';
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            // Allow Enter key to submit
            document.getElementById('query').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    submitQuery();
                }
            });
        </script>
    </body>
    </html>
    """


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": config.app_name,
        "version": config.app_version,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/query")
async def process_query(request: QueryRequest) -> QueryResponse:
    """Process a query synchronously."""
    try:
        response = query_processor.process_query(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query/async")
async def process_query_async(request: QueryRequest):
    """Process a query asynchronously and return request ID."""
    try:
        request_id = query_processor.process_query_async(request)
        return {"request_id": request_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/query/{request_id}")
async def get_query_status(request_id: str):
    """Get the status of a query request."""
    response = query_processor.get_request_status(request_id)
    if not response:
        raise HTTPException(status_code=404, detail="Request not found")
    return response


@app.get("/api/requests")
async def get_all_requests():
    """Get all active requests."""
    return query_processor.get_all_requests()


# Enhanced API endpoints
@app.post("/api/enhanced/query")
async def process_enhanced_query(request: QueryRequest):
    """Process a query with enhanced technical analysis."""
    try:
        response = enhanced_processor.process_query(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/research/mythos")
async def research_anthropic_mythos():
    """Start comprehensive research on Anthropic Mythos/Glasswing/Capybara."""
    try:
        from .research_mythos import main as run_mythos_research
        import threading
        
        # Run in background thread
        def run_research():
            try:
                run_mythos_research()
            except Exception as e:
                logger.error(f"Research failed: {e}")
        
        thread = threading.Thread(target=run_research, daemon=True)
        thread.start()
        
        return {
            "status": "started",
            "message": "Mythos research started in background",
            "research_id": f"mythos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/research/topics")
async def get_research_topics():
    """Get available research topics."""
    from .targeted_search import ResearchTopic
    
    topics = []
    for topic in ResearchTopic:
        topics.append({
            "id": topic.value,
            "name": topic.value.replace("_", " ").title(),
            "description": f"Research topic: {topic.value.replace('_', ' ')}"
        })
    
    return {"topics": topics}


def run_server():
    """Run the FastAPI server."""
    print(f"Starting {config.app_name} v{config.app_version}")
    print(f"Server running at http://{config.host}:{config.port}")
    print(f"API documentation at http://{config.host}:{config.port}/docs")
    print("\nPress Ctrl+C to stop the server")
    
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()