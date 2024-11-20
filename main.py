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

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    """Set up and return a configured Chrome WebDriver"""
    chrome_options = Options()
    
    # Headless mode
    # chrome_options.add_argument('--headless=new')  # Removed headless mode for debugging
    
    # Basic automation settings
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Performance optimization arguments
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-extensions')
    
    # Set page load strategy to eager
    chrome_options.page_load_strategy = 'eager'
    
    # Additional settings
    prefs = {
        'profile.default_content_setting_values.notifications': 2,
        'profile.default_content_setting_values.geolocation': 2,
        'profile.managed_default_content_settings.images': 1,
        'profile.default_content_setting_values.cookies': 1,
        'profile.managed_default_content_settings.javascript': 1,
        'profile.default_content_settings.popups': 2,
        'profile.default_content_settings.plugins': 2,
        'disk-cache-size': 4096,
        'profile.password_manager_enabled': False,
        'profile.history_enabled': False,
        'network.http.max-connections-per-server': 10
    }
    chrome_options.add_experimental_option('prefs', prefs)
    
    # Additional experimental options
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Set timeouts
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    
    # Execute CDP commands for additional optimizations
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    })
    
    return driver

def get_product_details(driver, product_url, max_retries=3):
    """Get detailed information from a product page with retry logic"""
    for attempt in range(max_retries):
        try:
            # Create new driver for each retry to avoid stale sessions
            if attempt > 0:
                try:
                    driver.quit()
                except:
                    pass
                driver = setup_driver()
                time.sleep(2)
            
            driver.get(product_url)
            time.sleep(3)  # Wait longer for initial page load
            
            wait = WebDriverWait(driver, 10)  # Increased wait time
            
            # Wait for main elements to load with multiple selectors
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-details--js")))
            except:
                # Try alternative selectors if the first one fails
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-name")))
            
            try:
                # Click the product details button to reveal description
                details_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "product-details--js")))
                driver.execute_script("arguments[0].click();", details_button)
                time.sleep(2)
            except Exception as e:
                logging.warning(f"Could not click details button: {str(e)}")
            
            # Get product details in one JavaScript call with more error handling
            script = """
                try {
                    return {
                        name: document.querySelector('.product-name')?.textContent?.trim() || 
                              document.querySelector('.pdp-link')?.textContent?.trim() || '',
                        price: document.querySelector('.price .sales .value')?.textContent?.trim() || 
                               document.querySelector('.price .value')?.textContent?.trim() || '',
                        description: document.querySelector('.product-details-tabs__item p')?.textContent?.trim() || '',
                        details: Array.from(document.querySelectorAll('.product-details-tabs__item p'))
                                 .slice(1)
                                 .map(p => p.textContent.trim())
                                 .join(' ') || '',
                        colors: Array.from(document.querySelectorAll('.swatches .swatch'))
                                 .map(swatch => swatch.getAttribute('title') || swatch.getAttribute('alt'))
                                 .filter(color => color)
                    };
                } catch (e) {
                    return {
                        name: '',
                        price: '',
                        description: '',
                        details: '',
                        colors: []
                    };
                }
            """
            result = driver.execute_script(script)
            
            # Get images with error handling
            images_script = """
                try {
                    return Array.from(document.querySelectorAll('.large-images img.zoom-image'))
                        .map(img => {
                            let src = img.getAttribute('data-zoom-image') || img.src;
                            return src.includes('?') ? src.split('?')[0] + '?$large$' : src + '?$large$';
                        })
                        .filter(src => src);
                } catch (e) {
                    return [];
                }
            """
            images = set(driver.execute_script(images_script))
            
            # Verify we got at least some basic data
            if not result['name'] and not result['price']:
                raise Exception("Failed to extract basic product information")
            
            return {
                'Gender': 'Women',  # Adjust based on URL/category
                'Name': result['name'] or "Name not available",
                'Colors': ', '.join(result['colors'] or []),
                'Description': result['description'] or "",
                'Details': result['details'] or "",
                'Price': result['price'] or "Price not available",
                'Images': list(images),
                'Product URL': product_url
            }
            
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed for {product_url}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)  # Wait longer between retries
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

