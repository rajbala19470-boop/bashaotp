# basha.py (uses only basha_iprn_vas_session cookie)

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

# ----------------- EMBEDDED COOKIE (only the session cookie) -----------------
EMBEDDED_COOKIES = [
    {
        "name": "basha_iprn_vas_session",
        "value": "eyJpdiI6IjUva0NVemN0cHVVcDYwUGJhSE5MTVE9PSIsInZhbHVlIjoiUnJtTFhmUEg5TkJkRVR4ZUM5V2dUa2oyWU5TTXE5NUVoUkFsdk1UeXdBVzZBa3k1Q2FEV3FON1ZWRU9LemhOUUVKU3F6QmNJY05VZm9oUEdGU0hYYW9UUmgxVFpGWXgwWlR5bFVPN3dOaVdIYVZXNlR6ZDI3aGR6SjV1Y1pYd3EiLCJtYWMiOiIyOTliYzdmYzhiMTA4NmM2NDQ0M2MyNGU5NGM2Mzk2NGNhZGVlMjU0YTBiMWVmY2Y2YjNjMDNkYmMzODgxN2I5IiwidGFnIjoiIn0%3D",
        "domain": "basha.cc",
        "hostOnly": True,
        "path": "/",
        "secure": False,
        "httpOnly": True,
        "sameSite": "lax",
        "session": False,
        "expirationDate": 1784521488,
    }
]

# Optional stealth (install with: pip install playwright-stealth)
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


def convert_cookie_array(cookies_array):
    """Convert browser cookie array to Playwright storageState format."""
    playwright_cookies = []
    for c in cookies_array:
        expires = -1
        if not c.get("session", False) and "expirationDate" in c:
            expires = int(c["expirationDate"])

        same_site = c.get("sameSite", "Lax")
        if same_site and isinstance(same_site, str):
            same_site = same_site.capitalize()
        if same_site not in ("Strict", "Lax", "None"):
            same_site = "Lax"

        pw_cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": expires,
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": same_site,
        }
        playwright_cookies.append(pw_cookie)

    return {"cookies": playwright_cookies, "origins": []}


def load_storage_state():
    """Load storage state: embedded -> file -> None."""
    # 1. Use embedded cookies if no file exists
    if not os.path.exists(COOKIE_FILE):
        logger.info("No cookie file found, using embedded session cookie.")
        return convert_cookie_array(EMBEDDED_COOKIES)

    # 2. Try to load from file
    try:
        with open(COOKIE_FILE, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            logger.info("Cookie file is raw array, converting.")
            storage = convert_cookie_array(data)
            # Save converted format for future
            with open(COOKIE_FILE, "w") as f:
                json.dump(storage, f, indent=2)
            return storage
        elif isinstance(data, dict) and "cookies" in data:
            return data
        else:
            logger.warning("Corrupted cookie file, falling back to embedded session cookie.")
            return convert_cookie_array(EMBEDDED_COOKIES)
    except Exception as e:
        logger.error(f"Failed to load cookie file: {e}, using embedded session cookie.")
        return convert_cookie_array(EMBEDDED_COOKIES)


async def login_and_refresh_cookies(browser):
    """
    Perform a fresh login (using EMAIL/PASSWORD) and save new cookies.
    Returns storage_state on success, None on failure.
    """
    try:
        context = await browser.new_context()
        page = await context.new_page()

        try:
            logger.info("Performing fresh login to refresh cookies...")
            await page.goto(LOGIN_URL, timeout=60000)
            await page.wait_for_load_state("networkidle")

            if HAS_STEALTH:
                await stealth_async(page)

            # Wait for login form
            try:
                await page.wait_for_selector('input', timeout=20000)
            except PlaywrightTimeoutError:
                logger.error("Login form did not appear. Cloudflare may be blocking.")
                return None

            async def find_element(selectors):
                for sel in selectors:
                    try:
                        el = await page.wait_for_selector(sel, timeout=3000)
                        if el:
                            return el
                    except PlaywrightTimeoutError:
                        continue
                return None

            # Email
            email_input = await find_element([
                'input[type="email"]', 'input[name="email"]',
                'input[placeholder*="email" i]', 'input[placeholder*="Email" i]',
                'input[id="email"]', '#email', 'input[type="text"][name="email"]'
            ])
            if not email_input:
                all_inputs = await page.query_selector_all('input')
                for inp in all_inputs:
                    t = await inp.get_attribute('type')
                    if t in ('email', 'text', None):
                        email_input = inp
                        break
            if not email_input:
                raise Exception("Could not find email input")
            await email_input.fill(EMAIL)

            # Password
            password_input = await find_element([
                'input[type="password"]', 'input[name="password"]',
                'input[placeholder*="password" i]', 'input[placeholder*="Password" i]',
                'input[id="password"]', '#password'
            ])
            if not password_input:
                raise Exception("Could not find password input")
            await password_input.fill(PASSWORD)

            # Submit
            submit_btn = await find_element([
                'button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Login")', 'button:has-text("Sign in")',
                'button:has-text("Log in")', '[type="submit"]',
                'button.btn-primary'
            ])
            if not submit_btn:
                raise Exception("Could not find submit button")
            await submit_btn.click()

            await asyncio.sleep(5)
            logger.info(f"After login, URL: {page.url}")

            if "/login" not in page.url:
                storage = await context.storage_state()
                with open(COOKIE_FILE, "w") as f:
                    json.dump(storage, f, indent=2)
                logger.info("New cookies saved successfully!")
                return storage
            else:
                logger.error("Login failed – still on login page.")
                return None
        finally:
            await page.close()
            await context.close()
    except Exception as e:
        logger.error(f"Login error: {e}")
        return None


async def create_context(browser):
    """Create browser context using best available cookies."""
    storage = load_storage_state()
    logger.info("Creating browser context with stored/embedded cookie(s).")
    return await browser.new_context(storage_state=storage)


async def check_login(page):
    """Check if session is valid."""
    try:
        await page.goto(MESSAGE_URL)
        await asyncio.sleep(1.5)
        if "/login" in page.url:
            return False
        return True
    except Exception:
        return False


async def cookie_refresh_loop(browser):
    """
    Every 12 hours, attempt to re-login and save new cookies.
    """
    global context
    while True:
        await asyncio.sleep(12 * 3600)  # 12 hours
        logger.info("⏰ 12-hour cookie refresh triggered...")
        try:
            new_storage = await login_and_refresh_cookies(browser)
            if new_storage:
                old_context = context
                context = await browser.new_context(storage_state=new_storage)
                await old_context.close()
                logger.info("✅ Cookies refreshed and context updated!")
            else:
                logger.warning("❌ Cookie refresh failed. Will retry in next cycle.")
        except Exception as e:
            logger.error(f"Cookie refresh error: {e}")


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
    """Return prefix (first 6 chars) and suffix (last 4 chars)."""
    if len(number) >= 10:
        return number[:6], number[-4:]
    return number, ""
