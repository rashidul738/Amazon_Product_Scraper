#!/usr/bin/env python3
"""
Amazon Product Scraper - A tool to scrape Amazon product data while bypassing anti-bot measures and Cloudflare protection.

This script uses advanced techniques to bypass Amazon's anti-bot systems and Cloudflare protection,
allowing you to extract product information from Amazon listings.
"""

import os
import sys
import re
import time
import json
import random
import logging
import argparse
import functools
from datetime import datetime
from urllib.parse import urlparse, urljoin, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar, MozillaCookieJar

# Third-party imports - make sure these are installed
import requests
from bs4 import BeautifulSoup
import cloudscraper
from fake_useragent import UserAgent
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import tls_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("amazon_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('amazon_scraper')

###################
# Proxy Manager
###################

class ProxyManager:
    """Manages and rotates proxies for requests."""
    
    def __init__(self, proxies=None, proxy_file=None):
        """
        Initialize the proxy manager.
        
        Args:
            proxies (list): List of proxy URLs
            proxy_file (str): Path to file containing proxy URLs (one per line)
        """
        self.proxies = []
        self.current_index = 0
        
        # Load proxies from list
        if proxies:
            self.proxies.extend(proxies)
            
        # Load proxies from file
        if proxy_file and os.path.exists(proxy_file):
            with open(proxy_file, 'r') as f:
                for line in f:
                    proxy = line.strip()
                    if proxy and proxy not in self.proxies:
                        self.proxies.append(proxy)
                        
        logger.info(f"Loaded {len(self.proxies)} proxies")
    
    def get_proxy(self):
        """
        Get the next proxy in rotation.
        
        Returns:
            dict: Proxy configuration for requests
        """
        if not self.proxies:
            return None
            
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        
        return {
            'http': proxy,
            'https': proxy
        }
    
    def mark_bad_proxy(self, proxy):
        """
        Mark a proxy as bad and remove it from rotation.
        
        Args:
            proxy (str): The proxy URL to remove
        """
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            logger.warning(f"Removed bad proxy: {proxy}. {len(self.proxies)} proxies remaining")

###################
# User Agent Rotator
###################

class UserAgentRotator:
    """Provides rotating user agents for requests."""
    
    def __init__(self, use_fake_ua=True):
        """
        Initialize the user agent rotator.
        
        Args:
            use_fake_ua (bool): Whether to use the fake_useragent library
        """
        self.use_fake_ua = use_fake_ua
        self.ua = None
        self.fallback_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        ]
        
        if use_fake_ua:
            try:
                self.ua = UserAgent()
                logger.info("Initialized fake user agent rotator")
            except Exception as e:
                logger.warning(f"Failed to initialize fake user agent: {str(e)}. Using fallback agents.")
                self.use_fake_ua = False
    
    def get_random_user_agent(self):
        """
        Get a random user agent.
        
        Returns:
            str: A random user agent string
        """
        if self.use_fake_ua and self.ua:
            try:
                return self.ua.random
            except Exception:
                pass
                
        return random.choice(self.fallback_agents)

###################
# Cookie Manager
###################

class CookieManager:
    """Manages cookies for maintaining sessions."""
    
    def __init__(self, cookie_file=None):
        """
        Initialize the cookie manager.
        
        Args:
            cookie_file (str): Path to cookie file (for loading/saving)
        """
        self.cookie_jar = MozillaCookieJar()
        self.cookie_file = cookie_file
        
        # Load cookies if file exists
        if cookie_file and os.path.exists(cookie_file):
            try:
                self.cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
                logger.info(f"Loaded cookies from {cookie_file}")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {str(e)}")
    
    def save_cookies(self):
        """Save cookies to file if cookie_file is specified."""
        if self.cookie_file:
            try:
                self.cookie_jar.save(self.cookie_file, ignore_discard=True, ignore_expires=True)
                logger.info(f"Saved cookies to {self.cookie_file}")
            except Exception as e:
                logger.warning(f"Failed to save cookies: {str(e)}")
    
    def update_from_response(self, response):
        """
        Update cookies from a response.
        
        Args:
            response (requests.Response): The response to extract cookies from
        """
        for cookie in response.cookies:
            self.cookie_jar.set_cookie(cookie)
    
    def get_cookie_dict(self):
        """
        Get cookies as a dictionary.
        
        Returns:
            dict: Dictionary of cookies
        """
        return {cookie.name: cookie.value for cookie in self.cookie_jar}

