# Amazon Product Scraper

A Python tool to scrape Amazon product data while bypassing anti-bot measures and Cloudflare protection.

## Features

- Bypasses Amazon's anti-bot systems
- Handles Cloudflare protection
- Rotates user agents
- Supports proxy rotation
- Uses multiple request methods (cloudscraper, tls_client, undetected_chromedriver)
- Extracts product details and search results
- Handles cookies for session persistence
- Includes retry mechanisms with exponential backoff
- Command-line interface for easy usage

## Installation

### Prerequisites

- Python 3.7+
- Chrome browser (for browser automation)

### Required Packages

```bash
pip install requests beautifulsoup4 cloudscraper fake-useragent undetected-chromedriver selenium tls-client
```

## Usage

### Command Line Interface

Search for products:

```bash
python amazon_scraper.py search --query "mechanical keyboard" --country "com" --output results.json --pretty
```

Get product details:

```bash
python amazon_scraper.py product --asin "B08JCQCPN6" --country "com" --output product.json --pretty
```

### Python API

```python
from amazon_scraper import AmazonScraper

# Initialize scraper
scraper = AmazonScraper(
    country="com",           # Amazon.com (US)
    use_browser=True,        # Use browser automation
    headless=True,           # Run browser in headless mode
    use_proxies=False,       # Don't use proxies
    max_retries=3            # Maximum retry attempts
)

try:
    # Search for products
    products = scraper.search_products(
        query="mechanical keyboard",
        page=1
    )
    
    # Get product details
    details = scraper.get_product_details("B08JCQCPN6")
    
finally:
    # Always close the scraper to clean up resources
    scraper.close()
```

See `amazon_scraper_example.py` for more detailed examples.

## Command Line Options

### General Options

- `action`: Either `search` or `product`
- `-c, --country`: Amazon country domain (e.g., "com", "co.uk")
- `-o, --output`: Output file path (JSON format)
- `--pretty`: Pretty-print JSON output
- `-v, --verbose`: Enable verbose logging

### Search Options

- `-q, --query`: Search query for product search
- `-p, --page`: Page number for search results
- `-d, --department`: Department to search in

### Product Options

- `-a, --asin`: Amazon ASIN (product ID) for product details

### Browser Options

- `--no-browser`: Do not use browser automation
- `--no-headless`: Do not run browser in headless mode (show browser window)

### Proxy Options

- `--use-proxies`: Use proxies for requests
- `--proxy-file`: Path to file containing proxy URLs (one per line)

### Other Options

- `--cookie-file`: Path to cookie file (for loading/saving cookies)
- `--retries`: Maximum number of retry attempts
- `--delay`: Delay between retries in seconds

## Important Notes

- This tool is for educational purposes only
- Use responsibly and respect Amazon's terms of service
- Using proxies is recommended for large-scale scraping
- Amazon may block your IP if you make too many requests
- Consider adding delays between requests to avoid detection

## Troubleshooting

### Common Issues

1. **CAPTCHA Challenges**: If you encounter frequent CAPTCHA challenges, try:
   - Using proxies
   - Reducing request frequency
   - Using browser automation mode

2. **IP Blocking**: If your IP gets blocked:
   - Use a different IP or proxy
   - Wait before making more requests
   - Try using a VPN

3. **Import Errors**: Make sure all required packages are installed:
   ```bash
   pip install requests beautifulsoup4 cloudscraper fake-useragent undetected-chromedriver selenium tls-client
   ```

4. **Browser Automation Issues**: If browser automation fails:
   - Make sure Chrome is installed
   - Update Chrome to the latest version
   - Try running without headless mode for debugging