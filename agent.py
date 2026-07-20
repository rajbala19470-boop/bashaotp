import asyncio
import time
import requests
import re
import json
import os
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
    "WhatsApp": [r'whatsapp', r'WhatsApp', r'whatsapp business'],
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
    "Apple": [r'apple', r'icloud'],
    "Microsoft": [r'microsoft', r'outlook'],
    "Yahoo": [r'yahoo'],
    "LinkedIn": [r'linkedin'],
    "Signal": [r'signal'],
    "Viber": [r'viber'],
    "Line": [r'line'],
    "WeChat": [r'wechat', r'weixin'],
    "Skype": [r'skype'],
    "Airbnb": [r'airbnb'],
    "eBay": [r'ebay'],
    "Shopee": [r'shopee'],
    "Temu": [r'temu'],
    "Twitch": [r'twitch'],
    "Reddit": [r'reddit'],
    "Pinterest": [r'pinterest'],
    "Tinder": [r'tinder'],
    "Bumble": [r'bumble'],
    "Revolut": [r'revolut'],
    "Wise": [r'wise'],
    "Venmo": [r'venmo'],
    "CashApp": [r'cashapp', r'cash app'],
    "DoorDash": [r'doordash'],
    "Lyft": [r'lyft'],
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
    # 1. per-country service
    eid = emoji_data.get("countries", {}).get(country.lower(), {}).get("services", {}).get(service.lower())
    if eid: return eid
    # 2. global service
    eid = emoji_data.get("global_services", {}).get(service.lower())
    if eid: return eid
    # 3. default hardcoded
    return DEFAULT_SERVICE_EMOJIS.get(service.lower())

# ============= SEEN OTP STORAGE ==============
seen_dict = {}
seen_lock = asyncio.Lock()

def reset_seen():
    global seen_dict
    seen_dict = {}
    if os.path.exists(SEEN_FILE): os.remove(SEEN_FILE)