###################
# Cloudflare Bypass
###################

class CloudflareBypass:
    """Handles bypassing Cloudflare protection."""
    
    def __init__(self, user_agent_rotator=None):
        """
        Initialize the Cloudflare bypass handler.
        
        Args:
            user_agent_rotator (UserAgentRotator): For rotating user agents
        """
        self.user_agent_rotator = user_agent_rotator or UserAgentRotator()
        self.scraper = None
        self.tls_client = None
        self.init_scrapers()
        
    def init_scrapers(self):
        """Initialize the cloudscraper and tls_client instances."""
        try:
            user_agent = self.user_agent_rotator.get_random_user_agent()
            
            # Initialize cloudscraper
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                },
                delay=5,
                interpreter='js2py'
            )
            self.scraper.headers.update({'User-Agent': user_agent})
            
            # Initialize tls_client
            self.tls_client = tls_client.Session(
                client_identifier = "Chrome/96.0.4664.110",
                random_tls_extension_order=True
            )
            self.tls_client.headers.update({
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache',
            })
            
            logger.info("Initialized Cloudflare bypass scrapers")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudflare bypass: {str(e)}")
            raise
    
    def get_with_cloudscraper(self, url, **kwargs):
        """
        Get a URL using cloudscraper.
        
        Args:
            url (str): The URL to request
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            requests.Response: The response
        """
        try:
            return self.scraper.get(url, **kwargs)
        except Exception as e:
            logger.error(f"Cloudscraper request failed: {str(e)}")
            # Reinitialize scraper with a new user agent
            self.init_scrapers()
            raise
    
    def get_with_tls_client(self, url, **kwargs):
        """
        Get a URL using tls_client.
        
        Args:
            url (str): The URL to request
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            requests.Response: The response
        """
        try:
            return self.tls_client.get(url, **kwargs)
        except Exception as e:
            logger.error(f"TLS client request failed: {str(e)}")
            # Reinitialize client with a new user agent
            self.init_scrapers()
            raise

###################
# Undetected Chrome Driver
###################

