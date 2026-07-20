import time
import requests
import threading
import html
import re
import json
import os
from datetime import datetime, timedelta
from telebot import TeleBot, types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from flask import Flask

# ================= CONFIG ==================
BOT_TOKEN = "8208003630:AAE9PGWAetvkB2SDcOigYS5Yjfo7UzqUvN4"
GROUP_ID = "-1004380384761"
API_TOKEN = "6e4b2ca76e753ac9024d3c71ca59d4e6"
API_URL = "http://headshotsms.kdns.fr/ints/login/api/agent_sms.php"
CHANNEL_URL = "Your Otp Channel"
BOT_URL = "Your Num Channel"
ADMIN_IDS = [8744359777]  # আপনার টেলিগ্রাম ইউজার আইডি দিন

SEEN_FILE = "sent_otps.json"
EMOJI_DATA_FILE = "emoji_data.json"  # কাস্টম ইমোজি ডাটা

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

# ================= ইমোজি ID (স্থায়ী) =================
EMOJI = {
    "SEPARATOR": "6307542847251814164",
    "OTP_BUTTON": "6206420230269310869",
    "CHANNEL_BUTTON": "6204010762206189094",
    "BOT_BUTTON": "5339267587337370029",
    "SUCCESS": "6205984471477393007",
    "PREFIX": "4958725487682650920"
}

# ================= ডিফল্ট ইমোজি ম্যাপিং =================
DEFAULT_EMOJIS = {
    "services": {
        "uber": "5298715455316303708",
        "bolt": "5343587658717219067"
    },
    "countries": {
        "kenya": "5294051631933967760",
        "morocco": "5292108962391414885"
    }
}

# ============= ফ্লাস্ক কিপ-এলাইভ ==============
app = Flask(__name__)
@app.route("/")
def home():
    return "OTP Bot Running"

# ============= ইমোজি ডাটা লোড/সেভ ==============
def load_emoji_data():
    if os.path.exists(EMOJI_DATA_FILE):
        with open(EMOJI_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"countries": {}, "services": {}}

def save_emoji_data(data):
    with open(EMOJI_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

emoji_data = load_emoji_data()

def get_country_emoji(country_name_upper):
    """দেশের জন্য ইমোজি ID রিটার্ন (প্রায়োরিটি: emoji_data > DEFAULT_EMOJIS)"""
    name_lower = country_name_upper.lower()
    # 1. কাস্টম ডাটা থেকে
    if name_lower in emoji_data["countries"]:
        return emoji_data["countries"][name_lower]
    # 2. ডিফল্ট থেকে
    if name_lower in DEFAULT_EMOJIS["countries"]:
        return DEFAULT_EMOJIS["countries"][name_lower]
    return None

def get_service_emoji(service_name_capitalized):
    """সার্ভিসের জন্য ইমোজি ID (প্রায়োরিটি: emoji_data > DEFAULT_EMOJIS)"""
    name_lower = service_name_capitalized.lower()
    if name_lower in emoji_data["services"]:
        return emoji_data["services"][name_lower]
    if name_lower in DEFAULT_EMOJIS["services"]:
        return DEFAULT_EMOJIS["services"][name_lower]
    return None

# ============= সীন OTP ম্যানেজমেন্ট ==============
def load_seen_otps():
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, 'r') as f:
                return json.load(f)
    except: pass
    return {}

def save_seen_otps(data):
    with open(SEEN_FILE, 'w') as f:
        json.dump(data, f)

seen_dict = load_seen_otps()
seen_lock = threading.Lock()

def cleanup_old_otps():
    while True:
        time.sleep(3600)
        seen_dict = load_seen_otps()
        now = time.time()
        cutoff = now - 24*3600
        old = len(seen_dict)
        seen_dict = {k:v for k,v in seen_dict.items() if v > cutoff}
        if len(seen_dict) < old:
            save_seen_otps(seen_dict)
            print(f"🧹 Cleaned {old - len(seen_dict)} old OTPs")

