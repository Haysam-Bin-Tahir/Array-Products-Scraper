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
    """Set up and return a configured Chrome WebDriver with performance optimizations"""
    chrome_options = Options()
    
    # Headless mode
    chrome_options.add_argument('--headless=new')  # New headless mode for Chrome
    
    # Basic automation settings
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--window-size=1920,1080')  # Set window size for headless mode
    
    # Performance optimization arguments
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-translate')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--incognito')
    
    # Additional headless optimizations
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-setuid-sandbox')
    chrome_options.add_argument('--disable-accelerated-2d-canvas')
    
    # Memory optimization
    chrome_options.add_argument('--disk-cache-size=0')
    chrome_options.add_argument('--media-cache-size=0')
    chrome_options.add_argument('--aggressive-cache-discard')
    
    # Page load strategy
    chrome_options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    
    # Preferences for performance
    prefs = {
        'profile.default_content_setting_values.notifications': 2,
        'profile.default_content_setting_values.geolocation': 2,
        'profile.managed_default_content_settings.images': 1,  # 2 to disable images, 1 to enable
        'profile.default_content_setting_values.cookies': 1,
        'profile.managed_default_content_settings.javascript': 1,
        'profile.default_content_setting_values.plugins': 2,
        'profile.default_content_setting_values.popups': 2,
        'profile.default_content_setting_values.auto_select_certificate': 2,
        'profile.default_content_setting_values.mixed_script': 2,
        'profile.default_content_setting_values.media_stream': 2,
        'profile.default_content_setting_values.media_stream_mic': 2,
        'profile.default_content_setting_values.media_stream_camera': 2,
        'profile.default_content_setting_values.protocol_handlers': 2,
        'profile.default_content_setting_values.ppapi_broker': 2,
        'profile.default_content_setting_values.automatic_downloads': 2,
        'profile.default_content_settings.state.flash': 2,
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
    
    # Execute CDP commands for additional optimizations
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    })
    
    # Disable webdriver flag
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Set timeouts
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    
    return driver