class UndetectedChromeDriver:
    """Manages an undetected Chrome driver for browser automation."""
    
    def __init__(self, headless=True, proxy=None):
        """
        Initialize the undetected Chrome driver.
        
        Args:
            headless (bool): Whether to run in headless mode
            proxy (str): Proxy to use
        """
        self.driver = None
        self.headless = headless
        self.proxy = proxy
        
    def initialize(self):
        """Initialize the Chrome driver."""
        if self.driver:
            return
            
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument("--headless")
                
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--window-size=1920,1080")
            
            if self.proxy:
                options.add_argument(f'--proxy-server={self.proxy}')
                
            self.driver = uc.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set additional properties to avoid detection
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": UserAgentRotator().get_random_user_agent()
            })
            
            # Add additional headers
            self.driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
                "headers": {
                    "Accept-Language": "en-US,en;q=0.9",
                    "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"96\", \"Google Chrome\";v=\"96\"",
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": "\"Windows\"",
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "none",
                    "sec-fetch-user": "?1",
                    "upgrade-insecure-requests": "1"
                }
            })
            
            logger.info("Initialized undetected Chrome driver")
        except Exception as e:
            logger.error(f"Failed to initialize undetected Chrome driver: {str(e)}")
            raise
    
    def get(self, url, wait_time=10):
        """
        Navigate to a URL and wait for page to load.
        
        Args:
            url (str): The URL to navigate to
            wait_time (int): Time to wait for page load in seconds
            
        Returns:
            str: The page source
        """
        if not self.driver:
            self.initialize()
            
        try:
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(wait_time)
            
            # Check for Cloudflare or CAPTCHA challenges
            if self._is_cloudflare_challenge() or self._is_captcha_challenge():
                logger.warning("Detected challenge page, waiting longer...")
                time.sleep(wait_time * 2)  # Wait longer for challenge to resolve
                
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Chrome driver navigation failed: {str(e)}")
            raise
    
    def _is_cloudflare_challenge(self):
        """Check if current page is a Cloudflare challenge."""
        try:
            return "Checking your browser" in self.driver.page_source or "cloudflare" in self.driver.page_source.lower()
        except:
            return False
    
    def _is_captcha_challenge(self):
        """Check if current page is a CAPTCHA challenge."""
        try:
            return "captcha" in self.driver.page_source.lower() or "robot" in self.driver.page_source.lower()
        except:
            return False
    
    def close(self):
        """Close the driver."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Closed undetected Chrome driver")
            except Exception as e:
                logger.warning(f"Error closing Chrome driver: {str(e)}")
            finally:
                self.driver = None

###################
# Amazon Scraper
###################

class AmazonScraper:
    """Scrapes product data from Amazon."""
    
    def __init__(self, country="com", use_browser=True, headless=True, 
                 use_proxies=False, proxy_list=None, proxy_file=None,
                 cookie_file=None, max_retries=3, retry_delay=5):
        """
        Initialize the Amazon scraper.
        
        Args:
            country (str): Amazon country domain (e.g., "com", "co.uk")
            use_browser (bool): Whether to use browser automation
            headless (bool): Whether to run browser in headless mode
            use_proxies (bool): Whether to use proxies
            proxy_list (list): List of proxy URLs
            proxy_file (str): Path to file containing proxy URLs
            cookie_file (str): Path to cookie file
            max_retries (int): Maximum number of retry attempts
            retry_delay (int): Delay between retries in seconds
        """
        self.base_url = f"https://www.amazon.{country}"
        self.country = country
        self.use_browser = use_browser
        self.headless = headless
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize components
        self.user_agent_rotator = UserAgentRotator()
        self.cookie_manager = CookieManager(cookie_file)
        
        # Initialize proxy manager if using proxies
        self.proxy_manager = None
        if use_proxies:
            self.proxy_manager = ProxyManager(proxy_list, proxy_file)
            
        # Initialize Cloudflare bypass
        self.cf_bypass = CloudflareBypass(self.user_agent_rotator)
        
        # Initialize browser driver if using browser
        self.browser = None
        if use_browser:
            proxy = None
            if self.proxy_manager:
                proxy_dict = self.proxy_manager.get_proxy()
                if proxy_dict:
                    proxy = proxy_dict['https']
                    
            self.browser = UndetectedChromeDriver(headless=headless, proxy=proxy)
        
        logger.info(f"Initialized Amazon scraper for amazon.{country}")
    
    def search_products(self, query, page=1, department=None):
        """
        Search for products on Amazon.
        
        Args:
            query (str): Search query
            page (int): Page number
            department (str): Department to search in
            
        Returns:
            list: List of product dictionaries
        """
        # Construct search URL
        encoded_query = quote_plus(query)
        url = f"{self.base_url}/s?k={encoded_query}"
        
        if department:
            url += f"&i={department}"
            
        if page > 1:
            url += f"&page={page}"
            
        logger.info(f"Searching for '{query}' on page {page}")
        
        # Get search results page
        html = self._get_page(url)
        if not html:
            logger.error("Failed to get search results page")
            return []
            
        # Parse search results
        return self._parse_search_results(html)
    
    def get_product_details(self, product_id):
        """
        Get detailed information about a product.
        
        Args:
            product_id (str): Amazon product ID (ASIN)
            
        Returns:
            dict: Product details
        """
        url = f"{self.base_url}/dp/{product_id}"
        logger.info(f"Getting details for product {product_id}")
        
        # Get product page
        html = self._get_page(url)
        if not html:
            logger.error(f"Failed to get product page for {product_id}")
            return {}
            
        # Parse product details
        return self._parse_product_details(html, product_id)
    
    def _get_page(self, url):
        """
        Get a page with retry logic and rotation of techniques.
        
        Args:
            url (str): The URL to get
            
        Returns:
            str: The HTML content or None if failed
        """
        methods = [
            self._get_with_browser,
            self._get_with_cloudscraper,
            self._get_with_tls_client,
            self._get_with_requests
        ]
        
        # If browser is not enabled, remove browser method
        if not self.use_browser:
            methods.remove(self._get_with_browser)
            
        # Try each method with retries
        for attempt in range(self.max_retries):
            # Shuffle methods to randomize the approach
            random.shuffle(methods)
            
            for method in methods:
                try:
                    html = method(url)
                    if html and self._is_valid_page(html):
                        return html
                except Exception as e:
                    logger.warning(f"Method {method.__name__} failed: {str(e)}")
                    continue
                    
            # If we get here, all methods failed
            logger.warning(f"All methods failed on attempt {attempt+1}/{self.max_retries}, retrying...")
            time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
            
        logger.error(f"Failed to get page {url} after {self.max_retries} attempts")
        return None
    
    def _get_with_browser(self, url):
        """Get page using undetected Chrome driver."""
        if not self.browser:
            return None
            
        return self.browser.get(url)
    
    def _get_with_cloudscraper(self, url):
        """Get page using cloudscraper."""
        response = self.cf_bypass.get_with_cloudscraper(
            url,
            cookies=self.cookie_manager.get_cookie_dict(),
            proxies=self.proxy_manager.get_proxy() if self.proxy_manager else None,
            timeout=30
        )
        
        if response.status_code == 200:
            self.cookie_manager.update_from_response(response)
            self.cookie_manager.save_cookies()
            return response.text
            
        return None
    
    def _get_with_tls_client(self, url):
        """Get page using tls_client."""
        response = self.cf_bypass.get_with_tls_client(
            url,
            cookies=self.cookie_manager.get_cookie_dict(),
            proxies=self.proxy_manager.get_proxy() if self.proxy_manager else None,
            timeout=30
        )
        
        if response.status_code == 200:
            self.cookie_manager.update_from_response(response)
            self.cookie_manager.save_cookies()
            return response.text
            
        return None
    
    def _get_with_requests(self, url):
        """Get page using standard requests with headers."""
        headers = {
            'User-Agent': self.user_agent_rotator.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'TE': 'trailers'
        }
        
        session = requests.Session()
        for cookie in self.cookie_manager.cookie_jar:
            session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)
            
        response = session.get(
            url,
            headers=headers,
            proxies=self.proxy_manager.get_proxy() if self.proxy_manager else None,
            timeout=30
        )
        
        if response.status_code == 200:
            self.cookie_manager.update_from_response(response)
            self.cookie_manager.save_cookies()
            return response.text
            
        return None
    
    def _is_valid_page(self, html):
        """
        Check if the page is valid (not a CAPTCHA or error page).
        
        Args:
            html (str): The HTML content to check
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not html:
            return False
            
        # Check for common challenge indicators
        challenge_indicators = [
            "captcha",
            "robot check",
            "verify you're a human",
            "checking your browser",
            "sorry, we just need to make sure you're not a robot",
            "to discuss automated access to amazon data please contact"
        ]
        
        html_lower = html.lower()
        for indicator in challenge_indicators:
            if indicator in html_lower:
                logger.warning(f"Detected challenge page: '{indicator}'")
                return False
                
        return True
    
    def _parse_search_results(self, html):
        """
        Parse search results from HTML.
        
        Args:
            html (str): The HTML content to parse
            
        Returns:
            list: List of product dictionaries
        """
        products = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all product containers
        result_elements = soup.select('div[data-component-type="s-search-result"]')
        
        for element in result_elements:
            try:
                # Extract ASIN
                asin = element.get('data-asin')
                if not asin:
                    continue
                    
                # Extract product title
                title_element = element.select_one('h2 a span')
                title = title_element.text.strip() if title_element else "Unknown Title"
                
                # Extract URL
                url_element = element.select_one('h2 a')
                url = urljoin(self.base_url, url_element.get('href')) if url_element else None
                
                # Extract price
                price_element = element.select_one('.a-price .a-offscreen')
                price = price_element.text.strip() if price_element else "N/A"
                
                # Extract rating
                rating_element = element.select_one('i.a-icon-star-small')
                rating = rating_element.text.strip() if rating_element else "N/A"
                
                # Extract review count
                review_element = element.select_one('span.a-size-base.s-underline-text')
                reviews = review_element.text.strip() if review_element else "0"
                
                # Extract image URL
                img_element = element.select_one('img.s-image')
                img_url = img_element.get('src') if img_element else None
                
                # Create product dictionary
                product = {
                    'asin': asin,
                    'title': title,
                    'url': url,
                    'price': price,
                    'rating': rating,
                    'reviews': reviews,
                    'image_url': img_url
                }
                
                products.append(product)
                
            except Exception as e:
                logger.warning(f"Error parsing product: {str(e)}")
                continue
                
        logger.info(f"Parsed {len(products)} products from search results")
        return products
    
    def _parse_product_details(self, html, product_id):
        """
        Parse product details from HTML.
        
        Args:
            html (str): The HTML content to parse
            product_id (str): The product ID (ASIN)
            
        Returns:
            dict: Product details
        """
        soup = BeautifulSoup(html, 'html.parser')
        details = {'asin': product_id}
        
        try:
            # Extract title
            title_element = soup.select_one('#productTitle')
            if title_element:
                details['title'] = title_element.text.strip()
                
            # Extract price
            price_element = soup.select_one('#priceblock_ourprice, #priceblock_dealprice, .a-price .a-offscreen')
            if price_element:
                details['price'] = price_element.text.strip()
                
            # Extract availability
            availability_element = soup.select_one('#availability')
            if availability_element:
                details['availability'] = availability_element.text.strip()
                
            # Extract rating
            rating_element = soup.select_one('#acrPopover')
            if rating_element:
                details['rating'] = rating_element.get('title', 'N/A')
                
            # Extract review count
            review_count_element = soup.select_one('#acrCustomerReviewText')
            if review_count_element:
                details['review_count'] = review_count_element.text.strip()
                
            # Extract product description
            description_element = soup.select_one('#productDescription')
            if description_element:
                details['description'] = description_element.text.strip()
                
            # Extract features
            feature_elements = soup.select('#feature-bullets ul li')
            if feature_elements:
                details['features'] = [element.text.strip() for element in feature_elements]
                
            # Extract images
            image_elements = soup.select('#altImages li img')
            if image_elements:
                details['images'] = [img.get('src', '').replace('._SS40_', '._SL1000_') for img in image_elements if 'sprite' not in img.get('src', '')]
                
            # Extract specifications
            spec_elements = soup.select('#productDetails_techSpec_section_1 tr')
            if spec_elements:
                specs = {}
                for element in spec_elements:
                    key_element = element.select_one('th')
                    value_element = element.select_one('td')
                    if key_element and value_element:
                        key = key_element.text.strip()
                        value = value_element.text.strip()
                        specs[key] = value
                details['specifications'] = specs
                
            # Extract categories
            category_elements = soup.select('#wayfinding-breadcrumbs_feature_div ul li')
            if category_elements:
                details['categories'] = [element.text.strip() for element in category_elements if element.text.strip()]
                
        except Exception as e:
            logger.error(f"Error parsing product details: {str(e)}")
            
        logger.info(f"Parsed details for product {product_id}")
        return details
    
    def close(self):
        """Clean up resources."""
        if self.browser:
            self.browser.close()
            
        # Save cookies
        self.cookie_manager.save_cookies()
        
        logger.info("Closed Amazon scraper")

