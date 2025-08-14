import time
import json
import logging
import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
import re
import random
from datetime import datetime
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HackRxSeleniumScraper:
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.base_url = "https://dashboard.hackrx.in"
        self.login_url = f"{self.base_url}/login"
        self.dashboard_url = f"{self.base_url}/submissions"
        self.submissions_all_url = f"{self.base_url}/submissions/all"
        self.driver = None
        self.is_authenticated = False
        self.headless = headless

    def verify_credentials_format(self):
        print("🔍 Verifying credential format...")
        print(f"Username: '{self.username}' (length: {len(self.username)})")
        print(f"Password: '{self.password}' (length: {len(self.password)})")
        
        issues = []
        if ' ' in self.username:
            issues.append("Username contains spaces")
        if ' ' in self.password:
            issues.append("Password contains spaces")
        if len(self.username) == 0:
            issues.append("Username is empty")
        if len(self.password) == 0:
            issues.append("Password is empty")
        if self.username != self.username.strip():
            issues.append("Username has leading/trailing whitespace")
        if self.password != self.password.strip():
            issues.append("Password has leading/trailing whitespace")
        
        if issues:
            print(f"⚠️ Potential issues: {issues}")
        else:
            print("✅ Credentials format looks good")
        
        return len(issues) == 0

    def create_driver(self):
        """Create Chrome WebDriver with cloud deployment optimizations"""
        chrome_options = Options()
        
        # Essential options for cloud deployment
        if self.headless:  # Always headless in production
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        
        # Memory and performance optimizations
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=4096")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--metrics-recording-only")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--safebrowsing-disable-auto-update")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-plugins-discovery")
        
        # Window size for headless mode
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Anti-detection options
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            service = Service()
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Enhanced stealth mode
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            print("✅ Chrome WebDriver created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create WebDriver with ChromeDriverManager: {e}")
            
            

    def human_like_delay(self, min_seconds=1, max_seconds=5):
        """Add human-like delays"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def human_like_typing(self, element, text, min_delay=0.05, max_delay=0.15):
        """Type text with human-like delays between characters"""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))

    def wait_for_page_load(self, timeout=35):
        """Wait for page to fully load with enhanced checks"""
        try:
            # Wait for the page to be in ready state
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for potential React/JS frameworks to load
            time.sleep(4)
            
            # Additional check for any loading spinners or indicators
            try:
                WebDriverWait(self.driver, 5).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='loading'], [class*='spinner'], .loading"))
                )
            except TimeoutException:
                pass  # No loading indicators found, which is fine
            
            return True
        except TimeoutException:
            print("⚠️ Page load timeout")
            return False

    def wait_for_element_interactable(self, by, selector, timeout=10):
        """Wait for element to be both present and interactable"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            return element
        except TimeoutException:
            return None

    def safe_click(self, element, max_attempts=3):
        """Safely click an element with retries"""
        for attempt in range(max_attempts):
            try:
                # Scroll element into view
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                self.human_like_delay(0.2, 1.2)
                
                # Try direct click first
                element.click()
                return True
            except ElementClickInterceptedException:
                if attempt < max_attempts - 1:
                    print(f"Click intercepted, attempt {attempt + 1}/{max_attempts}")
                    # Try ActionChains click
                    try:
                        ActionChains(self.driver).move_to_element(element).click().perform()
                        return True
                    except:
                        # Try JavaScript click as last resort
                        self.driver.execute_script("arguments[0].click();", element)
                        return True
                else:
                    print("❌ All click attempts failed")
                    return False
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"Click error: {e}, attempt {attempt + 1}/{max_attempts}")
                    time.sleep(1)
                else:
                    print(f"❌ Final click attempt failed: {e}")
                    return False
        return False

    def login(self) -> bool:
        """Perform login using Selenium with enhanced human-like behavior"""
        print("🔐 Logging in to HackRx dashboard...")
        
        try:
            # Navigate to login page
            print("Navigating to login page...")
            self.driver.get(self.login_url)
            
            if not self.wait_for_page_load():
                print("❌ Login page failed to load properly")
                return False
            
            # Add a random delay to appear more human-like
            self.human_like_delay(2, 4)
            
            print("✅ Login page loaded")
            print(f"Current URL: {self.driver.current_url}")
            print(f"Page title: {self.driver.title}")
            
            # Wait for and find login form elements
            print("Looking for login form elements...")
            
            # Try multiple selectors for username/team ID field
            username_selectors = [
                'input[placeholder*="team"]',
                'input[placeholder*="Team"]',
                'input[placeholder*="ID"]',
                'input[name*="team"]',
                'input[name*="username"]',
                'input[name*="email"]',
                'input[type="text"]:first-of-type',
                'input:not([type="password"]):not([type="hidden"]):not([type="submit"]):first-of-type'
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = self.wait_for_element_interactable(By.CSS_SELECTOR, selector, 5)
                    if username_field:
                        print(f"✅ Found username field with selector: {selector}")
                        break
                except TimeoutException:
                    continue
            
            if not username_field:
                print("❌ No username field found. Available input fields:")
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for i, inp in enumerate(inputs):
                    try:
                        print(f"  Input {i+1}: type='{inp.get_attribute('type')}', name='{inp.get_attribute('name')}', placeholder='{inp.get_attribute('placeholder')}', id='{inp.get_attribute('id')}'")
                    except:
                        print(f"  Input {i+1}: Could not read attributes")
                return False
            
            # Find password field
            password_field = self.wait_for_element_interactable(By.CSS_SELECTOR, 'input[type="password"]', 5)
            
            if not password_field:
                print("❌ No password field found")
                return False
            
            print("✅ Found password field")
            
            # Fill the form fields with human-like behavior
            print("Filling login form with human-like behavior...")
            
            # Focus on username field and fill it
            username_field.click()
            self.human_like_delay(0.5, 1)
            self.human_like_typing(username_field, self.username)
            print(f"✅ Entered username: {self.username}")
            
            # Add delay before moving to password field
            self.human_like_delay(1, 2)
            
            # Focus on password field and fill it
            password_field.click()
            self.human_like_delay(0.5, 1)
            self.human_like_typing(password_field, self.password)
            print("✅ Entered password")
            
            # Add delay before submitting
            self.human_like_delay(1, 2)
            
            # Look for submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'form button',
                'button'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.wait_for_element_interactable(By.CSS_SELECTOR, selector, 5)
                    if submit_button:
                        # Check if button text contains login-related words
                        button_text = submit_button.text.lower()
                        if any(word in button_text for word in ['login', 'sign', 'submit', 'enter']) or selector == 'button[type="submit"]':
                            print(f"✅ Found submit button with selector: {selector} (text: '{submit_button.text}')")
                            break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            if not submit_button:
                print("⚠️ No submit button found, trying Enter key...")
                password_field.send_keys(Keys.RETURN)
            else:
                # Click submit button with safe clicking
                print("Clicking submit button...")
                if not self.safe_click(submit_button):
                    print("⚠️ Button click failed, trying Enter key...")
                    password_field.send_keys(Keys.RETURN)
            
            # Wait for login to process with longer timeout
            print("Waiting for login to process...")
            time.sleep(7)  # Increased wait time
            
            # Check if login was successful
            current_url = self.driver.current_url
            print(f"After login URL: {current_url}")
            
            # Check for redirect or URL change (more reliable than just checking for 'login' in URL)
            if current_url != self.login_url and 'login' not in current_url.lower():
                print("✅ Login appears successful - redirected away from login")
                self.is_authenticated = True
                return True
            else:
                # Additional check: look for dashboard elements
                try:
                    dashboard_indicators = self.driver.find_elements(By.CSS_SELECTOR, 
                        "[href*='dashboard'], [href*='submission'], .dashboard, .nav, .navbar")
                    if dashboard_indicators:
                        print("✅ Login successful - found dashboard elements")
                        self.is_authenticated = True
                        return True
                except:
                    pass
                
                # Check for error messages
                page_source = self.driver.page_source
                print("\n🔍 Analyzing error messages...")
                
                # Look for specific error elements more carefully
                try:
                    error_selectors = [
                        ".error", ".alert-error", ".text-red", "[class*='error']",
                        ".invalid", ".wrong", ".fail", "[role='alert']"
                    ]
                    
                    for selector in error_selectors:
                        error_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for error_elem in error_elements:
                            if error_elem.is_displayed():
                                error_text = error_elem.text.strip()
                                if error_text and len(error_text) < 200:  # Avoid CSS content
                                    print(f"❌ Visible error: {error_text}")
                except:
                    pass
                
                # Look for loading indicators that might still be present
                loading_indicators = self.driver.find_elements(By.CSS_SELECTOR, 
                    "[class*='loading'], [class*='spinner'], .loading")
                if loading_indicators:
                    print("⏳ Still loading, waiting additional time...")
                    time.sleep(5)
                    current_url = self.driver.current_url
                    if current_url != self.login_url and 'login' not in current_url.lower():
                        print("✅ Login successful after additional wait")
                        self.is_authenticated = True
                        return True
                
                print("❌ Login failed - still on login page")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def verify_authentication(self) -> bool:
        """Verify that we're still authenticated"""
        try:
            print("🔍 Verifying authentication...")
            self.driver.get(self.dashboard_url)
            self.wait_for_page_load()
            
            current_url = self.driver.current_url
            if 'login' in current_url.lower():
                print("❌ Not authenticated - redirected to login")
                return False
            else:
                print("✅ Authentication verified")
                return True
                
        except Exception as e:
            print(f"❌ Auth verification error: {e}")
            return False

    def submit_webhook(self, webhook_url: str, notes: str) -> dict:
        """Submit webhook using Selenium with enhanced human-like behavior"""
        try:
            print("📤 Submitting webhook...")
            
            # Navigate to submissions page
            self.driver.get(self.dashboard_url)
            self.wait_for_page_load()
            
            if 'login' in self.driver.current_url:
                return {"success": False, "error": "Session expired - redirected to login"}
            
            print("✅ Submissions page loaded")
            self.human_like_delay(2, 3)
            
            # Look for webhook URL input field
            webhook_selectors = [
                'input[placeholder*="webhook"]',
                'input[placeholder*="URL"]',
                'input[placeholder*="endpoint"]',
                'input[name*="webhook"]',
                'input[name*="url"]',
                'input[type="url"]',
                'input[type="text"]'
            ]
            
            webhook_field = None
            for selector in webhook_selectors:
                try:
                    webhook_field = self.wait_for_element_interactable(By.CSS_SELECTOR, selector, 5)
                    if webhook_field:
                        print(f"✅ Found webhook field with selector: {selector}")
                        break
                except TimeoutException:
                    continue
            
            if not webhook_field:
                print("❌ No webhook field found. Available input fields:")
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for i, inp in enumerate(inputs):
                    try:
                        print(f"  Input {i+1}: type='{inp.get_attribute('type')}', name='{inp.get_attribute('name')}', placeholder='{inp.get_attribute('placeholder')}'")
                    except:
                        pass
                return {"success": False, "error": "No webhook input field found"}
            
            # Fill webhook URL with human-like behavior
            webhook_field.click()
            self.human_like_delay(0.5, 1)
            self.human_like_typing(webhook_field, webhook_url, 0.02, 0.05)  # Faster typing for URLs
            print(f"✅ Entered webhook URL: {webhook_url}")
            
            self.human_like_delay(1, 2)
            
            # Look for notes field (optional)
            notes_selectors = [
                'textarea[placeholder*="note"]',
                'textarea[name*="note"]',
                'input[placeholder*="note"]',
                'input[name*="note"]',
                'textarea',
                'input[name*="description"]'
            ]
            
            notes_field = None
            for selector in notes_selectors:
                try:
                    notes_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"✅ Found notes field with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if notes_field:
                notes_field.click()
                self.human_like_delay(0.5, 1)
                self.human_like_typing(notes_field, notes)
                print(f"✅ Entered notes: {notes}")
            else:
                print("⚠️ No notes field found")
            
            self.human_like_delay(1, 2)
            
            # Find and click Run button
            try:
                print("🔍 Looking for Run button...")
                run_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Run') and not(@disabled)]"))
                )
                print("✅ Found Run button, clicking...")
                run_button.click()
                print("✅ Clicked the Run button successfully!")
                
                # Wait for at least 7 seconds after clicking Run button
                print("⏳ Waiting 7 seconds for processing...")
                time.sleep(7)
                
            except Exception as e:
                print(f"⚠️ Run button not found or clickable: {e}")
                print("⚠️ Trying Enter key as fallback...")
                webhook_field.send_keys(Keys.RETURN)
                time.sleep(5)  # Still wait, but shorter for fallback
            
            # Check for success/error messages
            page_text = self.driver.page_source.lower()
            
            success_indicators = ['success', 'submitted', 'received', 'accepted']
            error_indicators = ['error', 'failed', 'invalid', 'cooldown']
            
            found_success = [s for s in success_indicators if s in page_text]
            found_errors = [e for e in error_indicators if e in page_text]
            
            if found_success:
                return {"success": True, "data": f"Success indicators: {found_success}"}
            elif found_errors:
                return {"success": False, "error": f"Error indicators: {found_errors}"}
            else:
                return {"success": True, "data": "Submission completed (no clear indicators)"}
                
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}"}

    def monitor_submission_results(self, target_notes: str, max_minutes: int = 10):
        """Monitor submission results"""
        print(f"🔍 Monitoring results for: '{target_notes}'")
        print(f"Checking every 15 seconds for up to {max_minutes} minutes...")
        
        max_checks = (max_minutes * 60) // 15
        check_count = 0
        
        while check_count < max_checks:
            check_count += 1
            print(f"\n📊 Check #{check_count}/{max_checks}")
            
            try:
                # Refresh the submissions page
                self.driver.get(self.dashboard_url)
                self.wait_for_page_load()
                
                # Also try the /all page
                self.driver.get(self.submissions_all_url)
                self.wait_for_page_load()
                
                page_text = self.driver.page_source
                
                if target_notes.lower() in page_text.lower():
                    print("🎉 SUBMISSION FOUND!")
                    
                    # Extract results from page
                    results = self.extract_submission_details(page_text, target_notes)
                    print(f"Status: {results['status']}")
                    print(f"Details: {results['details']}")
                    
                    if results["has_results"]:
                        print("✅ RESULTS AVAILABLE!")
                        break
                    elif results["is_processing"]:
                        print("⏳ Still processing...")
                    elif results["has_error"]:
                        print("❌ ERROR DETECTED!")
                        break
                else:
                    print("⏳ Submission not found yet...")
                
                if check_count < max_checks:
                    time.sleep(15)
                    
            except Exception as e:
                print(f"❌ Monitoring error: {e}")
        
        if check_count >= max_checks:
            print("⏰ Monitoring timeout reached")

    def extract_submission_details(self, page_text: str, target_notes: str) -> dict:
        notes_pos = page_text.lower().find(target_notes.lower())
        if notes_pos == -1:
            return {
                "status": "unknown",
                "has_results": False,
                "is_processing": False,
                "has_error": False,
                "details": "Submission not found on page",
                "metrics": {}
            }

        # Look in a larger context around our submission (increased window size)
        window_start = max(0, notes_pos - 2000)
        window_end = min(len(page_text), notes_pos + 2000)
        context = page_text[window_start:window_end]

        print(f"🔍 Debug: Found notes at position {notes_pos}")
        print(f"🔍 Debug: Context length: {len(context)}")

        # Enhanced status detection
        status_patterns = {
            'completed': r'(?:completed|success|✅)',
            'processing': r'(?:processing|evaluating|pending|⏳)',
            'failed': r'(?:failed|error|timeout|❌)',
            'submitted': r'(?:submitted|received)'
        }

        found_status = "unknown"
        for status_name, pattern in status_patterns.items():
            if re.search(pattern, context, re.IGNORECASE):
                found_status = status_name
                break

        # Enhanced metrics extraction with multiple patterns
        metrics = {}

        # Overall Score patterns
        score_patterns = [
            r'Overall\s+Score[:\s]*(\d+(?:\.\d+)?)',
            r'Score[:\s]*(\d+(?:\.\d+)?)',
            r'overall[:\s]*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:points?|pts?)'
        ]

        for pattern in score_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                metrics['overall_score'] = match.group(1)
                print(f"✅ Found Overall Score: {metrics['overall_score']}")
                break

        # Accuracy patterns
        accuracy_patterns = [
            r'Accuracy[:\s]*(\d+(?:\.\d+)?%?)',
            r'accuracy[:\s]*(\d+(?:\.\d+)?%?)',
            r'(\d+(?:\.\d+)?)%\s*(?:accuracy|acc)',
            r'correct[:\s]*(\d+(?:\.\d+)?%?)'
        ]

        for pattern in accuracy_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                accuracy_val = match.group(1)
                if not accuracy_val.endswith('%'):
                    accuracy_val += '%'
                metrics['accuracy'] = accuracy_val
                print(f"✅ Found Accuracy: {metrics['accuracy']}")
                break

        # Response Time patterns
        response_patterns = [
            r'Avg\s+Response[:\s]*(\d+(?:\.\d+)?)\s*ms',
            r'Average\s+Response[:\s]*(\d+(?:\.\d+)?)\s*ms',
            r'Response\s+Time[:\s]*(\d+(?:\.\d+)?)\s*ms',
            r'(\d+(?:\.\d+)?)\s*ms\s*(?:response|avg)',
            r'latency[:\s]*(\d+(?:\.\d+)?)\s*ms'
        ]

        for pattern in response_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                metrics['avg_response'] = f"{match.group(1)}ms"
                print(f"✅ Found Avg Response: {metrics['avg_response']}")
                break

        # Position/Rank patterns
        position_patterns = [
            r'Position[:\s]*#?(\d+)',
            r'Rank[:\s]*#?(\d+)',
            r'#(\d+)\s*(?:position|rank)',
            r'place[:\s]*(\d+)'
        ]

        for pattern in position_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                metrics['position'] = f"#{match.group(1)}"
                print(f"✅ Found Position: {metrics['position']}")
                break

        # Additional metrics that might be present
        additional_patterns = {
            'f1_score': [r'F1[:\s]*(\d+(?:\.\d+)?)', r'F1-Score[:\s]*(\d+(?:\.\d+)?)'],
            'precision': [r'Precision[:\s]*(\d+(?:\.\d+)?%?)'],
            'recall': [r'Recall[:\s]*(\d+(?:\.\d+)?%?)'],
            'throughput': [r'Throughput[:\s]*(\d+(?:\.\d+)?)', r'RPS[:\s]*(\d+(?:\.\d+)?)']
        }

        for metric_name, patterns in additional_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, context, re.IGNORECASE)
                if match:
                    metrics[metric_name] = match.group(1)
                    print(f"✅ Found {metric_name}: {metrics[metric_name]}")
                    break

        # Determine if we have meaningful results
        has_results = len(metrics) > 0 and any(key in metrics for key in ['overall_score', 'accuracy', 'avg_response'])

        # Check for error conditions
        error_keywords = ['error', 'failed', 'timeout', 'invalid', 'rejected']
        has_error = any(keyword in context.lower() for keyword in error_keywords) or found_status == 'failed'

        # Check if still processing
        is_processing = found_status in ['processing', 'submitted'] and not has_results and not has_error

        if has_results:
            details_parts = []
            if 'overall_score' in metrics:
                details_parts.append(f"Score: {metrics['overall_score']}")
            if 'accuracy' in metrics:
                details_parts.append(f"Accuracy: {metrics['accuracy']}")
            if 'avg_response' in metrics:
                details_parts.append(f"Response: {metrics['avg_response']}")
            if 'position' in metrics:
                details_parts.append(f"Position: {metrics['position']}")
            details = f"Status: {found_status}, " + ", ".join(details_parts)
        else:
            details = f"Status: {found_status}, No metrics found"

        result = {
            "status": found_status,
            "has_results": has_results,
            "is_processing": is_processing,
            "has_error": has_error,
            "details": details,
            "metrics": metrics
        }

        print(f"🔍 Final result: {result}")
        return result

    def format_detailed_success_message(self, task, details: Dict) -> str:
        """Format detailed success message with all metrics"""
        from datetime import datetime

        message = f"🎉 **HackRx Results Available!**\n\n"
        message += f"📝 **Notes:** {task.notes}\n"
        message += f"🌐 **Webhook:** {task.webhook_url}\n\n"

        metrics = details.get('metrics', {})

        if metrics:
            message += "📊 **Performance Metrics:**\n"

            if 'overall_score' in metrics:
                message += f"🎯 **Overall Score:** {metrics['overall_score']}\n"
            if 'accuracy' in metrics:
                message += f"🎲 **Accuracy:** {metrics['accuracy']}\n"
            if 'avg_response' in metrics:
                message += f"⚡ **Avg Response Time:** {metrics['avg_response']}\n"
            if 'position' in metrics:
                message += f"🏆 **Position:** {metrics['position']}\n"
            if 'f1_score' in metrics:
                message += f"📈 **F1 Score:** {metrics['f1_score']}\n"
            if 'precision' in metrics:
                message += f"🎯 **Precision:** {metrics['precision']}\n"
            if 'recall' in metrics:
                message += f"🔄 **Recall:** {metrics['recall']}\n"
            if 'throughput' in metrics:
                message += f"🚀 **Throughput:** {metrics['throughput']}\n"
        else:
            message += "✅ **Submission processed successfully**\n"

        message += f"\n🕐 **Completed at:** {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"
        return message