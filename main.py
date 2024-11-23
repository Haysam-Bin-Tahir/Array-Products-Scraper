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

def setup_driver():
    """Set up and return a configured Chrome WebDriver with minimal essential settings"""
    chrome_options = Options()
    
    # Essential settings only
    chrome_options.add_argument('--disable-http2')  # Prevent HTTP2 errors
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Set custom user agent
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    # Minimal prefs
    prefs = {
        'profile.default_content_setting_values.notifications': 2,
        'profile.managed_default_content_settings.images': 1,
        'profile.default_content_setting_values.cookies': 1,
        'profile.managed_default_content_settings.javascript': 1
    }
    chrome_options.add_experimental_option('prefs', prefs)
    
    # Basic stealth settings
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
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
    
    return driver

def get_product_details(driver, product_url, max_retries=3):
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
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "lv-product__name")))
            
            # Get product details in one JavaScript call
            script = """
                try {
                    return {
                        name: document.querySelector('.lv-product__name')?.textContent?.trim() || '',
                        price: document.querySelector('.lv-price.lv-product__price span')?.textContent?.trim() || '',
                        description: document.querySelector('.lv-product__description')?.textContent?.trim() || '',
                        details: document.querySelector('.lv-product-detailed-features__description')?.textContent?.trim() || '',
                        color: ''  // Will handle colors separately
                    };
                } catch (e) {
                    return {
                        name: '',
                        price: '',
                        description: '',
                        details: '',
                        color: ''
                    };
                }
            """
            result = driver.execute_script(script)
            
            # Try to get colors if they exist
            try:
                # Click color selector if it exists
                color_button = driver.find_element(By.CLASS_NAME, "lv-product-variation-selector")
                if "Colors" in color_button.text:
                    color_button.click()
                    time.sleep(1)
                    
                    # Get all color names
                    colors_script = """
                        return Array.from(document.querySelectorAll('.lv-product-panel-grid__item .lv-product-card__name'))
                            .map(el => el.textContent.trim())
                            .join(', ');
                    """
                    colors = driver.execute_script(colors_script)
                    result['color'] = colors
            except:
                pass
            
            # Get images with error handling
            images_script = """
                try {
                    return Array.from(document.querySelectorAll('.lv-list img.lv-smart-picture__object'))
                        .map(img => {
                            let srcset = img.getAttribute('srcset');
                            if (!srcset) return null;
                            // Get the largest image URL from srcset
                            let urls = srcset.split(',')
                                .map(s => s.trim().split(' ')[0])
                                .filter(url => url.includes('4096'));
                            return urls[0] || null;
                        })
                        .filter(src => src);
                } catch (e) {
                    return [];
                }
            """
            images = set(driver.execute_script(images_script))
            
            # Clean up the data
            name = result['name'].strip()
            price = result['price'].replace('$', '').replace(',', '').strip()
            description = result['description'].strip()
            details = result['details'].strip()
            color = result['color'].strip()
            
            # Verify we got at least some basic data
            if not name or not price:
                raise Exception("Failed to extract basic product information")
            
            return {
                'Gender': 'Men' if '/men/' in product_url.lower() else 'Women',
                'Name': name,
                'Color': color,
                'Description': description,
                'Details': details,
                'Price': price,
                'Images': list(images),
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

def scrape_products_from_page(driver, csv_filename):
    """Extract products from the current page and save in real-time"""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "lv-product-list__item")))
    
    # Get all product URLs in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.lv-product-list__item')).map(item => ({
            url: item.querySelector('.lv-product-card__url')?.href,
            price: item.querySelector('.lv-price span')?.textContent?.trim()
        })).filter(item => item.url);
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
    for index, product_data in enumerate(products_data, 1):
        try:
            logging.info(f"Scraping product {index}/{len(products_data)}")
            
            product = get_product_details(driver, product_data['url'])
            
            if product:
                # Save to CSV immediately
                df = pd.DataFrame([product])
                df.to_csv(csv_filename, mode='a', header=not os.path.exists(csv_filename), index=False)
                products.append(product)
                existing_urls.add(product_data['url'])
                logging.info(f"Scraped and saved product: {product['Name']}")
            
            # Go back to the product listing page
            driver.get(driver.current_url)
            time.sleep(1)
            
        except Exception as e:
            logging.error(f"Error processing product URL {product_data['url']}: {str(e)}")
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

def scrape_lv_category(gender, base_url, csv_filename):
    """Scrape a specific LV category (men/women) and save to dedicated CSV"""
    logging.info(f"Starting Louis Vuitton {gender}'s scraper")
    
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            driver = setup_driver()
            
            # Initial delay before accessing site
            time.sleep(random.uniform(5, 8))
            
            # Navigate directly to the category page
            driver.get(base_url)
            time.sleep(random.uniform(8, 10))  # Longer wait for page load
            
            # Check if we're on the right page
            if "louisvuitton.com" not in driver.current_url:
                logging.error(f"{gender}: Redirected away from LV site")
                retry_count += 1
                continue
            
            # Wait for initial products with longer timeout
            wait = WebDriverWait(driver, 45)
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "lv-product-list__item")))
            except:
                logging.error(f"{gender}: Products not found on page")
                retry_count += 1
                continue
            
            # Add random delay before scrolling
            time.sleep(random.uniform(3, 5))
            
            total_products = scroll_until_end(driver, wait)
            
            if total_products == 0:
                logging.error(f"{gender}: No products found after scrolling")
                retry_count += 1
                continue
                
            # Scrape products
            products = scrape_products_from_page(driver, csv_filename)
            if products:
                logging.info(f"{gender}: Successfully scraped {len(products)} products")
                break
            else:
                logging.error(f"{gender}: No products were scraped")
                retry_count += 1
            
        except Exception as e:
            logging.error(f"{gender}: Error during scraping (attempt {retry_count + 1}/{max_retries}): {str(e)}")
            retry_count += 1
            time.sleep(random.uniform(15, 30))
            
        finally:
            try:
                driver.quit()
            except:
                pass
    
    if retry_count == max_retries:
        logging.error(f"{gender}: Failed to scrape after maximum retries")

def scrape_lv():
    """Main function to scrape both men's and women's Louis Vuitton products"""
    men_base_url = 'https://us.louisvuitton.com/eng-us/men/ready-to-wear/all-ready-to-wear/_/N-tmfgzj3?page=27'
    women_base_url = 'https://us.louisvuitton.com/eng-us/women/ready-to-wear/all-ready-to-wear/_/N-to8aw9x?page=4'
    
    # Create ThreadPoolExecutor to run both scrapers in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both scraping tasks
        men_future = executor.submit(
            scrape_lv_category, 
            "Men", 
            men_base_url, 
            'lv_men_products.csv'
        )
        
        # Add delay between starting scrapers
        time.sleep(random.uniform(10, 15))
        
        women_future = executor.submit(
            scrape_lv_category, 
            "Women", 
            women_base_url, 
            'lv_women_products.csv'
        )
        
        # Wait for both tasks to complete
        try:
            men_result = men_future.result()
            logging.info("Men's scraping completed")
        except Exception as e:
            logging.error(f"Error in men's scraper: {str(e)}")
            
        try:
            women_result = women_future.result()
            logging.info("Women's scraping completed")
        except Exception as e:
            logging.error(f"Error in women's scraper: {str(e)}")

if __name__ == "__main__":
    try:
        scrape_lv()
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
