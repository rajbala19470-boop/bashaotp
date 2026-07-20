import time
import requests
import threading
import re
import json
import os
from datetime import datetime
from telebot import TeleBot, types
from telebot.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
)
from flask import Flask

# ================= কনফিগারেশন =================
BOT_TOKEN = "8208003630:AAE9PGWAetvkB2SDcOigYS5Yjfo7UzqUvN4"
GROUP_ID = "-1004380384761"
API_TOKEN = "6e4b2ca76e753ac9024d3c71ca59d4e6"
API_URL = "http://headshotsms.kdns.fr/ints/login/api/agent_sms.php"
CHANNEL_URL = "https://t.me/RHTotp"
BOT_URL = "http://t.me/RhtNumberRobot"
ADMIN_IDS = [8744359777]

SEEN_FILE = "sent_otps.json"
EMOJI_DATA_FILE = "emoji_data.json"

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

# ================= ইমোজি আইডি =================
EMOJI = {
    "SEPARATOR": "6307542847251814164",
    "PREFIX": "4958725487682650920",
    "OTP_BUTTON": "6206420230269310869",
    "CHANNEL_BUTTON": "6204010762206189094",
    "BOT_BUTTON": "5339267587337370029",
    "SUCCESS": "6205984471477393007",  # ✅
}

# ================= সার্ভিস ডিটেকশন প্যাটার্ন =================
SERVICE_PATTERNS = {
    "WhatsApp": [r'whatsapp', r'WhatsApp', r'whatsapp business', r'WhatsApp Business'],
    "Google": [r'google', r'gmail', r'google.*verification'],
    "Facebook": [r'facebook', r'fb', r'facebook.*code'],
    "Instagram": [r'instagram', r'ig'],
    "Telegram": [r'telegram', r'Telegram'],
    "TikTok": [r'tiktok', r'tik\s*tok'],
    "Snapchat": [r'snapchat'],
    "Twitter": [r'twitter', r'x\s*verification'],
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
    "Epic": [r'epic\s*games'],
}

def detect_service_from_message(message):
    if not message:
        return "UNKNOWN"
    msg = message.lower()
    for service, patterns in SERVICE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, msg):
                return service
    return "UNKNOWN"

# ============= ফ্লাস্ক ==============
app = Flask(__name__)
@app.route("/")
def home():
    return "OK"

# ============= ইমোজি ডাটা ম্যানেজমেন্ট ==============
def load_emoji_data():
    if os.path.exists(EMOJI_DATA_FILE):
        with open(EMOJI_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"countries": {}}

