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
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-info-panel__title")))
            
            # Get product details in one JavaScript call
            script = """
                try {
                    return {
                        name: document.querySelector('.product-info-panel__title span')?.textContent?.trim() || '',
                        price: document.querySelector('.product-info-panel__price')?.textContent?.trim() || '',
                        color: document.querySelector('.product-swatches-panel__description span')?.getAttribute('title')?.trim() || '',
                        details: Array.from(document.querySelectorAll('.product-details-accordion__description span'))
                            .map(span => span.textContent.trim())
                            .join(' | ') || ''
                    };
                } catch (e) {
                    return {
                        name: '',
                        price: '',
                        color: '',
                        details: ''
                    };
                }
            """
            result = driver.execute_script(script)
            
            # Try to get all colors
            try:
                # Click color selector if it exists
                color_button = driver.find_element(By.CLASS_NAME, "product-swatches-panel")
                color_button.click()
                time.sleep(1)
                
                # Get all color names
                colors_script = """
                    return Array.from(document.querySelectorAll('.sheet-container-image-item__title span'))
                        .map(el => el.textContent.trim())
                        .join(', ');
                """
                colors = driver.execute_script(colors_script)
                result['color'] = colors
            except:
                pass
            
            # Get sizes by clicking size selector and getting from modal
            try:
                # Click size selector chevron icon
                size_button = driver.find_element(By.CLASS_NAME, "transactional-picker__icon-container")
                driver.execute_script("arguments[0].click();", size_button)
                time.sleep(1)
                
                # Get sizes from modal
                sizes_script = """
                    return Array.from(document.querySelectorAll('.size-picker__size-box'))
                        .map(box => ({
                            size: box.getAttribute('value'),
                            available: !box.classList.contains('size-picker__size-box--muted')
                        }));
                """
                sizes = driver.execute_script(sizes_script)
                
                # Format sizes data
                sizes_info = []
                for size in sizes:
                    sizes_info.append(f"{size['size']}({'In Stock' if size['available'] else 'Out of Stock'})")
                sizes_str = ', '.join(sizes_info)
                result['sizes'] = sizes_str
                
                # Close modal if it exists
                try:
                    close_button = driver.find_element(By.CLASS_NAME, "sheet-container-header__close")
                    driver.execute_script("arguments[0].click();", close_button)
                    time.sleep(1)
                except:
                    pass
                
            except Exception as e:
                logging.warning(f"Error getting sizes: {str(e)}")
                result['sizes'] = ''
            
            # Get images with error handling
            images_script = """
                try {
                    return Array.from(document.querySelectorAll('.desktop-product-gallery__image__picture source'))
                        .map(source => {
                            let srcset = source.getAttribute('srcset') || source.getAttribute('data-srcset');
                            if (!srcset) return null;
                            // Get the largest image URL from srcset
                            let urls = srcset.split(',')
                                .map(s => s.trim().split(' ')[0])
                                .filter(url => url.includes('3000'));
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
            color = result['color'].strip()
            sizes = result.get('sizes', '')
            details = result.get('details', '').strip()
            
            # Verify we got at least some basic data
            if not name or not price:
                raise Exception("Failed to extract basic product information")
            
            return {
                'Gender': gender,
                'Name': name,
                'Color': color,
                'Sizes': sizes,
                'Price': price,
                'Details': details,
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

def scroll_and_click_view_more(driver, wait):
    """Scroll and click View More button until no more products load"""
    last_product_count = 0
    no_new_products_count = 0
    max_attempts_without_new = 5
    
    while True:
        # Get current product count
        current_count = len(driver.find_elements(By.CLASS_NAME, "product-listing-shelf__product-card"))
        logging.info(f"Current product count: {current_count}")
        
        if current_count == last_product_count:
            no_new_products_count += 1
            logging.info(f"No new products found, attempt {no_new_products_count}/{max_attempts_without_new}")
            
            if no_new_products_count >= max_attempts_without_new:
                logging.info("Reached maximum attempts without new products")
                break
        else:
            no_new_products_count = 0
            last_product_count = current_count
            logging.info("Found new products, continuing to scroll...")
        
        # Scroll down in smaller increments
        viewport_height = driver.execute_script("return window.innerHeight")
        current_scroll = driver.execute_script("return window.pageYOffset")
        
        # Scroll by 75% of viewport height for smoother loading
        scroll_amount = current_scroll + (viewport_height * 0.75)
        driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
        time.sleep(2)
        
        # Try to find and click View More button
        try:
            view_more = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "product-listing-shelf__view-more-new"))
            )
            logging.info("Found View More button, clicking...")
            driver.execute_script("arguments[0].click();", view_more)
            time.sleep(3)  # Wait longer after clicking
            
            # Scroll back up slightly to trigger lazy loading
            driver.execute_script(f"window.scrollTo(0, {max(0, scroll_amount - 200)});")
            time.sleep(1)
            
            # Then scroll back down
            driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
            time.sleep(1)
            
        except Exception as e:
            logging.info(f"No View More button found or error clicking it: {str(e)}")
            
            # If no button, try scrolling to absolute bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # Add random delay between actions
        time.sleep(random.uniform(1, 2))
        
        # Safety check - if we've loaded a lot of products, verify the count
        if current_count > 80:
            # Scroll back to top and then bottom to ensure all products are loaded
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Recheck product count
            final_count = len(driver.find_elements(By.CLASS_NAME, "product-listing-shelf__product-card"))
            if final_count > current_count:
                last_product_count = final_count
                no_new_products_count = 0
                logging.info(f"Found more products after full scroll: {final_count}")
    
    logging.info(f"Finished loading products. Total count: {current_count}")
    return current_count

def scrape_products_from_page(driver, csv_filename, gender):
    """Extract products from the current page and save in real-time"""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-listing-shelf__product-card")))
    
    # Get all product URLs in one JavaScript call
    script = """
        return Array.from(document.querySelectorAll('.product-listing-shelf__product-card'))
            .map(item => ({
                url: item.querySelector('a')?.href,
                price: item.querySelector('.product-card-v2-price__current')?.textContent?.trim()
            }))
            .filter(item => item.url);
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
            
            product = get_product_details(driver, product_data['url'], gender)
            
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

