# main.py (Event Loop Fix)
import asyncio
import sys
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global browser and context (filled later)
browser = None
context = None

# Admin commands (same as before)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("Bot is running.")

async def country_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
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
    update_country_emoji(country_name, emoji_id)
    await update.message.reply_text(f"Updated {country_name} emoji ID to {emoji_id}")

async def service_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
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
    update_service_emoji(service_name, emoji_id)
    await update.message.reply_text(f"Updated {service_name} emoji ID to {emoji_id}")

# ---------- BROWSER & MONITOR ----------
async def start_browser():
    global browser, context
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    import os
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
    """Continuously scrape and send new OTP messages."""
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
                # Build message (same logic as before)
                country_name = msg["country"].upper()
                countries = get_countries()
                country_info = next((c for c in countries if c["name"].upper() == country_name), None)
                if country_info:
                    flag = country_info["flag"]
                    emoji_id = country_info.get("emoji_id")
                    if emoji_id:
                        country_display = f'<tg-emoji emoji-id="{emoji_id}">{flag}</tg-emoji> {country_info["name"]} {country_info["country_code"]}'
                    else:
                        country_display = f'{flag} {country_info["name"]} {country_info["country_code"]}'
                else:
                    country_display = country_name

                service_name = msg["service"].capitalize()
                services = get_services()
                service_info = next((s for s in services if s["name"].lower() == service_name.lower()), None)
                if service_info and service_info.get("emoji_id"):
                    service_display = f'<tg-emoji emoji-id="{service_info["emoji_id"]}">🔧</tg-emoji> {service_name}'
                else:
                    service_display = f'#{service_name}'

                prefix, suffix = format_number(msg["number"])
                separator_id = EMOJI.get("SEPARATOR", "6204108584381322968")
                masked_number = f'{prefix}<tg-emoji emoji-id="{separator_id}">➖</tg-emoji>{suffix}'

                line1 = f'📞 {country_display} | {service_display}'
                text = f'{line1}\n{masked_number}'

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
                    await application.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="HTML", reply_markup=keyboard)
                    save_message(msg["id"])
                    logger.info(f"Sent OTP for {msg['service']} - {msg['number']}")
                except Exception as e:
                    logger.error(f"Send failed: {e}")
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(POLL_TIME)

# ---------- MAIN ENTRY POINT ----------
def main():
    # Initialize DB
    init_db()

    # Build PTB Application (synchronous)
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("country", country_command))
    application.add_handler(CommandHandler("service", service_command))

    # Get the event loop (works both v13 and v20)
    loop = asyncio.get_event_loop()

    # Start browser inside the loop
    logger.info("Launching browser...")
    loop.run_until_complete(start_browser())

    # Schedule the monitor loop as a background task
    loop.create_task(monitor_loop(application))

    # Run the bot. In v13 this blocks forever, in v20 it must be awaited.
    # We detect PTB version to adapt.
    try:
        # Try async run (v20)
        if hasattr(application.run_polling, '__await__'):
            logger.info("Running in async mode (PTB v20+)")
            loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES))
        else:
            logger.info("Running in sync mode (PTB v13.x)")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        # Cleanup
        if browser:
            loop.run_until_complete(browser.close())
        loop.close()

if __name__ == "__main__":
    main()
