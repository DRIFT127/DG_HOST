# -*- coding: utf-8 -*-
import telebot
from telebot import util
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import sys
import atexit
import requests
import io
from urllib.parse import urlparse

# --- Flask Keep Alive ---
from flask import Flask, send_file, abort
from threading import Thread

app = Flask('')

# ========== WEB HOSTING CONFIG ==========
WEB_HOSTING_DIR = os.path.join(os.path.dirname(__file__), 'web_hosting')
os.makedirs(WEB_HOSTING_DIR, exist_ok=True)

# ----- AUTO-DETECT PUBLIC URL -----
def get_public_base_url():
    # 1. Manually set env var
    if os.environ.get("PUBLIC_URL"):
        return os.environ["PUBLIC_URL"]
    
    # 2. Render
    if os.environ.get("RENDER_EXTERNAL_URL"):
        return os.environ["RENDER_EXTERNAL_URL"]
    
    # 3. Railway
    if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        return f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
    
    # 4. Replit
    repl_slug = os.environ.get("REPL_SLUG")
    repl_owner = os.environ.get("REPL_OWNER")
    if repl_slug and repl_owner:
        return f"https://{repl_slug}.{repl_owner}.repl.co"
    
    # 5. Termux / local – user must set PUBLIC_URL manually
    return "http://localhost:8080"  # fallback

PUBLIC_BASE_URL = get_public_base_url()
print(f"[Web Hosting] Public URL: {PUBLIC_BASE_URL}")

@app.route('/')
def home():
    return "I'm Marco File Host - Web Hosting Active"

@app.route('/web/<int:user_id>/')
def serve_website_index(user_id):
    return serve_website(user_id, 'index.html')

@app.route('/web/<int:user_id>/<path:path>')
def serve_website(user_id, path):
    user_web_dir = os.path.join(WEB_HOSTING_DIR, str(user_id))
    if not os.path.isdir(user_web_dir):
        return "No website hosted by this user", 404

    # Security: prevent directory traversal
    safe_path = os.path.normpath(path).lstrip('/')
    if safe_path.startswith('..') or os.path.isabs(safe_path):
        abort(403)

    full_path = os.path.join(user_web_dir, safe_path)
    if not os.path.exists(full_path):
        if os.path.isdir(full_path):
            index_path = os.path.join(full_path, 'index.html')
            if os.path.isfile(index_path):
                full_path = index_path
            else:
                return "File not found", 404
        else:
            return "File not found", 404

    if not os.path.isfile(full_path):
        return "Not a file", 404

    return send_file(full_path)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")
# --- End Flask Keep Alive ---

# --- Configuration ---
TOKEN = '8613550531:AAFQgxpad9W5Pe4ERHFf-I6hb77uLWZSN7Q'
OWNER_ID = 7637620066
ADMIN_ID = 7637620066
YOUR_USERNAME = 'DG_DRIFT'

# --- Force Subscription Channels (4 channels) ---
REQUIRED_CHANNELS = [
    '@driftfreeapis',
    '@driftfreesourcecode',
    '@DRIFTARMYFF',
    '@DGDRIFT'
]

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

FREE_USER_LIMIT = 2
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
banned_users = set()

BOT_START_TIME = datetime.now()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Keyboard Layouts ---
COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["📢 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥"],
    ["🌏 Upload", "📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬"],
    ["⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝", "📊 𝐒𝐓𝐀𝐓𝐔𝐒"],
    ["⚙️ Recommended Install", "🤖 𝐀𝐆𝐄𝐍𝐓"],
    ["🌐 𝐆𝐈𝐓𝐇𝐔𝐁", "🌐 Web Hosting"],
    ["📞 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫"]
]
ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["📢 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥"],
    ["🌏 Upload", "📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬"],
    ["⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝", "📊 𝐒𝐓𝐀𝐓𝐔𝐒"],
    ["💳 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧𝐬", "📢 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭"],
    ["🔒 𝐋𝐨𝐜𝐤 𝐁𝐨𝐭", "🟢 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐀𝐥𝐥 𝐂𝐨𝐝𝐞"],
    ["🛠️ 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥l", "⚙️ Recommended Install"],
    ["🤖 𝐀𝐆𝐄𝐍𝐓", "🌐 𝐆𝐈𝐓𝐇𝐔𝐁"],
    ["🌐 Web Hosting", "📞 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫"]
]

# --- Database Setup ---
DB_LOCK = threading.Lock()

