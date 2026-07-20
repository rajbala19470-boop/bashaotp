import asyncio
import time
import requests
import re
import json
import os
import signal
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import KeyboardButtonStyle as KBS

# ================= CONFIG =================
BOT_TOKEN = "8208003630:AAE9PGWAetvkB2SDcOigYS5Yjfo7UzqUvN4"
GROUP_ID = "-1004380384761"
API_TOKEN = "6e4b2ca76e753ac9024d3c71ca59d4e6"
API_URL = "http://headshotsms.kdns.fr/ints/login/api/agent_sms.php"
CHANNEL_URL = "https://t.me/RHTotp"
BOT_URL = "http://t.me/RhtNumberRobot"
ADMIN_IDS = [8744359777]

SEEN_FILE = "sent_otps.json"
EMOJI_DATA_FILE = "emoji_data.json"

# ================= CUSTOM EMOJI IDs =================
EMOJI = {
    "SEPARATOR": "6307542847251814164",
    "PREFIX": "4958725487682650920",
    "OTP_BUTTON": "6206420230269310869",
    "CHANNEL_BUTTON": "6204010762206189094",
    "BOT_BUTTON": "5339267587337370029",
    "SUCCESS": "6205984471477393007",
}

DEFAULT_SERVICE_EMOJIS = {
    "uber": "5298715455316303708",
    "bolt": "5343587658717219067",
}

SERVICE_PATTERNS = {
    "WhatsApp": [r'whatsapp', r'WhatsApp'],
    "Google": [r'google', r'gmail'],
    "Facebook": [r'facebook', r'fb'],
    "Instagram": [r'instagram', r'ig'],
    "Telegram": [r'telegram', r'Telegram'],
    "TikTok": [r'tiktok'],
    "Snapchat": [r'snapchat'],
    "Twitter": [r'twitter'],
    "Discord": [r'discord'],
    "Uber": [r'uber'],
    "Bolt": [r'bolt'],
    "Netflix": [r'netflix'],
    "Amazon": [r'amazon'],
    "PayPal": [r'paypal'],
    "Binance": [r'binance'],
    "Coinbase": [r'coinbase'],
    "Steam": [r'steam'],
    "Roblox": [r'roblox'],
}

def detect_service(msg):
    if not msg: return "UNKNOWN"
    msg_l = msg.lower()
    for srv, pats in SERVICE_PATTERNS.items():
        for p in pats:
            if re.search(p, msg_l):
                return srv
    return "UNKNOWN"

# ============= FLASK KEEP-ALIVE ==============
app = Flask(__name__)
@app.route("/")
def home(): return "OK"

# ============= EMOJI DATA MANAGEMENT ==============
def load_emoji_data():
    return json.load(open(EMOJI_DATA_FILE)) if os.path.exists(EMOJI_DATA_FILE) else {"countries": {}, "global_services": {}}

def save_emoji_data(data):
    json.dump(data, open(EMOJI_DATA_FILE, 'w'), indent=2)

emoji_data = load_emoji_data()

def get_country_emoji(country_upper):
    return emoji_data.get("countries", {}).get(country_upper.lower(), {}).get("emoji_id")

def get_service_emoji(country, service):
    # 1) per‑country service
    eid = emoji_data.get("countries", {}).get(country.lower(), {}).get("services", {}).get(service.lower())
    if eid: return eid
    # 2) global service
    eid = emoji_data.get("global_services", {}).get(service.lower())
    if eid: return eid
    # 3) hardcoded default
    return DEFAULT_SERVICE_EMOJIS.get(service.lower())

# ============= SEEN OTP STORAGE ==============
seen_dict = {}
seen_lock = asyncio.Lock()

def reset_seen():
    global seen_dict
    seen_dict = {}
    if os.path.exists(SEEN_FILE): os.remove(SEEN_FILE)

# ============= FULL COUNTRY CODE MAP (shortened – use your 180+ map) =============
COUNTRY_CODE_MAP = {
    "1": ("US", "🇺🇸", "USA"),
    "7": ("RU", "🇷🇺", "RUSSIA"),
    # … (paste your full mapping) …
    "880": ("BD", "🇧🇩", "BANGLADESH"),
    "998": ("UZ", "🇺🇿", "UZBEKISTAN"),
}

