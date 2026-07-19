# basha.py (optimized login: uses cookies, fallback to manual cookie creation, Cloudflare-avoidance)

import asyncio
import json
import re
import hashlib
import os
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from config import (
    LOGIN_URL, MESSAGE_URL, EMAIL, PASSWORD, COOKIE_FILE
)

logger = logging.getLogger(__name__)

# Optional stealth (install with: pip install playwright-stealth)
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    logger.info("playwright-stealth not installed; may help if Cloudflare blocks login.")

async def login_and_save_state(context, page):
    """
    Attempt to log in and save cookies.
    Returns True if login succeeded, False otherwise.
    """
    try:
        logger.info("Navigating to login page...")
        await page.goto(LOGIN_URL, timeout=60000)
        await page.wait_for_load_state("networkidle")

        # Apply stealth if available (helps bypass some basic bot detection)
        if HAS_STEALTH:
            await stealth_async(page)

        # Wait for any input field (Cloudflare may delay this)
        try:
            await page.wait_for_selector('input', timeout=20000)
        except PlaywrightTimeoutError:
            # Could be Cloudflare challenge – we can't solve it automatically.
            logger.error("Login form did not appear – possible Cloudflare/Turnstile block.")
            logger.error("Manual login required. Please open the site in a regular browser, log in, "
                         "and save the cookies to 'basha_cookie.json' using a browser extension.")
            return False

        # Helper to find an element using multiple possible selectors
        async def find_element(selectors, label):
            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el:
                        logger.info(f"{label} found: {sel}")
                        return el
                except PlaywrightTimeoutError:
                    continue
            return None

        # Email field
        email_input = await find_element([
            'input[type="email"]', 'input[name="email"]',
            'input[placeholder*="email" i]', 'input[placeholder*="Email" i]',
            'input[id="email"]', '#email', 'input[type="text"][name="email"]'
        ], "Email input")
        if not email_input:
            # Fallback: first visible text/email input
            all_inputs = await page.query_selector_all('input')
            for inp in all_inputs:
                t = await inp.get_attribute('type')
                if t in ('email', 'text', None):
                    email_input = inp
                    logger.warning("Using fallback email input (first text input)")
                    break
        if not email_input:
            raise Exception("Could not find email input field")

        await email_input.fill(EMAIL)

        # Password field
        password_input = await find_element([
            'input[type="password"]', 'input[name="password"]',
            'input[placeholder*="password" i]', 'input[placeholder*="Password" i]',
            'input[id="password"]', '#password'
        ], "Password input")
        if not password_input:
            raise Exception("Could not find password input field")
        await password_input.fill(PASSWORD)

        # Submit button
        submit_btn = await find_element([
            'button[type="submit"]', 'input[type="submit"]',
            'button:has-text("Login")', 'button:has-text("Sign in")',
            'button:has-text("Log in")', '[type="submit"]',
            'button.btn-primary', 'button:has-text("Submit")'
        ], "Submit button")
        if not submit_btn:
            raise Exception("Could not find submit button")
        await submit_btn.click()

        # Wait for navigation
        await asyncio.sleep(5)
        logger.info(f"After login, URL: {page.url}")

        if "/login" not in page.url:
            logger.info("Login successful, saving cookies.")
            await context.storage_state(path=COOKIE_FILE)
            return True
        else:
            logger.error("Login failed – still on login page.")
            return False

    except Exception as e:
        logger.error(f"Login error: {e}")
        return False

async def create_context(browser):
    """Create a browser context, loading cookies if available."""
    if os.path.exists(COOKIE_FILE):
        logger.info("Loading saved cookies.")
        context = await browser.new_context(storage_state=COOKIE_FILE)
    else:
        logger.info("No cookie file found – will try to login later.")
        context = await browser.new_context()
    return context

async def check_login(page):
    """Check if the current session is still valid."""
    try:
        await page.goto(MESSAGE_URL)
        await asyncio.sleep(1.5)
        return "/login" not in page.url
    except Exception:
        return False

async def fresh_login(browser):
    """Perform a fresh login, retrying up to 2 times."""
    for attempt in range(2):
        try:
            context = await browser.new_context()
            page = await context.new_page()
            try:
                success = await login_and_save_state(context, page)
                if success:
                    return context
                await context.close()
                logger.warning(f"Login attempt {attempt+1} unsuccessful.")
                if attempt == 0:
                    logger.info("Retrying in 10 seconds...")
                    await asyncio.sleep(10)
            finally:
                await page.close()
        except Exception as e:
            logger.error(f"Attempt {attempt+1} crashed: {e}")
    raise Exception("All login attempts failed. Provide a valid 'basha_cookie.json' manually.")

async def scrape_messages(context):
    """Scrape OTP messages from Basha."""
    page = await context.new_page()
    try:
        logger.info("Scraping messages...")
        await page.goto(MESSAGE_URL, timeout=30000)
        await asyncio.sleep(1.5)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.select('table tbody tr')
        messages = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4:
                continue
            raw_country = cols[0].get_text(strip=True)
            country = raw_country.split()[0] if raw_country else "Unknown"
            number = cols[1].get_text(strip=True)
            service = cols[2].get_text(strip=True)
            message = cols[3].get_text(strip=True)
            raw_id = f"{country}{number}{service}{message}"
            msg_id = hashlib.md5(raw_id.encode()).hexdigest()
            otp_match = re.search(r'\b\d{4,8}\b', message)
            otp = otp_match.group(0) if otp_match else None
            messages.append({
                "country": country,
                "number": number,
                "service": service,
                "message": message,
                "id": msg_id,
                "otp": otp
            })
        logger.info(f"Scraped {len(messages)} messages.")
        return messages
    finally:
        await page.close()

def format_number(number):
    """Return prefix (first 6 chars) and suffix (last 4 chars) for masking."""
    if len(number) >= 10:
        return number[:6], number[-4:]
    return number, ""