###################
# Retry Decorator
###################

def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts (int): Maximum number of retry attempts
        delay (float): Initial delay between retries in seconds
        backoff (float): Backoff multiplier (e.g. 2 means delay doubles each retry)
        exceptions (tuple): Exceptions to catch and retry
        
    Returns:
        function: Decorated function with retry logic
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_attempts, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"Retry: {func.__name__} failed with {str(e)}. Retrying in {mdelay} seconds...")
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)  # Last attempt
        return wrapper
    return decorator

###################
# Command-Line Interface
###################

def parse_arguments():
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Scrape Amazon product data while bypassing anti-bot measures.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Required arguments
    parser.add_argument(
        'action',
        choices=['search', 'product'],
        help='Action to perform: search for products or get product details'
    )
    
    # Search options
    search_group = parser.add_argument_group('Search Options')
    search_group.add_argument(
        '-q', '--query',
        help='Search query for product search'
    )
    search_group.add_argument(
        '-p', '--page',
        type=int,
        default=1,
        help='Page number for search results'
    )
    search_group.add_argument(
        '-d', '--department',
        help='Department to search in'
    )
    
    # Product options
    product_group = parser.add_argument_group('Product Options')
    product_group.add_argument(
        '-a', '--asin',
        help='Amazon ASIN (product ID) for product details'
    )
    
    # Amazon options
    amazon_group = parser.add_argument_group('Amazon Options')
    amazon_group.add_argument(
        '-c', '--country',
        default='com',
        help='Amazon country domain (e.g., "com", "co.uk")'
    )
    
    # Browser options
    browser_group = parser.add_argument_group('Browser Options')
    browser_group.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not use browser automation'
    )
    browser_group.add_argument(
        '--no-headless',
        action='store_true',
        help='Do not run browser in headless mode (show browser window)'
    )
    
    # Proxy options
    proxy_group = parser.add_argument_group('Proxy Options')
    proxy_group.add_argument(
        '--use-proxies',
        action='store_true',
        help='Use proxies for requests'
    )
    proxy_group.add_argument(
        '--proxy-file',
        help='Path to file containing proxy URLs (one per line)'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '-o', '--output',
        help='Output file path (JSON format)'
    )
    output_group.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output'
    )
    
    # Other options
    other_group = parser.add_argument_group('Other Options')
    other_group.add_argument(
        '--cookie-file',
        help='Path to cookie file (for loading/saving cookies)'
    )
    other_group.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Maximum number of retry attempts'
    )
    other_group.add_argument(
        '--delay',
        type=int,
        default=5,
        help='Delay between retries in seconds'
    )
    other_group.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate arguments
    if args.action == 'search' and not args.query:
        parser.error("search action requires --query")
        
    if args.action == 'product' and not args.asin:
        parser.error("product action requires --asin")
    
    return args

def main():
    """Main entry point for the application."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    try:
        # Initialize scraper
        scraper = AmazonScraper(
            country=args.country,
            use_browser=not args.no_browser,
            headless=not args.no_headless,
            use_proxies=args.use_proxies,
            proxy_file=args.proxy_file,
            cookie_file=args.cookie_file,
            max_retries=args.retries,
            retry_delay=args.delay
        )
        
        # Perform action
        result = None
        if args.action == 'search':
            result = scraper.search_products(
                query=args.query,
                page=args.page,
                department=args.department
            )
        elif args.action == 'product':
            result = scraper.get_product_details(args.asin)
        
        # Output result
        if result:
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    if args.pretty:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    else:
                        json.dump(result, f, ensure_ascii=False)
                print(f"Results saved to {args.output}")
            else:
                if args.pretty:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print(json.dumps(result, ensure_ascii=False))
        else:
            print("No results found")
            
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        return 130
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
        
    finally:
        # Clean up resources
        if 'scraper' in locals():
            scraper.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts