# Scrapling Query Tool

A local web application for query-driven web content extraction using Scrapling.

## Overview

The Scrapling Query Tool allows users to:
1. Enter a query/topic in a text box
2. Retrieve public web pages relevant to that subject/topic
3. Use Scrapling to extract useful content from fetched pages
4. View structured results in a clean, usable interface

## Features

- **Query-based search**: Enter any topic and find relevant web pages
- **Multiple extraction methods**: Choose between static, dynamic, or stealthy fetchers
- **Structured results**: View extracted content with titles, snippets, metadata
- **Real-time status**: Track progress from search to extraction
- **Responsive UI**: Clean, modern interface that works on desktop and mobile
- **Async processing**: Handle long-running extraction tasks without blocking

## Architecture

```
tools/scrapling_query_app/
├── __init__.py              # Package definition
├── __main__.py             # CLI entry point
├── config.py               # Configuration management
├── models.py               # Data models (Pydantic)
├── search_providers.py     # Search engine integration
├── scrapling_extractor.py  # Scrapling integration layer
├── query_processor.py      # Core query processing logic
├── server.py               # FastAPI web server
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation

### Option 1: Install with pip (recommended)

```bash
cd /path/to/simp/tools/scrapling_query_app
pip install -r requirements.txt
```

### Option 2: Install Scrapling (optional)

For full functionality with actual web extraction:

```bash
pip install scrapling
```

Note: The tool will work without Scrapling installed, using fallback mock data.

## Usage

### Starting the server

```bash
cd /path/to/simp
python -m tools.scrapling_query_app
```

Or directly:

```bash
cd /path/to/simp/tools/scrapling_query_app
python -m scrapling_query_app
```

### Environment variables

Configure the tool using environment variables:

```bash
export SCRAPLING_QUERY_HOST="127.0.0.1"
export SCRAPLING_QUERY_PORT=8051
export SCRAPLING_QUERY_FETCHER="dynamic"
export SCRAPLING_QUERY_MAX_RESULTS=10
```

### Using the web interface

1. Open your browser to `http://127.0.0.1:8051`
2. Enter a search query (e.g., "machine learning tutorials")
3. Select the number of results and extraction method
4. Click "Search & Extract"
5. View the results as they are processed

### API endpoints

The tool provides a REST API:

- `GET /` - Web interface
- `GET /api/health` - Health check
- `POST /api/query` - Process query synchronously
- `POST /api/query/async` - Process query asynchronously
- `GET /api/query/{request_id}` - Get query status
- `GET /api/requests` - List all active requests

Example API usage:

```bash
# Process a query
curl -X POST http://127.0.0.1:8051/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Python web scraping", "max_results": 5}'

# Process async and check status
curl -X POST http://127.0.0.1:8051/api/query/async \
  -H "Content-Type: application/json" \
  -d '{"query": "Python web scraping", "max_results": 5}'
# Returns: {"request_id": "uuid", "status": "queued"}

curl http://127.0.0.1:8051/api/query/{request_id}
```

## Extraction Methods

The tool supports three extraction methods:

1. **Static (`static`)**: Uses `FetcherSession` for static websites. Fast and lightweight.
2. **Dynamic (`dynamic`)**: Uses `DynamicSession` for JavaScript-heavy websites. Requires browser automation.
3. **Stealthy (`stealthy`)**: Uses `StealthySession` for websites with anti-bot protection.

## Search Providers

Currently implemented search providers:

1. **DuckDuckGo**: Real web search using DuckDuckGo's HTML interface
2. **Mock**: Mock provider for testing (returns example data)

To add a new search provider, implement the `SearchProvider` base class in `search_providers.py`.

## Safe Use Guidelines

### Rate Limiting
- The tool includes delays between requests to be respectful to websites
- Default delay: 1 second between search requests
- Consider increasing delays for large-scale extraction

### robots.txt Compliance
- The tool respects `robots.txt` by default (via Scrapling)
- Configure `respect_robots_txt` in config.py

### Content Limits
- Extracted content is limited to 5000 characters by default
- Configure `max_content_length` in config.py

### Legal Considerations
- Only scrape publicly accessible content
- Respect website terms of service
- Do not scrape personal or private data
- Use for legitimate research and analysis purposes

## Testing

Run the test suite:

```bash
cd /path/to/simp
python -m pytest tests/test_scrapling_query_app.py -v
```

## Development

### Adding new features

1. **New search provider**: Implement `SearchProvider` in `search_providers.py`
2. **New extraction method**: Add to `FetcherType` enum and implement in `scrapling_extractor.py`
3. **UI enhancements**: Modify the HTML/CSS/JS in `server.py`

### Code style

- Use type hints throughout
- Follow PEP 8 guidelines
- Use dataclasses for data models
- Add docstrings for public functions and classes

## Limitations

1. **Search quality**: The DuckDuckGo HTML parser is basic. For production use, consider using official APIs.
2. **Extraction accuracy**: Content extraction depends on website structure. Some sites may require custom selectors.
3. **Performance**: Dynamic extraction (with browser automation) is slower than static extraction.
4. **Scale**: Designed for small to medium scale extraction. Not suitable for large-scale crawling.

## Troubleshooting

### "Scrapling not installed" warnings
The tool will work with mock data if Scrapling is not installed. Install Scrapling for actual web extraction:

```bash
pip install scrapling
```

### Browser automation issues
For dynamic extraction, ensure you have Chrome/Chromium installed and available in PATH.

### Port already in use
Change the port using environment variables:

```bash
export SCRAPLING_QUERY_PORT=8052
python -m tools.scrapling_query_app
```

## License

Part of the SIMP (Structured Intent Messaging Protocol) system.

## Acknowledgments

- [Scrapling](https://github.com/D4Vinci/Scrapling) - Web scraping framework
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [DuckDuckGo](https://duckduckgo.com/) - Search provider