def save_emoji_data(data):
    with open(EMOJI_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

emoji_data = load_emoji_data()

def get_country_emoji(country_name_upper):
    name_lower = country_name_upper.lower()
    country = emoji_data.get("countries", {}).get(name_lower, {})
    return country.get("emoji_id")

def get_service_emoji(country_name, service_name):
    country_lower = country_name.lower()
    services = emoji_data.get("countries", {}).get(country_lower, {}).get("services", {})
    return services.get(service_name.lower())

# ============= OTP স্টোরেজ ==============
seen_dict = {}
seen_lock = threading.Lock()

def reset_seen():
    global seen_dict
    seen_dict = {}
    if os.path.exists(SEEN_FILE):
        os.remove(SEEN_FILE)

# ============= কান্ট্রি ম্যাপিং =============
COUNTRY_CODE_MAP = {
    "1": ("US", "🇺🇸", "USA"),
    "7": ("RU", "🇷🇺", "RUSSIA"),
    "20": ("EG", "🇪🇬", "EGYPT"),
    "27": ("ZA", "🇿🇦", "SOUTH AFRICA"),
    "30": ("GR", "🇬🇷", "GREECE"),
    "31": ("NL", "🇳🇱", "NETHERLANDS"),
    "33": ("FR", "🇫🇷", "FRANCE"),
    "34": ("ES", "🇪🇸", "SPAIN"),
    "39": ("IT", "🇮🇹", "ITALY"),
    "40": ("RO", "🇷🇴", "ROMANIA"),
    "41": ("CH", "🇨🇭", "SWITZERLAND"),
    "44": ("GB", "🇬🇧", "UNITED KINGDOM"),
    "46": ("SE", "🇸🇪", "SWEDEN"),
    "48": ("PL", "🇵🇱", "POLAND"),
    "49": ("DE", "🇩🇪", "GERMANY"),
    "52": ("MX", "🇲🇽", "MEXICO"),
    "55": ("BR", "🇧🇷", "BRAZIL"),
    "60": ("MY", "🇲🇾", "MALAYSIA"),
    "63": ("PH", "🇵🇭", "PHILIPPINES"),
    "66": ("TH", "🇹🇭", "THAILAND"),
    "81": ("JP", "🇯🇵", "JAPAN"),
    "82": ("KR", "🇰🇷", "SOUTH KOREA"),
    "84": ("VN", "🇻🇳", "VIETNAM"),
    "86": ("CN", "🇨🇳", "CHINA"),
    "90": ("TR", "🇹🇷", "TURKEY"),
    "91": ("IN", "🇮🇳", "INDIA"),
    "92": ("PK", "🇵🇰", "PAKISTAN"),
    "93": ("AF", "🇦🇫", "AFGHANISTAN"),
    "94": ("LK", "🇱🇰", "SRI LANKA"),
    "212": ("MA", "🇲🇦", "MOROCCO"),
    "213": ("DZ", "🇩🇿", "ALGERIA"),
    "234": ("NG", "🇳🇬", "NIGERIA"),
    "251": ("ET", "🇪🇹", "ETHIOPIA"),
    "254": ("KE", "🇰🇪", "KENYA"),
    "263": ("ZW", "🇿🇼", "ZIMBABWE"),
    "351": ("PT", "🇵🇹", "PORTUGAL"),
    "380": ("UA", "🇺🇦", "UKRAINE"),
    "880": ("BD", "🇧🇩", "BANGLADESH"),
    "966": ("SA", "🇸🇦", "SAUDI ARABIA"),
    "971": ("AE", "🇦🇪", "UAE"),
    "977": ("NP", "🇳🇵", "NEPAL"),
    "994": ("AZ", "🇦🇿", "AZERBAIJAN"),
}

def get_country_info(number):
    clean = number.replace("+", "")
    for code in sorted(COUNTRY_CODE_MAP.keys(), key=len, reverse=True):
        if clean.startswith(code):
            iso, flag, name = COUNTRY_CODE_MAP[code]
            return {"iso": iso, "flag": flag, "name": name}
    return None

# ============= OTP এক্সট্র্যাক্টর =============
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
    m = re.findall(r'(\d{4,8})', text)
    return max(m, key=len) if m else None

# ============= API পার্সার =============
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

# ============= মেসেজ সেন্ড (নতুন স্টাইল) =============
def send_otp_to_group(service, number, message, dt):
    try:
        otp = extract_otp(message)
        if not otp: return

        # সার্ভিস ডিটেক্ট
        detected = detect_service_from_message(message)
        if detected == "UNKNOWN" and service and service != "UNKNOWN":
            detected = service
        service_name = detected.strip().title() if detected else "UNKNOWN"

        # কান্ট্রি ইনফো
        country_info = get_country_info(number)
        if country_info:
            iso = country_info["iso"]
            flag = country_info["flag"]
            name = country_info["name"]

            # কান্ট্রি ইমোজি
            country_emoji_id = get_country_emoji(name)
            if country_emoji_id:
                country_display = f'<tg-emoji emoji-id="{country_emoji_id}">{flag}</tg-emoji><b>{iso}</b>'
            else:
                country_display = f'{flag}<b>{iso}</b>'

            # সার্ভিস ইমোজি
            service_emoji_id = get_service_emoji(name, detected)
        else:
            country_display = "<b>??</b>"
            service_emoji_id = None
            name = "UNKNOWN"

        if service_emoji_id:
            service_display = f'<tg-emoji emoji-id="{service_emoji_id}">🔧</tg-emoji>'
        else:
            service_display = f'#{service_name}'

        # মাস্কড নাম্বার
        clean = number.replace("+","")
        pfx = clean[:5] if len(clean)>=5 else clean[:len(clean)-4]
        sfx = clean[-4:] if len(clean)>=4 else clean
        masked = f'<b>+{pfx}<tg-emoji emoji-id="{EMOJI["SEPARATOR"]}">➖</tg-emoji>{sfx}</b>'

        # প্রিফিক্স
        prefix = f'<tg-emoji emoji-id="{EMOJI["PREFIX"]}">🤖</tg-emoji>'

        text = f"{prefix}{country_display} | {service_display} {masked}"

        # ────────── বাটন (স্টাইল + কাস্টম ইমোজি) ──────────
        # style: 2 = success (সবুজ), 1 = primary (নীল)
        otp_btn = InlineKeyboardButton(
            text="𝐎𝐓𝐏",
            copy_text=CopyTextButton(text=otp),
            style=2,                                 # success green
            icon_custom_emoji_id=EMOJI["OTP_BUTTON"]
        )
        channel_btn = InlineKeyboardButton(
            text="𝐂𝐇𝐀𝐍𝐍𝐄𝐋",
            url=CHANNEL_URL,
            style=1,                                 # primary blue
            icon_custom_emoji_id=EMOJI["CHANNEL_BUTTON"]
        )
        bot_btn = InlineKeyboardButton(
            text="𝐁𝐎𝐓",
            url=BOT_URL,
            style=1,
            icon_custom_emoji_id=EMOJI["BOT_BUTTON"]
        )
        keyboard = InlineKeyboardMarkup([[otp_btn], [channel_btn, bot_btn]])

        sent = bot.send_message(
            GROUP_ID, text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        print(f"✅ Sent {service_name} ({name})")
        threading.Thread(target=lambda: time.sleep(650) or bot.delete_message(GROUP_ID, sent.message_id)).start()
    except Exception as e:
        print(f"❌ Send error: {e}")

# ============= স্ক্র্যাপার =============
def otp_scraper():
    page = 1
    while True:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            params = {"token": API_TOKEN, "from": today, "to": today, "limit": 100, "page": page}
            r = requests.get(API_URL, params=params, timeout=10)
            r.raise_for_status()
            records = parse_agent_sms_response(r.json())
            if not records:
                page = 1 if page>1 else 1
                time.sleep(10)
                continue
            now = time.time()
            new = 0
            for rec in records:
                if not rec['number'] or not rec['message']: continue
                otp = extract_otp(rec['message'])
                if not otp: continue
                uid = f"{rec['datetime']}_{rec['number']}_{otp}"
                with seen_lock:
                    if uid in seen_dict:
                        if now - seen_dict[uid] > 86400:
                            seen_dict[uid] = now
                            new += 1
                            send_otp_to_group(rec['sender'], rec['number'], rec['message'], rec['datetime'])
                    else:
                        seen_dict[uid] = now
                        new += 1
                        send_otp_to_group(rec['sender'], rec['number'], rec['message'], rec['datetime'])
                if len(seen_dict) % 50 == 0:
                    with open(SEEN_FILE,'w') as f: json.dump(seen_dict, f)
            if new:
                with open(SEEN_FILE,'w') as f: json.dump(seen_dict, f)
                print(f"🎯 {new} new")
            page += 1
            if page > 50: page = 1
        except Exception as e:
            print(f"Scraper error: {e}")
            time.sleep(5)

# ============= অ্যাডমিন কমান্ড =============
pending_requests = {}

def admin_only(func):
    def wrapper(message):
        if message.from_user.id not in ADMIN_IDS:
            return
        return func(message)
    return wrapper

@bot.message_handler(commands=["start"])
@admin_only
def start_cmd(message):
    bot.reply_to(message, "🤖 বট রানিং")

@bot.message_handler(commands=["stats"])
@admin_only
def stats_cmd(message):
    bot.reply_to(message, f"📊 {len(seen_dict)} OTPs tracked")

@bot.message_handler(commands=["ping"])
@admin_only
def ping_cmd(message):
    bot.reply_to(message, "🏓 Pong")

@bot.message_handler(commands=["set"])
@admin_only
def set_cmd(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ ফরম্যাট: /set COUNTRY SERVICE")
            return
        country = parts[1].upper()
        service = parts[2].capitalize()
        existing = get_service_emoji(country, service)
        if existing:
            bot.reply_to(message, f"✅ {country} এর {service} এর ইমোজি আগেই সেট করা আছে।", parse_mode="HTML")
            return
        pending_requests[message.from_user.id] = {"country": country, "service": service}
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.upper()==country), "🏳")
        bot.reply_to(message,
            f"{flag} <b>{country}</b> - <b>{service}</b> এর ইমোজি সেট নেই।\n\n"
            f"ইমোজি আইডি পাঠান:\n<code>{country}|{service}|EMOJI_ID</code>",
            parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=["list"])
@admin_only
def list_cmd(message):
    if not emoji_data.get("countries"):
        bot.reply_to(message, "📭 এখনও কিছু সেট করা হয়নি")
        return
    txt = "📋 <b>ইমোজি লিস্ট:</b>\n"
    for ctry, data in emoji_data["countries"].items():
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.lower()==ctry), "🏳")
        txt += f"\n{flag} <b>{ctry.upper()}</b>"
        if "emoji_id" in data:
            txt += f"\n  🏴 কান্ট্রি: <code>{data['emoji_id']}</code>"
        for svc, eid in data.get("services", {}).items():
            txt += f"\n  📱 {svc.capitalize()}: <code>{eid}</code>"
    bot.reply_to(message, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.from_user.id in pending_requests)