def scrape_burberry_category(gender, base_url, csv_filename):
    """Scrape a specific Burberry category (men/women) and save to dedicated CSV"""
    logging.info(f"Starting Burberry {gender}'s scraper")
    
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
            if "burberry.com" not in driver.current_url:
                logging.error(f"{gender}: Redirected away from Burberry site")
                retry_count += 1
                continue
            
            # Wait for initial products with longer timeout
            wait = WebDriverWait(driver, 45)
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-listing-shelf__product-card")))
            except:
                logging.error(f"{gender}: Products not found on page")
                retry_count += 1
                continue
            
            # Add random delay before scrolling
            time.sleep(random.uniform(3, 5))
            
            # Scroll and click View More until all products are loaded
            scroll_and_click_view_more(driver, wait)
            
            # Scrape products
            products = scrape_products_from_page(driver, csv_filename, gender)
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

def scrape_burberry():
    """Main function to scrape both men's and women's Burberry products sequentially"""
    men_base_url = 'https://us.burberry.com/l/mens-clothing/'
    women_base_url = 'https://us.burberry.com/l/womens-clothing/'
    
    # Scrape men's products first
    try:
        logging.info("Starting men's scraping...")
        scrape_burberry_category("Men", men_base_url, 'burberry_men_products.csv')
        logging.info("Men's scraping completed")
    except Exception as e:
        logging.error(f"Error in men's scraper: {str(e)}")
    
    # Add delay between categories
    time.sleep(random.uniform(10, 15))
    
    # Then scrape women's products
    try:
        logging.info("Starting women's scraping...")
        scrape_burberry_category("Women", women_base_url, 'burberry_women_products.csv')
        logging.info("Women's scraping completed")
    except Exception as e:
        logging.error(f"Error in women's scraper: {str(e)}")

if __name__ == "__main__":
    try:
        scrape_burberry()
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
