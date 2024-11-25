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
    total_height = driver.execute_script("return document.body.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")
    current_position = 0
    
    while current_position < total_height:
        # Variable scroll speed and distance
        scroll_amount = random.randint(200, 500)
        scroll_time = random.uniform(500, 1500)  # milliseconds
        current_position = min(current_position + scroll_amount, total_height)
        
        # Smooth scroll with variable speed
        driver.execute_script(f"""
            const start = window.pageYOffset;
            const distance = {current_position} - start;
            const duration = {scroll_time};
            let startTime = null;
            
            function animation(currentTime) {{
                if (startTime === null) startTime = currentTime;
                const timeElapsed = currentTime - startTime;
                const progress = Math.min(timeElapsed / duration, 1);
                
                window.scrollTo(0, start + distance * easeInOutQuad(progress));
                
                if (timeElapsed < duration) {{
                    requestAnimationFrame(animation);
                }}
            }}
            
            function easeInOutQuad(t) {{
                return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            }}
            
            requestAnimationFrame(animation);
        """)
        
        # Random pauses and micro-movements
        time.sleep(random.uniform(0.8, 2.0))
        
        # Sometimes move mouse randomly
        if random.random() < 0.3:
            element = driver.find_element(By.TAG_NAME, "body")
            action = webdriver.ActionChains(driver)
            action.move_to_element_with_offset(element, random.randint(0, 800), random.randint(0, 600))
            action.perform()
            time.sleep(random.uniform(0.1, 0.3))

def scrape_products_from_page(driver, output_file):
    """Scrape products from the current page"""
    products = []
    
    try:
        # Wait for products to be visible and get them
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.grid-tile")))
        product_cards = driver.find_elements(By.CSS_SELECTOR, "li.grid-tile")
        logging.info(f"Found {len(product_cards)} products on page")
        
        if not product_cards:
            return []
            
        for card in product_cards:
            try:
                # Scroll element into view and wait for images to load
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card)
                time.sleep(1)  # Wait for images to start loading
                
                # Extract product details
                try:
                    name = card.find_element(By.CSS_SELECTOR, ".product-infos h2.product-name").text.strip()
                except:
                    logging.warning("Could not get name")
                    continue
                
                try:
                    price = card.find_element(By.CSS_SELECTOR, ".product-price .price-sales").text.strip()
                except:
                    logging.warning("Could not get price")
                    continue
                
                try:
                    link = card.find_element(By.CSS_SELECTOR, "figure.product-image a.thumb-link").get_attribute("href")
                except:
                    logging.warning("Could not get link")
                    continue
                
                # Get images - updated selector and logic
                try:
                    images = []
                    # Wait for images to be present
                    img_elements = WebDriverWait(card, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".thumb-image-wrap img.thumb-img"))
                    )
                    
                    for img in img_elements:
                        # Try srcset first
                        srcset = img.get_attribute("srcset")
                        if srcset and not srcset.endswith('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'):
                            # Parse srcset to get highest resolution URL
                            urls = [url.strip().split(' ')[0] for url in srcset.split(',')]
                            if urls:
                                images.append(urls[-1])  # Get highest resolution URL
                                continue
                                
                        # Try data-srcset if srcset is not available
                        data_srcset = img.get_attribute("data-srcset")
                        if data_srcset and not data_srcset.endswith('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'):
                            urls = [url.strip().split(' ')[0] for url in data_srcset.split(',')]
                            if urls:
                                images.append(urls[-1])
                                continue
                    
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

def scroll_and_load_all_products(driver, wait):
    """Scroll until no more products load"""
    total_products = 0
    no_new_products_count = 0
    max_attempts = 3
    
    while no_new_products_count < max_attempts:
        try:
            # Get current scroll position
            current_position = driver.execute_script("return window.pageYOffset;")
            
            # Scroll in smaller increments
            for _ in range(4):  # Scroll in 4 steps
                # Calculate next scroll position (25% of remaining page height each time)
                scroll_height = driver.execute_script("return document.body.scrollHeight;")
                next_position = current_position + (scroll_height - current_position) / 4
                
                # Smooth scroll to next position
                driver.execute_script(f"""
                    window.scrollTo({{
                        top: {next_position},
                        behavior: 'smooth'
                    }});
                """)
                time.sleep(1)  # Wait for scroll and images to load
                current_position = next_position
            
            time.sleep(2)  # Additional wait for new products to load
            
            # Get current product count
            current_count = len(driver.find_elements(By.CSS_SELECTOR, "li.grid-tile"))
            
            if current_count > total_products:
                total_products = current_count
                no_new_products_count = 0
                logging.info(f"Found {current_count} products")
            else:
                no_new_products_count += 1
                logging.info(f"No new products found, attempt {no_new_products_count}/{max_attempts}")
            
        except Exception as e:
            logging.warning(f"Error during scroll: {str(e)}")
            no_new_products_count += 1
    
    logging.info(f"Finished loading products. Total count: {total_products}")
    return total_products

def scrape_givenchy(url):
    """Main function to scrape Givenchy products"""
    products_data = []
    driver = None
    
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 10)
        
        try:
            driver.get(url)
        except TimeoutException:
            pass
            
        time.sleep(5)
        
        # Check if we're on the right page
        if "givenchy.com" not in driver.current_url:
            logging.error("Redirected away from Givenchy site")
            return products_data
        
        # Load all products by scrolling
        total_products = scroll_and_load_all_products(driver, wait)
        logging.info(f"Found {total_products} total products")
        
        # Wait for images to load
        time.sleep(3)
        
        # Scrape all products
        products = scrape_products_from_page(driver, 'givenchy_women_products.csv')
        if products:
            products_data.extend(products)
            logging.info(f"Successfully scraped {len(products)} products")
        else:
            logging.error("No products found")
            
    except Exception as e:
        logging.error(f"Error during scraping: {str(e)}")
        
    finally:
        if driver:
            driver.quit()
            
    return products_data

if __name__ == "__main__":
    givenchy_url = 'https://www.givenchy.com/us/en-US/women/ready-to-wear/?page=16'
    products = scrape_givenchy(givenchy_url)
    logging.info(f"Total products scraped: {len(products)}")
