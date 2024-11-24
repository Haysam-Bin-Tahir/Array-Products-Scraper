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
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "productCard")))
    
    # Get all product data in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.productCard')).map(item => {
            // Get product details
            const title = item.querySelector('.productCard__content__main__name')?.textContent?.trim() || '';
            const price = item.querySelector('.productCard__content__main__price-container__price p')?.textContent?.trim() || '';
            const url = item.querySelector('a.productCard__image')?.href || '';
            
            // Get both main and hover images
            const mainImage = item.querySelector('.productCard__image__picture__image img')?.src || '';
            const hoverImage = item.querySelector('.productCard__image__picture__imageHover img')?.src || '';
            const images = [mainImage, hoverImage].filter(src => src);
            
            return {
                name: title,
                price: price,
                url: url,
                images: images
            };
        }).filter(item => item.name && item.price && item.url);
    """
    products_data = driver.execute_script(script)
    logging.info(f"Found {len(products_data)} products on page")
    
    # Load existing URLs to avoid duplicates
    existing_urls = set()
    if os.path.exists(csv_filename):
        df = pd.read_csv(csv_filename)
        if 'Gender' not in df.columns:
            df['Gender'] = 'Men'
            df.to_csv(csv_filename, index=False)
        existing_urls = set(df['Product URL'].tolist())
    
    # Process and save new products
    products = []
    for product_data in products_data:
        if product_data['url'] not in existing_urls:
            product = {
                'Gender': 'Men',
                'Name': product_data['name'],
                'Price': product_data['price'].replace('$', '').replace(',', '').strip(),
                'Images': ' | '.join(product_data['images']),
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
    scroll_pause_time = 0.1
    scroll_increment = 1500
    
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
            
            # Get current product count using correct selector
            current_count = len(driver.find_elements(By.CLASS_NAME, "productCard"))
            
            if current_count > total_products:
                total_products = current_count
                bottom_reached_count = 0
                logging.info(f"Found {current_count} products")
            
            # Check if we've hit bottom
            if current_position + viewport_height >= total_height - 50:
                bottom_reached_count += 1
                logging.info(f"Bottom reached {bottom_reached_count}/{required_bottom_hits} times")
                
                if bottom_reached_count < required_bottom_hits:
                    # Scroll up more aggressively
                    scroll_up_position = max(0, current_position - 3000)
                    driver.execute_script(f"window.scrollTo(0, {scroll_up_position});")
                    time.sleep(0.3)
            
        except Exception as e:
            logging.warning(f"Error during scroll: {str(e)}")
            time.sleep(0.2)
            continue
    
    logging.info(f"Finished loading products. Total count: {total_products}")
    return total_products

def scrape_valentino(url):
    """Main function to scrape Valentino products"""
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            driver = setup_driver()
            driver.get(url)
            time.sleep(5)
            
            # Check if we're on the right page
            if "valentino.com" not in driver.current_url:
                logging.error("Redirected away from Valentino site")
                retry_count += 1
                continue
            
            # Try to click either type of View All button
            try:
                # First try the button with data-page-size
                view_all_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "p.vlt-cta-white[data-page-size]"))
                )
                driver.execute_script("arguments[0].click();", view_all_button)
                logging.info("Clicked View All button with data-page-size")
                time.sleep(3)
            except:
                try:
                    # Then try the other View All button
                    view_all_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".categoryListining__load-more__cta-container .vlt-cta-white"))
                    )
                    driver.execute_script("arguments[0].click();", view_all_button)
                    logging.info("Clicked View All button in container")
                    time.sleep(3)
                except Exception as e:
                    logging.warning(f"Could not find or click any View All button: {str(e)}")
            
            wait = WebDriverWait(driver, 1)
            total_products = scroll_and_load_all_products(driver, wait)
            
            if total_products > 0:
                products = scrape_products_from_page(driver, 'valentino_men_products.csv')
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
    valentino_url = 'https://www.valentino.com/en-us/men/ready-to-wear?productcategorylist_675964757=true&productcategorylist_804968256=true&productcategorylist_877364845=true'
    scrape_valentino(valentino_url)
