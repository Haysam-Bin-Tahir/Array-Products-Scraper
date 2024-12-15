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
    chrome_options.add_argument('--disable-gpu')
    
    # Disable performance monitoring and logging
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-breakpad')
    chrome_options.add_argument('--disable-component-extensions-with-background-pages')
    chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
    chrome_options.add_argument('--disable-ipc-flooding-protection')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
    chrome_options.add_argument('--force-color-profile=srgb')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--no-first-run')
    
    # Memory management
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-software-rasterizer')
    
    # Window options
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    
    # Disable logging
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--silent')
    
    # Performance preferences
    prefs = {
        'profile.default_content_setting_values.images': 1,
        'profile.managed_default_content_settings.images': 1,
        'profile.managed_default_content_settings.javascript': 1,
        'profile.default_content_settings.cookies': 1,
        'profile.managed_default_content_settings.cookies': 1,
        'profile.managed_default_content_settings.plugins': 1,
        'profile.managed_default_content_settings.popups': 1,
        'profile.managed_default_content_settings.geolocation': 2,
        'profile.managed_default_content_settings.notifications': 2,
        'profile.default_content_settings.automatic_downloads': 1,
        'profile.default_content_settings.mixed_script': 1,
        'profile.default_content_settings.media_stream': 1,
        'profile.default_content_settings.media_stream_mic': 1,
        'profile.default_content_settings.media_stream_camera': 1,
        'profile.default_content_settings.protocol_handlers': 1,
        'profile.default_content_settings.ppapi_broker': 1,
        'profile.default_content_settings.automatic_downloads': 1,
        'profile.default_content_settings.midi_sysex': 1,
        'profile.default_content_settings.push_messaging': 1,
        'profile.default_content_settings.ssl_cert_decisions': 1,
        'profile.default_content_settings.metro_switch_to_desktop': 1,
        'profile.default_content_settings.protected_media_identifier': 1,
        'profile.default_content_settings.site_engagement': 1,
        'profile.default_content_settings.durable_storage': 1
    }
    chrome_options.add_experimental_option('prefs', prefs)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logging.error(f"Error setting up Chrome driver: {str(e)}")
        raise

def add_random_delays():
    """Add more varied random delays"""
    delay = random.uniform(2, 5)
    micro_delay = random.uniform(0, 0.5)
    time.sleep(delay + micro_delay)

def human_like_scroll(driver):
    """More realistic human-like scrolling"""
    try:
        # Get initial scroll height
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        current_position = 0
        
        while current_position < total_height:
            # Variable scroll speed and distance
            scroll_amount = random.randint(600, 900)
            current_position = min(current_position + scroll_amount, total_height)
            
            # Simple smooth scroll
            driver.execute_script(f"window.scrollTo({{top: {current_position}, behavior: 'smooth'}})")

            # Update total height as it might change due to dynamic loading
            total_height = driver.execute_script("return document.body.scrollHeight")
            
    except Exception as e:
        logging.error(f"Error during scroll: {str(e)}")

def scrape_products_from_page(driver, output_file):
    """Scrape products from the current page"""
    products = []
    processed_urls = set()  # Keep track of processed URLs to avoid duplicates
    
    try:
        # Wait for products to be visible and get them
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product.js-product")))
        product_cards = driver.find_elements(By.CSS_SELECTOR, "div.product.js-product")  # Changed to target the product container
        logging.info(f"Found {len(product_cards)} products on page")
        
        if not product_cards:
            return []
            
        for card in product_cards:
            try:
                # Get link first to check for duplicates
                try:
                    link = card.find_element(By.CSS_SELECTOR, "div.product-tile a").get_attribute("href")
                    if link in processed_urls:  # Skip if we've already processed this URL
                        continue
                    processed_urls.add(link)
                except:
                    logging.warning("Could not get link")
                    continue
                
                # Scroll element into view and wait for images to load
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card)
                time.sleep(1)  # Wait for images to start loading
                
                # Extract product details
                try:
                    # Get name and material
                    name_elem = card.find_element(By.CSS_SELECTOR, "p.link.small").text.strip()
                    try:
                        material = card.find_element(By.CSS_SELECTOR, "p.text-primary.plp-material").text.strip()
                        name = f"{name_elem} - {material}"
                    except:
                        name = name_elem
                except:
                    logging.warning("Could not get name")
                    continue
                
                try:
                    # Get price - updated selector to match exact structure
                    price_elem = card.find_element(By.CSS_SELECTOR, "div.price span.value")
                    price = price_elem.text.strip()
                    if not price:  # If price is empty, try getting it from the parent
                        price = price_elem.get_attribute('textContent').strip()
                except:
                    logging.warning("Could not get price")
                    continue
                
                # Get images - updated selector and logic for Loro Piana
                try:
                    images = []
                    # Get main and hover images
                    img_elements = card.find_elements(By.CSS_SELECTOR, ".lazy__wrapper img.lazy__img")
                    
                    for img in img_elements:
                        # Try data-src first (original high-res image)
                        data_src = img.get_attribute("data-src")
                        if data_src and not data_src.endswith('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'):
                            # Remove _SMALL from URL to get higher resolution
                            high_res_url = data_src.replace('_SMALL.jpg', '.jpg')
                            images.append(high_res_url)
                            continue
                            
                        # Try src as fallback
                        src = img.get_attribute("src")
                        if src and not src.endswith('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'):
                            # Remove _SMALL from URL to get higher resolution
                            high_res_url = src.replace('_SMALL.jpg', '.jpg')
                            images.append(high_res_url)
                    
                    # Also get color swatch image if available
                    try:
                        swatch_img = card.find_element(By.CSS_SELECTOR, ".swatch-plp.color-value img.d-block")
                        swatch_src = swatch_img.get_attribute("src")
                        if swatch_src and not swatch_src.endswith('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'):
                            high_res_url = swatch_src.replace('_SMALL.jpg', '.jpg')
                            images.append(high_res_url)
                    except:
                        pass
                    
                    # Remove duplicates while preserving order
                    images = list(dict.fromkeys(images))
                    
                except Exception as img_error:
                    logging.warning(f"Error getting images: {str(img_error)}")
                    images = []
                
                if name and price and link:  # Only add if we have all required fields
                    product = {
                        'Gender': 'Women',  # Adjust based on the URL being scraped
                        'Name': name,
                        'Price': price.replace('$', '').replace(',', '').strip(),
                        'Images': ' | '.join(images),
                        'Product URL': link
                    }
                    products.append(product)
                    logging.info(f"Scraped product: {name} with {len(images)} images")
                else:
                    logging.warning(f"Missing required fields - Name: {bool(name)}, Price: {bool(price)}, Link: {bool(link)}")
                
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
        else:
            logging.warning("No products were successfully scraped")
            
        return products
        
    except Exception as e:
        logging.error(f"Error in scrape_products_from_page: {str(e)}")
        return []

