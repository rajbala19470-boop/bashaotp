# database.py

import sqlite3
from config import DATABASE

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS countries (
            name TEXT PRIMARY KEY,
            iso TEXT,
            country_code TEXT,
            flag TEXT,
            emoji_id TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS services (
            name TEXT PRIMARY KEY,
            emoji_id TEXT
        )
    ''')
    conn.commit()

    # Insert default countries if table is empty
    c.execute("SELECT COUNT(*) FROM countries")
    if c.fetchone()[0] == 0:
        all_countries = [
            ("AFGHANISTAN", "AF", "+93", "🇦🇫"),
            ("ALBANIA", "AL", "+355", "🇦🇱"),
            ("ALGERIA", "DZ", "+213", "🇩🇿"),
            ("ANDORRA", "AD", "+376", "🇦🇩"),
            ("ANGOLA", "AO", "+244", "🇦🇴"),
            ("ANTIGUA AND BARBUDA", "AG", "+1-268", "🇦🇬"),
            ("ARGENTINA", "AR", "+54", "🇦🇷"),
            ("ARMENIA", "AM", "+374", "🇦🇲"),
            ("AUSTRALIA", "AU", "+61", "🇦🇺"),
            ("AUSTRIA", "AT", "+43", "🇦🇹"),
            ("AZERBAIJAN", "AZ", "+994", "🇦🇿"),
            ("BAHAMAS", "BS", "+1-242", "🇧🇸"),
            ("BAHRAIN", "BH", "+973", "🇧🇭"),
            ("BANGLADESH", "BD", "+880", "🇧🇩"),
            ("BARBADOS", "BB", "+1-246", "🇧🇧"),
            ("BELARUS", "BY", "+375", "🇧🇾"),
            ("BELGIUM", "BE", "+32", "🇧🇪"),
            ("BELIZE", "BZ", "+501", "🇧🇿"),
            ("BENIN", "BJ", "+229", "🇧🇯"),
            ("BHUTAN", "BT", "+975", "🇧🇹"),
            ("BOLIVIA", "BO", "+591", "🇧🇴"),
            ("BOSNIA AND HERZEGOVINA", "BA", "+387", "🇧🇦"),
            ("BOTSWANA", "BW", "+267", "🇧🇼"),
            ("BRAZIL", "BR", "+55", "🇧🇷"),
            ("BRUNEI", "BN", "+673", "🇧🇳"),
            ("BULGARIA", "BG", "+359", "🇧🇬"),
            ("BURKINA FASO", "BF", "+226", "🇧🇫"),
            ("BURUNDI", "BI", "+257", "🇧🇮"),
            ("CABO VERDE", "CV", "+238", "🇨🇻"),
            ("CAMBODIA", "KH", "+855", "🇰🇭"),
            ("CAMEROON", "CM", "+237", "🇨🇲"),
            ("CANADA", "CA", "+1", "🇨🇦"),
            ("CENTRAL AFRICAN REPUBLIC", "CF", "+236", "🇨🇫"),
            ("CHAD", "TD", "+235", "🇹🇩"),
            ("CHILE", "CL", "+56", "🇨🇱"),
            ("CHINA", "CN", "+86", "🇨🇳"),
            ("COLOMBIA", "CO", "+57", "🇨🇴"),
            ("COMOROS", "KM", "+269", "🇰🇲"),
            ("CONGO, DEMOCRATIC REPUBLIC", "CD", "+243", "🇨🇩"),
            ("CONGO, REPUBLIC", "CG", "+242", "🇨🇬"),
            ("COSTA RICA", "CR", "+506", "🇨🇷"),
            ("CROATIA", "HR", "+385", "🇭🇷"),
            ("CUBA", "CU", "+53", "🇨🇺"),
            ("CYPRUS", "CY", "+357", "🇨🇾"),
            ("CZECH REPUBLIC", "CZ", "+420", "🇨🇿"),
            ("DENMARK", "DK", "+45", "🇩🇰"),
            ("DJIBOUTI", "DJ", "+253", "🇩🇯"),
            ("DOMINICA", "DM", "+1-767", "🇩🇲"),
            ("DOMINICAN REPUBLIC", "DO", "+1-809, +1-829, +1-849", "🇩🇴"),
            ("ECUADOR", "EC", "+593", "🇪🇨"),
            ("EGYPT", "EG", "+20", "🇪🇬"),
            ("EL SALVADOR", "SV", "+503", "🇸🇻"),
            ("EQUATORIAL GUINEA", "GQ", "+240", "🇬🇶"),
            ("ERITREA", "ER", "+291", "🇪🇷"),
            ("ESTONIA", "EE", "+372", "🇪🇪"),
            ("ESWATINI", "SZ", "+268", "🇸🇿"),
            ("ETHIOPIA", "ET", "+251", "🇪🇹"),
            ("FIJI", "FJ", "+679", "🇫🇯"),
            ("FINLAND", "FI", "+358", "🇫🇮"),
            ("FRANCE", "FR", "+33", "🇫🇷"),
            ("GABON", "GA", "+241", "🇬🇦"),
            ("GAMBIA", "GM", "+220", "🇬🇲"),
            ("GEORGIA", "GE", "+995", "🇬🇪"),
            ("GERMANY", "DE", "+49", "🇩🇪"),
            ("GHANA", "GH", "+233", "🇬🇭"),
            ("GREECE", "GR", "+30", "🇬🇷"),
            ("GRENADA", "GD", "+1-473", "🇬🇩"),
            ("GUATEMALA", "GT", "+502", "🇬🇹"),
            ("GUINEA", "GN", "+224", "🇬🇳"),
            ("GUINEA-BISSAU", "GW", "+245", "🇬🇼"),
            ("GUYANA", "GY", "+592", "🇬🇾"),
            ("HAITI", "HT", "+509", "🇭🇹"),
            ("HONDURAS", "HN", "+504", "🇭🇳"),
            ("HUNGARY", "HU", "+36", "🇭🇺"),
            ("ICELAND", "IS", "+354", "🇮🇸"),
            ("INDIA", "IN", "+91", "🇮🇳"),
            ("INDONESIA", "ID", "+62", "🇮🇩"),
            ("IRAN", "IR", "+98", "🇮🇷"),
            ("IRAQ", "IQ", "+964", "🇮🇶"),
            ("IRELAND", "IE", "+353", "🇮🇪"),
            ("ISRAEL", "IL", "+972", "🇮🇱"),
            ("ITALY", "IT", "+39", "🇮🇹"),
            ("JAMAICA", "JM", "+1-876", "🇯🇲"),
            ("JAPAN", "JP", "+81", "🇯🇵"),
            ("JORDAN", "JO", "+962", "🇯🇴"),
            ("KAZAKHSTAN", "KZ", "+7", "🇰🇿"),
            ("KENYA", "KE", "+254", "🇰🇪"),
            ("KIRIBATI", "KI", "+686", "🇰🇮"),
            ("KOREA, NORTH", "KP", "+850", "🇰🇵"),
            ("KOREA, SOUTH", "KR", "+82", "🇰🇷"),
            ("KOSOVO", "XK", "+383", "🇽🇰"),
            ("KUWAIT", "KW", "+965", "🇰🇼"),
            ("KYRGYZSTAN", "KG", "+996", "🇰🇬"),
            ("LAOS", "LA", "+856", "🇱🇦"),
            ("LATVIA", "LV", "+371", "🇱🇻"),
            ("LEBANON", "LB", "+961", "🇱🇧"),
            ("LESOTHO", "LS", "+266", "🇱🇸"),
            ("LIBERIA", "LR", "+231", "🇱🇷"),
            ("LIBYA", "LY", "+218", "🇱🇾"),
            ("LIECHTENSTEIN", "LI", "+423", "🇱🇮"),
            ("LITHUANIA", "LT", "+370", "🇱🇹"),
            ("LUXEMBOURG", "LU", "+352", "🇱🇺"),
            ("MADAGASCAR", "MG", "+261", "🇲🇬"),
            ("MALAWI", "MW", "+265", "🇲🇼"),
            ("MALAYSIA", "MY", "+60", "🇲🇾"),
            ("MALDIVES", "MV", "+960", "🇲🇻"),
            ("MALI", "ML", "+223", "🇲🇱"),
            ("MALTA", "MT", "+356", "🇲🇹"),
            ("MARSHALL ISLANDS", "MH", "+692", "🇲🇭"),
            ("MAURITANIA", "MR", "+222", "🇲🇷"),
            ("MAURITIUS", "MU", "+230", "🇲🇺"),
            ("MEXICO", "MX", "+52", "🇲🇽"),
            ("MICRONESIA", "FM", "+691", "🇫🇲"),
            ("MOLDOVA", "MD", "+373", "🇲🇩"),
            ("MONACO", "MC", "+377", "🇲🇨"),
            ("MONGOLIA", "MN", "+976", "🇲🇳"),
            ("MONTENEGRO", "ME", "+382", "🇲🇪"),
            ("MOROCCO", "MA", "+212", "🇲🇦"),
            ("MOZAMBIQUE", "MZ", "+258", "🇲🇿"),
            ("MYANMAR", "MM", "+95", "🇲🇲"),
            ("NAMIBIA", "NA", "+264", "🇳🇦"),
            ("NAURU", "NR", "+674", "🇳🇷"),
            ("NEPAL", "NP", "+977", "🇳🇵"),
            ("NETHERLANDS", "NL", "+31", "🇳🇱"),
            ("NEW ZEALAND", "NZ", "+64", "🇳🇿"),
            ("NICARAGUA", "NI", "+505", "🇳🇮"),
            ("NIGER", "NE", "+227", "🇳🇪"),
            ("NIGERIA", "NG", "+234", "🇳🇬"),
            ("NORTH MACEDONIA", "MK", "+389", "🇲🇰"),
            ("NORWAY", "NO", "+47", "🇳🇴"),
            ("OMAN", "OM", "+968", "🇴🇲"),
            ("PAKISTAN", "PK", "+92", "🇵🇰"),
            ("PALAU", "PW", "+680", "🇵🇼"),
            ("PALESTINE", "PS", "+970", "🇵🇸"),
            ("PANAMA", "PA", "+507", "🇵🇦"),
            ("PAPUA NEW GUINEA", "PG", "+675", "🇵🇬"),
            ("PARAGUAY", "PY", "+595", "🇵🇾"),
            ("PERU", "PE", "+51", "🇵🇪"),
            ("PHILIPPINES", "PH", "+63", "🇵🇭"),
            ("POLAND", "PL", "+48", "🇵🇱"),
            ("PORTUGAL", "PT", "+351", "🇵🇹"),
            ("QATAR", "QA", "+974", "🇶🇦"),
            ("ROMANIA", "RO", "+40", "🇷🇴"),
            ("RUSSIA", "RU", "+7", "🇷🇺"),
            ("RWANDA", "RW", "+250", "🇷🇼"),
            ("SAINT KITTS AND NEVIS", "KN", "+1-869", "🇰🇳"),
            ("SAINT LUCIA", "LC", "+1-758", "🇱🇨"),
            ("SAINT VINCENT AND THE GRENADINES", "VC", "+1-784", "🇻🇨"),
            ("SAMOA", "WS", "+685", "🇼🇸"),
            ("SAN MARINO", "SM", "+378", "🇸🇲"),
            ("SAO TOME AND PRINCIPE", "ST", "+239", "🇸🇹"),
            ("SAUDI ARABIA", "SA", "+966", "🇸🇦"),
            ("SENEGAL", "SN", "+221", "🇸🇳"),
            ("SERBIA", "RS", "+381", "🇷🇸"),
            ("SEYCHELLES", "SC", "+248", "🇸🇨"),
            ("SIERRA LEONE", "SL", "+232", "🇸🇱"),
            ("SINGAPORE", "SG", "+65", "🇸🇬"),
            ("SLOVAKIA", "SK", "+421", "🇸🇰"),
            ("SLOVENIA", "SI", "+386", "🇸🇮"),
            ("SOLOMON ISLANDS", "SB", "+677", "🇸🇧"),
            ("SOMALIA", "SO", "+252", "🇸🇴"),
            ("SOUTH AFRICA", "ZA", "+27", "🇿🇦"),
            ("SOUTH SUDAN", "SS", "+211", "🇸🇸"),
            ("SPAIN", "ES", "+34", "🇪🇸"),
            ("SRI LANKA", "LK", "+94", "🇱🇰"),
            ("SUDAN", "SD", "+249", "🇸🇩"),
            ("SURINAME", "SR", "+597", "🇸🇷"),
            ("SWEDEN", "SE", "+46", "🇸🇪"),
            ("SWITZERLAND", "CH", "+41", "🇨🇭"),
            ("SYRIA", "SY", "+963", "🇸🇾"),
            ("TAIWAN", "TW", "+886", "🇹🇼"),
            ("TAJIKISTAN", "TJ", "+992", "🇹🇯"),
            ("TANZANIA", "TZ", "+255", "🇹🇿"),
            ("THAILAND", "TH", "+66", "🇹🇭"),
            ("TIMOR-LESTE", "TL", "+670", "🇹🇱"),
            ("TOGO", "TG", "+228", "🇹🇬"),
            ("TONGA", "TO", "+676", "🇹🇴"),
            ("TRINIDAD AND TOBAGO", "TT", "+1-868", "🇹🇹"),
            ("TUNISIA", "TN", "+216", "🇹🇳"),
            ("TURKEY", "TR", "+90", "🇹🇷"),
            ("TURKMENISTAN", "TM", "+993", "🇹🇲"),
            ("TUVALU", "TV", "+688", "🇹🇻"),
            ("UGANDA", "UG", "+256", "🇺🇬"),
            ("UKRAINE", "UA", "+380", "🇺🇦"),
            ("UNITED ARAB EMIRATES", "AE", "+971", "🇦🇪"),
            ("UNITED KINGDOM", "GB", "+44", "🇬🇧"),
            ("UNITED STATES", "US", "+1", "🇺🇸"),
            ("URUGUAY", "UY", "+598", "🇺🇾"),
            ("UZBEKISTAN", "UZ", "+998", "🇺🇿"),
            ("VANUATU", "VU", "+678", "🇻🇺"),
            ("VATICAN CITY", "VA", "+379", "🇻🇦"),
            ("VENEZUELA", "VE", "+58", "🇻🇪"),
            ("VIETNAM", "VN", "+84", "🇻🇳"),
            ("YEMEN", "YE", "+967", "🇾🇪"),
            ("ZAMBIA", "ZM", "+260", "🇿🇲"),
            ("ZIMBABWE", "ZW", "+263", "🇿🇼"),
        ]
        c.executemany(
            "INSERT INTO countries (name, iso, country_code, flag, emoji_id) VALUES (?,?,?,?, NULL)",
            all_countries
        )
        conn.commit()

    # Insert default services if table empty
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        all_services = [
            ("WhatsApp",),
            ("Telegram",),
            ("Facebook",),
            ("Instagram",),
            ("Google",),
            ("Amazon",),
            ("Uber",),
            ("Bolt",),
            ("Paytm",),
            ("Ola",),
            ("Swiggy",),
            ("Zomato",),
            ("Netflix",),
            ("Hotstar",),
            ("Prime Video",),
            ("Discord",),
            ("Snapchat",),
            ("TikTok",),
            ("LinkedIn",),
            ("Twitter",),
            ("Microsoft",),
            ("Apple",),
            ("Yahoo",),
            ("Binance",),
            ("Coinbase",),
            ("PayPal",),
            ("Spotify",),
            ("Reddit",),
            ("Airbnb",),
            ("Flipkart",),
            ("Shopify",),
            ("Steam",),
        ]
        c.executemany(
            "INSERT INTO services (name, emoji_id) VALUES (?, NULL)",
            all_services
        )
        conn.commit()

    # --- Pre-set default custom emoji IDs (as given by user) ---
    # Morocco emoji_id
    c.execute("UPDATE countries SET emoji_id = ? WHERE name = 'MOROCCO'", ("5292108962391414885",))
    # Bolt emoji_id
    c.execute("UPDATE services SET emoji_id = ? WHERE name = 'Bolt'", ("5343587658717219067",))
    conn.commit()

    conn.close()

def is_duplicate(msg_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM messages WHERE id=?", (msg_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def save_message(msg_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO messages (id) VALUES (?)", (msg_id,))
    conn.commit()
    conn.close()

def get_countries():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM countries")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_country_emoji(country_name, emoji_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE countries SET emoji_id=? WHERE name=?", (emoji_id, country_name))
    conn.commit()
    conn.close()

def get_services():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM services")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_service_emoji(service_name, emoji_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO services (name, emoji_id) VALUES (?,?)", (service_name, emoji_id))
    conn.commit()
    conn.close()