# ============= FULL COUNTRY CODE MAP (180+ COUNTRIES) =============
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
    "43": ("AT", "🇦🇹", "AUSTRIA"),
    "44": ("GB", "🇬🇧", "UNITED KINGDOM"),
    "46": ("SE", "🇸🇪", "SWEDEN"),
    "48": ("PL", "🇵🇱", "POLAND"),
    "49": ("DE", "🇩🇪", "GERMANY"),
    "51": ("PE", "🇵🇪", "PERU"),
    "52": ("MX", "🇲🇽", "MEXICO"),
    "54": ("AR", "🇦🇷", "ARGENTINA"),
    "55": ("BR", "🇧🇷", "BRAZIL"),
    "56": ("CL", "🇨🇱", "CHILE"),
    "57": ("CO", "🇨🇴", "COLOMBIA"),
    "58": ("VE", "🇻🇪", "VENEZUELA"),
    "60": ("MY", "🇲🇾", "MALAYSIA"),
    "62": ("ID", "🇮🇩", "INDONESIA"),
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
    "95": ("MM", "🇲🇲", "MYANMAR"),
    "98": ("IR", "🇮🇷", "IRAN"),
    "211": ("SS", "🇸🇸", "SOUTH SUDAN"),
    "212": ("MA", "🇲🇦", "MOROCCO"),
    "213": ("DZ", "🇩🇿", "ALGERIA"),
    "216": ("TN", "🇹🇳", "TUNISIA"),
    "218": ("LY", "🇱🇾", "LIBYA"),
    "220": ("GM", "🇬🇲", "GAMBIA"),
    "221": ("SN", "🇸🇳", "SENEGAL"),
    "222": ("MR", "🇲🇷", "MAURITANIA"),
    "223": ("ML", "🇲🇱", "MALI"),
    "224": ("GN", "🇬🇳", "GUINEA"),
    "225": ("CI", "🇨🇮", "IVORY COAST"),
    "226": ("BF", "🇧🇫", "BURKINA FASO"),
    "227": ("NE", "🇳🇪", "NIGER"),
    "228": ("TG", "🇹🇬", "TOGO"),
    "229": ("BJ", "🇧🇯", "BENIN"),
    "230": ("MU", "🇲🇺", "MAURITIUS"),
    "231": ("LR", "🇱🇷", "LIBERIA"),
    "232": ("SL", "🇸🇱", "SIERRA LEONE"),
    "233": ("GH", "🇬🇭", "GHANA"),
    "234": ("NG", "🇳🇬", "NIGERIA"),
    "235": ("TD", "🇹🇩", "CHAD"),
    "236": ("CF", "🇨🇫", "CENTRAL AFRICAN REPUBLIC"),
    "237": ("CM", "🇨🇲", "CAMEROON"),
    "238": ("CV", "🇨🇻", "CAPE VERDE"),
    "239": ("ST", "🇸🇹", "SAO TOME AND PRINCIPE"),
    "240": ("GQ", "🇬🇶", "EQUATORIAL GUINEA"),
    "241": ("GA", "🇬🇦", "GABON"),
    "242": ("CG", "🇨🇬", "CONGO"),
    "243": ("CD", "🇨🇩", "DR CONGO"),
    "244": ("AO", "🇦🇴", "ANGOLA"),
    "245": ("GW", "🇬🇼", "GUINEA-BISSAU"),
    "246": ("IO", "🇮🇴", "BRITISH INDIAN OCEAN"),
    "248": ("SC", "🇸🇨", "SEYCHELLES"),
    "249": ("SD", "🇸🇩", "SUDAN"),
    "250": ("RW", "🇷🇼", "RWANDA"),
    "251": ("ET", "🇪🇹", "ETHIOPIA"),
    "252": ("SO", "🇸🇴", "SOMALIA"),
    "253": ("DJ", "🇩🇯", "DJIBOUTI"),
    "254": ("KE", "🇰🇪", "KENYA"),
    "255": ("TZ", "🇹🇿", "TANZANIA"),
    "256": ("UG", "🇺🇬", "UGANDA"),
    "257": ("BI", "🇧🇮", "BURUNDI"),
    "258": ("MZ", "🇲🇿", "MOZAMBIQUE"),
    "260": ("ZM", "🇿🇲", "ZAMBIA"),
    "261": ("MG", "🇲🇬", "MADAGASCAR"),
    "262": ("RE", "🇷🇪", "REUNION"),
    "263": ("ZW", "🇿🇼", "ZIMBABWE"),
    "264": ("NA", "🇳🇦", "NAMIBIA"),
    "265": ("MW", "🇲🇼", "MALAWI"),
    "266": ("LS", "🇱🇸", "LESOTHO"),
    "267": ("BW", "🇧🇼", "BOTSWANA"),
    "268": ("SZ", "🇸🇿", "ESWATINI"),
    "269": ("KM", "🇰🇲", "COMOROS"),
    "290": ("SH", "🇸🇭", "SAINT HELENA"),
    "291": ("ER", "🇪🇷", "ERITREA"),
    "297": ("AW", "🇦🇼", "ARUBA"),
    "298": ("FO", "🇫🇴", "FAROE ISLANDS"),
    "299": ("GL", "🇬🇱", "GREENLAND"),
    "350": ("GI", "🇬🇮", "GIBRALTAR"),
    "351": ("PT", "🇵🇹", "PORTUGAL"),
    "352": ("LU", "🇱🇺", "LUXEMBOURG"),
    "353": ("IE", "🇮🇪", "IRELAND"),
    "354": ("IS", "🇮🇸", "ICELAND"),
    "355": ("AL", "🇦🇱", "ALBANIA"),
    "356": ("MT", "🇲🇹", "MALTA"),
    "357": ("CY", "🇨🇾", "CYPRUS"),
    "358": ("FI", "🇫🇮", "FINLAND"),
    "359": ("BG", "🇧🇬", "BULGARIA"),
    "370": ("LT", "🇱🇹", "LITHUANIA"),
    "371": ("LV", "🇱🇻", "LATVIA"),
    "372": ("EE", "🇪🇪", "ESTONIA"),
    "373": ("MD", "🇲🇩", "MOLDOVA"),
    "374": ("AM", "🇦🇲", "ARMENIA"),
    "375": ("BY", "🇧🇾", "BELARUS"),
    "376": ("AD", "🇦🇩", "ANDORRA"),
    "377": ("MC", "🇲🇨", "MONACO"),
    "378": ("SM", "🇸🇲", "SAN MARINO"),
    "380": ("UA", "🇺🇦", "UKRAINE"),
    "381": ("RS", "🇷🇸", "SERBIA"),
    "382": ("ME", "🇲🇪", "MONTENEGRO"),
    "383": ("XK", "🇽🇰", "KOSOVO"),
    "385": ("HR", "🇭🇷", "CROATIA"),
    "386": ("SI", "🇸🇮", "SLOVENIA"),
    "387": ("BA", "🇧🇦", "BOSNIA AND HERZEGOVINA"),
    "389": ("MK", "🇲🇰", "NORTH MACEDONIA"),
    "420": ("CZ", "🇨🇿", "CZECH REPUBLIC"),
    "421": ("SK", "🇸🇰", "SLOVAKIA"),
    "423": ("LI", "🇱🇮", "LIECHTENSTEIN"),
    "500": ("FK", "🇫🇰", "FALKLAND ISLANDS"),
    "501": ("BZ", "🇧🇿", "BELIZE"),
    "502": ("GT", "🇬🇹", "GUATEMALA"),
    "503": ("SV", "🇸🇻", "EL SALVADOR"),
    "504": ("HN", "🇭🇳", "HONDURAS"),
    "505": ("NI", "🇳🇮", "NICARAGUA"),
    "506": ("CR", "🇨🇷", "COSTA RICA"),
    "507": ("PA", "🇵🇦", "PANAMA"),
    "509": ("HT", "🇭🇹", "HAITI"),
    "590": ("GP", "🇬🇵", "GUADELOUPE"),
    "591": ("BO", "🇧🇴", "BOLIVIA"),
    "592": ("GY", "🇬🇾", "GUYANA"),
    "593": ("EC", "🇪🇨", "ECUADOR"),
    "594": ("GF", "🇬🇫", "FRENCH GUIANA"),
    "595": ("PY", "🇵🇾", "PARAGUAY"),
    "596": ("MQ", "🇲🇶", "MARTINIQUE"),
    "597": ("SR", "🇸🇷", "SURINAME"),
    "598": ("UY", "🇺🇾", "URUGUAY"),
    "599": ("BQ", "🇧🇶", "CARIBBEAN NETHERLANDS"),
    "880": ("BD", "🇧🇩", "BANGLADESH"),
    "960": ("MV", "🇲🇻", "MALDIVES"),
    "961": ("LB", "🇱🇧", "LEBANON"),
    "962": ("JO", "🇯🇴", "JORDAN"),
    "963": ("SY", "🇸🇾", "SYRIA"),
    "964": ("IQ", "🇮🇶", "IRAQ"),
    "965": ("KW", "🇰🇼", "KUWAIT"),
    "966": ("SA", "🇸🇦", "SAUDI ARABIA"),
    "967": ("YE", "🇾🇪", "YEMEN"),
    "968": ("OM", "🇴🇲", "OMAN"),
    "970": ("PS", "🇵🇸", "PALESTINE"),
    "971": ("AE", "🇦🇪", "UAE"),
    "972": ("IL", "🇮🇱", "ISRAEL"),
    "973": ("BH", "🇧🇭", "BAHRAIN"),
    "974": ("QA", "🇶🇦", "QATAR"),
    "975": ("BT", "🇧🇹", "BHUTAN"),
    "976": ("MN", "🇲🇳", "MONGOLIA"),
    "977": ("NP", "🇳🇵", "NEPAL"),
    "992": ("TJ", "🇹🇯", "TAJIKISTAN"),
    "993": ("TM", "🇹🇲", "TURKMENISTAN"),
    "994": ("AZ", "🇦🇿", "AZERBAIJAN"),
    "995": ("GE", "🇬🇪", "GEORGIA"),
    "996": ("KG", "🇰🇬", "KYRGYZSTAN"),
    "998": ("UZ", "🇺🇿", "UZBEKISTAN"),
}

