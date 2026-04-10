# Scrapling Query Tool - Quick Start

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the tool:**
   ```bash
   ./run.sh
   ```
   Or:
   ```bash
   python -m scrapling_query_app
   ```

3. **Open your browser:**
   - Go to http://127.0.0.1:8051
   - Enter a query (e.g., "python web scraping")
   - Click "Search & Extract"
   - View the results!

## Features

- **Query-based search**: Enter any topic to find relevant web pages
- **Multiple extraction methods**: Static, dynamic, or stealthy fetchers
- **Real-time progress**: See search → extraction → results
- **Structured output**: Titles, snippets, authors, dates, tags
- **Async processing**: Handle long-running tasks without blocking

## API Usage

```bash
# Health check
curl http://127.0.0.1:8051/api/health

# Sync query
curl -X POST http://127.0.0.1:8051/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 3}'

# Async query
curl -X POST http://127.0.0.1:8051/api/query/async \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 3}'

# Check status
curl http://127.0.0.1:8051/api/query/{request_id}
```

## Configuration

Set environment variables:
```bash
export SCRAPLING_QUERY_PORT=8052  # Change port
export SCRAPLING_QUERY_FETCHER="static"  # Change default fetcher
export SCRAPLING_QUERY_MAX_RESULTS=5  # Change default results
```

## Testing

```bash
# Run unit tests
python test_app.py

# Test with mock data (default)
# The tool works without Scrapling installed
```

## Next Steps

1. **Install Scrapling** for actual web extraction:
   ```bash
   pip install scrapling
   ```

2. **Add your own search provider** in `search_providers.py`

3. **Customize the UI** in `server.py` (HTML/CSS/JS)

## Troubleshooting

- **Port already in use**: Change `SCRAPLING_QUERY_PORT`
- **Missing dependencies**: Run `pip install -r requirements.txt`
- **No internet**: Tool works offline with mock data
- **Scrapling not installed**: Uses realistic fallback data