# ============= কান্ট্রি ডিটেকশন ও আইএসও ম্যাপিং ==============
COUNTRY_CODE_MAP = {
    "263": ("ZW", "🇿🇼", "ZIMBABWE"), "1": ("US", "🇺🇸", "USA"),
    "52": ("MX", "🇲🇽", "MEXICO"), "58": ("VE", "🇻🇪", "VENEZUELA"),
    "55": ("BR", "🇧🇷", "BRAZIL"), "54": ("AR", "🇦🇷", "ARGENTINA"),
    "57": ("CO", "🇨🇴", "COLOMBIA"), "51": ("PE", "🇵🇪", "PERU"),
    "56": ("CL", "🇨🇱", "CHILE"), "91": ("IN", "🇮🇳", "INDIA"),
    "92": ("PK", "🇵🇰", "PAKISTAN"), "62": ("ID", "🇮🇩", "INDONESIA"),
    "63": ("PH", "🇵🇭", "PHILIPPINES"), "84": ("VN", "🇻🇳", "VIETNAM"),
    "66": ("TH", "🇹🇭", "THAILAND"), "60": ("MY", "🇲🇾", "MALAYSIA"),
    "86": ("CN", "🇨🇳", "CHINA"), "81": ("JP", "🇯🇵", "JAPAN"),
    "82": ("KR", "🇰🇷", "SOUTH KOREA"), "880": ("BD", "🇧🇩", "BANGLADESH"),
    "94": ("LK", "🇱🇰", "SRI LANKA"), "95": ("MM", "🇲🇲", "MYANMAR"),
    "977": ("NP", "🇳🇵", "NEPAL"), "93": ("AF", "🇦🇫", "AFGHANISTAN"),
    "966": ("SA", "🇸🇦", "SAUDI ARABIA"), "971": ("AE", "🇦🇪", "UAE"),
    "98": ("IR", "🇮🇷", "IRAN"), "964": ("IQ", "🇮🇶", "IRAQ"),
    "972": ("IL", "🇮🇱", "ISRAEL"), "90": ("TR", "🇹🇷", "TURKEY"),
    "967": ("YE", "🇾🇪", "YEMEN"), "962": ("JO", "🇯🇴", "JORDAN"),
    "961": ("LB", "🇱🇧", "LEBANON"), "965": ("KW", "🇰🇼", "KUWAIT"),
    "974": ("QA", "🇶🇦", "QATAR"), "973": ("BH", "🇧🇭", "BAHRAIN"),
    "968": ("OM", "🇴🇲", "OMAN"), "44": ("GB", "🇬🇧", "UNITED KINGDOM"),
    "7": ("RU", "🇷🇺", "RUSSIA"), "33": ("FR", "🇫🇷", "FRANCE"),
    "49": ("DE", "🇩🇪", "GERMANY"), "39": ("IT", "🇮🇹", "ITALY"),
    "34": ("ES", "🇪🇸", "SPAIN"), "31": ("NL", "🇳🇱", "NETHERLANDS"),
    "48": ("PL", "🇵🇱", "POLAND"), "380": ("UA", "🇺🇦", "UKRAINE"),
    "40": ("RO", "🇷🇴", "ROMANIA"), "32": ("BE", "🇧🇪", "BELGIUM"),
    "46": ("SE", "🇸🇪", "SWEDEN"), "41": ("CH", "🇨🇭", "SWITZERLAND"),
    "43": ("AT", "🇦🇹", "AUSTRIA"), "30": ("GR", "🇬🇷", "GREECE"),
    "351": ("PT", "🇵🇹", "PORTUGAL"), "36": ("HU", "🇭🇺", "HUNGARY"),
    "420": ("CZ", "🇨🇿", "CZECH REPUBLIC"), "994": ("AZ", "🇦🇿", "AZERBAIJAN"),
    "995": ("GE", "🇬🇪", "GEORGIA"), "375": ("BY", "🇧🇾", "BELARUS"),
    "234": ("NG", "🇳🇬", "NIGERIA"), "20": ("EG", "🇪🇬", "EGYPT"),
    "27": ("ZA", "🇿🇦", "SOUTH AFRICA"), "212": ("MA", "🇲🇦", "MOROCCO"),
    "213": ("DZ", "🇩🇿", "ALGERIA"), "254": ("KE", "🇰🇪", "KENYA"),
    "251": ("ET", "🇪🇹", "ETHIOPIA"), "233": ("GH", "🇬🇭", "GHANA"),
    "225": ("CI", "🇨🇮", "IVORY COAST"), "255": ("TZ", "🇹🇿", "TANZANIA"),
    "256": ("UG", "🇺🇬", "UGANDA"), "269": ("KM", "🇰🇲", "COMOROS"),
    "998": ("UZ", "🇺🇿", "UZBEKISTAN"), "996": ("KG", "🇰🇬", "KYRGYZSTAN"),
    "992": ("TJ", "🇹🇯", "TAJIKISTAN"), "993": ("TM", "🇹🇲", "TURKMENISTAN"),
}