def get_country_info(number):
    clean = number.replace("+", "")
    for code in sorted(COUNTRY_CODE_MAP.keys(), key=len, reverse=True):
        if clean.startswith(code):
            iso, flag, name = COUNTRY_CODE_MAP[code]
            return {"iso": iso, "flag": flag, "name": name}
    return None

# ============= FORMAT NUMBER (from your basha.py) =============
def format_number(number):
    """Formats phone number: +2126509559 -> ('21265', '9559')"""
    clean = number.replace('+', '').replace(' ', '').strip()
    if len(clean) < 9:
        return clean[:5] if len(clean) >= 5 else clean, clean[-4:] if len(clean) >= 4 else ""
    return clean[:5], clean[-4:]

# ============= OTP EXTRACTOR =============
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

# ============= API PARSER =============
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

# ============= SEND OTP TO GROUP =============
async def send_otp_to_group(app_bot, service, number, message, dt):
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
            service_emoji_id = None
            name = "UNKNOWN"

        if service_emoji_id:
            service_display = f'<tg-emoji emoji-id="{service_emoji_id}">🔧</tg-emoji>'
        else:
            service_display = f'#{service_name}'

        # format number using your basha.py logic
        prefix_num, suffix_num = format_number(number)
        masked = f'<b>+{prefix_num}<tg-emoji emoji-id="{EMOJI["SEPARATOR"]}">➖</tg-emoji>{suffix_num}</b>'

        prefix_emoji = f'<tg-emoji emoji-id="{EMOJI["PREFIX"]}">🤖</tg-emoji>'
        text = f"{prefix_emoji}{country_display} | {service_display} {masked}"

        # ====== INLINE BUTTONS WITH STYLE & CUSTOM EMOJI (like your example) ======
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
        # auto-delete after 650 seconds
        asyncio.create_task(delete_later(app_bot, sent.message_id))
    except Exception as e:
        print(f"❌ Send error: {e}")

