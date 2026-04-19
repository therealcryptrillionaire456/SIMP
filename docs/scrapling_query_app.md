# Scrapling Query Tool Documentation

## Overview

The Scrapling Query Tool is a local web application that allows users to:
1. Enter a query/topic in a text box
2. Retrieve public web pages relevant to that subject/topic
3. Use Scrapling to extract useful content from fetched pages
4. View structured results in a clean, usable interface

The tool is designed to be self-contained and runnable locally with minimal setup.

## Architecture

### Directory Structure
```
tools/scrapling_query_app/
├── __init__.py              # Package definition
├── __main__.py             # CLI entry point
├── config.py               # Configuration management
├── models.py               # Data models (dataclasses)
├── search_providers.py     # Search engine integration
├── scrapling_extractor.py  # Scrapling integration layer
├── query_processor.py      # Core query processing logic
├── server.py               # FastAPI web server
├── requirements.txt        # Python dependencies
├── README.md              # Detailed documentation
├── QUICKSTART.md          # Quick start guide
├── run.sh                 # Startup script
└── test_app.py            # Integration tests
```

### Core Components

1. **Models** (`models.py`): Data classes for requests, responses, and extracted content
2. **Search Providers** (`search_providers.py`): Interfaces to search engines (DuckDuckGo, Mock)
3. **Scrapling Extractor** (`scrapling_extractor.py`): Integration with Scrapling library for content extraction
4. **Query Processor** (`query_processor.py`): Orchestrates search → extraction workflow
5. **Web Server** (`server.py`): FastAPI server with HTML frontend and REST API

## Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)

### Step-by-Step Installation

1. **Clone or navigate to the SIMP repository:**
   ```bash
   cd /path/to/simp
   ```

2. **Install dependencies:**
   ```bash
   cd tools/scrapling_query_app
   pip install -r requirements.txt
   ```

3. **Optional: Install Scrapling for actual web extraction:**
   ```bash
   pip install scrapling
   ```
   Note: The tool works without Scrapling installed, using realistic fallback data.

## Usage

### Starting the Server

**Option 1: Using the run script (recommended):**
```bash
cd tools/scrapling_query_app
./run.sh
```

**Option 2: Direct Python execution:**
```bash
cd /path/to/simp
python -m tools.scrapling_query_app
```

**Option 3: From the tools directory:**
```bash
cd tools/scrapling_query_app
python -m scrapling_query_app
```

### Using the Web Interface

1. Open your browser to `http://127.0.0.1:8051`
2. Enter a search query (e.g., "machine learning tutorials")
3. Select the number of results (default: 10)
4. Choose an extraction method:
   - **Dynamic**: For JavaScript-heavy websites (default)
   - **Static**: For simple, static websites (faster)
   - **Stealthy**: For websites with anti-bot protection
5. Click "Search & Extract"
6. View the results as they are processed

### API Usage

The tool provides a REST API for programmatic access:

#### Health Check
```bash
curl http://127.0.0.1:8051/api/health
```

#### Synchronous Query
```bash
curl -X POST http://127.0.0.1:8051/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "python web scraping",
    "max_results": 5,
    "fetcher_type": "dynamic",
    "use_cache": true
  }'
```

#### Asynchronous Query
```bash
# Start async query
curl -X POST http://127.0.0.1:8051/api/query/async \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 3}'

# Check status
curl http://127.0.0.1:8051/api/query/{request_id}
```

#### List Active Requests
```bash
curl http://127.0.0.1:8051/api/requests
```

## Configuration

### Environment Variables

Configure the tool using environment variables:

```bash
# Server configuration
export SCRAPLING_QUERY_HOST="127.0.0.1"  # Server host
export SCRAPLING_QUERY_PORT=8051         # Server port

# Search configuration
export SCRAPLING_QUERY_FETCHER="dynamic"  # Default fetcher
export SCRAPLING_QUERY_MAX_RESULTS=10     # Default results per query

# Behavior configuration
export SCRAPLING_QUERY_RESPECT_ROBOTS=true  # Respect robots.txt
```

### Configuration File

The configuration is managed in `tools/scrapling_query_app/config.py`. Key settings:

```python
app_name: str = "Scrapling Query Tool"  # Application name
host: str = "127.0.0.1"                 # Server host
port: int = 8051                        # Server port
default_fetcher: str = "dynamic"        # Default extraction method
max_results_per_query: int = 10         # Maximum results per query
max_content_length: int = 5000          # Maximum content length (characters)
search_timeout: int = 30                # Search timeout (seconds)
respect_robots_txt: bool = True         # Respect robots.txt
```

## Search Providers

### Available Providers

1. **Mock Search Provider**: Returns example data for testing
   - Always available
   - No internet required
   - Good for development and testing

2. **DuckDuckGo Search Provider**: Real web search using DuckDuckGo HTML
   - Requires internet connection
   - May be blocked or rate-limited
   - Falls back to mock data if unavailable

### Adding a New Search Provider

To add a new search provider:

1. Implement the `SearchProvider` base class:
   ```python
   class NewSearchProvider(SearchProvider):
       def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
           # Implementation
   ```

2. Add to the provider factory in `search_providers.py`:
   ```python
   providers = {
       "newprovider": NewSearchProvider,
       # ... existing providers
   }
   ```

## Extraction Methods

### Fetcher Types

1. **Static Fetcher** (`FetcherType.STATIC`):
   - Uses `FetcherSession` from Scrapling
   - For static websites without JavaScript
   - Fast and lightweight
   - Best for: News sites, documentation, blogs