def init_db():
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_uploads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, file_id TEXT, file_name TEXT, file_type TEXT, file_size INTEGER, user_name TEXT, user_username TEXT, timestamp TEXT, extra_info TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS verified_users (user_id INTEGER PRIMARY KEY, verified_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, banned_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_websites (user_id INTEGER PRIMARY KEY, folder_path TEXT, url TEXT, created_at TEXT)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database init error: {e}")

def load_data():
    global banned_users
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError:
                pass
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            user_files.setdefault(user_id, []).append((file_name, file_type))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(row[0] for row in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(row[0] for row in c.fetchall())
        c.execute('SELECT user_id FROM banned_users')
        banned_users = set(row[0] for row in c.fetchall())
        conn.close()
    except Exception as e:
        logger.error(f"Data load error: {e}")

init_db()
load_data()

# --- Stylish Text Converter ---
def stylish_text(text: str) -> str:
    text = re.sub(r'</?code>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G',
        'H': 'H', 'I': 'I', 'J': 'J', 'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N',
        'O': 'O', 'P': 'P', 'Q': 'Q', 'R': 'R', 'S': 'S', 'T': 'T', 'U': 'U',
        'V': 'V', 'W': 'W', 'X': 'X', 'Y': 'Y', 'Z': 'Z'
    }
    return ''.join(mapping.get(ch, ch) for ch in text)

# --- Ban Functions ---
def ban_user(user_id):
    if user_id in admin_ids or user_id == OWNER_ID:
        return False
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO banned_users (user_id, banned_at) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        banned_users.add(user_id)
        return True
    except:
        return False

def unban_user(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        banned_users.discard(user_id)
        return True
    except:
        return False

def is_user_banned(user_id):
    return user_id in banned_users

# --- Multi‑channel Verification ---
def is_user_verified(user_id):
    if user_id in admin_ids or user_id == OWNER_ID:
        return True
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT 1 FROM verified_users WHERE user_id = ?', (user_id,))
        result = c.fetchone() is not None
        conn.close()
        return result
    except:
        return False

def set_user_verified(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO verified_users (user_id, verified_at) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def is_user_member_all_channels(user_id):
    if user_id in admin_ids or user_id == OWNER_ID:
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = bot.get_chat_member(channel, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def send_join_prompt(chat_id, user_id):
    text = (
        "🔐 Jᴏɪɴ Aʟʟ Cʜᴀɴɴᴇʟs Tᴏ Uɴʟᴏᴄᴋ Tʜᴇ Bᴏᴛ 🚀\n"
        "📢 Cᴏᴍᴘʟᴇᴛᴇ Aʟʟ Cʜᴀɴɴᴇʟ Jᴏɪɴs Tᴏ Gᴇᴛ Aᴄᴄᴇss ✅\n"
        "⚡ Aғᴛᴇʀ Jᴏɪɴɪɴɢ, Cʟɪᴄᴋ \"Vᴇʀɪғʏ\" Tᴏ Cᴏɴᴛɪɴᴜᴇ. 🔓"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in REQUIRED_CHANNELS:
        markup.add(types.InlineKeyboardButton("CLICK", url=f"https://t.me/{ch.lstrip('@')}"))
    markup.add(types.InlineKeyboardButton("✅ VERIFY", callback_data=f"verify_channel_{user_id}"))
    bot.send_message(chat_id, text, parse_mode=None, reply_markup=markup, disable_web_page_preview=True)

def check_subscription_and_continue(message=None, call=None):
    user_id = (message.from_user.id if message else call.from_user.id)
    chat_id = (message.chat.id if message else call.message.chat.id)
    if is_user_banned(user_id):
        bot.send_message(chat_id, stylish_text("🚫 You are banned from using this bot."))
        return False
    if user_id in admin_ids or user_id == OWNER_ID:
        return True
    if is_user_verified(user_id):
        return True
    if is_user_member_all_channels(user_id):
        set_user_verified(user_id)
        return True
    else:
        send_join_prompt(chat_id, user_id)
        return False

# --- Verification Callback ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_channel_'))
def verify_channel_callback(call):
    user_id = int(call.data.split('_')[-1])
    if user_id != call.from_user.id:
        bot.answer_callback_query(call.id, stylish_text("This verification is not for you."), show_alert=True)
        return
    if is_user_verified(user_id):
        bot.answer_callback_query(call.id, stylish_text("You are already verified."), show_alert=True)
        bot.edit_message_text(stylish_text("✅ You are already verified. You can now use the bot."),
                              call.message.chat.id, call.message.message_id)
        return
    if is_user_member_all_channels(user_id):
        set_user_verified(user_id)
        bot.answer_callback_query(call.id, stylish_text("✅ Verification successful! You can now use the bot."), show_alert=True)
        bot.edit_message_text(stylish_text("✅ Verification successful! You can now use the bot.\nSend /start to begin."),
                              call.message.chat.id, call.message.message_id)
    else:
        missing = []
        for ch in REQUIRED_CHANNELS:
            try:
                member = bot.get_chat_member(ch, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    missing.append(ch)
            except:
                missing.append(ch)
        if missing:
            missing_list = "\n".join(missing)
            bot.answer_callback_query(call.id, stylish_text(f"❌ You are not a member of:\n{missing_list}\nPlease join all channels first."), show_alert=True)
        else:
            bot.answer_callback_query(call.id, stylish_text("❌ Verification failed. Please join all channels and try again."), show_alert=True)

# --- Helper Functions ---
def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                    try: script_info['log_file'].close()
                    except: pass
                if script_key in bot_scripts: del bot_scripts[script_key]
            return is_running
        except psutil.NoSuchProcess:
            if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                try: script_info['log_file'].close()
                except: pass
            if script_key in bot_scripts: del bot_scripts[script_key]
            return False
        except Exception as e:
            logger.error(f"Error checking process {script_key}: {e}")
            return False
    return False

def kill_process_tree(process_info):
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try: process_info['log_file'].close()
            except: pass
        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            pid = process.pid
            if pid:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        try: child.terminate()
                        except: pass
                    psutil.wait_procs(children, timeout=1)
                    try:
                        parent.terminate()
                        try: parent.wait(timeout=1)
                        except: parent.kill()
                    except: pass
                except psutil.NoSuchProcess:
                    pass
    except Exception as e:
        logger.error(f"Error killing process tree: {e}")

# --- Automatic Package Installation & Script Running ---
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'bs4': 'beautifulsoup4',
    'requests': 'requests',
    'pillow': 'Pillow',
    'cv2': 'opencv-python',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'dateutil': 'python-dateutil',
    'pandas': 'pandas',
    'numpy': 'numpy',
    'flask': 'Flask',
    'psutil': 'psutil',
}
for core in ['asyncio', 'json', 'datetime', 'os', 'sys', 're', 'time', 'math', 'random', 'logging', 'threading', 'subprocess', 'zipfile', 'tempfile', 'shutil', 'sqlite3', 'atexit']:
    TELEGRAM_MODULES[core] = None

def attempt_install_pip(module_name, message):
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if package_name is None:
        return False
    try:
        bot.reply_to(message, stylish_text(f"🐍 Installing {package_name}..."))
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', package_name], capture_output=True, text=True)
        if result.returncode == 0:
            bot.reply_to(message, stylish_text(f"✅ Package {package_name} installed."))
            return True
        else:
            bot.reply_to(message, stylish_text(f"❌ Failed to install {package_name}."))
            return False
    except Exception as e:
        bot.reply_to(message, stylish_text(f"❌ Install error: {e}"))
        return False

def attempt_install_npm(module_name, user_folder, message):
    try:
        bot.reply_to(message, stylish_text(f"🟠 Installing Node package {module_name}..."))
        result = subprocess.run(['npm', 'install', module_name], cwd=user_folder, capture_output=True, text=True)
        if result.returncode == 0:
            bot.reply_to(message, stylish_text(f"✅ Node package {module_name} installed."))
            return True
        else:
            bot.reply_to(message, stylish_text(f"❌ Failed to install {module_name}."))
            return False
    except Exception as e:
        bot.reply_to(message, stylish_text(f"❌ NPM error: {e}"))
        return False

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Failed to run '{file_name}' after {max_attempts} attempts."))
        return
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Attempt {attempt} to run Python: {script_path}")
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Script '{file_name}' not found!"))
            remove_user_file_db(script_owner_id, file_name)
            return
        if attempt == 1:
            check_proc = subprocess.Popen([sys.executable, script_path], cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                _, stderr = check_proc.communicate(timeout=5)
                if check_proc.returncode != 0 and stderr:
                    match = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1)
                        if attempt_install_pip(module_name, message_obj_for_reply):
                            bot.reply_to(message_obj_for_reply, stylish_text(f"🔄 Retrying '{file_name}'..."))
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt+1)).start()
                            return
                        else:
                            bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Missing module {module_name}. Install failed."))
                            return
            except subprocess.TimeoutExpired:
                check_proc.kill()
                check_proc.communicate()
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8')
        process = subprocess.Popen([sys.executable, script_path], cwd=user_folder, stdout=log_file, stderr=log_file, stdin=subprocess.PIPE)
        bot_scripts[script_key] = {
            'process': process,
            'log_file': log_file,
            'file_name': file_name,
            'chat_id': message_obj_for_reply.chat.id,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(),
            'user_folder': user_folder,
            'type': 'py',
            'script_key': script_key
        }
        bot.reply_to(message_obj_for_reply, stylish_text(f"✅ Python script '{file_name}' started! (PID: {process.pid})"))
    except Exception as e:
        bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Error: {e}"))
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Failed to run '{file_name}' after {max_attempts} attempts."))
        return
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Attempt {attempt} to run JS: {script_path}")
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, stylish_text(f"❌ JS script '{file_name}' not found!"))
            remove_user_file_db(script_owner_id, file_name)
            return
        if attempt == 1:
            check_proc = subprocess.Popen(['node', script_path], cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                _, stderr = check_proc.communicate(timeout=5)
                if check_proc.returncode != 0 and stderr:
                    match = re.search(r"Cannot find module '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1)
                        if not module_name.startswith('.') and not module_name.startswith('/'):
                            if attempt_install_npm(module_name, user_folder, message_obj_for_reply):
                                bot.reply_to(message_obj_for_reply, stylish_text(f"🔄 Retrying '{file_name}'..."))
                                time.sleep(2)
                                threading.Thread(target=run_js_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt+1)).start()
                                return
                            else:
                                bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Missing Node module {module_name}."))
                                return
            except subprocess.TimeoutExpired:
                check_proc.kill()
                check_proc.communicate()
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8')
        process = subprocess.Popen(['node', script_path], cwd=user_folder, stdout=log_file, stderr=log_file, stdin=subprocess.PIPE)
        bot_scripts[script_key] = {
            'process': process,
            'log_file': log_file,
            'file_name': file_name,
            'chat_id': message_obj_for_reply.chat.id,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(),
            'user_folder': user_folder,
            'type': 'js',
            'script_key': script_key
        }
        bot.reply_to(message_obj_for_reply, stylish_text(f"✅ JS script '{file_name}' started! (PID: {process.pid})"))
    except Exception as e:
        bot.reply_to(message_obj_for_reply, stylish_text(f"❌ Error: {e}"))
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

# --- Database Operations (file, active, subscription, admin) ---
def save_user_file(user_id, file_name, file_type='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
                      (user_id, file_name, file_type))
            conn.commit()
            user_files.setdefault(user_id, [])
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
        except Exception as e:
            logger.error(f"Error saving file: {e}")
        finally:
            conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]:
                    del user_files[user_id]
        except Exception as e:
            logger.error(f"Error removing file: {e}")
        finally:
            conn.close()

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding active user: {e}")
        finally:
            conn.close()

def save_subscription(user_id, expiry):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            expiry_str = expiry.isoformat()
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (user_id, expiry_str))
            conn.commit()
            user_subscriptions[user_id] = {'expiry': expiry}
        except Exception as e:
            logger.error(f"Error saving subscription: {e}")
        finally:
            conn.close()

def remove_subscription_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            if user_id in user_subscriptions:
                del user_subscriptions[user_id]
        except Exception as e:
            logger.error(f"Error removing subscription: {e}")
        finally:
            conn.close()

def add_admin_db(admin_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
            conn.commit()
            admin_ids.add(admin_id)
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
        finally:
            conn.close()

def remove_admin_db(admin_id):
    if admin_id == OWNER_ID:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
            conn.commit()
            if c.rowcount > 0:
                admin_ids.discard(admin_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            return False
        finally:
            conn.close()

# --- Pending Upload Functions (with extra_info for GitHub and Website) ---
def add_pending_upload(user_id, file_id, file_name, file_type, file_size, user_name, user_username, extra_info=""):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            timestamp = datetime.now().isoformat()
            c.execute('''INSERT INTO pending_uploads (user_id, file_id, file_name, file_type, file_size, user_name, user_username, timestamp, extra_info)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (user_id, file_id, file_name, file_type, file_size, user_name, user_username, timestamp, extra_info))
            conn.commit()
            return c.lastrowid
        except Exception as e:
            logger.error(f"Error adding pending upload: {e}")
            return None
        finally:
            conn.close()

def get_pending_upload(upload_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('SELECT id, user_id, file_id, file_name, file_type, file_size, user_name, user_username, extra_info FROM pending_uploads WHERE id = ?', (upload_id,))
            row = c.fetchone()
            if row:
                return {'id': row[0], 'user_id': row[1], 'file_id': row[2], 'file_name': row[3],
                        'file_type': row[4], 'file_size': row[5], 'user_name': row[6], 'user_username': row[7], 'extra_info': row[8]}
            return None
        except Exception as e:
            logger.error(f"Error getting pending upload: {e}")
            return None
        finally:
            conn.close()

def delete_pending_upload(upload_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM pending_uploads WHERE id = ?', (upload_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting pending upload: {e}")
            return False
        finally:
            conn.close()

# --- Website specific DB functions ---
def save_user_website(user_id, web_dir):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_websites (user_id, folder_path, url, created_at) VALUES (?, ?, ?, ?)',
                  (user_id, web_dir, f"{PUBLIC_BASE_URL}/web/{user_id}/", datetime.now().isoformat()))
        conn.commit()
        conn.close()

def delete_user_website(user_id):
    web_dir = os.path.join(WEB_HOSTING_DIR, str(user_id))
    if os.path.isdir(web_dir):
        shutil.rmtree(web_dir, ignore_errors=True)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM user_websites WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

def user_has_website(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT 1 FROM user_websites WHERE user_id = ?', (user_id,))
        result = c.fetchone() is not None
        conn.close()
        return result

def get_user_website_url(user_id):
    return f"{PUBLIC_BASE_URL}/web/{user_id}/"

# --- File Processing after Admin Approval (with website support) ---
def process_approved_file(upload_id, admin_chat_id, user_message_obj=None):
    pending = get_pending_upload(upload_id)
    if not pending:
        bot.send_message(admin_chat_id, stylish_text(f"❌ Pending upload {upload_id} not found."))
        return False

    user_id = pending['user_id']
    file_id = pending['file_id']
    file_name = pending['file_name']
    file_ext = os.path.splitext(file_name)[1].lower()

    # ---------- WEBSITE HANDLING ----------
    if pending.get('extra_info') == 'website':
        if file_ext != '.zip':
            bot.send_message(admin_chat_id, "❌ Website upload must be a ZIP file.")
            delete_pending_upload(upload_id)
            return False

        # Delete existing website if any
        if user_has_website(user_id):
            delete_user_website(user_id)

        web_dir = os.path.join(WEB_HOSTING_DIR, str(user_id))
        os.makedirs(web_dir, exist_ok=True)

        try:
            file_info = bot.get_file(file_id)
            zip_content = bot.download_file(file_info.file_path)

            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(zip_content)

            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(web_dir)

            # If everything is inside a single folder, move contents up
            items = os.listdir(web_dir)
            if len(items) == 1 and os.path.isdir(os.path.join(web_dir, items[0])):
                inner = os.path.join(web_dir, items[0])
                for item in os.listdir(inner):
                    shutil.move(os.path.join(inner, item), web_dir)
                os.rmdir(inner)

            shutil.rmtree(temp_dir, ignore_errors=True)

            # Verify index.html exists somewhere
            if not os.path.exists(os.path.join(web_dir, 'index.html')):
                found = False
                for root, dirs, files in os.walk(web_dir):
                    if 'index.html' in files:
                        found = True
                        break
                if not found:
                    bot.send_message(admin_chat_id, "❌ No index.html found in the zip.")
                    delete_user_website(user_id)
                    delete_pending_upload(upload_id)
                    return False

            save_user_website(user_id, web_dir)
            website_url = get_user_website_url(user_id)
            bot.send_message(admin_chat_id, f"✅ Website deployed for user {user_id}\nURL: {website_url}")
            bot.send_message(user_id, stylish_text(f"✅ Your website is now live!\n{website_url}"))
            delete_pending_upload(upload_id)
            return True

        except Exception as e:
            logger.error(f"Website deployment error: {e}")
            bot.send_message(admin_chat_id, f"❌ Failed to deploy website: {e}")
            delete_user_website(user_id)
            delete_pending_upload(upload_id)
            return False

    # ---------- NORMAL SCRIPT / ZIP HANDLING (original code) ----------
    file_type = pending['file_type']
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.send_message(admin_chat_id, stylish_text(f"⚠️ User limit reached ({current_files}/{limit_str}). Cannot approve."))
        delete_pending_upload(upload_id)
        return False

    try:
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        user_folder = get_user_folder(user_id)
        if file_ext == '.zip':
            temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
            zip_path = os.path.join(temp_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(downloaded)
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(temp_dir)
            extracted = os.listdir(temp_dir)
            py_files = [f for f in extracted if f.endswith('.py')]
            js_files = [f for f in extracted if f.endswith('.js')]
            req_file = 'requirements.txt' if 'requirements.txt' in extracted else None
            pkg_json = 'package.json' if 'package.json' in extracted else None
            if req_file:
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', os.path.join(temp_dir, req_file)], check=True, capture_output=True)
                    bot.send_message(admin_chat_id, stylish_text("✅ Python deps installed."))
                except Exception as e:
                    bot.send_message(admin_chat_id, stylish_text(f"❌ Python deps failed: {e}"))
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    delete_pending_upload(upload_id)
                    return False
            if pkg_json:
                try:
                    subprocess.run(['npm', 'install'], cwd=temp_dir, check=True, capture_output=True)
                    bot.send_message(admin_chat_id, stylish_text("✅ Node deps installed."))
                except Exception as e:
                    bot.send_message(admin_chat_id, stylish_text(f"❌ Node deps failed: {e}"))
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    delete_pending_upload(upload_id)
                    return False
            main_script = None
            for p in ['main.py', 'bot.py', 'app.py']:
                if p in py_files:
                    main_script = p
                    file_type = 'py'
                    break
            if not main_script:
                for p in ['index.js', 'main.js', 'bot.js', 'app.js']:
                    if p in js_files:
                        main_script = p
                        file_type = 'js'
                        break
            if not main_script and py_files:
                main_script = py_files[0]
                file_type = 'py'
            elif not main_script and js_files:
                main_script = js_files[0]
                file_type = 'js'
            if not main_script:
                bot.send_message(admin_chat_id, stylish_text("❌ No .py or .js script found in zip."))
                shutil.rmtree(temp_dir, ignore_errors=True)
                delete_pending_upload(upload_id)
                return False
            for item in os.listdir(temp_dir):
                src = os.path.join(temp_dir, item)
                dst = os.path.join(user_folder, item)
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                elif os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
            shutil.rmtree(temp_dir, ignore_errors=True)
            save_user_file(user_id, main_script, file_type)
            script_path = os.path.join(user_folder, main_script)
            if file_type == 'py':
                threading.Thread(target=run_script, args=(script_path, user_id, user_folder, main_script, user_message_obj)).start()
            else:
                threading.Thread(target=run_js_script, args=(script_path, user_id, user_folder, main_script, user_message_obj)).start()
            bot.send_message(admin_chat_id, stylish_text(f"✅ Approved and started: {main_script}"))
            return True
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f:
                f.write(downloaded)
            save_user_file(user_id, file_name, file_type)
            if file_type == 'py':
                threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, user_message_obj)).start()
            else:
                threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, user_message_obj)).start()
            bot.send_message(admin_chat_id, stylish_text(f"✅ Approved and started: {file_name}"))
            return True
    except Exception as e:
        logger.error(f"Error in process_approved_file: {e}", exc_info=True)
        bot.send_message(admin_chat_id, stylish_text(f"❌ Error: {e}"))
        return False
    finally:
        delete_pending_upload(upload_id)

# --- Document Handler (with website flag support) ---
pending_web_upload = {}  # {user_id: True}

@bot.message_handler(content_types=['document'])
def handle_file_upload_doc(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    doc = message.document
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Bot locked, cannot accept files."))
        return

    # Check if this is a website upload
    is_website = pending_web_upload.pop(user_id, False)
    if is_website:
        # For website uploads we bypass file limit (website does not count toward script limit)
        if doc.file_size > 20 * 1024 * 1024:
            bot.reply_to(message, stylish_text("⚠️ Website ZIP too large (max 20MB)."))
            return
        file_name = doc.file_name
        if not file_name.lower().endswith('.zip'):
            bot.reply_to(message, stylish_text("⚠️ Website upload must be a ZIP file."))
            return
        user_name = message.from_user.first_name
        user_username = message.from_user.username or "No username"
        upload_id = add_pending_upload(
            user_id=user_id,
            file_id=doc.file_id,
            file_name=file_name,
            file_type='zip',
            file_size=doc.file_size,
            user_name=user_name,
            user_username=user_username,
            extra_info="website"
        )
        if not upload_id:
            bot.reply_to(message, stylish_text("❌ Internal error, please try later."))
            return
        bot.reply_to(message, stylish_text(f"✅ Website ZIP submitted for admin approval. You will be notified when it is live."))
        for admin_id in admin_ids:
            try:
                caption = (f"📥 New WEBSITE requires approval\n"
                           f"👤 User: {user_name} (@{user_username})\n"
                           f"🆔 User ID: {user_id}\n"
                           f"📄 File: {file_name}\n"
                           f"📏 Size: {doc.file_size // 1024} KB\n"
                           f"🆔 Upload ID: {upload_id}")
                sent = bot.send_document(admin_id, doc.file_id, caption=stylish_text(caption))
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_upload_{upload_id}"),
                    types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_upload_{upload_id}")
                )
                bot.edit_message_reply_markup(admin_id, sent.message_id, reply_markup=markup)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        return

    # Normal script upload (py/js/zip) – apply file limit
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, stylish_text(f"⚠️ File limit ({current_files}/{limit_str}) reached."))
        return
    file_name = doc.file_name
    if not file_name:
        bot.reply_to(message, stylish_text("⚠️ No file name."))
        return
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, stylish_text("⚠️ Only .py, .js, .zip allowed."))
        return
    if doc.file_size > 20 * 1024 * 1024:
        bot.reply_to(message, stylish_text("⚠️ File too large (max 20MB)."))
        return
    user_name = message.from_user.first_name
    user_username = message.from_user.username or "No username"
    upload_id = add_pending_upload(
        user_id=user_id,
        file_id=doc.file_id,
        file_name=file_name,
        file_type=file_ext[1:],
        file_size=doc.file_size,
        user_name=user_name,
        user_username=user_username,
        extra_info=""
    )
    if not upload_id:
        bot.reply_to(message, stylish_text("❌ Internal error, please try later."))
        return
    bot.reply_to(message, stylish_text(f"✅ File {file_name} submitted for admin approval. You will be notified when approved or rejected."))
    for admin_id in admin_ids:
        try:
            caption = (f"📥 New file requires approval\n"
                       f"👤 User: {user_name} (@{user_username})\n"
                       f"🆔 User ID: {user_id}\n"
                       f"📄 File: {file_name}\n"
                       f"📏 Size: {doc.file_size // 1024} KB\n"
                       f"🆔 Upload ID: {upload_id}")
            sent = bot.send_document(admin_id, doc.file_id, caption=stylish_text(caption))
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_upload_{upload_id}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_upload_{upload_id}")
            )
            bot.edit_message_reply_markup(admin_id, sent.message_id, reply_markup=markup)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# --- Approval / Rejection Callback (unchanged) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_upload_') or call.data.startswith('reject_upload_'))
def handle_approval_callback(call):
    if not check_subscription_and_continue(None, call):
        return
    admin_id = call.from_user.id
    if admin_id not in admin_ids:
        bot.answer_callback_query(call.id, stylish_text("⚠️ Only admins can approve/reject."), show_alert=True)
        return
    upload_id = int(call.data.split('_')[-1])
    pending = get_pending_upload(upload_id)
    if not pending:
        bot.answer_callback_query(call.id, stylish_text("⚠️ This upload request no longer exists."), show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
        return
    user_id = pending['user_id']
    file_name = pending['file_name']
    if call.data.startswith('approve_upload_'):
        bot.answer_callback_query(call.id, stylish_text("✅ Approving and processing..."))
        success = process_approved_file(upload_id, admin_chat_id=call.message.chat.id, user_message_obj=call.message)
        if success:
            try:
                bot.send_message(user_id, stylish_text(f"✅ Your file {file_name} has been approved and processed."))
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")
            try:
                bot.edit_message_caption(
                    caption=stylish_text(call.message.caption + "\n\n✅ APPROVED"),
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=None
                )
            except: pass
        else:
            bot.send_message(call.message.chat.id, stylish_text(f"❌ Failed to process file for user {user_id}."))
    else:
        bot.answer_callback_query(call.id, stylish_text("❌ Rejected."))
        delete_pending_upload(upload_id)
        reject_msg = "AGLI BAR SE YE FILE RUN MT KARNA SIR"
        try:
            bot.send_message(user_id, stylish_text(f"❌ Your file {file_name} was rejected by admin.\n\n{reject_msg}"))
        except Exception as e:
            logger.error(f"Could not notify user {user_id}: {e}")
        try:
            bot.edit_message_caption(
                caption=stylish_text(call.message.caption + "\n\n❌ REJECTED"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except: pass

# ======================= GITHUB DEPLOY =======================
def parse_github_url(url):
    url = re.sub(r'\.git$', '', url)
    if 'github.com' not in url:
        raise ValueError("Not a valid GitHub URL")
    parts = url.split('github.com/')[-1].split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL format")
    owner = parts[0]
    repo = parts[1]
    branch = 'main'
    if len(parts) >= 4 and parts[2] == 'tree':
        branch = parts[3]
    return owner, repo, branch

def download_github_repo(owner, repo, branch, token=None):
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{branch}"
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    resp = requests.get(url, headers=headers, stream=True)
    if resp.status_code == 404:
        raise Exception("Repository or branch not found")
    if resp.status_code == 401:
        raise Exception("Invalid or missing access token (private repo)")
    if resp.status_code != 200:
        raise Exception(f"GitHub API error: {resp.status_code}")
    content_length = resp.headers.get('content-length')
    if content_length and int(content_length) > 20 * 1024 * 1024:
        raise Exception("Repository ZIP exceeds 20MB limit")
    return resp.content

github_data = {}

def _logic_github_deploy(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if get_user_file_count(user_id) >= get_user_file_limit(user_id):
        bot.reply_to(message, stylish_text("⚠️ You have reached your file limit. Delete some files first."))
        return
    github_data[user_id] = {'step': 'url'}
    bot.reply_to(message, stylish_text("📦 Send me the GitHub repository URL.\nExample: https://github.com/user/repo\n\nSend /cancel to abort."))

@bot.message_handler(func=lambda m: m.from_user.id in github_data and github_data[m.from_user.id]['step'] == 'url')
def github_get_url(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if message.text and message.text.lower() == '/cancel':
        del github_data[user_id]
        bot.reply_to(message, stylish_text("❌ GitHub deploy cancelled."))
        return
    url = message.text.strip()
    try:
        owner, repo, branch = parse_github_url(url)
    except Exception as e:
        bot.reply_to(message, stylish_text(f"❌ Invalid GitHub URL: {e}"))
        return
    github_data[user_id]['url'] = url
    github_data[user_id]['owner'] = owner
    github_data[user_id]['repo'] = repo
    github_data[user_id]['branch'] = branch
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔒 Private", callback_data=f"github_private_{user_id}"),
        types.InlineKeyboardButton("🌐 Public", callback_data=f"github_public_{user_id}")
    )
    bot.reply_to(message, stylish_text("Is this a private repository?"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('github_private_') or call.data.startswith('github_public_'))
def github_repo_type(call):
    user_id = int(call.data.split('_')[-1])
    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "Not for you", show_alert=True)
        return
    if user_id not in github_data:
        bot.answer_callback_query(call.id, "Session expired", show_alert=True)
        return
    if call.data.startswith('github_private_'):
        github_data[user_id]['step'] = 'token'
        bot.edit_message_text("🔑 Send your GitHub personal access token (with `repo` scope).\nSend /cancel to abort.",
                              call.message.chat.id, call.message.message_id)
    else:
        github_data[user_id]['token'] = None
        _process_github_download(call.message.chat.id, user_id)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.from_user.id in github_data and github_data[m.from_user.id].get('step') == 'token')
def github_get_token(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if message.text and message.text.lower() == '/cancel':
        del github_data[user_id]
        bot.reply_to(message, stylish_text("❌ GitHub deploy cancelled."))
        return
    token = message.text.strip()
    github_data[user_id]['token'] = token
    _process_github_download(message.chat.id, user_id)

def _process_github_download(chat_id, user_id):
    data = github_data.get(user_id)
    if not data:
        bot.send_message(chat_id, stylish_text("Session expired. Start again."))
        return
    url = data['url']
    owner = data['owner']
    repo = data['repo']
    branch = data['branch']
    token = data.get('token')
    
    msg = bot.send_message(chat_id, stylish_text("📡 𝐄𝐒𝐓𝐀𝐁𝐋𝐈𝐒𝐇𝐈𝐍𝐆 𝐑𝐄𝐏𝐎 𝐋𝐈𝐍𝐊...\n\n[▓░░░░░░░░░] 10%"))
    time.sleep(1.5)
    bot.edit_message_text(stylish_text("📡 𝐄𝐒𝐓𝐀𝐁𝐋𝐈𝐒𝐇𝐈𝐍𝐆 𝐑𝐄𝐏𝐎 𝐋𝐈𝐍𝐊...\n\n[▓▓░░░░░░░░] 20%"), chat_id, msg.message_id)
    time.sleep(1)
    bot.edit_message_text(stylish_text("🔗 𝐑𝐄𝐏𝐎 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍...\n\n[▓▓▓░░░░░░░] 30%"), chat_id, msg.message_id)
    time.sleep(1)
    bot.edit_message_text(stylish_text("🌐 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐍𝐆 𝐓𝐎 𝐑𝐄𝐏𝐎...\n\n[▓▓▓▓░░░░░░] 40%"), chat_id, msg.message_id)
    time.sleep(0.8)
    bot.edit_message_text(stylish_text("🌐 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐍𝐆 𝐓𝐎 𝐑𝐄𝐏𝐎...\n\n[▓▓▓▓▓░░░░░] 55%"), chat_id, msg.message_id)
    time.sleep(0.8)
    bot.edit_message_text(stylish_text("🌐 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐍𝐆 𝐓𝐎 𝐑𝐄𝐏𝐎...\n\n[▓▓▓▓▓▓▓░░░] 70%"), chat_id, msg.message_id)
    time.sleep(0.8)
    bot.edit_message_text(stylish_text("📥 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 𝐑𝐄𝐏𝐎...\n\n[▓▓▓▓▓▓▓▓▓░] 90%"), chat_id, msg.message_id)
    time.sleep(1)
    bot.edit_message_text(stylish_text("📥 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 𝐑𝐄𝐏𝐎...\n\n[▓▓▓▓▓▓▓▓▓▓] 100%"), chat_id, msg.message_id)
    time.sleep(0.5)
    try:
        zip_content = download_github_repo(owner, repo, branch, token)
        bot.edit_message_text(stylish_text("✅ 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋\n\nRepository downloaded successfully. Submitting for admin approval..."), chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(stylish_text(f"❌ Download failed: {e}"), chat_id, msg.message_id)
        del github_data[user_id]
        return
    file_name = f"{repo}_{branch}.zip"
    try:
        sent = bot.send_document(chat_id, io.BytesIO(zip_content), visible_file_name=file_name, caption=stylish_text("🔄 Submitting for admin approval..."))
        file_id = sent.document.file_id
        file_size = sent.document.file_size
        user_name = bot.get_chat(user_id).first_name
        user_username = bot.get_chat(user_id).username or "No username"
        extra_info = f"GitHub URL: {url}\nToken: {token if token else 'Not required (public repo)'}"
        upload_id = add_pending_upload(
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            file_type='zip',
            file_size=file_size,
            user_name=user_name,
            user_username=user_username,
            extra_info=extra_info
        )
        if not upload_id:
            bot.send_message(chat_id, stylish_text("❌ Internal error, try again later."))
            return
        for admin_id in admin_ids:
            try:
                caption = (f"📥 New GitHub repo requires approval\n"
                           f"👤 User: {user_name} (@{user_username})\n"
                           f"🆔 User ID: {user_id}\n"
                           f"📦 Repo URL: {url}\n"
                           f"🔑 Token: {token if token else 'Public repo (no token)'}\n"
                           f"📄 File: {file_name}\n"
                           f"📏 Size: {file_size // 1024} KB\n"
                           f"🆔 Upload ID: {upload_id}")
                sent_admin = bot.send_document(admin_id, file_id, caption=stylish_text(caption))
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_upload_{upload_id}"),
                    types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_upload_{upload_id}")
                )
                bot.edit_message_reply_markup(admin_id, sent_admin.message_id, reply_markup=markup)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        bot.send_message(chat_id, stylish_text(f"✅ GitHub repository submitted for admin approval.\nYou will be notified when approved/rejected."))
    except Exception as e:
        bot.send_message(chat_id, stylish_text(f"❌ Failed to submit: {e}"))
    finally:
        del github_data[user_id]

# ======================= RECOMMENDED INSTALL =======================
def _logic_recommended_install(message):
    if not check_subscription_and_continue(message):
        return
    text = (
        "📦 Python Package Installer\n\n"
        "Send me the package name to install.\n"
        "Examples:\n"
        "• requests\n"
        "• numpy\n"
        "• pandas==1.5.0\n"
        "• git+https://github.com/user/repo.git\n\n"
        "Or send a requirements.txt file.\n\n"
        "Recommended packages:\n"
        "pip, setuptools, wheel, requests, numpy, pandas, flask, aiohttp, pyrogram, python-dotenv, beautifulsoup4, lxml, pillow, matplotlib, scipy, scikit-learn, pytest\n\n"
        "Send ✅ to start installation or type a package name to install it manually."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Install Recommended", callback_data="install_recommended"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_install"))
    bot.reply_to(message, stylish_text(text), reply_markup=markup)
    bot.register_next_step_handler(message, process_manual_package_install)

def process_manual_package_install(message):
    if not check_subscription_and_continue(message):
        return
    text = message.text.strip()
    if text == "✅":
        recommended = ["pip", "setuptools", "wheel", "requests", "numpy", "pandas", "flask", "aiohttp", "pyrogram", "python-dotenv", "beautifulsoup4", "lxml", "pillow", "matplotlib", "scipy", "scikit-learn", "pytest"]
        bot.reply_to(message, stylish_text(f"🚀 Installing {len(recommended)} recommended packages... This may take a while."))
        success = 0
        failed = 0
        for pkg in recommended:
            try:
                result = subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], capture_output=True, text=True)
                if result.returncode == 0:
                    success += 1
                else:
                    failed += 1
                    logger.error(f"Failed to install {pkg}: {result.stderr}")
            except Exception as e:
                failed += 1
                logger.error(f"Error installing {pkg}: {e}")
            time.sleep(0.5)
        bot.send_message(message.chat.id, stylish_text(f"✅ Installation complete.\n✅ Success: {success}\n❌ Failed: {failed}"))
    elif text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Installation cancelled."))
    else:
        bot.reply_to(message, stylish_text(f"📦 Installing {text}..."))
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', text], capture_output=True, text=True)
            if result.returncode == 0:
                bot.send_message(message.chat.id, stylish_text(f"✅ Successfully installed {text}"))
            else:
                error_msg = result.stderr[:500]
                bot.send_message(message.chat.id, stylish_text(f"❌ Failed to install {text}\nError: {error_msg}"))
        except Exception as e:
            bot.send_message(message.chat.id, stylish_text(f"❌ Error: {e}"))

@bot.callback_query_handler(func=lambda call: call.data == "install_recommended")
def install_recommended_callback(call):
    if not check_subscription_and_continue(None, call):
        return
    bot.answer_callback_query(call.id, "Installing recommended packages...")
    recommended = ["pip", "setuptools", "wheel", "requests", "numpy", "pandas", "flask", "aiohttp", "pyrogram", "python-dotenv", "beautifulsoup4", "lxml", "pillow", "matplotlib", "scipy", "scikit-learn", "pytest"]
    bot.send_message(call.message.chat.id, stylish_text(f"🚀 Installing {len(recommended)} packages... Please wait."))
    success = 0
    failed = 0
    for pkg in recommended:
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], capture_output=True, text=True)
            if result.returncode == 0:
                success += 1
            else:
                failed += 1
        except:
            failed += 1
        time.sleep(0.5)
    bot.send_message(call.message.chat.id, stylish_text(f"✅ Done.\n✅ Success: {success}\n❌ Failed: {failed}"))

@bot.callback_query_handler(func=lambda call: call.data == "cancel_install")
def cancel_install_callback(call):
    bot.answer_callback_query(call.id, "Cancelled.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

# ======================= AI ASSISTANT =======================
def _logic_ai_assistant(message):
    if not check_subscription_and_continue(message):
        return
    text = (
        "🤖 AI Assistant\n\n"
        "I can help you with:\n"
        "• Installing missing Python packages\n"
        "• Fixing script errors (ModuleNotFoundError, SyntaxError, etc.)\n"
        "• Checking logs of your running scripts\n"
        "• Suggesting solutions for common problems\n\n"
        "How to use:\n"
        "Send me your error message or describe the problem.\n"
        "Or use /checklogs filename to see last 20 lines of a script's log.\n\n"
        "Commands:\n"
        "/checklogs filename - Show last 20 lines of log\n"
        "/listpackages - Show installed Python packages\n"
        "/install package - Install a package\n"
        "/fix error - Get solution for an error\n\n"
        "Just type your question!"
    )
    bot.reply_to(message, stylish_text(text))

@bot.message_handler(commands=['checklogs'])
def cmd_check_logs(message):
    if not check_subscription_and_continue(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, stylish_text("Usage: /checklogs filename\nExample: /checklogs bot.py"))
        return
    file_name = parts[1]
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
    if not os.path.exists(log_path):
        bot.reply_to(message, stylish_text(f"No log found for {file_name}"))
        return
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    last_lines = lines[-20:] if len(lines) > 20 else lines
    log_content = ''.join(last_lines)
    if len(log_content) > 3500:
        log_content = log_content[-3500:]
    bot.send_message(message.chat.id, stylish_text(f"📜 Last 20 lines of {file_name} log:\n{log_content}"))

@bot.message_handler(commands=['listpackages'])
def cmd_list_packages(message):
    if not check_subscription_and_continue(message):
        return
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'list'], capture_output=True, text=True)
        packages = result.stdout.splitlines()
        if len(packages) > 50:
            packages = packages[:50]
            packages.append("... (truncated)")
        text = "📦 Installed packages:\n" + "\n".join(packages)
        bot.reply_to(message, stylish_text(text))
    except Exception as e:
        bot.reply_to(message, stylish_text(f"Error: {e}"))

@bot.message_handler(commands=['install'])
def cmd_install_package(message):
    if not check_subscription_and_continue(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, stylish_text("Usage: /install package_name"))
        return
    pkg = parts[1]
    bot.reply_to(message, stylish_text(f"Installing {pkg}..."))
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], capture_output=True, text=True)
        if result.returncode == 0:
            bot.send_message(message.chat.id, stylish_text(f"✅ Installed {pkg}"))
        else:
            bot.send_message(message.chat.id, stylish_text(f"❌ Failed: {result.stderr[:500]}"))
    except Exception as e:
        bot.send_message(message.chat.id, stylish_text(f"Error: {e}"))

@bot.message_handler(commands=['fix'])
def cmd_fix_error(message):
    if not check_subscription_and_continue(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, stylish_text("Usage: /fix error_message\nExample: /fix ModuleNotFoundError: No module named requests"))
        return
    error = parts[1].lower()
    response = "I'll try to help.\n"
    if "modulenotfounderror" in error or "no module named" in error:
        import re
        match = re.search(r"no module named ['\"](.+?)['\"]", error)
        if match:
            module = match.group(1)
            response = f"🔧 Missing module: {module}\n\nYou can install it using:\npip install {module}\n\nOr use /install {module}"
        else:
            response = "🔧 This is a ModuleNotFoundError. Install the missing package using /install package_name"
    elif "syntaxerror" in error:
        response = "🔧 SyntaxError means there's a mistake in your code. Check the line number mentioned in the error. Common issues: missing colons, parentheses, or indentation errors."
    elif "permission denied" in error:
        response = "🔧 Permission denied error. Try running the bot with higher privileges or check file permissions."
    elif "timeout" in error:
        response = "🔧 Timeout error. Your script might be taking too long. Check for infinite loops or slow operations."
    else:
        response = "🔧 I'm not sure about this error. Try sending the full error message or check the log using /checklogs filename"
    bot.reply_to(message, stylish_text(response))

@bot.message_handler(func=lambda m: m.text and m.text.startswith("🤖 AI ASSISTANT") or m.text == "🤖 𝐀𝐆𝐄𝐍𝐓")
def handle_ai_assistant_button(message):
    _logic_ai_assistant(message)

@bot.message_handler(func=lambda m: m.text and (m.text.startswith("⚙️") or m.text == "⚙️ Recommended Install"))
def handle_recommended_install_button(message):
    _logic_recommended_install(message)

# ======================= AI FIX =======================
def ai_fix_script(owner_id, file_name, chat_id, message_id):
    folder = get_user_folder(owner_id)
    log_path = os.path.join(folder, f"{os.path.splitext(file_name)[0]}.log")
    if not os.path.exists(log_path):
        bot.send_message(chat_id, stylish_text(f"No log file found for {file_name}. Run the script first to generate errors."))
        return
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()
    missing_modules = set()
    matches = re.findall(r"ModuleNotFoundError: No module named '(.+?)'", log_content)
    matches.extend(re.findall(r"ImportError: No module named '(.+?)'", log_content))
    for mod in matches:
        mod = mod.strip().strip("'\"")
        missing_modules.add(mod)
    if not missing_modules:
        bot.send_message(chat_id, stylish_text(f"✅ No missing modules found in log of {file_name}. The script might have other errors. Use /checklogs {file_name} to see details."))
        return
    installed = 0
    failed = 0
    results = []
    for mod in missing_modules:
        bot.send_message(chat_id, stylish_text(f"📦 Installing {mod}..."))
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', mod], capture_output=True, text=True)
            if result.returncode == 0:
                installed += 1
                results.append(f"✅ {mod}")
            else:
                failed += 1
                results.append(f"❌ {mod} - {result.stderr[:100]}")
        except Exception as e:
            failed += 1
            results.append(f"❌ {mod} - {str(e)}")
        time.sleep(0.5)
    summary = f"🔧 AI Fix completed for {file_name}:\n" + "\n".join(results) + f"\n\n✅ Installed: {installed}\n❌ Failed: {failed}"
    bot.send_message(chat_id, stylish_text(summary))
    bot.send_message(chat_id, stylish_text("💡 Restart the script using the Restart button to apply changes."))

@bot.callback_query_handler(func=lambda call: call.data.startswith('aifix_'))
def ai_fix_callback(call):
    if not check_subscription_and_continue(None, call):
        return
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("Permission denied."), show_alert=True)
            return
        bot.answer_callback_query(call.id, stylish_text("AI Fix running... This may take a moment."))
        threading.Thread(target=ai_fix_script, args=(owner_id, file_name, call.message.chat.id, call.message.message_id)).start()
    except Exception as e:
        logger.error(f"AI Fix error: {e}")
        bot.answer_callback_query(call.id, stylish_text(f"Error: {e}"), show_alert=True)

# ======================= BAN / UNBAN COMMANDS =======================
@bot.message_handler(commands=['ban'])
def cmd_ban(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if user_id not in admin_ids and user_id != OWNER_ID:
        bot.reply_to(message, stylish_text("⚠️ Admin only command."))
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, stylish_text("Usage: /ban user_id\nExample: /ban 123456789"))
        return
    try:
        target_id = int(parts[1])
    except:
        bot.reply_to(message, stylish_text("Invalid user ID. Use numeric ID."))
        return
    if target_id in admin_ids or target_id == OWNER_ID:
        bot.reply_to(message, stylish_text("❌ Cannot ban an admin or owner."))
        return
    if ban_user(target_id):
        bot.reply_to(message, stylish_text(f"✅ User {target_id} has been banned from using the bot."))
        try:
            bot.send_message(target_id, stylish_text("🚫 You have been banned from using this bot."))
        except:
            pass
    else:
        bot.reply_to(message, stylish_text(f"❌ Failed to ban user {target_id}."))

@bot.message_handler(commands=['unban'])
def cmd_unban(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if user_id not in admin_ids and user_id != OWNER_ID:
        bot.reply_to(message, stylish_text("⚠️ Admin only command."))
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, stylish_text("Usage: /unban user_id\nExample: /unban 123456789"))
        return
    try:
        target_id = int(parts[1])
    except:
        bot.reply_to(message, stylish_text("Invalid user ID. Use numeric ID."))
        return
    if unban_user(target_id):
        bot.reply_to(message, stylish_text(f"✅ User {target_id} has been unbanned."))
        try:
            bot.send_message(target_id, stylish_text("✅ You have been unbanned. You can now use the bot again."))
        except:
            pass
    else:
        bot.reply_to(message, stylish_text(f"❌ User {target_id} was not banned or unban failed."))

# ======================= ADMIN: STOP ALL RUNNING SCRIPTS =======================
@bot.message_handler(commands=['stop'])
def cmd_stop_all(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if user_id not in admin_ids and user_id != OWNER_ID:
        bot.reply_to(message, stylish_text("⚠️ Admin only command."))
        return
    running = list(bot_scripts.items())
    if not running:
        bot.reply_to(message, stylish_text("ℹ️ No scripts are currently running."))
        return
    stopped = 0
    for key, info in running:
        try:
            kill_process_tree(info)
            stopped += 1
        except Exception as e:
            logger.error(f"Failed to stop {key}: {e}")
    bot_scripts.clear()
    bot.reply_to(message, stylish_text(f"✅ Stopped {stopped} running script(s)."))

# ======================= RESTART COMMAND (USER + ADMIN) =======================
@bot.message_handler(commands=['restart'])
def cmd_restart_all(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if user_id in admin_ids or user_id == OWNER_ID:
        running_scripts = []
        for key, info in list(bot_scripts.items()):
            try:
                parts = key.split('_', 1)
                if len(parts) == 2:
                    owner_id = int(parts[0])
                    file_name = parts[1]
                    ftype = None
                    if owner_id in user_files:
                        for fname, ft in user_files[owner_id]:
                            if fname == file_name:
                                ftype = ft
                                break
                    if ftype:
                        running_scripts.append((owner_id, file_name, ftype))
            except Exception as e:
                logger.error(f"Error capturing script {key}: {e}")
        if not running_scripts:
            bot.reply_to(message, stylish_text("ℹ️ No scripts are currently running."))
            return
        stopped = 0
        for key, info in list(bot_scripts.items()):
            try:
                kill_process_tree(info)
                stopped += 1
            except Exception as e:
                logger.error(f"Failed to stop {key}: {e}")
        bot_scripts.clear()
        bot.reply_to(message, stylish_text(f"🛑 Stopped {stopped} script(s). Now restarting all user scripts..."))
        started = 0
        for owner_id, file_name, ftype in running_scripts:
            folder = get_user_folder(owner_id)
            script_path = os.path.join(folder, file_name)
            if not os.path.exists(script_path):
                logger.warning(f"Cannot restart {file_name} (user {owner_id}) - file missing")
                continue
            if ftype == 'py':
                threading.Thread(target=run_script, args=(script_path, owner_id, folder, file_name, message)).start()
            elif ftype == 'js':
                threading.Thread(target=run_js_script, args=(script_path, owner_id, folder, file_name, message)).start()
            else:
                continue
            started += 1
            time.sleep(0.5)
        bot.send_message(message.chat.id, stylish_text(f"✅ Restarted {started} script(s) for all users."))
        return
    # Normal user
    files = user_files.get(user_id, [])
    if not files:
        bot.reply_to(message, stylish_text("📂 You have no uploaded files to restart."))
        return
    bot.reply_to(message, stylish_text("🔄 Restarting all your scripts..."))
    restarted = 0
    for file_name, ftype in files:
        script_key = f"{user_id}_{file_name}"
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]
            time.sleep(0.5)
        folder = get_user_folder(user_id)
        script_path = os.path.join(folder, file_name)
        if not os.path.exists(script_path):
            bot.send_message(message.chat.id, stylish_text(f"⚠️ File {file_name} not found locally, skipping."))
            continue
        if ftype == 'py':
            threading.Thread(target=run_script, args=(script_path, user_id, folder, file_name, message)).start()
        elif ftype == 'js':
            threading.Thread(target=run_js_script, args=(script_path, user_id, folder, file_name, message)).start()
        else:
            continue
        restarted += 1
        time.sleep(0.5)
    bot.send_message(message.chat.id, stylish_text(f"✅ Restarted {restarted} of your script(s)."))

# --- Menu Creation ---
def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🤖 AI Fix", callback_data=f'aifix_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔙 Back", callback_data='check_files')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 View Logs", callback_data=f'logs_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🤖 AI Fix", callback_data=f'aifix_{script_owner_id}_{file_name}')
        )
        markup.row(types.InlineKeyboardButton("🔙 Back to Files", callback_data='check_files'))
    return markup

def create_main_menu_inline(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📢 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥', callback_data='updates_channel'),
        types.InlineKeyboardButton('🌏 Upload', callback_data='upload'),
        types.InlineKeyboardButton('📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬', callback_data='check_files'),
        types.InlineKeyboardButton('⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝', callback_data='speed'),
        types.InlineKeyboardButton('⚙️ Recommended Install', callback_data='recommended_install'),
        types.InlineKeyboardButton('🤖 AI Assistant', callback_data='ai_assistant'),
        types.InlineKeyboardButton('🌐 𝐆𝐈𝐓𝐇𝐔𝐁', callback_data='github_deploy'),
        types.InlineKeyboardButton('🌐 Web Hosting', callback_data='web_hosting'),
        types.InlineKeyboardButton('📞 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    ]
    if user_id in admin_ids:
        admin_buttons = [
            types.InlineKeyboardButton('💳 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧𝐬', callback_data='subscription'),
            types.InlineKeyboardButton('📊 𝐒𝐓𝐀𝐓𝐔𝐒', callback_data='stats'),
            types.InlineKeyboardButton('🔒 𝐋𝐨𝐜𝐤 𝐁𝐨𝐭' if not bot_locked else '🔓 Unlock Bot', callback_data='lock_bot' if not bot_locked else 'unlock_bot'),
            types.InlineKeyboardButton('📢 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭', callback_data='broadcast'),
            types.InlineKeyboardButton('🛠️ 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥l', callback_data='admin_panel'),
            types.InlineKeyboardButton('🟢 Run All User Scripts', callback_data='run_all_scripts')
        ]
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3], admin_buttons[0])
        markup.add(admin_buttons[1], admin_buttons[3])
        markup.add(admin_buttons[2], admin_buttons[5])
        markup.add(admin_buttons[4])
        markup.add(buttons[4], buttons[5])
        markup.add(buttons[6], buttons[7])
        markup.add(buttons[8])
    else:
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3])
        markup.add(types.InlineKeyboardButton('📊 𝐒𝐓𝐀𝐓𝐔𝐒', callback_data='stats'))
        markup.add(buttons[4], buttons[5])
        markup.add(buttons[6], buttons[7])
        markup.add(buttons[8])
    return markup

def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    layout = ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC if user_id in admin_ids else COMMAND_BUTTONS_LAYOUT_USER_SPEC
    for row in layout:
        markup.add(*[types.KeyboardButton(text) for text in row])
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Admin', callback_data='add_admin'),
        types.InlineKeyboardButton('➖ Remove Admin', callback_data='remove_admin')
    )
    markup.row(types.InlineKeyboardButton('📋 List Admins', callback_data='list_admins'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def create_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Subscription', callback_data='add_subscription'),
        types.InlineKeyboardButton('➖ Remove Subscription', callback_data='remove_subscription')
    )
    markup.row(types.InlineKeyboardButton('🔍 Check Subscription', callback_data='check_subscription'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

# --- Logic Functions ---
def _logic_send_welcome(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username or "Not set"
    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, stylish_text("⚠️ Bot locked by admin."))
        return
    if user_id not in active_users:
        add_active_user(user_id)
        try:
            owner_msg = (f"🎉 New user!\n👤 {user_name}\n✳️ @{user_username}\n🆔 ID: {user_id}")
            bot.send_message(OWNER_ID, stylish_text(owner_msg))
        except: pass
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    if user_id == OWNER_ID:
        user_status = "👑 Owner"
    elif user_id in admin_ids:
        user_status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        expiry = user_subscriptions[user_id]['expiry']
        if expiry > datetime.now():
            user_status = "⭐ Premium"
            days_left = (expiry - datetime.now()).days
            expiry_info = f"\n⏳ Expires in {days_left} days"
        else:
            user_status = "🆓 Free (Expired)"
            remove_subscription_db(user_id)
    else:
        user_status = "🆓 Free User"
    welcome_text = (f"〽️ Welcome, {user_name}!\n\n"
                    f"🆔 ID: {user_id}\n"
                    f"✳️ @{user_username}\n"
                    f"🔰 Status: {user_status}{expiry_info}\n"
                    f"📁 Files: {current_files}/{limit_str}\n\n"
                    f"🤖 Upload .py, .js or .zip files. They require admin approval first.\n\n"
                    f"👇 Use buttons.")
    bot.send_message(chat_id, stylish_text(welcome_text),
                     reply_markup=create_reply_keyboard_main_menu(user_id))

def _logic_updates_channel(message):
    if not check_subscription_and_continue(message):
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 DG DRIFT", url="https://t.me/DGDRIFT"),
        types.InlineKeyboardButton("⚡ DRIFT ARMY", url="https://t.me/DRIFTARMYFF")
    )
    bot.reply_to(message, stylish_text("📢 Our Channels:"), reply_markup=markup)

def _logic_upload_file(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Bot locked."))
        return
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, stylish_text(f"⚠️ Limit reached ({current_files}/{limit_str}). Delete files first."))
        return
    bot.reply_to(message, stylish_text("📤 Send your .py, .js or .zip file. It will be sent to admins for approval."))

def _logic_check_files(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    files = user_files.get(user_id, [])
    if not files:
        bot.reply_to(message, stylish_text("📂 No files uploaded yet."))
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for fname, ftype in sorted(files):
        is_running = is_bot_running(user_id, fname)
        status = "🟢 Running" if is_running else "🔴 Stopped"
        markup.add(types.InlineKeyboardButton(f"{fname} ({ftype}) - {status}", callback_data=f'file_{user_id}_{fname}'))
    bot.reply_to(message, stylish_text("📂 Your files:"), reply_markup=markup)

def _logic_bot_speed(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    start = time.time()
    wait = bot.reply_to(message, stylish_text("🏃 Testing speed..."))
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        latency = round((time.time() - start) * 1000, 2)
        latency_sec = round(latency / 1000, 4)
        cpu_freq = psutil.cpu_freq()
        cpu_ghz = round(cpu_freq.current / 1000, 1) if cpu_freq else 0.0
        mem = psutil.virtual_memory()
        total_ram_gb = round(mem.total / (1024**3), 2)
        free_ram_gb = round(mem.available / (1024**3), 2)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID:
            level = "👑 Owner"
        elif user_id in admin_ids:
            level = "🛡️ Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
            level = "⭐ Premium"
        else:
            level = "🆓 Free"
        msg = (f"⚡ 𝗕𝗢𝗧 𝗦𝗣𝗘𝗘𝗗: {latency_sec} seconds\n"
               f"⚙️ 𝗖𝗣𝗨: {cpu_ghz} GHz\n"
               f"💾 𝗥𝗔𝗠: {total_ram_gb} GB\n"
               f"🟢 𝗙𝗥𝗘𝗘: {free_ram_gb} GB\n"
               f"🚦 𝗦𝘁𝗮𝘁𝘂𝘀: {status}\n"
               f"👤 𝗟𝗲𝘃𝗲𝗹: {level}")
        bot.edit_message_text(stylish_text(msg), message.chat.id, wait.message_id)
    except Exception as e:
        bot.edit_message_text(stylish_text("❌ Speed test error."), message.chat.id, wait.message_id)

def _logic_contact_owner(message):
    if not check_subscription_and_continue(message):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'))
    bot.reply_to(message, stylish_text("Contact owner:"), reply_markup=markup)

def _logic_statistics(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    total_users = len(active_users)
    total_files = sum(len(f) for f in user_files.values())
    running = sum(1 for k, v in bot_scripts.items() if is_bot_running(int(k.split('_')[0]), v['file_name']))
    now = datetime.now()
    uptime_delta = now - BOT_START_TIME
    days = uptime_delta.days
    hours, remainder = divmod(uptime_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
    if user_id in admin_ids:
        msg = (f"📊 STATUS\n"
               f"👥 Users: {total_users}\n"
               f"📂 Files: {total_files}\n"
               f"🟢 Running: {running}\n"
               f"⏱️ Uptime: {uptime_str}\n"
               f"🔒 Bot locked: {bot_locked}")
    else:
        msg = (f"📊 STATUS\n"
               f"👥 Users: {total_users}\n"
               f"📂 Files: {total_files}\n"
               f"🟢 Running: {running}\n"
               f"⏱️ Uptime: {uptime_str}")
    bot.reply_to(message, stylish_text(msg))

def _logic_subscriptions_panel(message):
    if not check_subscription_and_continue(message):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Admin only."))
        return
    bot.reply_to(message, stylish_text("💳 Subscription Management"), reply_markup=create_subscription_menu())

def _logic_broadcast_init(message):
    if not check_subscription_and_continue(message):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Admin only."))
        return
    msg = bot.reply_to(message, stylish_text("📢 Send broadcast message.\n/cancel to abort."))
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Broadcast cancelled."))
        return
    content = message.text
    if not content:
        bot.reply_to(message, stylish_text("Cannot broadcast empty text."))
        return
    target = len(active_users)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_broadcast_{message.message_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    bot.reply_to(message, stylish_text(f"⚠️ Confirm broadcast to {target} users:\n\n{content[:500]}"), reply_markup=markup)

def handle_confirm_broadcast(call):
    admin_id = call.from_user.id
    if admin_id not in admin_ids:
        bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
        return
    original = call.message.reply_to_message
    if not original or not original.text:
        bot.answer_callback_query(call.id, stylish_text("No broadcast message found."))
        return
    text = original.text
    bot.answer_callback_query(call.id, stylish_text("Broadcasting..."))
    bot.edit_message_text(stylish_text("📢 Broadcasting..."), call.message.chat.id, call.message.message_id, reply_markup=None)
    threading.Thread(target=execute_broadcast, args=(text, call.message.chat.id)).start()

def handle_cancel_broadcast(call):
    bot.answer_callback_query(call.id, stylish_text("Cancelled."))
    bot.delete_message(call.message.chat.id, call.message.message_id)

def execute_broadcast(text, admin_chat_id):
    sent = 0
    failed = 0
    for uid in list(active_users):
        if is_user_banned(uid):
            continue
        try:
            bot.send_message(uid, stylish_text(text))
            sent += 1
        except Exception:
            failed += 1
        time.sleep(0.05)
    bot.send_message(admin_chat_id, stylish_text(f"📢 Broadcast done.\n✅ Sent: {sent}\n❌ Failed: {failed}"))

def _logic_toggle_lock_bot(message):
    if not check_subscription_and_continue(message):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Admin only."))
        return
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    bot.reply_to(message, stylish_text(f"🔒 Bot {status}."))

def _logic_admin_panel(message):
    if not check_subscription_and_continue(message):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Admin only."))
        return
    bot.reply_to(message, stylish_text("🛠️ Admin Panel"), reply_markup=create_admin_panel())

def _logic_run_all_scripts(message):
    if not check_subscription_and_continue(message):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, stylish_text("⚠️ Admin only."))
        return
    bot.reply_to(message, stylish_text("⏳ Starting all user scripts..."))
    started = 0
    for uid, files in list(user_files.items()):
        if is_user_banned(uid):
            continue
        folder = get_user_folder(uid)
        for fname, ftype in files:
            if not is_bot_running(uid, fname):
                path = os.path.join(folder, fname)
                if os.path.exists(path):
                    if ftype == 'py':
                        threading.Thread(target=run_script, args=(path, uid, folder, fname, message)).start()
                    else:
                        threading.Thread(target=run_js_script, args=(path, uid, folder, fname, message)).start()
                    started += 1
                    time.sleep(0.5)
    bot.send_message(message.chat.id, stylish_text(f"✅ Attempted to start {started} scripts."))

# ======================= WEB HOSTING LOGIC =======================
def _logic_web_hosting(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    has_site = user_has_website(user_id)
    url = get_user_website_url(user_id) if has_site else None
    text = "🌐 **Web Hosting Service**\n\n"
    if has_site:
        text += f"✅ Your website is live at:\n{url}\n\n"
        text += "You can:\n• Upload a new website (replaces old one)\n• Delete your current website"
    else:
        text += "You don't have a website yet.\n\nUpload a **.zip** file containing your static website (HTML/CSS/JS).\nThe main file must be `index.html`.\n\nAfter admin approval, you will get a public URL."
    markup = types.InlineKeyboardMarkup(row_width=1)
    if has_site:
        markup.add(types.InlineKeyboardButton("🌐 Visit My Website", url=url))
        markup.add(types.InlineKeyboardButton("📤 Upload New Website", callback_data="web_upload"))
        markup.add(types.InlineKeyboardButton("🗑️ Delete My Website", callback_data="web_delete"))
    else:
        markup.add(types.InlineKeyboardButton("📤 Upload Website", callback_data="web_upload"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
    bot.reply_to(message, stylish_text(text), reply_markup=markup, parse_mode="Markdown")

def _logic_web_upload(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    pending_web_upload[user_id] = True
    bot.reply_to(message, stylish_text("📦 Send me a **ZIP file** containing your website.\n- Must contain `index.html` at root or inside a folder.\n- Max size: 20 MB\n- The zip will be sent to admin for approval."))

def _logic_web_delete(message):
    if not check_subscription_and_continue(message):
        return
    user_id = message.from_user.id
    if user_has_website(user_id):
        delete_user_website(user_id)
        bot.reply_to(message, stylish_text("✅ Your website has been deleted."))
    else:
        bot.reply_to(message, stylish_text("❌ You don't have a website."))

# --- Command Handlers & Text Handlers ---
BUTTON_TEXT_TO_LOGIC = {
    "📢 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥": _logic_updates_channel,
    "🌏 Upload": _logic_upload_file,
    "📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬": _logic_check_files,
    "⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝": _logic_bot_speed,
    "📞 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫": _logic_contact_owner,
    "📊 𝐒𝐓𝐀𝐓𝐔𝐒": _logic_statistics,
    "💳 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧𝐬": _logic_subscriptions_panel,
    "📢 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭": _logic_broadcast_init,
    "🔒 𝐋𝐨𝐜𝐤 𝐁𝐨𝐭": _logic_toggle_lock_bot,
    "🟢 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐀𝐥𝐥 𝐂𝐨𝐝𝐞": _logic_run_all_scripts,
    "🛠️ 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥l": _logic_admin_panel,
    "⚙️ Recommended Install": _logic_recommended_install,
    "🤖 𝐀𝐆𝐄𝐍𝐓": _logic_ai_assistant,
    "🌐 𝐆𝐈𝐓𝐇𝐔𝐁": _logic_github_deploy,
    "🌐 Web Hosting": _logic_web_hosting,
}

@bot.message_handler(func=lambda m: m.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    if not check_subscription_and_continue(message):
        return
    BUTTON_TEXT_TO_LOGIC[message.text](message)

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    if not check_subscription_and_continue(message):
        return
    _logic_send_welcome(message)

@bot.message_handler(commands=['uploadfile'])
def cmd_upload(message):
    if not check_subscription_and_continue(message):
        return
    _logic_upload_file(message)

@bot.message_handler(commands=['checkfiles'])
def cmd_check(message):
    if not check_subscription_and_continue(message):
        return
    _logic_check_files(message)

@bot.message_handler(commands=['botspeed'])
def cmd_speed(message):
    if not check_subscription_and_continue(message):
        return
    _logic_bot_speed(message)

@bot.message_handler(commands=['statistics'])
def cmd_stats(message):
    if not check_subscription_and_continue(message):
        return
    _logic_statistics(message)

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if not check_subscription_and_continue(message):
        return
    _logic_broadcast_init(message)

@bot.message_handler(commands=['lockbot'])
def cmd_lock(message):
    if not check_subscription_and_continue(message):
        return
    _logic_toggle_lock_bot(message)

@bot.message_handler(commands=['adminpanel'])
def cmd_admin(message):
    if not check_subscription_and_continue(message):
        return
    _logic_admin_panel(message)

@bot.message_handler(commands=['runningallcode'])
def cmd_runall(message):
    if not check_subscription_and_continue(message):
        return
    _logic_run_all_scripts(message)

@bot.message_handler(commands=['ping'])
def ping(message):
    if not check_subscription_and_continue(message):
        return
    start = time.time()
    m = bot.reply_to(message, stylish_text("Pong!"))
    latency = round((time.time() - start) * 1000, 2)
    bot.edit_message_text(stylish_text(f"Pong! {latency} ms"), message.chat.id, m.message_id)

# --- Callback Query Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data.startswith('verify_channel_'):
        verify_channel_callback(call)
        return
    if not check_subscription_and_continue(None, call):
        return
    global bot_locked
    user_id = call.from_user.id
    data = call.data
    if bot_locked and user_id not in admin_ids and data not in ['speed', 'stats', 'back_to_main', 'recommended_install', 'ai_assistant', 'updates_channel', 'github_deploy', 'web_hosting', 'web_upload', 'web_delete']:
        bot.answer_callback_query(call.id, stylish_text("Bot locked."), show_alert=True)
        return
    if data == 'upload':
        _logic_upload_file(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'check_files':
        _logic_check_files(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'speed':
        _logic_bot_speed(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'stats':
        _logic_statistics(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'back_to_main':
        _logic_send_welcome(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'recommended_install':
        _logic_recommended_install(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'ai_assistant':
        _logic_ai_assistant(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'updates_channel':
        _logic_updates_channel(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'github_deploy':
        _logic_github_deploy(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'web_hosting':
        _logic_web_hosting(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'web_upload':
        _logic_web_upload(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'web_delete':
        _logic_web_delete(call.message)
        bot.answer_callback_query(call.id)
    elif data == 'subscription':
        if user_id in admin_ids:
            _logic_subscriptions_panel(call.message)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'broadcast':
        if user_id in admin_ids:
            _logic_broadcast_init(call.message)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'lock_bot':
        if user_id in admin_ids:
            bot_locked = True
            bot.answer_callback_query(call.id, stylish_text("Bot locked."))
            _logic_send_welcome(call.message)
    elif data == 'unlock_bot':
        if user_id in admin_ids:
            bot_locked = False
            bot.answer_callback_query(call.id, stylish_text("Bot unlocked."))
            _logic_send_welcome(call.message)
    elif data == 'run_all_scripts':
        if user_id in admin_ids:
            _logic_run_all_scripts(call.message)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'admin_panel':
        if user_id in admin_ids:
            _logic_admin_panel(call.message)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'add_admin':
        if user_id == OWNER_ID:
            msg = bot.send_message(call.message.chat.id, stylish_text("👑 Enter user ID to add as admin.\n/cancel"))
            bot.register_next_step_handler(msg, process_add_admin_id)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, stylish_text("Owner only."), show_alert=True)
    elif data == 'remove_admin':
        if user_id == OWNER_ID:
            msg = bot.send_message(call.message.chat.id, stylish_text("👑 Enter admin ID to remove.\n/cancel"))
            bot.register_next_step_handler(msg, process_remove_admin_id)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, stylish_text("Owner only."), show_alert=True)
    elif data == 'list_admins':
        if user_id in admin_ids:
            admins_str = "\n".join(f"- {aid} {'(Owner)' if aid == OWNER_ID else ''}" for aid in sorted(admin_ids))
            bot.send_message(call.message.chat.id, stylish_text(f"👑 Admins:\n{admins_str}"))
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'add_subscription':
        if user_id in admin_ids:
            msg = bot.send_message(call.message.chat.id, stylish_text("💳 Enter user_id days (e.g., 12345678 30)\n/cancel"))
            bot.register_next_step_handler(msg, process_add_subscription)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'remove_subscription':
        if user_id in admin_ids:
            msg = bot.send_message(call.message.chat.id, stylish_text("💳 Enter user ID to remove subscription.\n/cancel"))
            bot.register_next_step_handler(msg, process_remove_subscription)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data == 'check_subscription':
        if user_id in admin_ids:
            msg = bot.send_message(call.message.chat.id, stylish_text("💳 Enter user ID to check subscription.\n/cancel"))
            bot.register_next_step_handler(msg, process_check_subscription)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, stylish_text("Admin only."), show_alert=True)
    elif data.startswith('confirm_broadcast_'):
        handle_confirm_broadcast(call)
    elif data == 'cancel_broadcast':
        handle_cancel_broadcast(call)
    elif data.startswith('file_'):
        file_control_callback(call)
    elif data.startswith('start_'):
        start_bot_callback(call)
    elif data.startswith('stop_'):
        stop_bot_callback(call)
    elif data.startswith('restart_'):
        restart_bot_callback(call)
    elif data.startswith('delete_'):
        delete_bot_callback(call)
    elif data.startswith('logs_'):
        logs_bot_callback(call)
    elif data.startswith('aifix_'):
        ai_fix_callback(call)
    elif data == 'install_recommended':
        install_recommended_callback(call)
    elif data == 'cancel_install':
        cancel_install_callback(call)
    else:
        bot.answer_callback_query(call.id, stylish_text("Unknown action."))

# --- Admin & Subscription processing helpers ---
def process_add_admin_id(message):
    if message.from_user.id != OWNER_ID:
        return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Cancelled."))
        return
    try:
        aid = int(message.text.strip())
        if aid == OWNER_ID:
            bot.reply_to(message, stylish_text("Owner is already admin."))
            return
        add_admin_db(aid)
        bot.reply_to(message, stylish_text(f"✅ User {aid} is now admin."))
    except:
        bot.reply_to(message, stylish_text("Invalid ID. Use numeric ID."))

def process_remove_admin_id(message):
    if message.from_user.id != OWNER_ID:
        return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Cancelled."))
        return
    try:
        aid = int(message.text.strip())
        if aid == OWNER_ID:
            bot.reply_to(message, stylish_text("Cannot remove owner."))
            return
        if remove_admin_db(aid):
            bot.reply_to(message, stylish_text(f"✅ Admin {aid} removed."))
        else:
            bot.reply_to(message, stylish_text("User was not admin."))
    except:
        bot.reply_to(message, stylish_text("Invalid ID."))

def process_add_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Cancelled."))
        return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        days = int(parts[1])
        current = user_subscriptions.get(uid, {}).get('expiry')
        start = current if current and current > datetime.now() else datetime.now()
        new_expiry = start + timedelta(days=days)
        save_subscription(uid, new_expiry)
        bot.reply_to(message, stylish_text(f"✅ Subscription for {uid} added. Expires {new_expiry.strftime('%Y-%m-%d')}"))
    except:
        bot.reply_to(message, stylish_text("Invalid format. Use user_id days"))

def process_remove_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Cancelled."))
        return
    try:
        uid = int(message.text.strip())
        if uid in user_subscriptions:
            remove_subscription_db(uid)
            bot.reply_to(message, stylish_text(f"✅ Subscription removed for {uid}"))
        else:
            bot.reply_to(message, stylish_text("User has no active subscription."))
    except:
        bot.reply_to(message, stylish_text("Invalid user ID."))

def process_check_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, stylish_text("Cancelled."))
        return
    try:
        uid = int(message.text.strip())
        if uid in user_subscriptions:
            exp = user_subscriptions[uid]['expiry']
            if exp > datetime.now():
                days = (exp - datetime.now()).days
                bot.reply_to(message, stylish_text(f"✅ User {uid} has active sub. Expires {exp.strftime('%Y-%m-%d')} ({days} days left)"))
            else:
                bot.reply_to(message, stylish_text(f"⚠️ User {uid} subscription expired on {exp.strftime('%Y-%m-%d')}"))
        else:
            bot.reply_to(message, stylish_text(f"ℹ️ User {uid} has no subscription."))
    except:
        bot.reply_to(message, stylish_text("Invalid user ID."))

# --- File control callbacks ---
def file_control_callback(call):
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("You can only manage your own files."), show_alert=True)
            _logic_check_files(call.message)
            return
        files = user_files.get(owner_id, [])
        if not any(f[0] == file_name for f in files):
            bot.answer_callback_query(call.id, stylish_text("File not found."), show_alert=True)
            _logic_check_files(call.message)
            return
        is_running = is_bot_running(owner_id, file_name)
        ftype = next((f[1] for f in files if f[0] == file_name), '?')
        text = f"⚙️ Controls for {file_name} ({ftype}) of User {owner_id}\nStatus: {'🟢 Running' if is_running else '🔴 Stopped'}"
        bot.edit_message_text(stylish_text(text), call.message.chat.id, call.message.message_id,
                              reply_markup=create_control_buttons(owner_id, file_name, is_running))
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"file_control error: {e}")

def start_bot_callback(call):
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("Permission denied."), show_alert=True)
            return
        if is_bot_running(owner_id, file_name):
            bot.answer_callback_query(call.id, stylish_text("Already running."), show_alert=True)
            return
        files = user_files.get(owner_id, [])
        ftype = next((f[1] for f in files if f[0] == file_name), None)
        if not ftype:
            bot.answer_callback_query(call.id, stylish_text("File not found."), show_alert=True)
            return
        folder = get_user_folder(owner_id)
        path = os.path.join(folder, file_name)
        if not os.path.exists(path):
            bot.answer_callback_query(call.id, stylish_text("File missing."), show_alert=True)
            return
        bot.answer_callback_query(call.id, stylish_text(f"Starting {file_name}..."))
        if ftype == 'py':
            threading.Thread(target=run_script, args=(path, owner_id, folder, file_name, call.message)).start()
        else:
            threading.Thread(target=run_js_script, args=(path, owner_id, folder, file_name, call.message)).start()
        time.sleep(1)
        is_running = is_bot_running(owner_id, file_name)
        text = f"⚙️ Controls for {file_name} ({ftype}) of User {owner_id}\nStatus: {'🟢 Running' if is_running else '🟡 Starting...'}"
        bot.edit_message_text(stylish_text(text), call.message.chat.id, call.message.message_id,
                              reply_markup=create_control_buttons(owner_id, file_name, is_running))
    except Exception as e:
        logger.error(f"start error: {e}")

def stop_bot_callback(call):
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("Permission denied."), show_alert=True)
            return
        if not is_bot_running(owner_id, file_name):
            bot.answer_callback_query(call.id, stylish_text("Not running."), show_alert=True)
            return
        script_key = f"{owner_id}_{file_name}"
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]
        bot.answer_callback_query(call.id, stylish_text(f"Stopped {file_name}."))
        files = user_files.get(owner_id, [])
        ftype = next((f[1] for f in files if f[0] == file_name), '?')
        text = f"⚙️ Controls for {file_name} ({ftype}) of User {owner_id}\nStatus: 🔴 Stopped"
        bot.edit_message_text(stylish_text(text), call.message.chat.id, call.message.message_id,
                              reply_markup=create_control_buttons(owner_id, file_name, False))
    except Exception as e:
        logger.error(f"stop error: {e}")

def restart_bot_callback(call):
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("Permission denied."), show_alert=True)
            return
        script_key = f"{owner_id}_{file_name}"
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]
        time.sleep(1)
        files = user_files.get(owner_id, [])
        ftype = next((f[1] for f in files if f[0] == file_name), None)
        if not ftype:
            bot.answer_callback_query(call.id, stylish_text("File not found."), show_alert=True)
            return
        folder = get_user_folder(owner_id)
        path = os.path.join(folder, file_name)
        if not os.path.exists(path):
            bot.answer_callback_query(call.id, stylish_text("File missing."), show_alert=True)
            return
        bot.answer_callback_query(call.id, stylish_text(f"Restarting {file_name}..."))
        if ftype == 'py':
            threading.Thread(target=run_script, args=(path, owner_id, folder, file_name, call.message)).start()
        else:
            threading.Thread(target=run_js_script, args=(path, owner_id, folder, file_name, call.message)).start()
        time.sleep(1)
        is_running = is_bot_running(owner_id, file_name)
        text = f"⚙️ Controls for {file_name} ({ftype}) of User {owner_id}\nStatus: {'🟢 Running' if is_running else '🟡 Starting...'}"
        bot.edit_message_text(stylish_text(text), call.message.chat.id, call.message.message_id,
                              reply_markup=create_control_buttons(owner_id, file_name, is_running))
    except Exception as e:
        logger.error(f"restart error: {e}")

def delete_bot_callback(call):
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("Permission denied."), show_alert=True)
            return
        script_key = f"{owner_id}_{file_name}"
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]
        folder = get_user_folder(owner_id)
        file_path = os.path.join(folder, file_name)
        log_path = os.path.join(folder, f"{os.path.splitext(file_name)[0]}.log")
        for p in (file_path, log_path):
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        remove_user_file_db(owner_id, file_name)
        bot.answer_callback_query(call.id, stylish_text(f"Deleted {file_name}."))
        bot.edit_message_text(stylish_text(f"🗑️ Deleted {file_name} (User {owner_id})"), call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"delete error: {e}")

def logs_bot_callback(call):
    try:
        _, owner_id_str, file_name = call.data.split('_', 2)
        owner_id = int(owner_id_str)
        if call.from_user.id != owner_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, stylish_text("Permission denied."), show_alert=True)
            return
        folder = get_user_folder(owner_id)
        log_path = os.path.join(folder, f"{os.path.splitext(file_name)[0]}.log")
        if not os.path.exists(log_path):
            bot.answer_callback_query(call.id, stylish_text("No logs yet."), show_alert=True)
            return
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            logs = f.read()
        if len(logs) > 4000:
            logs = logs[-4000:]
            logs = "...\n" + logs
        bot.send_message(call.message.chat.id, stylish_text(f"📜 Logs for {file_name}:\n{logs}"))
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"logs error: {e}")

# --- Cleanup and Main ---
def cleanup():
    logger.warning("Shutting down, killing all scripts...")
    for key, info in list(bot_scripts.items()):
        kill_process_tree(info)
    logger.warning("Cleanup done.")
atexit.register(cleanup)

if __name__ == '__main__':
    logger.info("🤖 Bot starting...")
    keep_alive()
    logger.info("🚀 Polling started.")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)