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
from selenium.common.exceptions import TimeoutException

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

def scrape_products_from_page(driver, output_file):
    """Scrape products from the current page"""
    products = []
    
    try:
        # Wait for products to be visible and get them
        product_cards = driver.find_elements(By.CSS_SELECTOR, "article.product-card")
        logging.info(f"Found {len(product_cards)} products on page")
        
        if not product_cards:
            return []
            
        for card in product_cards:
            try:
                # Extract product details
                name = card.find_element(By.CSS_SELECTOR, ".product-card__name").text.strip()
                price = card.find_element(By.CSS_SELECTOR, ".product-card__price").text.strip()
                link = card.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                
                # Get images
                try:
                    # Try to get both main and hover images
                    images = card.find_elements(By.CSS_SELECTOR, "img.product-card__picture")
                    image_urls = []
                    
                    for img in images:
                        # Get srcset attribute which contains high-res images
                        srcset = img.get_attribute("srcset")
                        if srcset:
                            # Get the first (main) image URL from srcset
                            image_url = srcset.split(',')[0].split(' ')[0]
                            if image_url and not image_url.endswith('placeholder.svg'):
                                image_urls.append(image_url)
                    
                    # Remove duplicates while preserving order
                    image_urls = list(dict.fromkeys(image_urls))
                    
                except Exception as img_error:
                    logging.warning(f"Error getting images: {str(img_error)}")
                    image_urls = []
                
                product = {
                    'Gender': 'Men',
                    'name': name,
                    'price': price,
                    'link': link,
                    'main_image': image_urls[0] if image_urls else '',
                    'hover_image': image_urls[1] if len(image_urls) > 1 else ''
                }
                products.append(product)
                
            except Exception as e:
                logging.warning(f"Error scraping individual product: {str(e)}")
                continue
        
        # Save to CSV if we have products
        if products:
            df = pd.DataFrame(products)
            
            # If file exists, append without header
            if os.path.exists(output_file):
                df.to_csv(output_file, mode='a', header=False, index=False)
            else:
                df.to_csv(output_file, index=False)
                
            logging.info(f"Saved {len(products)} products to {output_file}")
            
        return products
        
    except Exception as e:
        logging.error(f"Error in scrape_products_from_page: {str(e)}")
        return []

def scroll_and_load_all_products(driver, wait):
    """Scroll smoothly until absolute bottom is reached multiple times"""
    total_products = 0
    bottom_reached_count = 0
    required_bottom_hits = 1  # Number of times we need to hit bottom
    scroll_pause_time = 0.5  # Increased pause time
    scroll_increment = 500  # Smaller increments for smoother scrolling
    
    while bottom_reached_count < required_bottom_hits:
        try:
            # Get current position
            current_position = driver.execute_script("return window.pageYOffset")
            total_height = driver.execute_script("return document.body.scrollHeight")
            viewport_height = driver.execute_script("return window.innerHeight")
            
            # Smooth scroll down
            next_position = min(current_position + scroll_increment, total_height - viewport_height)
            driver.execute_script(f"window.scrollTo({{top: {next_position}, behavior: 'smooth'}});")
            time.sleep(scroll_pause_time)
            
            # Wait for images to load
            try:
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "img.product-card__picture[srcset*='prada']")) > 0)
            except:
                pass
            
            # Get current product count
            current_count = len(driver.find_elements(By.CSS_SELECTOR, "article.product-card"))
            
            if current_count > total_products:
                total_products = current_count
                bottom_reached_count = 0
                logging.info(f"Found {current_count} products")
            
            # Check if we've hit bottom
            if current_position + viewport_height >= total_height - 50:
                bottom_reached_count += 1
                logging.info(f"Bottom reached {bottom_reached_count}/{required_bottom_hits} times")
                
                if bottom_reached_count < required_bottom_hits:
                    # Scroll back up to trigger more loading
                    driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
                    time.sleep(1)
            
        except Exception as e:
            logging.warning(f"Error during scroll: {str(e)}")
            time.sleep(0.5)
            continue
    
    # Final scroll to top
    driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
    time.sleep(1)
    
    logging.info(f"Finished loading products. Total count: {total_products}")
    return total_products

def scrape_prada(base_url):
    """Main function to scrape Prada products"""
    retry_count = 0
    max_retries = 3
    page_num = 1
    max_pages = 23
    products_data = []
    driver = None
    
    try:
        # Initialize driver once
        driver = setup_driver()
        wait = WebDriverWait(driver, 10)
        driver.set_page_load_timeout(5)
        
        while retry_count < max_retries and page_num <= max_pages:
            try:
                url = f"{base_url}/page/{page_num}"
                logging.info(f"Scraping page {page_num}: {url}")
                
                try:
                    driver.get(url)
                except TimeoutException:
                    pass
                    
                time.sleep(5)
                
                # Check if we're on the right page
                if "prada.com" not in driver.current_url:
                    logging.error(f"Redirected away from Prada site on page {page_num}")
                    retry_count += 1
                    continue
                
                # Scroll to load all images
                total_products = scroll_and_load_all_products(driver, wait)
                logging.info(f"Found {total_products} products after scrolling")
                
                # Wait a bit for images to finish loading
                time.sleep(3)
                    
                # Scrape products from current page
                try:
                    products = scrape_products_from_page(driver, 'prada_men_products.csv')
                    if products:
                        products_data.extend(products)
                        logging.info(f"Successfully scraped {len(products)} products from page {page_num}")
                        page_num += 1  # Move to next page only on success
                        retry_count = 0  # Reset retry count on success
                    else:
                        logging.error(f"No products found on page {page_num}")
                        retry_count += 1
                except Exception as e:
                    logging.error(f"Error scraping page {page_num}: {str(e)}")
                    retry_count += 1
                    
            except Exception as e:
                logging.error(f"Error during scraping page {page_num} (attempt {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                time.sleep(random.uniform(10, 15))
                
            # Add delay between pages
            time.sleep(random.uniform(3, 5))
        
    finally:
        try:
            if driver:
                driver.quit()
        except:
            pass
    
    if retry_count == max_retries:
        logging.error("Failed to scrape after maximum retries")
        
    return products_data

if __name__ == "__main__":
    prada_url = 'https://www.prada.com/us/en/mens/ready-to-wear/c/10130US'
    products_data = scrape_prada(prada_url)
