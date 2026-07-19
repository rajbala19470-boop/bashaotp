# basha.py (improved login: robust selector, timeout handling, retries)

import asyncio
import json
import re
import hashlib
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from config import (
    LOGIN_URL, MESSAGE_URL, EMAIL, PASSWORD, COOKIE_FILE
)

async def login_and_save_state(context, page):
    """Perform login and save browser state to cookie file."""
    try:
        await page.goto(LOGIN_URL, timeout=60000)
        # Wait for page to be fully loaded
        await page.wait_for_load_state("networkidle")
        
        # Try multiple possible selectors for email input
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="Email" i]',
            'input[id="email"]',
            '#email',
        ]
        email_input = None
        for selector in email_selectors:
            try:
                email_input = await page.wait_for_selector(selector, timeout=5000)
                if email_input:
                    break
            except PlaywrightTimeoutError:
                continue
        
        if not email_input:
            raise Exception("Could not find email input field")

        await email_input.fill(EMAIL)
        
        # Try multiple possible selectors for password input
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[placeholder*="password" i]',
            'input[placeholder*="Password" i]',
            'input[id="password"]',
            '#password',
        ]
        password_input = None
        for selector in password_selectors:
            try:
                password_input = await page.wait_for_selector(selector, timeout=5000)
                if password_input:
                    break
            except PlaywrightTimeoutError:
                continue
        
        if not password_input:
            raise Exception("Could not find password input field")

        await password_input.fill(PASSWORD)
        
        # Try multiple possible submit button selectors
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            '[type="submit"]',
        ]
        submit_btn = None
        for selector in submit_selectors:
            try:
                submit_btn = await page.wait_for_selector(selector, timeout=5000)
                if submit_btn:
                    break
            except PlaywrightTimeoutError:
                continue
        
        if not submit_btn:
            raise Exception("Could not find submit button")

        await submit_btn.click()
        
        # Wait for login to complete
        await asyncio.sleep(5)
        
        # Check if login succeeded (URL no longer contains /login)
        if "/login" not in page.url:
            await context.storage_state(path=COOKIE_FILE)
            return True
        return False
    except Exception as e:
        # Log the error and re-raise
        print(f"Login error: {e}")
        raise

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
    try:
        success = await login_and_save_state(context, page)
        if not success:
            await context.close()
            raise Exception("Basha login failed – still on login page")
        return context
    finally:
        await page.close()

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
    if len(number) >= 10:
        prefix = number[:6]
        suffix = number[-4:]
        return prefix, suffix
    return number, ""