2. **Dynamic Fetcher** (`FetcherType.DYNAMIC`):
   - Uses `DynamicSession` from Scrapling
   - For JavaScript-heavy websites
   - Requires browser automation
   - Best for: Single-page applications, modern web apps

3. **Stealthy Fetcher** (`FetcherType.STEALTHY`):
   - Uses `StealthySession` from Scrapling
   - For websites with anti-bot protection
   - Most resource-intensive
   - Best for: E-commerce, social media, protected content

### Content Extraction Process

1. **Fetch page**: Retrieve HTML content using selected fetcher
2. **Parse content**: Extract title, main content, metadata
3. **Clean text**: Remove HTML tags, normalize whitespace
4. **Extract metadata**: Author, publication date, images, links
5. **Structure output**: Format as `ExtractedContent` object

## Safe Use Guidelines

### Rate Limiting
- Default delay of 1 second between requests
- Configure delays in search providers
- Respect website terms of service

### robots.txt Compliance
- Enabled by default via Scrapling
- Configure `respect_robots_txt` in config
- Check individual website policies

### Content Limits
- Maximum 5000 characters per extraction (configurable)
- Limit number of results per query
- Set appropriate timeouts

### Legal Considerations
1. **Only scrape publicly accessible content**
2. **Respect website terms of service**
3. **Do not scrape personal or private data**
4. **Use for legitimate research and analysis**
5. **Attribute content appropriately**
6. **Check copyright restrictions**

### Ethical Guidelines
- Use the tool for learning and research
- Don't overload websites with requests
- Cache results when possible
- Consider using official APIs when available

## Testing

### Running Tests

```bash
# Run all tests
cd /path/to/simp
python -m pytest tests/test_scrapling_query_app.py -v

# Run specific test class
python -m pytest tests/test_scrapling_query_app.py::TestModels -v

# Run with coverage
python -m pytest tests/test_scrapling_query_app.py --cov=tools.scrapling_query_app
```

### Test Categories

1. **Model Tests**: Validate data structures
2. **Search Provider Tests**: Test search functionality
3. **Extractor Tests**: Test content extraction
4. **Query Processor Tests**: Test end-to-end workflow
5. **Error Handling Tests**: Test failure scenarios

## Development

### Adding Features

#### New Search Provider
1. Create provider class in `search_providers.py`
2. Implement `search()` method
3. Add to provider factory
4. Write tests

#### New Extraction Method
1. Add to `FetcherType` enum in `models.py`
2. Implement extraction method in `scrapling_extractor.py`
3. Update `ScraplingExtractor` class
4. Write tests

#### UI Enhancements
1. Modify HTML/CSS/JS in `server.py`
2. Update API endpoints if needed
3. Test with different screen sizes

### Code Style
- Use type hints throughout
- Follow PEP 8 guidelines
- Use dataclasses for data models
- Add docstrings for public functions
- Write tests for new functionality

## Troubleshooting

### Common Issues

#### "Port already in use"
```bash
# Change port
export SCRAPLING_QUERY_PORT=8052
python -m tools.scrapling_query_app
```

#### "Module not found" errors
```bash
# Install dependencies
pip install -r tools/scrapling_query_app/requirements.txt
```

#### "Scrapling not installed" warnings
- The tool works with mock data
- Install Scrapling for actual extraction:
  ```bash
  pip install scrapling
  ```

#### Search not returning results
- Check internet connection
- Try mock search provider
- Check DuckDuckGo availability

#### Extraction taking too long
- Reduce `max_results_per_query`
- Use static fetcher for simple sites
- Increase timeouts in config

### Debugging

#### Enable Debug Logging
```python
# In config.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Check Server Logs
```bash
# Run server with verbose output
python -m tools.scrapling_query_app 2>&1 | tee server.log
```

#### Test API Endpoints
```bash
# Use curl to test endpoints
curl -v http://127.0.0.1:8051/api/health
```

## Limitations

### Current Limitations
1. **Search quality**: DuckDuckGo HTML parsing is basic
2. **Extraction accuracy**: Depends on website structure
3. **Performance**: Dynamic extraction is slower
4. **Scale**: Designed for small to medium scale
5. **Dependencies**: Requires Scrapling for full functionality

### Future Improvements
1. **Additional search providers**: Google, Bing, etc.
2. **Better content extraction**: AI-powered extraction
3. **Caching**: Persistent result caching
4. **Batch processing**: Process multiple queries
5. **Export options**: JSON, CSV, PDF export

## Integration with SIMP System

The Scrapling Query Tool is designed as a standalone tool within the SIMP ecosystem. Potential integration points:

1. **Agent registration**: Register as a SIMP agent
2. **Intent handling**: Process scraping intents
3. **Result sharing**: Share extracted content via broker
4. **Orchestration**: Include in automated workflows

## License and Attribution

Part of the SIMP (Structured Intent Messaging Protocol) system.

### Acknowledgments
- [Scrapling](https://github.com/D4Vinci/Scrapling): Web scraping framework
- [FastAPI](https://fastapi.tiangolo.com/): Web framework
- [DuckDuckGo](https://duckduckgo.com/): Search provider

## Support

For issues, questions, or contributions:
1. Check the troubleshooting section
2. Review the documentation
3. Test with mock data
4. Report issues with logs and steps to reproduce

---

*Last updated: April 2024*  
*Version: 0.1.0*