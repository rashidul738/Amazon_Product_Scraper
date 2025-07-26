#!/usr/bin/env python3
"""
Example usage of the Amazon Product Scraper.

This script demonstrates how to use the AmazonScraper class to scrape product data
from Amazon while bypassing anti-bot measures and Cloudflare protection.
"""

import json
from amazon_scraper import AmazonScraper

def search_example():
    """Example of searching for products."""
    print("=== Search Example ===")
    
    # Initialize scraper
    scraper = AmazonScraper(
        country="com",           # Amazon.com (US)
        use_browser=True,        # Use browser automation
        headless=True,           # Run browser in headless mode
        use_proxies=False,       # Don't use proxies
        max_retries=3,           # Maximum retry attempts
        retry_delay=5            # Delay between retries in seconds
    )
    
    try:
        # Search for products
        products = scraper.search_products(
            query="mechanical keyboard",
            page=1,
            department=None
        )
        
        # Print results
        print(f"Found {len(products)} products")
        for i, product in enumerate(products[:5], 1):  # Print first 5 products
            print(f"\nProduct {i}:")
            print(f"  ASIN: {product.get('asin')}")
            print(f"  Title: {product.get('title')}")
            print(f"  Price: {product.get('price')}")
            print(f"  Rating: {product.get('rating')}")
            print(f"  URL: {product.get('url')}")
            
        # Save results to file
        with open("search_results.json", "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
            print("\nResults saved to search_results.json")
            
    finally:
        # Always close the scraper to clean up resources
        scraper.close()

def product_example():
    """Example of getting product details."""
    print("\n=== Product Details Example ===")
    
    # Initialize scraper
    scraper = AmazonScraper(
        country="com",           # Amazon.com (US)
        use_browser=True,        # Use browser automation
        headless=True,           # Run browser in headless mode
        cookie_file="amazon_cookies.txt"  # Save/load cookies
    )
    
    try:
        # Get product details (example ASIN for a popular product)
        product_id = "B08JCQCPN6"  # Example ASIN - replace with a real one
        details = scraper.get_product_details(product_id)
        
        # Print basic details
        print(f"Product: {details.get('title')}")
        print(f"Price: {details.get('price')}")
        print(f"Rating: {details.get('rating')}")
        print(f"Availability: {details.get('availability')}")
        
        # Print features
        if 'features' in details and details['features']:
            print("\nFeatures:")
            for feature in details['features'][:3]:  # Print first 3 features
                print(f"  • {feature}")
                
        # Print specifications
        if 'specifications' in details and details['specifications']:
            print("\nSpecifications:")
            for key, value in list(details['specifications'].items())[:3]:  # Print first 3 specs
                print(f"  • {key}: {value}")
                
        # Save results to file
        with open("product_details.json", "w", encoding="utf-8") as f:
            json.dump(details, f, indent=2, ensure_ascii=False)
            print("\nDetails saved to product_details.json")
            
    finally:
        # Always close the scraper to clean up resources
        scraper.close()

def main():
    """Run the examples."""
    # Uncomment the example you want to run
    search_example()
    # product_example()

if __name__ == "__main__":
    main()