def load_all_products(driver, wait):
    """Load all products by scrolling and clicking the load more button"""
    try:
        previous_height = 0
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            # Get current scroll height
            current_height = driver.execute_script("return document.body.scrollHeight")
            
            # If height hasn't changed after scrolling, try to find and click the button
            if current_height == previous_height:
                try:
                    # Try to find the "View more" button
                    load_more_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.ais-InfiniteHits-loadMore"))
                    )
                    
                    # Scroll to button
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                    time.sleep(2)
                    
                    # Click using JavaScript
                    driver.execute_script("arguments[0].click();", load_more_button)
                    logging.info("Clicked 'View more' button")
                    
                    # Wait for new products to load
                    time.sleep(5)
                    retry_count = 0  # Reset retry count after successful click
                    
                except TimeoutException:
                    retry_count += 1
                    logging.info(f"No more 'View more' button found (attempt {retry_count}/{max_retries})")
                    if retry_count >= max_retries:
                        logging.info("Finished loading products")
                        break
            else:
                retry_count = 0  # Reset retry count if height changed
            
            # Scroll down
            human_like_scroll(driver)
            time.sleep(2)
            
            # Update previous height
            previous_height = current_height
            
    except Exception as e:
        logging.error(f"Error while loading products: {str(e)}")
    
    # Get final product count
    total_products = len(driver.find_elements(By.CSS_SELECTOR, "div.product.js-product"))
    logging.info(f"Finished loading all products. Total count: {total_products}")
    return total_products

def scrape_loropiana(base_url):
    """Main function to scrape Loro Piana products"""
    products_data = []
    driver = None
    page = 1
    max_retries = 3  # Maximum number of retries per page
    
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 10)
        
        while True:  # Continue until no more products found
            url = f"{base_url}?page={page}"
            logging.info(f"Scraping page {page}: {url}")
            
            retry_count = 0
            success = False
            
            # Retry logic for HTTP2 errors
            while retry_count < max_retries and not success:
                try:
                    # Quit and reinitialize driver on retry
                    if retry_count > 0:
                        driver.quit()
                        driver = setup_driver()
                        wait = WebDriverWait(driver, 10)
                    
                    driver.get(url)
                    time.sleep(5)  # Wait for page load
                    
                    # Check if we're on the right page
                    if "loropiana.com" not in driver.current_url:
                        logging.error("Redirected away from Loro Piana site")
                        return products_data
                    
                    # Check if there are products on the page
                    products_present = wait.until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.product.js-product"))
                    )
                    
                    if not products_present:
                        logging.info(f"No products found on page {page}, ending pagination")
                        return products_data
                        
                    success = True
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        logging.error(f"Failed to load page {page} after {max_retries} attempts: {str(e)}")
                        return products_data
                    logging.warning(f"Error on attempt {retry_count}, retrying: {str(e)}")
                    time.sleep(5)  # Wait before retry
                    continue
            
            if not success:
                break
            
            # Wait for images to load
            time.sleep(3)
            
            # Scroll page to load all images
            human_like_scroll(driver)
            time.sleep(2)
            
            # Scrape products from current page
            products = scrape_products_from_page(driver, 'loropiana_women_products.csv')
            if products:
                products_data.extend(products)
                logging.info(f"Successfully scraped {len(products)} products from page {page}")
            else:
                logging.warning(f"No products found on page {page}, ending pagination")
                break
            
            # Move to next page
            page += 1
            
            # Add a longer delay between pages
            time.sleep(random.uniform(8, 12))
            
    except Exception as e:
        logging.error(f"Error during scraping: {str(e)}")
        
    finally:
        if driver:
            driver.quit()
            
    logging.info(f"Finished scraping all pages. Total products: {len(products_data)}")
    return products_data

if __name__ == "__main__":
    loropiana_base_url = 'https://us.loropiana.com/en/c/woman'
    products = scrape_loropiana(loropiana_base_url)
    logging.info(f"Total products scraped: {len(products)}")
