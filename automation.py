import os
import time
import json
import pickle
import logging
import random
import ssl
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IdeasoftBot")

# Workaround for SSL certificate verification issue on macOS
ssl._create_default_https_context = ssl._create_unverified_context

class IdeasoftBot:
    def __init__(self, shop_url="https://vhex10.myideasoft.com", log_callback=None):
        self.shop_url = shop_url.rstrip('/')
        self.driver = None
        self.wait = None
        self.session_path = Path("data/ideasoft_session.pkl")
        self.session_path.parent.mkdir(exist_ok=True)
        self.log_callback = log_callback

    def log(self, message, level="info"):
        logger.info(message)
        if self.log_callback:
            self.log_callback(message, level)

    def _init_driver(self, headless=False):
        """Initialize undetected chrome driver"""
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        
        try:
            # Force version 146 to match the user's browser version
            self.driver = uc.Chrome(options=options, version_main=146)
            self.wait = WebDriverWait(self.driver, 20)
            self.log("Driver initialized successfully.")
        except Exception as e:
            self.log(f"Driver initialization failed: {e}", "error")
            raise

    def save_session(self):
        """Save current session cookies"""
        if self.driver:
            with open(self.session_path, "wb") as f:
                pickle.dump(self.driver.get_cookies(), f)
            logger.info("Session cookies saved.")

    def load_session(self):
        """Load saved cookies into driver"""
        if self.session_path.exists() and self.driver:
            try:
                with open(self.session_path, "rb") as f:
                    cookies = pickle.load(f)
                
                # Must be on the domain to add cookies
                self.driver.get(f"{self.shop_url}/panel/login")
                time.sleep(2)
                
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except:
                        pass
                logger.info("Session cookies loaded.")
                return True
            except Exception as e:
                logger.error(f"Failed to load cookies: {e}")
        return False

    def check_login(self, force_check=True):
        """Check if currently logged in. If force_check is True, navigates to dashboard."""
        if not self.driver: return False
        
        try:
            if force_check:
                self.driver.get(f"{self.shop_url}/panel/dashboard")
                time.sleep(3)
                
            current_url = self.driver.current_url.lower()
            
            # 1. URL-based check
            if "panel" not in current_url or "login" in current_url:
                return False
                
            # 2. Page content check (detect session expired messages)
            # We look for common "Session expired" text or login title
            page_text = self.driver.page_source.lower()
            expiration_keywords = [
                "oturum süreniz doldu", 
                "lütfen giriş yapın", 
                "session expired",
                "login_form", # Common element in login pages
                "geçersiz oturum"
            ]
            
            for kw in expiration_keywords:
                if kw in page_text:
                    self.log(f"Oturum kapalı veya süresi dolmuş tespit edildi: {kw}", "warning")
                    # Force delete session file if it's outdated
                    if self.session_path.exists():
                        self.session_path.unlink()
                        self.log("Geçersiz oturum dosyası silindi.", "info")
                    self.driver.delete_all_cookies()
                    return False
            
            return True
        except Exception as e:
            self.log(f"check_login hatası: {e}", "debug")
            return False

    def login(self, username=None, password=None):
        """Improved login flow: Cookies -> Auto-fill -> Manual Wait"""
        if not self.driver:
            self._init_driver(headless=False)
            
        # 1. Try Cookies
        if self.load_session():
            if self.check_login():
                self.log("Kayıtlı oturum ile giriş başarılı.")
                return True
            else:
                self.log("Kayıtlı oturum geçersiz, yeni giriş yapılacak.", "info")
                self.driver.delete_all_cookies()
                # If check_login failed, it already unlinked the session path
        
        # 2. Auto-fill Credentials if provided
        self.driver.get(f"{self.shop_url}/panel/login")
        time.sleep(3)
        
        if username and password:
            try:
                logger.info(f"Attempting to auto-fill login for {username}...")
                user_field = self.wait.until(EC.presence_of_element_located((By.NAME, "username")))
                pass_field = self.driver.find_element(By.NAME, "password")
                
                user_field.clear()
                user_field.send_keys(username)
                pass_field.clear()
                pass_field.send_keys(password)
                
                # Click login button
                login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_btn.click()
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Auto-fill failed or not found: {e}")

        # 3. Wait for manual completion (Captcha/2FA)
        logger.info("Waiting for manual login completion (2FA/Captcha)...")
        start_time = time.time()
        timeout = 600 # 10 minutes
        
        while time.time() - start_time < timeout:
            try:
                # Use passive check (no navigation) to avoid refresh loop
                if self.check_login(force_check=False):
                    self.log("Giriş başarılı (panel tespit edildi)!", "success")
                    self.save_session()
                    return True
                
                # Check if driver is still open
                _ = self.driver.window_handles
            except Exception as e:
                logger.warning(f"Browser closed or error during login wait: {e}")
                return False
                
            time.sleep(5)
            
        logger.warning("Manual login timeout.")
        return False

    def update_price(self, sku, new_price):
        """Search product by SKU and update price1"""
        try:
            # Verify driver and login status
            is_logged_in = False
            try:
                if self.driver:
                    is_logged_in = self.check_login()
            except:
                self.log("Driver bağlantısı koptu, yeniden başlatılıyor...", "warning")
                self.driver = None

            if not self.driver or not is_logged_in:
                if not self.login():
                    return False, "Giriş başarısız. Lütfen tekrar oturum açın."

            # 1. Search products page
            self.log(f"Ürün aranıyor: {sku}...", "info")
            self.driver.get(f"{self.shop_url}/panel/products")
            time.sleep(3)
            
            # DISMISS BANNERS / OVERLAYS via JS
            self.driver.execute_script("""
                const selectors = [
                    '.modal-backdrop', '.modal', '.adpilot-banner', 
                    '[class*="banner"]', '[id*="banner"]', 
                    '#adpilot-gift-modal', '.gift-modal'
                ];
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
                document.body.style.overflow = 'auto';
            """)
            
            # Wait for search box (try name, id, and CSS)
            search_box = None
            search_selectors = [
                (By.CSS_SELECTOR, "input[placeholder*='Stok kodu veya ürün adına']"),
                (By.CSS_SELECTOR, "input[placeholder*='arama yapabilirsiniz']"),
                (By.NAME, "q"), (By.NAME, "search"), (By.ID, "product-search")
            ]
            
            for selector in search_selectors:
                try:
                    search_box = self.wait.until(EC.presence_of_element_located(selector))
                    if search_box: break
                except:
                    continue
            
            if not search_box:
                return False, f"Arama kutusu bulunamadı (URL: {self.driver.current_url})"

            # Type SKU via JS if needed
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_box)
            search_box.clear()
            search_box.send_keys(sku)
            search_box.send_keys(Keys.RETURN)
            
            # Wait for search results
            self.log(f"Sonuçlar bekleniyor ({sku})...", "info")
            time.sleep(2) # Back to faster speed
            
            # 2. Strict SKU Matching - Ensure we are clicking the right product row
            try:
                # Get all table rows that could be product results
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tr, .product-list-row")
                
                target_edit_link = None
                for row in rows:
                    if sku in row.text:
                        # Find the edit link within THIS specific row
                        try:
                            target_edit_link = row.find_element(By.CSS_SELECTOR, "a[href*='/panel/products/edit/']")
                            if target_edit_link:
                                break
                        except:
                            continue
                
                if not target_edit_link:
                    # Fallback if specific row not identified but results are few
                    self.log(f"Satır bazlı eşleşme bulunamadı, genel kontrol yapılıyor...", "warning")
                    target_edit_link = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/panel/products/edit/']")))

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_edit_link)
                self.driver.execute_script("arguments[0].click();", target_edit_link) # FAST JS click
            except Exception as e:
                return False, f"Hata: SKU eşleşen ürün bulunamadı veya tıklanamadı ({sku})"

            # 3. Update Price 1
            self.log(f"Fiyat alanı aranıyor (Fiyat 1)...", "info")
            time.sleep(2) 
            
            # DISMISS BANNERS AGAIN (in case they re-appear on new page)
            self.driver.execute_script("document.querySelectorAll('.modal-backdrop, .modal, [class*=\"banner\"]' ).forEach(el => el.remove());")
            
            price_field = None
            price_selectors = [
                (By.ID, "price1"), (By.NAME, "price1"), (By.CSS_SELECTOR, "input[name*='price1']")
            ]
            
            for selector in price_selectors:
                try:
                    price_field = self.wait.until(EC.presence_of_element_located(selector))
                    if price_field: break
                except:
                    continue
            
            if not price_field:
                return False, "Fiyat alanı bulunamadı (price1)."
            
            # FORCED JS UPDATE
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", price_field)
            time.sleep(1)
            
            price_str = str(new_price).replace(',', '.')
            self.log(f"Fiyat güncelleniyor -> {price_str} ₺", "info")
            
            # Use JS to set value and trigger events immediately
            self.driver.execute_script(f"""
                arguments[0].value = '{price_str}';
                arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                arguments[0].dispatchEvent(new Event('blur', {{ bubbles: true }}));
            """, price_field)
            
            time.sleep(1)
            
            # 4. Save
            try:
                self.log("Kaydet butonu aranıyor (sağ üst)...", "info")
                save_btn = None
                
                # Highly targeted selectors based on IdeaSoft's panel headers
                save_selectors = [
                    (By.XPATH, "//button[contains(., 'Kaydet')]"),
                    (By.XPATH, "//div[contains(@class, 'header')]//button[contains(., 'Kaydet')]"),
                    (By.XPATH, "//*[@id='save-button']"),
                    (By.CSS_SELECTOR, ".btn-save"),
                    (By.CSS_SELECTOR, ".btn-success"),
                    (By.XPATH, "//button[@type='submit']")
                ]
                
                for selector in save_selectors:
                    try:
                        # Find all matching elements and pick the first one that is visible
                        elements = self.driver.find_elements(*selector)
                        for el in elements:
                            if el.is_displayed():
                                save_btn = el
                                break
                        if save_btn: break
                    except:
                        continue
                
                if not save_btn:
                    return False, "Kaydet butonu sağ üstte bulunamadı."

                # AGGRESSIVE JS CLICK for the header button
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
                time.sleep(1)
                self.log("İşlem kaydediliyor...", "info")
                self.driver.execute_script("arguments[0].click();", save_btn)
                
                # Wait for any success message or redirect
                time.sleep(2)
                
                self.log(f"Başarıyla güncellendi: {sku}", "success")
                return True, "Başarılı"
            except Exception as e:
                self.log(f"Kaydetme hatası: {e}", "error")
                return False, f"Kaydetme başarısız: {str(e)}"

        except Exception as e:
            logger.error(f"Update failed for {sku}: {e}")
            return False, f"Sistem hatası: {str(e)}"

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