def get_country_info(number):
    clean = number.replace("+", "")
    for code in sorted(COUNTRY_CODE_MAP.keys(), key=len, reverse=True):
        if clean.startswith(code):
            iso, flag, name = COUNTRY_CODE_MAP[code]
            return {"iso": iso, "flag": flag, "name": name}
    return None

def format_number(number):
    clean = number.replace('+', '').replace(' ', '').strip()
    if len(clean) < 9:
        return clean[:5] if len(clean) >= 5 else clean, clean[-4:] if len(clean) >= 4 else ""
    return clean[:5], clean[-4:]

def extract_otp(text):
    if not text: return None
    text = ' '.join(text.split())
    for pat, l in [(r'(\d{3})[-—\s](\d{3})',6),(r'(\d{2})[-—\s](\d{3})',5),
                   (r'(\d{3})[-—\s](\d{2})',5),(r'(\d{3})[-—\s](\d{2})[-—\s](\d{2})',7),
                   (r'(\d{4})[-—\s](\d{4})',8)]:
        m = re.search(pat, text)
        if m:
            otp = ''.join(m.groups())
            if otp.isdigit() and len(otp)==l: return otp
    for kw in ['code','otp','pin','verification','код','كود','验证码']:
        m = re.search(r'{}\s*:?\s*#?\s*(\d{{4,8}})'.format(re.escape(kw)), text, re.I)
        if m and 4<=len(m.group(1))<=8: return m.group(1)
    for l in [6,5,4,7,8]:
        m = re.findall(r'\b(\d{'+str(l)+r'})\b', text)
        if m: return m[0]
    lines = text.split('\n')
    for line in reversed(lines):
        m = re.search(r'(\d{4,8})\s*$', line)
        if m: return m.group(1)
    m = re.search(r'[\(\[]\s*(\d{4,8})\s*[\)\]]', text)
    if m: return m.group(1)
    m = re.findall(r'(\d{4,8})', text)
    return max(m, key=len) if m else None

def parse_agent_sms_response(response_data):
    records = []
    if isinstance(response_data, list):
        for sms in response_data:
            if isinstance(sms, dict):
                number = str(sms.get('phone_number','')).strip()
                sender = str(sms.get('sender','')).strip()
                message = str(sms.get('message_body','')).strip()
                dt = str(sms.get('received_at',''))
                if number and message:
                    records.append({'sender':sender,'number':number,'message':message,'datetime':dt})
    return records