def get_product_details(driver, product_url):
    """Get detailed information from a product page"""
    try:
        driver.get(product_url)
        wait = WebDriverWait(driver, 5)
        
        # Wait for main elements to load
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-info-box")))
        
        # Get product name and price in one JavaScript call for better performance
        script = """
            return {
                name: document.querySelector('h1.product-name.product-detail-product-name')?.textContent?.trim() || '',
                price: document.querySelector('.price')?.textContent?.trim() || '',
                description: document.querySelector('.product-detail > p')?.textContent?.trim() || ''
            }
        """
        result = driver.execute_script(script)
        
        name = result['name'] or "Name not available"
        price = result['price'] or "Price not available"
        description = result['description'] or ""
        
        if not price or price == "Price not available":
            try:
                price_element = driver.find_element(By.CSS_SELECTOR, "input.gucciProductPrice")
                price = f"$ {price_element.get_attribute('value')}"
            except:
                logging.warning(f"No price found for {product_url}")
        
        # Get all images in one go using JavaScript
        images_script = """
            return Array.from(document.querySelectorAll('.product-detail-carousel source[data-image-size="standard-retina"]'))
                .map(source => source.srcset)
                .filter(srcset => srcset)
                .map(srcset => srcset.startsWith('http') ? srcset : 'https:' + srcset);
        """
        images = set(driver.execute_script(images_script))
        
        # Log successful extraction
        logging.info(f"Successfully extracted - Name: {name}, Price: {price}")
        
        return {
            'Gender': 'Women',
            'Name': name,
            'Description': description,
            'Price': price,
            'Images': list(images),
            'Product URL': product_url
        }
        
    except Exception as e:
        logging.error(f"Error getting product details from {product_url}: {str(e)}")
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
    wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "product-tiles-grid-item")))
    
    # Get all product URLs and prices in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.product-tiles-grid-item')).map(item => ({
            url: item.querySelector('a.product-tiles-grid-item-link')?.href,
            price: item.querySelector('.product-tiles-grid-item-info p.price span.sale')?.textContent?.trim()
        })).filter(item => item.url);
    """
    products_data = driver.execute_script(script)
    
    logging.info(f"Found {len(products_data)} unique products")
    
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
            product = get_product_details(driver, product_data['url'])
            
            if product and product.get('Images'):
                # If grid price is available, use it
                if product_data.get('price'):
                    product['Price'] = product_data['price']
                
                # Save to CSV
                df = pd.DataFrame([{
                    'Gender': product['Gender'],
                    'Name': product['Name'],
                    'Description': product['Description'],
                    'Price': product['Price'],
                    'Images': ','.join(product['Images']),
                    'Product URL': product['Product URL']
                }])
                
                df.to_csv(csv_filename, mode='a', header=not os.path.exists(csv_filename), index=False)
                products.append(product)
                logging.info(f"Scraped and saved product: {product['Name']} with price {product['Price']}")
            
            # Go back to the product listing page
            driver.execute_script("window.history.go(-1)")
            time.sleep(1)
            
        except Exception as e:
            logging.error(f"Error processing product URL {product_data['url']}: {str(e)}")
            continue
            
    return products

def scrape_gucci_with_agent(start_page, end_page, agent_num):
    base_url = 'https://www.gucci.com/us/en/ca/women/ready-to-wear-for-women-c-women-readytowear'
    logging.info(f"Agent {agent_num}: Starting scrape from page {start_page} to {end_page}")
    all_products = []
    
    # Define CSV filename with agent number
    csv_filename = f'gucci_products_agent_{agent_num}.csv'
    
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 5)
        
        # Scrape assigned pages
        for page_num in range(start_page, end_page):
            page_url = f"{base_url}/{page_num}"
            logging.info(f"Agent {agent_num}: Scraping products from page {page_num}: {page_url}")
            
            driver.get(page_url)
            
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "product-tiles-grid-item"))
            )
            logging.info(f"Agent {agent_num}: Product grid loaded for page {page_num}")
            
            products = scrape_products_from_page(driver, csv_filename)
            all_products.extend(products)
            
            logging.info(f"Agent {agent_num}: Completed page {page_num}, total products: {len(all_products)}")
            time.sleep(1)
        
        logging.info(f"Agent {agent_num}: Successfully scraped {len(all_products)} products")
        
    except Exception as e:
        logging.error(f"Agent {agent_num}: Error during scraping: {e}")
        raise
    
    finally:
        try:
            driver.quit()
            logging.info(f"Agent {agent_num}: Browser closed successfully")
        except:
            pass
    
    return all_products

def combine_csv_files(num_agents):
    """Combine CSV files from all agents into one final file"""
    dfs = []
    for i in range(num_agents):
        try:
            df = pd.read_csv(f'gucci_products_agent_{i}.csv')
            dfs.append(df)
            os.remove(f'gucci_products_agent_{i}.csv')  # Clean up individual files
        except FileNotFoundError:
            continue
    
    if dfs:
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df.to_csv('gucci_products.csv', index=False)
        logging.info(f"Combined {len(dfs)} files into gucci_products.csv")

def scrape_gucci():
    num_agents = 4  # Number of parallel scrapers
    total_pages = 13  # Total number of pages to scrape
    
    # Calculate pages per agent
    pages_per_agent = math.ceil(total_pages / num_agents)
    
    # Create tasks for each agent
    tasks = []
    for i in range(num_agents):
        start_page = i * pages_per_agent
        end_page = min((i + 1) * pages_per_agent, total_pages)
        tasks.append((start_page, end_page, i))
    
    # Run agents in parallel
    with ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = [
            executor.submit(scrape_gucci_with_agent, start, end, agent_num)
            for start, end, agent_num in tasks
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
        scrape_gucci()
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