def get_country_info(number):
    clean = number.replace("+", "")
    for code in sorted(COUNTRY_CODE_MAP.keys(), key=len, reverse=True):
        if clean.startswith(code):
            iso, flag, name = COUNTRY_CODE_MAP[code]
            return {"iso": iso, "flag": flag, "name": name}
    return None

# ============= OTP এক্সট্রাক্টর (আগের মতো) =============
def extract_otp(text):
    if not text: return None
    text = ' '.join(text.split())
    # ... (আগের সম্পূর্ণ extract_otp ফাংশন বসান) ...
    # এখানে সংক্ষেপে দিচ্ছি, আপনি আগের বড় ফাংশনটি বসিয়ে দেবেন।
    match = re.search(r'(\d{3})[-—\s](\d{3})', text)
    if match: return match.group(1)+match.group(2)
    # ... বাকি প্যাটার্ন ...
    matches = re.findall(r'\b(\d{4,8})\b', text)
    if matches: return max(matches, key=len)
    return None

# ============= API পার্সার =============
def parse_agent_sms_response(response_data):
    records = []
    if isinstance(response_data, list):
        for sms in response_data:
            if isinstance(sms, dict):
                number = str(sms.get('phone_number', '')).strip()
                service = str(sms.get('sender', '')).strip()
                message = str(sms.get('message_body', '')).strip()
                dt = str(sms.get('received_at', ''))
                if number and message:
                    if not service:
                        m = re.search(r'Your (\w+) verification', message, re.IGNORECASE)
                        service = m.group(1) if m else "UNKNOWN"
                    records.append({
                        'service': service,
                        'number': number,
                        'message': message,
                        'datetime': dt
                    })
    return records