# ============= ASYNC SEND OTP (fixed default emoji for unknown country) =============
async def send_otp(app_bot, service, number, message, dt):
    try:
        otp = extract_otp(message)
        if not otp: return

        detected = detect_service(message)
        if detected == "UNKNOWN" and service and service != "UNKNOWN":
            detected = service
        service_name = detected.strip().title() if detected else "UNKNOWN"

        country_info = get_country_info(number)
        if country_info:
            iso = country_info["iso"]
            flag = country_info["flag"]
            name = country_info["name"]

            country_emoji_id = get_country_emoji(name)
            if country_emoji_id:
                country_display = f'<tg-emoji emoji-id="{country_emoji_id}">{flag}</tg-emoji><b>{iso}</b>'
            else:
                country_display = f'{flag}<b>{iso}</b>'

            service_emoji_id = get_service_emoji(name, detected)
        else:
            country_display = "<b>??</b>"
            name = "UNKNOWN"
            # ★ FIX: even for unknown country, look up default/global service emoji
            service_emoji_id = get_service_emoji("UNKNOWN", detected)

        if service_emoji_id:
            service_display = f'<tg-emoji emoji-id="{service_emoji_id}">🔧</tg-emoji>'
        else:
            service_display = f'#{service_name}'

        prefix_num, suffix_num = format_number(number)
        masked = f'<b>+{prefix_num}<tg-emoji emoji-id="{EMOJI["SEPARATOR"]}">➖</tg-emoji>{suffix_num}</b>'

        prefix_emoji = f'<tg-emoji emoji-id="{EMOJI["PREFIX"]}">🤖</tg-emoji>'
        text = f"{prefix_emoji}{country_display} | {service_display} {masked}"

        # Inline buttons with STYLE & CUSTOM EMOJI
        otp_btn = InlineKeyboardButton(
            "𝐎𝐓𝐏",
            copy_text=CopyTextButton(text=otp),
            style=KBS.SUCCESS,
            icon_custom_emoji_id=EMOJI["OTP_BUTTON"]
        )
        channel_btn = InlineKeyboardButton(
            "𝐂𝐇𝐀𝐍𝐍𝐄𝐋",
            url=CHANNEL_URL,
            style=KBS.PRIMARY,
            icon_custom_emoji_id=EMOJI["CHANNEL_BUTTON"]
        )
        bot_btn = InlineKeyboardButton(
            "𝐁𝐎𝐓",
            url=BOT_URL,
            style=KBS.PRIMARY,
            icon_custom_emoji_id=EMOJI["BOT_BUTTON"]
        )
        keyboard = InlineKeyboardMarkup([[otp_btn], [channel_btn, bot_btn]])

        sent = await app_bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        print(f"✅ Sent {service_name} ({name}) - {otp}")
        await asyncio.sleep(650)
        try:
            await app_bot.delete_message(GROUP_ID, sent.message_id)
        except:
            pass
    except Exception as e:
        print(f"❌ Send error: {e}")

# ============= ASYNC SCRAPER =============
async def scraper_loop(application: Application):
    page = 1
    while True:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            params = {"token": API_TOKEN, "from": today, "to": today, "limit": 100, "page": page}
            print(f"📡 Fetching page {page} ({today})...")
            r = requests.get(API_URL, params=params, timeout=10)
            r.raise_for_status()
            records = parse_agent_sms_response(r.json())
            if not records:
                print(f"📭 No records on page {page}")
                page = 1 if page>1 else 1
                await asyncio.sleep(3.5)
                continue
            now = time.time()
            new = 0
            for rec in records:
                if not rec['number'] or not rec['message']: continue
                otp = extract_otp(rec['message'])
                if not otp: continue
                uid = f"{rec['datetime']}_{rec['number']}_{otp}"
                async with seen_lock:
                    if uid in seen_dict:
                        if now - seen_dict[uid] > 86400:
                            seen_dict[uid] = now
                            new += 1
                            asyncio.create_task(send_otp(application.bot, rec['sender'], rec['number'], rec['message'], rec['datetime']))
                    else:
                        seen_dict[uid] = now
                        new += 1
                        asyncio.create_task(send_otp(application.bot, rec['sender'], rec['number'], rec['message'], rec['datetime']))
                if len(seen_dict) % 50 == 0:
                    with open(SEEN_FILE, 'w') as f: json.dump(seen_dict, f)
            if new:
                with open(SEEN_FILE, 'w') as f: json.dump(seen_dict, f)
                print(f"🎯 Page {page}: {new} new OTPs")
            else:
                print(f"📭 Page {page}: no new OTPs")
            page += 1
            if page > 50: page = 1
            await asyncio.sleep(3.5)
        except Exception as e:
            print(f"❌ Scraper error: {e}")
            await asyncio.sleep(5)

# ============= ADMIN COMMANDS =============
pending_requests = {}

async def admin_only(update: Update):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only command.")
        return False
    return True

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    await update.message.reply_text("🤖 Bot Active\n✅ KBS style buttons\n✅ Scraper running every 3.5s")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    async with seen_lock:
        count = len(seen_dict)
    await update.message.reply_text(f"📊 {count} OTPs tracked")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    await update.message.reply_text("🏓 Pong")