async def delete_later(bot, msg_id):
    await asyncio.sleep(650)
    try:
        await bot.delete_message(GROUP_ID, msg_id)
    except:
        pass

# ============= SCRAPER LOOP =============
async def scraper_loop(app):
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
                await asyncio.sleep(10)
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
                            asyncio.create_task(send_otp_to_group(app.bot, rec['sender'], rec['number'], rec['message'], rec['datetime']))
                    else:
                        seen_dict[uid] = now
                        new += 1
                        asyncio.create_task(send_otp_to_group(app.bot, rec['sender'], rec['number'], rec['message'], rec['datetime']))
                if len(seen_dict) % 50 == 0:
                    with open(SEEN_FILE, 'w') as f: json.dump(seen_dict, f)
            if new:
                with open(SEEN_FILE, 'w') as f: json.dump(seen_dict, f)
                print(f"🎯 {new} new OTPs")
            page += 1
            if page > 50: page = 1
        except Exception as e:
            print(f"Scraper error: {e}")
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
    await update.message.reply_text("🤖 Bot Active\n\n✅ All commands working\n✅ Custom emoji buttons with style\n✅ Full country support")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    async with seen_lock:
        count = len(seen_dict)
    await update.message.reply_text(f"📊 {count} OTPs tracked")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    await update.message.reply_text("🏓 Pong!")

