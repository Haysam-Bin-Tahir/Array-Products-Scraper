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
    """Set up and return a configured Chrome WebDriver with enhanced anti-bot measures"""
    chrome_options = Options()
    
    # Enhanced anti-bot measures
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # More realistic user agents with full browser details
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0'
    ]
    chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    # Add more realistic browser characteristics
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--disable-translate')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--start-maximized')
    
    # Add timezone and geolocation
    chrome_options.add_argument('--timezone=America/New_York')
    chrome_options.add_argument('--geolocation=40.7128,-74.0060')  # NYC coordinates
    
    # Add language and locale settings
    chrome_options.add_argument('--lang=en-US')
    chrome_options.add_argument('--accept-lang=en-US,en;q=0.9')
    
    # Add headers
    chrome_options.add_argument('--accept=text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    chrome_options.add_argument('--accept-encoding=gzip, deflate, br')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Execute CDP commands to mask webdriver and add more browser fingerprinting
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            // Overwrite the 'webdriver' property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Add language and platform details
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // Add plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return [
                        {name: 'Chrome PDF Plugin'},
                        {name: 'Chrome PDF Viewer'},
                        {name: 'Native Client'}
                    ];
                }
            });
            
            // Add chrome object
            window.chrome = {
                runtime: {},
                webstore: {},
                app: {
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    },
                    getDetails: function() {},
                    getIsInstalled: function() {},
                    installState: function() {},
                    isInstalled: false,
                    runningState: function() {}
                }
            };
            
            // Add permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        '''
    })
    
    # Add cookies
    driver.execute_cdp_cmd('Network.enable', {})
    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
        'headers': {
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1'
        }
    })
    
    return driver

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
        product_cards = driver.find_elements(By.CSS_SELECTOR, "div.js-product-tile-main-link")
        logging.info(f"Found {len(product_cards)} products on page")
        
        if not product_cards:
            return []
            
        for card in product_cards:
            try:
                # Extract product details
                name = card.find_element(By.CSS_SELECTOR, ".js-product-tile-title a").text.strip()
                
                # Get price (handle both sale and regular prices)
                try:
                    price = card.find_element(By.CSS_SELECTOR, ".sales-price .nowrap").text.strip()
                except:
                    try:
                        price = card.find_element(By.CSS_SELECTOR, ".standard-price .nowrap").text.strip()
                    except:
                        price = ""
                
                link = card.find_element(By.CSS_SELECTOR, ".js-product-tile-link").get_attribute("href")
                
                # Get images
                try:
                    images = []
                    # Get all images from infinite slider
                    img_elements = card.find_elements(By.CSS_SELECTOR, ".infinite-slider-slide img")
                    for img in img_elements:
                        src = img.get_attribute("src")
                        if src and "lacoste.com" in src and "placeholder" not in src:
                            # Get highest resolution image by modifying URL parameters
                            src = src.replace("imwidth=135", "imwidth=1000")
                            images.append(src)
                    
                    # Remove duplicates while preserving order
                    images = list(dict.fromkeys(images))
                    
                except Exception as img_error:
                    logging.warning(f"Error getting images: {str(img_error)}")
                    images = []
                
                product = {
                    'Gender': 'Men',
                    'Name': name,
                    'Price': price.replace('$', '').replace(',', '').strip(),
                    'Images': ' | '.join(images),
                    'Product URL': link
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

def scroll_and_wait_for_images(driver):
    """Scroll to bottom and ensure images are loaded"""
    try:
        # Scroll to bottom smoothly
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        current_position = 0
        
        while current_position < total_height:
            # Scroll in smaller increments
            scroll_amount = 300
            current_position = min(current_position + scroll_amount, total_height)
            driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(0.3)  # Short pause between scrolls
            
            # Update total height as it might change
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height > total_height:
                total_height = new_height
        
        # Wait for images to load
        time.sleep(2)
        
        # Scroll back to top
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
    except Exception as e:
        logging.error(f"Error during scrolling: {str(e)}")

def scrape_lacoste(base_url):
    """Main function to scrape Lacoste products"""
    page_num = 1
    products_data = []
    driver = None
    
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 10)
        
        while True:  # Keep going until no products found
            url = f"{base_url}?page={page_num}"
            logging.info(f"Scraping page {page_num}: {url}")
            
            try:
                driver.get(url)
                time.sleep(3)  # Wait for initial load
                
                # Scroll and wait for images to load
                scroll_and_wait_for_images(driver)
                
                # Now scrape products
                products = scrape_products_from_page(driver, 'lacoste_women_products.csv')
                
                if not products:
                    logging.info(f"No products found on page {page_num}, ending scrape")
                    break
                    
                products_data.extend(products)
                logging.info(f"Successfully scraped {len(products)} products from page {page_num}")
                page_num += 1
                
            except Exception as e:
                logging.error(f"Error on page {page_num}: {str(e)}")
                break
                
            # Add delay between pages
            time.sleep(2)
            
    except Exception as e:
        logging.error(f"Error during scraping: {str(e)}")
        
    finally:
        if driver:
            driver.quit()
            
    return products_data

if __name__ == "__main__":
    lacoste_url = 'https://www.lacoste.com/us/lacoste/women/clothing/'
    products = scrape_lacoste(lacoste_url)
    logging.info(f"Total products scraped: {len(products)}")
