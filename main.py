import logging
import random
import time
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO)

def setup_driver():
    """Set up and return a configured Chrome WebDriver"""
    chrome_options = Options()
    
    # Basic options
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Disable GPU completely
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-gpu-sandbox')
    chrome_options.add_argument('--disable-gpu-compositing')
    chrome_options.add_argument('--disable-gl-drawing-for-tests')
    
    # Memory and performance options
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-zygote')
    chrome_options.add_argument('--disable-setuid-sandbox')
    chrome_options.add_argument('--disable-accelerated-2d-canvas')
    chrome_options.add_argument('--disable-accelerated-jpeg-decoding')
    chrome_options.add_argument('--disable-accelerated-mjpeg-decode')
    chrome_options.add_argument('--disable-accelerated-video-decode')
    chrome_options.add_argument('--disable-webgl')
    chrome_options.add_argument('--disable-3d-apis')
    
    # Connection options
    chrome_options.add_argument('--disable-ipc-flooding-protection')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    
    # Additional stability options
    chrome_options.add_argument('--disable-features=NetworkService')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--disable-breakpad')
    chrome_options.add_argument('--disable-component-update')
    
    # Window options
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--hide-scrollbars')
    
    # Additional experimental options
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Increase timeouts in prefs
    chrome_options.add_experimental_option('prefs', {
        'profile.default_content_setting_values.images': 1,
        'profile.managed_default_content_settings.images': 1,
        'profile.managed_default_content_settings.javascript': 1,
        'profile.managed_default_content_settings.cookies': 1,
        'profile.default_content_settings.cookies': 1,
        'network.http.max-connections-per-server': 5
    })
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Set various timeouts
    driver.set_page_load_timeout(120)
    driver.set_script_timeout(120)
    driver.implicitly_wait(20)
    
    return driver

def scrape_products_from_page(driver, csv_filename):
    """Extract products from the current page and save in real-time"""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-grid-product")))
    
    # Get all product data in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.product-grid-product')).map(item => {
            // Get product details
            const title = item.querySelector('.product-grid-product-info__name h2')?.textContent?.trim() || '';
            const price = item.querySelector('.price-current__amount .money-amount__main')?.textContent?.trim() || '';
            const url = item.querySelector('.product-link')?.href || '';
            const image = item.querySelector('.media-image__image')?.src || '';
            
            return {
                name: title,
                price: price,
                url: url,
                image: image
            };
        }).filter(item => item.name && item.price && item.url);
    """
    products_data = driver.execute_script(script)
    logging.info(f"Found {len(products_data)} products on page")
    
    # Load existing data and add gender if needed
    if os.path.exists(csv_filename):
        df = pd.read_csv(csv_filename)
        if 'Gender' not in df.columns:
            df['Gender'] = 'Men'  # Add gender column to existing data
            df.to_csv(csv_filename, index=False)
        existing_urls = set(df['Product URL'].tolist())
    else:
        existing_urls = set()
    
    # Process and save new products
    products = []
    for product_data in products_data:
        if product_data['url'] not in existing_urls:
            product = {
                'Gender': 'Women',  # Add gender for new products
                'Name': product_data['name'],
                'Price': product_data['price'].replace('$', '').replace(',', '').strip(),
                'Image': product_data['image'],
                'Product URL': product_data['url']
            }
            
            # Save to CSV immediately
            df = pd.DataFrame([product])
            df.to_csv(csv_filename, mode='a', header=not os.path.exists(csv_filename), index=False)
            products.append(product)
            existing_urls.add(product_data['url'])
            
    return products

def scroll_and_load_all_products(driver, wait):
    """Scroll smoothly until absolute bottom is reached multiple times"""
    total_products = 0
    bottom_reached_count = 0
    required_bottom_hits = 3
    scroll_pause_time = 0.15
    scroll_increment = 900
    
    while bottom_reached_count < required_bottom_hits:
        try:
            # Get current position
            current_position = driver.execute_script("return window.pageYOffset")
            total_height = driver.execute_script("return document.body.scrollHeight")
            viewport_height = driver.execute_script("return window.innerHeight")
            
            # Smooth scroll down
            next_position = current_position + scroll_increment
            driver.execute_script(f"window.scrollTo(0, {next_position});")
            time.sleep(scroll_pause_time)
            
            # Get current product count
            current_count = len(driver.find_elements(By.CLASS_NAME, "product-grid-product"))
            
            if current_count > total_products:
                total_products = current_count
                bottom_reached_count = 0
                logging.info(f"Found {current_count} products")
            
            # Check if we've hit bottom
            if current_position + viewport_height >= total_height - 50:
                bottom_reached_count += 1
                logging.info(f"Bottom reached {bottom_reached_count}/{required_bottom_hits} times")
                
                if bottom_reached_count < required_bottom_hits:
                    scroll_up_position = max(0, current_position - 2000)
                    driver.execute_script(f"window.scrollTo(0, {scroll_up_position});")
                    time.sleep(0.5)
            
        except Exception as e:
            logging.warning(f"Error during scroll: {str(e)}")
            time.sleep(0.3)
            continue
    
    logging.info(f"Finished loading products. Total count: {total_products}")
    return total_products

def scrape_zara(url):
    """Main function to scrape Zara products"""
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            driver = setup_driver()
            driver.get(url)
            time.sleep(5)
            
            # Check if we're on the right page
            if "zara.com" not in driver.current_url:
                logging.error("Redirected away from Zara site")
                retry_count += 1
                continue
            
            wait = WebDriverWait(driver, 10)
            total_products = scroll_and_load_all_products(driver, wait)
            
            if total_products > 0:
                products = scrape_products_from_page(driver, 'zara_women_products.csv')
                logging.info(f"Successfully scraped {len(products)} products")
                break
            else:
                logging.error("No products found")
                retry_count += 1
                
        except Exception as e:
            logging.error(f"Error during scraping (attempt {retry_count + 1}/{max_retries}): {str(e)}")
            retry_count += 1
            time.sleep(random.uniform(10, 15))
            
        finally:
            try:
                driver.quit()
            except:
                pass
    
    if retry_count == max_retries:
        logging.error("Failed to scrape after maximum retries")

if __name__ == "__main__":
    zara_url = 'https://www.zara.com/us/en/woman-skirts-l1299.html?v1=2420454'  # Replace with the Zara URL you want to scrape
    scrape_zara(zara_url)