def scrape_products_from_page(driver, csv_filename, resume_url=None):
    """Extract products from the current page and save in real-time"""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "product-tile-container")))
    
    # Get all product URLs in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.product-tile-container')).map(item => ({
            url: item.querySelector('.pdp-link a')?.href,
            price: item.querySelector('.price .sales .value')?.textContent?.trim()
        })).filter(item => item.url);
    """
    products_data = driver.execute_script(script)
    
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
    
    logging.info(f"Found {len(products_data)} new unique products")
    
    # Handle resume logic
    if resume_url:
        try:
            resume_index = next(i for i, p in enumerate(products_data) if p['url'] == resume_url) + 1
            products_data = products_data[resume_index:]
            logging.info(f"Resuming from product {resume_index + 1}")
        except (StopIteration, ValueError):
            logging.info("Resume URL not found on this page, starting from beginning")
    
    products = []
    for index, product_data in enumerate(products_data, 1):
        try:
            logging.info(f"Scraping product {index}/{len(products_data)}")
            
            # Skip if URL already exists
            if product_data['url'] in existing_urls:
                logging.info(f"Skipping already scraped product: {product_data['url']}")
                continue
                
            product = get_product_details(driver, product_data['url'])
            
            if product:
                # Save to CSV
                df = pd.DataFrame([{
                    'Gender': product['Gender'],
                    'Name': product['Name'],
                    'Colors': product['Colors'],
                    'Description': product['Description'],
                    'Details': product['Details'],
                    'Price': product['Price'],
                    'Images': ','.join(product['Images']),
                    'Product URL': product['Product URL']
                }])
                
                df.to_csv(csv_filename, mode='a', header=not os.path.exists(csv_filename), index=False)
                products.append(product)
                existing_urls.add(product_data['url'])
                logging.info(f"Scraped and saved product: {product['Name']}")
            
            # Go back to the product listing page
            driver.get(driver.current_url)  # Refresh instead of using history
            time.sleep(2)
            
        except Exception as e:
            if "disconnected" in str(e):
                logging.warning("Browser disconnected, recreating driver...")
                try:
                    driver.quit()
                except:
                    pass
                driver = setup_driver()
                driver.get(driver.current_url)
                continue
            
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

def scrape_mk_with_agent(start_page, agent_num):
    base_url = 'https://www.michaelkors.com/women/clothing/?start=0&sz=400'
    us_site_url = 'https://www.michaelkors.com/region-selector?from=/'
    logging.info(f"Agent {agent_num}: Starting scrape from page {start_page}")
    all_products = []
    
    # Define CSV filename with agent number
    csv_filename = f'mk_products_agent_{agent_num}.csv'
    
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 30)  # Increased wait time for initial load
        
        # First handle region selection
        driver.get(us_site_url)
        time.sleep(3)
        
        try:
            # Try to select US region if redirected to region selector
            us_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='michaelkors.com/us']")))
            driver.execute_script("arguments[0].click();", us_button)
            time.sleep(3)
        except Exception as e:
            logging.warning(f"Could not find US region button: {str(e)}")
        
        # Now try to access the main page
        driver.get(base_url)
        time.sleep(5)  # Wait longer for initial page load
        
        # Verify we're on the US site
        if "michaelkors.global" in driver.current_url:
            logging.error(f"Agent {agent_num}: Redirected to global site, cannot proceed")
            return all_products
        
        # Wait for initial products to appear and count them
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-tile-container")))
            
            # Wait for product count to stabilize
            last_count = 0
            stable_count = 0
            max_attempts = 10
            
            for attempt in range(max_attempts):
                current_count = len(driver.find_elements(By.CLASS_NAME, "product-tile-container"))
                logging.info(f"Current product count: {current_count}")
                
                if current_count == last_count:
                    stable_count += 1
                    if stable_count >= 3:  # Count is stable for 3 consecutive checks
                        logging.info(f"Product count stabilized at {current_count}")
                        break
                else:
                    stable_count = 0
                    last_count = current_count
                
                time.sleep(2)  # Wait between checks
                
                # Scroll a bit to trigger more loading
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, 0);")  # Scroll back to top
                
            logging.info(f"Found initial {current_count} products")
            
        except Exception as e:
            logging.error(f"Agent {agent_num}: Could not find product tiles: {str(e)}")
            return all_products
        
        # Now proceed with scraping the products
        try:
            products = scrape_products_from_page(driver, csv_filename)
            if products:
                all_products.extend(products)
                logging.info(f"Agent {agent_num}: Successfully scraped {len(products)} products")
            
        except Exception as e:
            logging.error(f"Agent {agent_num}: Error during scraping: {str(e)}")
        
        logging.info(f"Agent {agent_num}: Successfully scraped total of {len(all_products)} products")
        
    except Exception as e:
        logging.error(f"Agent {agent_num}: Error during scraping: {str(e)}")
    
    finally:
        try:
            driver.quit()
            logging.info(f"Agent {agent_num}: Browser closed successfully")
        except:
            pass
    
    return all_products

def combine_csv_files(num_agents):
    """Combine CSV files from all agents into one final file with deduplication"""
    dfs = []
    for i in range(num_agents):
        try:
            df = pd.read_csv(f'mk_products_agent_{i}.csv')
            dfs.append(df)
            os.remove(f'mk_products_agent_{i}.csv')  # Clean up individual files
        except FileNotFoundError:
            continue
    
    if dfs:
        # Combine all DataFrames and remove duplicates based on Product URL
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df.drop_duplicates(subset=['Product URL'], keep='first', inplace=True)
        combined_df.to_csv('mk_products.csv', index=False)
        logging.info(f"Combined {len(dfs)} files into mk_products.csv with {len(combined_df)} unique products")

def scrape_mk():
    num_agents = 1  # Number of parallel scrapers
    
    # Create tasks for each agent - now just with start pages
    tasks = [(i, i) for i in range(num_agents)]
    
    # Run agents in parallel
    with ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = [
            executor.submit(scrape_mk_with_agent, start_page, agent_num)
            for start_page, agent_num in tasks
        ]
        
        # Wait for all agents to complete
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logging.error(f"Agent failed: {str(e)}")
    
    # Combine results from all agents
    combine_csv_files(num_agents)

if __name__ == "__main__":
    try:
        scrape_mk()
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