def receive_emoji_id(message):
    try:
        parts = message.text.strip().split("|")
        if len(parts) != 3 or not parts[2].isdigit():
            bot.reply_to(message, "❌ ফরম্যাট: COUNTRY|SERVICE|EMOJI_ID")
            return
        country, service, eid = parts[0].strip().upper(), parts[1].strip().capitalize(), parts[2].strip()
        country_lower = country.lower()
        service_lower = service.lower()
        emoji_data.setdefault("countries", {}).setdefault(country_lower, {})
        emoji_data["countries"][country_lower].setdefault("services", {})[service_lower] = eid
        save_emoji_data(emoji_data)
        del pending_requests[message.from_user.id]
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.upper()==country), "🏳")
        bot.reply_to(message,
            f"✅ {flag} <b>{country}</b> - <b>{service}</b>\n"
            f"🆔 ইমোজি আইডি: <code>{eid}</code>\nপরবর্তী OTP তে এই ইমোজি দেখাবে।",
            parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")
        if message.from_user.id in pending_requests: del pending_requests[message.from_user.id]

# ============= মেইন =============
if __name__ == "__main__":
    print("🚀 Starting with custom emoji buttons...")
    reset_seen()
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False), daemon=True).start()
    threading.Thread(target=otp_scraper, daemon=True).start()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
