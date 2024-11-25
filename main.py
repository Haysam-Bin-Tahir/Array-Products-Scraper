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
        product_cards = driver.find_elements(By.CSS_SELECTOR, "div.product-tile")
        logging.info(f"Found {len(product_cards)} products on page")
        
        if not product_cards:
            return []
            
        for card in product_cards:
            try:
                # Extract product details
                name = card.find_element(By.CSS_SELECTOR, ".pdp-link .link").text.strip()
                
                # Get price (handle both sale and regular prices)
                try:
                    price = card.find_element(By.CSS_SELECTOR, ".sales .value").text.strip()
                except:
                    try:
                        price = card.find_element(By.CSS_SELECTOR, ".price .value").text.strip()
                    except:
                        price = ""
                
                link = card.find_element(By.CSS_SELECTOR, ".pdp-link .link").get_attribute("href")
                
                # Get images
                try:
                    images = []
                    # Get both primary and hover images
                    img_elements = card.find_elements(By.CSS_SELECTOR, ".tile-image-container img")
                    for img in img_elements:
                        # Try to get src first
                        src = img.get_attribute("src")
                        if src and "tom_ford" in src:
                            # Get highest resolution by modifying URL
                            high_res_src = src + "?w=2307"
                            images.append(high_res_src)
                            continue
                            
                        # If no src, try srcset
                        srcset = img.get_attribute("srcset")
                        if srcset:
                            # Get highest resolution image from srcset
                            srcset_urls = srcset.split(',')
                            for url in srcset_urls:
                                if "2307w" in url:
                                    highest_res = url.split(' ')[0].strip()
                                    if highest_res and "tom_ford" in highest_res:
                                        images.append(highest_res)
                                        break
                    
                    # Remove duplicates while preserving order
                    images = list(dict.fromkeys(images))
                    
                except Exception as img_error:
                    logging.warning(f"Error getting images: {str(img_error)}")
                    images = []
                
                product = {
                    'Gender': 'Women',
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

def scroll_and_load_all_products(driver, wait):
    """Scroll until no more products load"""
    total_products = 0
    no_new_products_count = 0
    max_attempts = 3
    
    while no_new_products_count < max_attempts:
        try:
            # Scroll to bottom smoothly
            driver.execute_script("""
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            """)
            time.sleep(2)  # Wait for new products to load
            
            # Get current product count
            current_count = len(driver.find_elements(By.CSS_SELECTOR, "div.product-tile"))
            
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

def scrape_tomford(url):
    """Main function to scrape Tom Ford products"""
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
        
        # # Check if we're on the right page
        # if "tomford.com" not in driver.current_url:
        #     logging.error("Redirected away from Tom Ford site")
        #     return products_data
        
        # Load all products by scrolling
        total_products = scroll_and_load_all_products(driver, wait)
        logging.info(f"Found {total_products} total products")
        
        # Wait for images to load
        time.sleep(3)
        
        # Scrape all products
        products = scrape_products_from_page(driver, 'tomford_women_products.csv')
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
    tomford_url = 'https://www.tomfordfashion.com/en-us/women/ready-to-wear/?start=0&sz=418'
    products = scrape_tomford(tomford_url)
    logging.info(f"Total products scraped: {len(products)}")
