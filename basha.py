# basha.py (Updated with country name cleaning and number formatting)

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
    await page.goto(LOGIN_URL)
    await page.wait_for_load_state("networkidle")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await asyncio.sleep(5)
    if "/login" not in page.url:
        await context.storage_state(path=COOKIE_FILE)
        return True
    return False

async def create_context(browser):
    if os.path.exists(COOKIE_FILE):
        context = await browser.new_context(storage_state=COOKIE_FILE)
    else:
        context = await browser.new_context()
    return context

async def check_login(page):
    await page.goto(MESSAGE_URL)
    await asyncio.sleep(1.5)
    if "/login" in page.url:
        return False
    return True

async def fresh_login(browser):
    context = await browser.new_context()
    page = await context.new_page()
    success = await login_and_save_state(context, page)
    await page.close()
    if not success:
        await context.close()
        raise Exception("Basha login failed")
    return context

async def scrape_messages(context):
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
            # Clean country name: keep first word before any numbers/dash
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
        return messages
    finally:
        await page.close()

def format_number(number):
    """
    Formats phone number for display.
    Removes '+' and spaces, then splits:
    - prefix: first 5 digits (country code + some)
    - suffix: last 4 digits
    The '+' is added back in main.py
    Example: '+880170652' -> ('88017', '0652')
    Example: '+2126509559' -> ('21265', '9559')
    """
    # Remove '+' and any spaces
    clean = number.replace('+', '').replace(' ', '').strip()
    
    # If number is too short, return as is
    if len(clean) < 9:   # need at least 9 digits for 5 prefix + 4 suffix
        return clean, ''
    
    # Take first 5 digits as prefix, last 4 digits as suffix
    prefix = clean[:5]
    suffix = clean[-4:]
    
    return prefix, suffix
