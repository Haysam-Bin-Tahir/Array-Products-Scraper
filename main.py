from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import logging
import time
import os
import re
from concurrent.futures import ThreadPoolExecutor
import math
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver(max_retries=3):
    """Set up and return a configured Chrome WebDriver with retry logic"""
    for attempt in range(max_retries):
        try:
            chrome_options = Options()
            
            # Essential settings only
            chrome_options.add_argument('--disable-http2')  # Prevent HTTP2 errors
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # Additional connection settings
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--dns-prefetch-disable')
            chrome_options.add_argument('--disable-extensions')
            
            # Set custom user agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            # Minimal prefs
            prefs = {
                'profile.default_content_setting_values.notifications': 2,
                'profile.managed_default_content_settings.images': 1,
                'profile.default_content_setting_values.cookies': 1,
                'profile.managed_default_content_settings.javascript': 1,
                'network.http.connection-timeout': 30,
                'network.http.connection-retry-timeout': 30
            }
            chrome_options.add_experimental_option('prefs', prefs)
            
            # Basic stealth settings
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Create service with retry logic
            service = Service(ChromeDriverManager().install())
            service.start()  # Explicitly start the service
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Basic timeouts
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(30)
            
            # Basic stealth
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                '''
            })
            
            # Test connection
            driver.get('about:blank')
            
            return driver
            
        except Exception as e:
            logging.error(f"Failed to setup driver (attempt {attempt + 1}/{max_retries}): {str(e)}")
            try:
                if 'driver' in locals():
                    driver.quit()
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(random.uniform(5, 10))  # Wait before retrying
                continue
            raise Exception(f"Failed to setup driver after {max_retries} attempts")
    
    raise Exception("Failed to setup driver")

def get_product_details(driver, product_url, gender, max_retries=3):
    """Get detailed information from a product page with retry logic"""
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                try:
                    driver.quit()
                except:
                    pass
                driver = setup_driver()
                time.sleep(2)
            
            driver.get(product_url)
            time.sleep(2)
            
            wait = WebDriverWait(driver, 10)
            
            # Wait for main elements to load
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "title-price-block")))
            
            # Get product details in one JavaScript call
            script = """
                try {
                    return {
                        name: document.querySelector('.text-book-6.lg\\\\:text-book-5')?.textContent?.trim() || '',
                        price: document.querySelector('.text-light-6 span')?.textContent?.trim() || '',
                        color: document.querySelector('.text-light-6')?.textContent?.trim() || '',
                    };
                } catch (e) {
                    return {
                        name: '',
                        price: '',
                        color: ''
                    };
                }
            """
            result = driver.execute_script(script)
            
            # Click Information & Details button and get details
            try:
                details_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Information & Details')]"))
                )
                driver.execute_script("arguments[0].click();", details_button)
                time.sleep(1)
                
                # Get all text from details modal
                details_script = """
                    try {
                        const detailsDiv = document.querySelector('.gap-lg.lg\\\\:gap-xl');
                        if (!detailsDiv) return '';
                        
                        // Get all text content from the modal
                        const allText = Array.from(detailsDiv.querySelectorAll('p, .text-light-6'))
                            .map(el => el.textContent.trim())
                            .filter(text => text)
                            .join(' | ');
                        
                        return allText;
                    } catch (e) {
                        return '';
                    }
                """
                details = driver.execute_script(details_script)
                result['details'] = details
                
            except Exception as e:
                logging.warning(f"Error getting product details: {str(e)}")
                result['details'] = ''
            
            # Try to get colors
            try:
                # First try to get single color
                color_script = """
                    try {
                        // First try to get single color
                        const colorSpan = document.querySelector('.gap-primitives-1 .text-light-6');
                        if (colorSpan) return colorSpan.textContent.trim();
                        
                        // If no single color, try to get multiple colors
                        const colorButton = document.querySelector('.gap-primitives-2');
                        if (colorButton) {
                            colorButton.click();
                            // Wait briefly for modal to open
                            return new Promise(resolve => {
                                setTimeout(() => {
                                    const colors = Array.from(document.querySelectorAll('.gap-sm.mb-4 span.text-center.text-text-primary'))
                                        .map(span => span.textContent.trim())
                                        .filter(Boolean)
                                        .join(', ');
                                    resolve(colors);
                                }, 1000);
                            });
                        }
                        return '';
                    } catch (e) {
                        return '';
                    }
                """
                color = driver.execute_script(color_script)
                result['color'] = color
                
            except Exception as e:
                logging.warning(f"Error getting colors: {str(e)}")
                result['color'] = ''
            
            # Get sizes by clicking size selector and getting from modal
            try:
                # Click size selector button
                size_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='size-selector']"))
                )
                driver.execute_script("arguments[0].click();", size_button)
                time.sleep(1)
                
                # Click US tab if not already selected
                us_tab = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[role='tab']:nth-child(2)"))
                )
                if not "selected" in us_tab.get_attribute("data-headlessui-state"):
                    driver.execute_script("arguments[0].click();", us_tab)
                    time.sleep(1)
                
                # Get sizes from modal
                sizes_script = """
                    try {
                        const sizes = [];
                        // Get all size options (both available and disabled)
                        document.querySelectorAll('[data-testid="size-not-disabled"], [data-testid="size-disabled"]').forEach(item => {
                            const label = item.querySelector('label');
                            const isDisabled = item.querySelector('.line-through');
                            if (label) {
                                sizes.push({
                                    size: label.textContent.trim(),
                                    available: !isDisabled
                                });
                            }
                        });
                        return sizes;
                    } catch (e) {
                        return [];
                    }
                """
                sizes = driver.execute_script(sizes_script)
                
                # Format sizes data
                sizes_info = []
                for size in sizes:
                    sizes_info.append(f"{size['size']}({'In Stock' if size['available'] else 'Out of Stock'})")
                sizes_str = ', '.join(sizes_info)
                result['sizes'] = sizes_str
                
            except Exception as e:
                logging.warning(f"Error getting sizes: {str(e)}")
                result['sizes'] = ''
            
            # Get images with error handling
            images_script = """
                try {
                    const images = new Set();
                    
                    // Get all img elements in the slider
                    document.querySelectorAll('.embla__slide img').forEach(img => {
                        const src = img.getAttribute('src');
                        if (src && src.includes('armani.com')) {
                            images.add(src);
                        }
                    });
                    
                    return Array.from(images);
                } catch (e) {
                    return [];
                }
            """
            images = driver.execute_script(images_script)
            
            # No need for cleaning URLs anymore since we're getting direct src
            cleaned_images = images
            
            # Clean up the data
            name = result['name'].strip()
            price = result['price'].replace('$', '').replace(',', '').strip()
            color = result['color'].replace('Colour:', '').strip()
            sizes = result.get('sizes', '')
            details = result.get('details', '')
            
            # Verify we got at least some basic data
            if not name or not price:
                raise Exception("Failed to extract basic product information")
            
            return {
                'Gender': gender,
                'Name': name,
                'Color': color,
                'Sizes': sizes,
                'Price': price,
                'Details': details,  # Renamed from description to details
                'Images': cleaned_images,
                'Product URL': product_url
            }
            
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed for {product_url}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            logging.error(f"All attempts failed for {product_url}")
            return None
    
    return None

def get_last_scraped_product(csv_filename):
    """Get the last successfully scraped product URL from the CSV"""
    try:
        df = pd.read_csv(csv_filename)
        if not df.empty:
            return df['Product URL'].iloc[-1]
    except (FileNotFoundError, pd.errors.EmptyDataError):
        pass
    return None

def scrape_products_from_page(driver, csv_filename, gender):
    """Extract products directly from the product tiles"""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "outline-stroke-cards-hover")))
    
    # Get all product data in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.outline-stroke-cards-hover')).map(item => {
            // Get all image sources from the product tile
            const images = Array.from(item.querySelectorAll('picture img'))
                .map(img => img.getAttribute('src'))
                .filter(src => src && src.includes('armani.com'));
            
            return {
                name: item.querySelector('.text-book-6')?.textContent?.trim() || '',
                price: item.querySelector('.text-light-6')?.textContent?.trim() || '',
                url: item.querySelector('a')?.href || '',
                images: [...new Set(images)]  // Remove duplicates
            };
        }).filter(item => item.name && item.price && item.url);
    """
    products_data = driver.execute_script(script)
    logging.info(f"Found {len(products_data)} products on page")
    
    # Load existing URLs from CSV to avoid duplicates
    existing_urls = set()
    try:
        if os.path.exists(csv_filename):
            df = pd.read_csv(csv_filename)
            existing_urls = set(df['Product URL'].tolist())
    except Exception as e:
        logging.warning(f"Could not load existing URLs: {str(e)}")
    
    # Filter out already scraped products
    products_data = [p for p in products_data if p['url'] not in existing_urls]
    logging.info(f"Found {len(products_data)} new products to scrape")
    
    products = []
    for product_data in products_data:
        try:
            product = {
                'Gender': gender,
                'Name': product_data['name'],
                'Price': product_data['price'].replace('$', '').replace(',', '').strip(),
                'Images': product_data['images'],
                'Product URL': product_data['url']
            }
            
            # Save to CSV immediately
            df = pd.DataFrame([product])
            df.to_csv(csv_filename, mode='a', header=not os.path.exists(csv_filename), index=False)
            products.append(product)
            existing_urls.add(product_data['url'])
            logging.info(f"Scraped and saved product: {product['Name']}")
            
        except Exception as e:
            logging.error(f"Error processing product: {str(e)}")
            continue
            
    return products

def has_more_products(driver, last_product_count):
    """Check if more products loaded after scrolling"""
    try:
        # Get current number of products
        script = """
            return document.querySelectorAll('.product-tile-container').length;
        """
        current_count = driver.execute_script(script)
        
        # If we got more products after scrolling, there might be more
        return current_count > last_product_count
    except Exception as e:
        logging.error(f"Error checking for more products: {str(e)}")
        return False

def scroll_to_bottom(driver):
    """Scroll to bottom and wait for new products to load"""
    try:
        # Get current height
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        # Scroll in smaller increments
        viewport_height = driver.execute_script("return window.innerHeight")
        current_scroll = 0
        
        while current_scroll < last_height:
            # Scroll by viewport height
            current_scroll += viewport_height
            driver.execute_script(f"window.scrollTo(0, {current_scroll});")
            time.sleep(1)  # Wait between scrolls
            
            # Update total height
            last_height = driver.execute_script("return document.body.scrollHeight")
            
    except Exception as e:
        logging.error(f"Error scrolling: {str(e)}")

def scroll_until_end(driver, wait):
    """Scroll until no more products load, with improved detection"""
    try:
        last_count = 0
        no_new_products_count = 0
        max_attempts_without_new = 5
        scroll_pause_time = 2
        
        while no_new_products_count < max_attempts_without_new:
            # Get current product count
            current_count = len(driver.find_elements(By.CLASS_NAME, "lv-product-list__item"))
            logging.info(f"Current product count: {current_count}")
            
            if current_count == last_count:
                no_new_products_count += 1
                logging.info(f"No new products found, attempt {no_new_products_count}/{max_attempts_without_new}")
                
                # Try different scroll positions when stuck
                if no_new_products_count > 1:
                    # Random scroll behavior
                    total_height = driver.execute_script("return document.body.scrollHeight")
                    current_position = driver.execute_script("return window.pageYOffset")
                    
                    # Random scroll up between 10% and 30% of current position
                    scroll_up = max(0, current_position - (current_position * random.uniform(0.1, 0.3)))
                    driver.execute_script(f"window.scrollTo(0, {scroll_up});")
                    time.sleep(random.uniform(1, 2))
                    
                    # Random scroll down
                    viewport_height = driver.execute_script("return window.innerHeight")
                    scroll_down = min(total_height, current_position + (viewport_height * random.uniform(1.2, 1.8)))
                    driver.execute_script(f"window.scrollTo(0, {scroll_down});")
                    time.sleep(random.uniform(1, 2))
            else:
                no_new_products_count = 0
                last_count = current_count
                logging.info("Found new products, continuing to scroll...")
            
            # Random scroll increment
            viewport_height = driver.execute_script("return window.innerHeight")
            current_scroll = driver.execute_script("return window.pageYOffset")
            scroll_amount = current_scroll + (viewport_height * random.uniform(0.5, 0.8))
            driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
            
            # Random delay between scrolls
            time.sleep(scroll_pause_time + random.uniform(0.5, 1.5))
            
        logging.info(f"Finished scrolling, found total of {current_count} products")
        return current_count
        
    except Exception as e:
        logging.error(f"Error during scrolling: {str(e)}")
        return 0

def scrape_armani_category(gender, base_url, csv_filename):
    """Scrape a specific Armani category (men/women) and save to dedicated CSV"""
    logging.info(f"Starting Armani {gender}'s scraper")
    
    retry_count = 0
    max_retries = 5
    
    # Set max pages based on gender
    max_pages = 10 if gender == "Men" else 4
    
    try:
        driver = setup_driver()
        
        for page in range(1, max_pages + 1):
            while retry_count < max_retries:
                try:
                    # Construct page URL
                    page_url = f"{base_url}/?page={page}"
                    logging.info(f"Scraping {gender}'s page {page}: {page_url}")
                    
                    # Navigate to the page
                    driver.get(page_url)
                    time.sleep(5)  # Reduced initial wait
                    
                    # Check if we're on the right page
                    if "armani.com" not in driver.current_url:
                        logging.error(f"{gender}: Redirected away from Armani site on page {page}")
                        retry_count += 1
                        continue
                    
                    # Wait for initial products with longer timeout
                    wait = WebDriverWait(driver, 45)
                    try:
                        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "outline-stroke-cards-hover")))
                    except:
                        logging.error(f"{gender}: Products not found on page {page}")
                        retry_count += 1
                        continue
                    
                    # Quick scroll to bottom and back up
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                    
                    # One more quick scroll down
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # Scrape products from current page
                    products = scrape_products_from_page(driver, csv_filename, gender)
                    if products:
                        logging.info(f"{gender}: Successfully scraped {len(products)} products from page {page}")
                        break  # Break retry loop for this page
                    else:
                        logging.error(f"{gender}: No products were scraped from page {page}")
                        retry_count += 1
                    
                except Exception as e:
                    logging.error(f"{gender}: Error during scraping page {page} (attempt {retry_count + 1}/{max_retries}): {str(e)}")
                    retry_count += 1
                    time.sleep(random.uniform(15, 30))
            
            # Reset retry count for next page
            retry_count = 0
            
            # Add shorter delay between pages
            if page < max_pages:
                time.sleep(3)
                
    except Exception as e:
        logging.error(f"{gender}: Error during scraping: {str(e)}")
    finally:
        try:
            driver.quit()
        except:
            pass

def scrape_armani():
    """Main function to scrape both men's and women's Armani products sequentially"""
    men_base_url = 'https://www.armani.com/en-us/giorgio-armani/man/clothing'
    women_base_url = 'https://www.armani.com/en-us/giorgio-armani/woman/clothing'
    
    try:
        logging.info("Starting women's scraping...")
        scrape_armani_category("Women", women_base_url, 'armani_women_products.csv')
        logging.info("Women's scraping completed")
    except Exception as e:
        logging.error(f"Error in women's scraper: {str(e)}")

if __name__ == "__main__":
    try:
        scrape_armani()
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