async def set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    try:
        parts = update.message.text.split()
        if len(parts) < 3:
            await update.message.reply_text("❌ Format: /set COUNTRY SERVICE\nExample: /set BANGLADESH bKash")
            return
        country = parts[1].upper()
        service = parts[2].capitalize()
        existing = get_service_emoji(country, service)
        if existing:
            await update.message.reply_text(f"✅ {country} এর {service} ইতিমধ্যে সেট আছে।\nইমোজি আইডি: <code>{existing}</code>", parse_mode="HTML")
            return
        pending_requests[update.effective_user.id] = {"country": country, "service": service}
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.upper()==country), "🏳")
        await update.message.reply_text(
            f"{flag} <b>{country}</b> - <b>{service}</b> এর ইমোজি নেই।\n\n"
            f"📝 ইমোজি আইডি পাঠান:\n<code>{country}|{service}|EMOJI_ID</code>",
            parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def service_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    try:
        text = update.message.text.replace("/service", "", 1).strip()
        if not text:
            await update.message.reply_text("Format: /service ServiceName EmojiID\nExample: /service Uber 5298715455316303708")
            return
        if '|' in text:
            parts = text.split('|')
        else:
            parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("ইমোজি আইডি দাও।")
            return
        service = parts[0].strip().capitalize()
        emoji_id = parts[1].strip()
        if not emoji_id.isdigit():
            await update.message.reply_text("ইমোজি আইডি শুধু সংখ্যা হবে।")
            return
        emoji_data["global_services"][service.lower()] = emoji_id
        save_emoji_data(emoji_data)
        await update.message.reply_text(f"✅ {service} এর গ্লোবাল ইমোজি সেট হয়েছে: <code>{emoji_id}</code>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update): return
    txt = "📋 <b>ইমোজি তালিকা:</b>\n"
    if emoji_data.get("countries"):
        for ctry, data in emoji_data["countries"].items():
            flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.lower()==ctry), "🏳")
            txt += f"\n{flag} <b>{ctry.upper()}</b>"
            if "emoji_id" in data:
                txt += f"\n  🏴 কান্ট্রি: <code>{data['emoji_id']}</code>"
            for svc, eid in data.get("services", {}).items():
                txt += f"\n  📱 {svc.capitalize()}: <code>{eid}</code>"
    if emoji_data.get("global_services"):
        txt += "\n\n<b>🌐 গ্লোবাল সার্ভিস:</b>"
        for svc, eid in emoji_data["global_services"].items():
            txt += f"\n  {svc.capitalize()}: <code>{eid}</code>"
    if not txt.strip():
        txt = "📭 কিছু সেট করা হয়নি"
    await update.message.reply_text(txt, parse_mode="HTML")

async def receive_emoji_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or user_id not in pending_requests:
        return
    try:
        text = update.message.text.strip()
        parts = text.split("|")
        if len(parts) != 3 or not parts[2].isdigit():
            await update.message.reply_text("❌ ফরম্যাট: COUNTRY|SERVICE|EMOJI_ID")
            return
        country, service, eid = parts[0].upper(), parts[1].capitalize(), parts[2]
        cl, sl = country.lower(), service.lower()
        emoji_data.setdefault("countries", {}).setdefault(cl, {}).setdefault("services", {})[sl] = eid
        save_emoji_data(emoji_data)
        del pending_requests[user_id]
        flag = next((f for c,(iso,f,n) in COUNTRY_CODE_MAP.items() if n.upper()==country), "🏳")
        await update.message.reply_text(
            f"✅ {flag} <b>{country}</b> - <b>{service}</b>\n🆔 ইমোজি: <code>{eid}</code>",
            parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        if user_id in pending_requests: del pending_requests[user_id]

# ============= MAIN =============
async def main():
    print("🚀 Starting Bot with style & custom emoji...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(CommandHandler("set", set_cmd))
    application.add_handler(CommandHandler("service", service_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_emoji_id))
    
    # Flask in separate thread
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False), daemon=True).start()
    
    reset_seen()
    asyncio.create_task(scraper_loop(application))
    
    print("✅ Bot is now running with KBS style buttons!")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
