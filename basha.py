# basha.py

import asyncio
import json
import re
import hashlib
import os
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from config import (
    LOGIN_URL, MESSAGE_URL, EMAIL, PASSWORD, COOKIE_FILE
)

async def login_and_save_state(context, page):
    """Perform login and save browser state to cookie file."""
    await page.goto(LOGIN_URL)
    await page.wait_for_load_state("networkidle")
    # fill email
    await page.fill('input[type="email"]', EMAIL)
    # fill password
    await page.fill('input[type="password"]', PASSWORD)
    # click submit
    await page.click('button[type="submit"]')
    await asyncio.sleep(5)
    # check if login succeeded (URL no longer contains /login)
    if "/login" not in page.url:
        # save storage state
        await context.storage_state(path=COOKIE_FILE)
        return True
    return False

async def create_context(browser):
    """Create a new browser context, using saved cookies if available."""
    if os.path.exists(COOKIE_FILE):
        context = await browser.new_context(storage_state=COOKIE_FILE)
    else:
        context = await browser.new_context()
    return context

async def check_login(page):
    """Check if current session is still valid; if not, try to login."""
    await page.goto(MESSAGE_URL)
    await asyncio.sleep(1.5)
    if "/login" in page.url:
        # cookie expired, need fresh login
        # We need a new page/context for login. We'll call login_and_save_state
        return False
    return True

async def fresh_login(browser):
    """Start a new context, perform login, save cookies, return new context."""
    context = await browser.new_context()
    page = await context.new_page()
    success = await login_and_save_state(context, page)
    await page.close()
    if not success:
        await context.close()
        raise Exception("Basha login failed")
    return context

async def scrape_messages(context):
    """Scrape messages from Basha, returns list of dicts with country, number, service, message, and id."""
    page = await context.new_page()
    try:
        await page.goto(MESSAGE_URL)
        await asyncio.sleep(1.5)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.select('table tbody tr')
        messages = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4:
                continue
            country = cols[0].get_text(strip=True)
            number = cols[1].get_text(strip=True)
            service = cols[2].get_text(strip=True)
            message = cols[3].get_text(strip=True)
            # generate unique ID
            raw_id = f"{country}{number}{service}{message}"
            msg_id = hashlib.md5(raw_id.encode()).hexdigest()
            # extract OTP from message (4-8 digit number)
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
        return messages
    finally:
        await page.close()

def format_number(number):
    """Mask middle digits of phone number with a custom emoji separator."""
    # Expect format +8801712345678, return +88017➖5678 (using emoji id later)
    # Simple approach: keep first 6 chars and last 4 chars, insert separator
    if len(number) >= 10:
        prefix = number[:6]   # e.g., +88017
        suffix = number[-4:]  # e.g., 5678
        return prefix, suffix
    return number, ""