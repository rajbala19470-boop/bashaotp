# main.py (Fixed missing import, improved logging, fixed country display without code, and fixed number format without +)

import asyncio
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import KeyboardButtonStyle as KBS

from config import (
    BOT_TOKEN, ADMIN_IDS, GROUP_ID, POLL_TIME,
    CHANNEL_URL, BOT_URL
)
from database import (
    init_db, is_duplicate, save_message, get_countries,
    update_country_emoji, get_services, update_service_emoji
)
from emoji import EMOJI
from basha import (
    async_playwright, create_context, check_login,
    fresh_login, scrape_messages, format_number
)

# Configure detailed logging for debugging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

browser = None
context = None

# ----- Admin Commands -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/start command from user {user_id}")
    if user_id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /start attempt by {user_id}")
        return
    await update.message.reply_text("Bot is running.")

async def country_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/country command received from {user_id}, args={context.args}")
    if user_id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /country attempt by {user_id}")
        return

    if not context.args:
        await update.message.reply_text("Send: CountryName|EmojiID\nExample: Bangladesh|6204108584381322968")
        return

    input_text = " ".join(context.args)
    parts = input_text.split("|")
    if len(parts) != 2:
        await update.message.reply_text("Invalid format. Use CountryName|EmojiID")
        return

    country_name = parts[0].strip().upper()
    emoji_id = parts[1].strip()
    logger.info(f"Updating country {country_name} with emoji_id {emoji_id}")

    # Update database
    update_country_emoji(country_name, emoji_id)

    # Fetch country flag
    countries = get_countries()
    country_info = next((c for c in countries if c["name"].upper() == country_name), None)
    flag = country_info["flag"] if country_info else "🏳"
    logger.info(f"Country info found: {country_info}")

    # Success reply with custom emoji
    reply_text = (
        f'<tg-emoji emoji-id="{emoji_id}">{flag}</tg-emoji> Is added '
        f'<tg-emoji emoji-id="{EMOJI["SUCCESS"]}">✅</tg-emoji>'
    )
    await update.message.reply_text(reply_text, parse_mode="HTML")
    logger.info(f"Sent success reply for country {country_name}")

async def service_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/service command received from {user_id}, args={context.args}")
    if user_id not in ADMIN_IDS:
        logger.warning(f"Unauthorized /service attempt by {user_id}")
        return

    if not context.args:
        await update.message.reply_text("Send: ServiceName|EmojiID\nExample: WhatsApp|6204108584381322968")
        return

    input_text = " ".join(context.args)
    parts = input_text.split("|")
    if len(parts) != 2:
        await update.message.reply_text("Invalid format. Use ServiceName|EmojiID")
        return

    service_name = parts[0].strip().capitalize()
    emoji_id = parts[1].strip()
    logger.info(f"Updating service {service_name} with emoji_id {emoji_id}")

    update_service_emoji(service_name, emoji_id)

    reply_text = (
        f'<tg-emoji emoji-id="{emoji_id}">🔧</tg-emoji> Is added '
        f'<tg-emoji emoji-id="{EMOJI["SUCCESS"]}">✅</tg-emoji>'
    )
    await update.message.reply_text(reply_text, parse_mode="HTML")
    logger.info(f"Sent success reply for service {service_name}")

# ----- Browser & Monitor -----
async def start_browser():
    global browser, context
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    if os.path.exists("basha_cookie.json"):
        context = await create_context(browser)
    else:
        context = await fresh_login(browser)

async def ensure_logged_in():
    global context, browser
    page = await context.new_page()
    try:
        await page.goto("https://basha.cc/my/messages")
        await asyncio.sleep(1.5)
        if "/login" in page.url:
            logger.info("Cookie expired, re-logging in...")
            await context.close()
            context = await fresh_login(browser)
    except Exception as e:
        logger.error(f"Login check error: {e}")
    finally:
        await page.close()

async def monitor_loop(application: Application):
    global context
    while True:
        try:
            await ensure_logged_in()
            messages = await scrape_messages(context)
            for msg in messages:
                if is_duplicate(msg["id"]):
                    continue
                if not msg.get("otp"):
                    continue

                # --- Country display (flag/emoji + name, no code) ---
                country_name = msg["country"].upper()
                countries = get_countries()
                country_info = next((c for c in countries if c["name"].upper() == country_name), None)
                if country_info:
                    flag = country_info["flag"]
                    emoji_id = country_info.get("emoji_id")
                    if emoji_id:
                        country_display = f'<tg-emoji emoji-id="{emoji_id}">{flag}</tg-emoji> {country_info["name"]}'
                    else:
                        country_display = f'{flag} {country_info["name"]}'
                else:
                    country_display = country_name

                # --- Service display ---
                service_name = msg["service"].capitalize()
                services = get_services()
                service_info = next((s for s in services if s["name"].lower() == service_name.lower()), None)
                if service_info and service_info.get("emoji_id"):
                    service_display = f'<tg-emoji emoji-id="{service_info["emoji_id"]}">🔧</tg-emoji> {service_name}'
                else:
                    service_display = f'#{service_name}'

                # --- Masked number without leading + ---
                prefix, suffix = format_number(msg["number"])
                # Remove leading +
                prefix_clean = prefix.lstrip("+")
                separator_id = EMOJI["SEPARATOR"]
                masked_number = f'{prefix_clean}<tg-emoji emoji-id="{separator_id}">➖</tg-emoji>{suffix}'

                # Final text: line1 = 📞 COUNTRY | SERVICE, line2 = masked number
                text = f'📞 {country_display} | {service_display}\n{masked_number}'

                # Buttons
                otp_btn = InlineKeyboardButton(
                    "𝐎𝐓𝐏",
                    copy_text=CopyTextButton(text=msg["otp"]),
                    style=KBS.SUCCESS,
                    icon_custom_emoji_id=EMOJI["OTP_BUTTON"]
                )
                channel_btn = InlineKeyboardButton(
                    "𝐂𝐇𝐀𝐍𝐍𝐄𝐋", url=CHANNEL_URL,
                    style=KBS.PRIMARY,
                    icon_custom_emoji_id=EMOJI["CHANNEL_BUTTON"]
                )
                bot_btn = InlineKeyboardButton(
                    "𝐁𝐎𝐓", url=BOT_URL,
                    style=KBS.PRIMARY,
                    icon_custom_emoji_id=EMOJI["BOT_BUTTON"]
                )
                keyboard = InlineKeyboardMarkup([[otp_btn], [channel_btn, bot_btn]])

                try:
                    await application.bot.send_message(
                        chat_id=GROUP_ID, text=text,
                        parse_mode="HTML", reply_markup=keyboard
                    )
                    save_message(msg["id"])
                    logger.info(f"Sent OTP for {msg['service']} - {msg['number']}")
                except Exception as e:
                    logger.error(f"Send failed: {e}")
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(POLL_TIME)

# ----- Main -----
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("country", country_command))
    application.add_handler(CommandHandler("service", service_command))

    loop = asyncio.get_event_loop()
    logger.info("Launching browser...")
    loop.run_until_complete(start_browser())
    loop.create_task(monitor_loop(application))

    try:
        if hasattr(application.run_polling, '__await__'):
            loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES))
        else:
            application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        if browser:
            loop.run_until_complete(browser.close())
        loop.close()

if __name__ == "__main__":
    main()