async def set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    try:
        parts = update.message.text.split()
        if len(parts) < 3:
            await update.message.reply_text("❌ /set COUNTRY SERVICE")
            return
        country = parts[1].upper()
        service = parts[2].capitalize()
        existing = get_service_emoji(country, service)
        if existing:
            await update.message.reply_text(f"✅ {country} - {service} already set.\nID: <code>{existing}</code>", parse_mode="HTML")
            return
        pending_requests[update.effective_user.id] = {"country": country, "service": service}
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.upper()==country), "🏳")
        await update.message.reply_text(
            f"{flag} <b>{country}</b> - <b>{service}</b> needs an emoji.\n"
            f"Send: <code>{country}|{service}|EMOJI_ID</code>",
            parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def service_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    try:
        text = update.message.text.replace("/service", "", 1).strip()
        if not text:
            await update.message.reply_text("Format: /service ServiceName EmojiID")
            return
        if '|' in text:
            parts = text.split('|')
        else:
            parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("Emoji ID missing.")
            return
        service = parts[0].strip().capitalize()
        emoji_id = parts[1].strip()
        if not emoji_id.isdigit():
            await update.message.reply_text("Emoji ID must be numeric.")
            return
        emoji_data["global_services"][service.lower()] = emoji_id
        save_emoji_data(emoji_data)
        await update.message.reply_text(f"✅ {service} global emoji set: <code>{emoji_id}</code>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    txt = "📋 <b>Emoji List:</b>\n"
    if emoji_data.get("countries"):
        for ctry, data in emoji_data["countries"].items():
            flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.lower()==ctry), "🏳")
            txt += f"\n{flag} <b>{ctry.upper()}</b>"
            if "emoji_id" in data:
                txt += f"\n  🏴 Country: <code>{data['emoji_id']}</code>"
            for svc, eid in data.get("services", {}).items():
                txt += f"\n  📱 {svc.capitalize()}: <code>{eid}</code>"
    if emoji_data.get("global_services"):
        txt += "\n\n<b>🌐 Global Services:</b>"
        for svc, eid in emoji_data["global_services"].items():
            txt += f"\n  {svc.capitalize()}: <code>{eid}</code>"
    if not txt.strip():
        txt = "📭 Nothing set yet"
    await update.message.reply_text(txt, parse_mode="HTML")

async def receive_emoji_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or user_id not in pending_requests:
        return
    try:
        text = update.message.text.strip()
        parts = text.split("|")
        if len(parts) != 3 or not parts[2].isdigit():
            await update.message.reply_text("❌ Format: COUNTRY|SERVICE|EMOJI_ID")
            return
        country, service, eid = parts[0].upper(), parts[1].capitalize(), parts[2]
        cl, sl = country.lower(), service.lower()
        emoji_data.setdefault("countries", {}).setdefault(cl, {}).setdefault("services", {})[sl] = eid
        save_emoji_data(emoji_data)
        del pending_requests[user_id]
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.upper()==country), "🏳")
        await update.message.reply_text(
            f"✅ {flag} <b>{country}</b> - <b>{service}</b>\nID: <code>{eid}</code>",
            parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        if user_id in pending_requests: del pending_requests[user_id]

# ============= MAIN (with graceful shutdown) =============
async def main():
    print("🚀 Starting OTP Bot with KBS style & default emoji fix...")
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(CommandHandler("set", set_cmd))
    application.add_handler(CommandHandler("service", service_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_emoji_id))

    # Flask keep‑alive
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False), daemon=True).start()

    # Reset seen on first run
    reset_seen()

    # Start the scraper inside the same event loop
    loop = asyncio.get_running_loop()
    scraper_task = asyncio.create_task(scraper_loop(application))

    print("✅ Bot is now running. Press Ctrl+C to stop.")

    # Graceful shutdown on SIGINT/SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(application, scraper_task)))
        except NotImplementedError:
            pass

    # Drop pending updates to avoid conflicts from previous runs
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.run_polling(drop_pending_updates=True)

async def shutdown(application, scraper_task):
    print("\n🛑 Shutting down...")
    scraper_task.cancel()
    try:
        await scraper_task
    except asyncio.CancelledError:
        pass
    # Cancel all remaining tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    print("✅ Shutdown complete.")
    asyncio.get_running_loop().stop()

if __name__ == "__main__":
    asyncio.run(main())