# ============= ফরম্যাটিং ও মেসেজ সেন্ড =============
def send_otp_to_group(service, number, message, dt):
    try:
        otp = extract_otp(message)
        if not otp:
            return

        # ---- Prefix ----
        prefix_emoji = f'<tg-emoji emoji-id="{EMOJI["PREFIX"]}">🤖</tg-emoji>'

        # ---- Country ----
        country_info = get_country_info(number)
        if country_info:
            iso = country_info["iso"]
            flag = country_info["flag"]
            name = country_info["name"]
            emoji_id = get_country_emoji(name)
            if emoji_id:
                country_display = f'<tg-emoji emoji-id="{emoji_id}">{flag}</tg-emoji><b>{iso}</b>'
            else:
                country_display = f'{flag}<b>{iso}</b>'
        else:
            # অজানা কান্ট্রি
            # যদি কোনো নাম পাওয়া না যায় (একেবারেই মেলেনি)
            country_display = "<b>??</b>"  # ফলব্যাক

        # ---- Service ----
        service_clean = service.strip().title() if service else "UNKNOWN"
        emoji_id = get_service_emoji(service_clean)
        if emoji_id:
            service_display = f'<tg-emoji emoji-id="{emoji_id}">🔧</tg-emoji>'
        else:
            service_display = f'#{service_clean}'

        # ---- Masked Number ----
        clean_num = number.replace("+", "")
        if len(clean_num) >= 9:
            prefix_num = clean_num[:5]
            suffix_num = clean_num[-4:]
        else:
            prefix_num = clean_num[:5] if len(clean_num)>=5 else clean_num
            suffix_num = clean_num[-4:] if len(clean_num)>=4 else ""
        masked = f'<b>+{prefix_num}<tg-emoji emoji-id="{EMOJI["SEPARATOR"]}">➖</tg-emoji>{suffix_num}</b>'

        # ---- Full Text ----
        text = f"{prefix_emoji}{country_display} | {service_display} {masked}"

        # ---- Buttons ----
        otp_btn = InlineKeyboardButton(
            text="𝐎𝐓𝐏 📋",
            copy_text=CopyTextButton(text=otp)
        )
        channel_btn = InlineKeyboardButton(
            text="𝐂𝐇𝐀𝐍𝐍𝐄𝐋 📢",
            url=CHANNEL_URL
        )
        bot_btn = InlineKeyboardButton(
            text="𝐁𝐎𝐓 🤖",
            url=BOT_URL
        )
        keyboard = InlineKeyboardMarkup([[otp_btn], [channel_btn, bot_btn]])

        sent = bot.send_message(
            GROUP_ID, text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        print(f"✅ OTP sent: {service_clean} - {number}")
        threading.Thread(target=delete_after_delay, args=(sent.message_id, 650)).start()
    except Exception as e:
        print(f"❌ Send error: {e}")

def delete_after_delay(msg_id, delay):
    time.sleep(delay)
    try:
        bot.delete_message(GROUP_ID, msg_id)
    except: pass

# ============= অ্যাডমিন কমান্ড (শুধু ADMIN_IDS) =============
def admin_only(func):
    def wrapper(message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ Admin only command.")
            return
        return func(message)
    return wrapper

@bot.message_handler(commands=["start"])
@admin_only
def start_cmd(message):
    bot.reply_to(message, "🤖 Bot Active")

@bot.message_handler(commands=["stats"])
@admin_only
def stats_cmd(message):
    with seen_lock:
        count = len(seen_dict)
    bot.reply_to(message, f"📊 {count} OTPs tracked")

@bot.message_handler(commands=["ping"])
@admin_only
def ping_cmd(message):
    bot.reply_to(message, "🏓 Pong!")

@bot.message_handler(commands=["setcountry"])
@admin_only
def set_country(message):
    try:
        # ফরম্যাট: /setcountry KENYA|5294051631933967760
        parts = message.text.split(" ", 1)[1].split("|")
        if len(parts) != 2:
            bot.reply_to(message, "Format: /setcountry COUNTRY|EMOJI_ID\nExample: /setcountry BANGLADESH|6204108584381322968")
            return
        country = parts[0].strip().lower()
        emoji_id = parts[1].strip()
        emoji_data["countries"][country] = emoji_id
        save_emoji_data(emoji_data)
        bot.reply_to(message, f'<tg-emoji emoji-id="{emoji_id}">✅</tg-emoji> Country emoji set for {country.upper()}', parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=["setservice"])
@admin_only
def set_service(message):
    try:
        parts = message.text.split(" ", 1)[1].split("|")
        if len(parts) != 2:
            bot.reply_to(message, "Format: /setservice SERVICE|EMOJI_ID\nExample: /setservice WhatsApp|5294000123456789012")
            return
        service = parts[0].strip().lower()
        emoji_id = parts[1].strip()
        emoji_data["services"][service] = emoji_id
        save_emoji_data(emoji_data)
        bot.reply_to(message, f'<tg-emoji emoji-id="{emoji_id}">✅</tg-emoji> Service emoji set for {service.capitalize()}', parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# ============= স্ক্র্যাপার থ্রেড =============
def otp_scraper():
    print("🟢 Scraper Started")
    page = 1
    while True:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            params = {"token": API_TOKEN, "from": today, "to": today, "limit": 100, "page": page}
            print(f"📡 Page {page}")
            r = requests.get(API_URL, params=params, timeout=10)
            r.raise_for_status()
            records = parse_agent_sms_response(r.json())
            if not records:
                if page == 1:
                    print("📭 No records today")
                else:
                    page = 1
                time.sleep(10)
                continue
            current_time = time.time()
            new = 0
            for rec in records:
                if not rec['number'] or not rec['message']: continue
                otp = extract_otp(rec['message'])
                if not otp: continue
                uid = f"{rec['datetime']}_{rec['number']}_{otp}"
                with seen_lock:
                    if uid in seen_dict: continue
                    seen_dict[uid] = current_time
                    new += 1
                    if len(seen_dict) % 50 == 0: save_seen_otps(seen_dict)
                send_otp_to_group(rec['service'], rec['number'], rec['message'], rec['datetime'])
            if new:
                save_seen_otps(seen_dict)
                print(f"🎯 {new} new OTPs")
            page += 1
            if page > 50: page = 1
        except Exception as e:
            print(f"Scraper error: {e}")
            time.sleep(5)

# ============= মেইন =============
if __name__ == "__main__":
    print("="*50)
    print("🚀 Starting Bot with new format")
    threading.Thread(target=cleanup_old_otps, daemon=True).start()
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False), daemon=True).start()
    threading.Thread(target=otp_scraper, daemon=True).start()
    print("✅ Bot running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
