import os
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

app = Flask(__name__)

# 🔑 اطلاعات اصلی پلتفرم (مقادیر خودت رو جایگزین کن)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # توکن دریافت شده از BotFather
MINI_APP_URL = "https://YOUR-NETLIFY-URL.netlify.app"  # آدرس مینی‌اپ در Netlify

# ---------------------------------------------------------
# دیتابیس ساده در حافظه (در مراحل بعد به SQLite/Redis ارتقا می‌دهیم)
# ---------------------------------------------------------
users_db = {} 
# ساختار: { user_id: { "phone": "...", "is_vip": False, "api_key": "" } }

signals_history = [
    # نمونه تاریخچه معاملات برای نمایش در مینی‌اپ
    {"id": 1, "symbol": "BTCUSDT", "type": "BUY", "entry": 65000, "exit": 67200, "profit_percent": 3.38, "status": "TP_HIT"},
    {"id": 2, "symbol": "XAUUSD", "type": "SELL", "entry": 2410, "exit": 2395, "profit_percent": 0.62, "status": "TP_HIT"}
]

# ---------------------------------------------------------
# بخش ۱: ربات تلگرام و احراز هویت با شماره موبایل
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in users_db:
        # اگر کاربر قبلاً شماره تلفن داده باشد
        user_info = users_db[user_id]
        status_text = "⭐ حساب VIP (ترید خودکار فعال)" if user_info.get("is_vip") else "👤 حساب رایگان (ترید دستی)"
        
        web_app_button = KeyboardButton(
            text="🚀 ورود به مینی‌اپ معامله‌گر", 
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
        reply_markup = ReplyKeyboardMarkup([[web_app_button]], resize_keyboard=True)
        
        await update.message.reply_text(
            f"خوش آمدید!\nوضعیت حساب شما: {status_text}\nشماره تایید شده: {user_info['phone']}",
            reply_markup=reply_markup
        )
    else:
        # اگر شماره تلفن هنوز ثبت نشده باشد (قفل امنیتی)
        contact_button = KeyboardButton(text="📱 ارسال شماره موبایل جهت احراز هویت", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True)
        
        await update.message.reply_text(
            "به ربات معامله‌گر خودکار خوش آمدید! 👋\n\n"
            "برای امنیت حساب و دسترسی به مینی‌اپ، لطفاً روی دکمه زیر کلیک کنید تا شماره موبایل شما تایید شود:",
            reply_markup=reply_markup
        )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = update.effective_user.id
    
    # تایید اینکه شماره حتماً متعلق به خودِ کاربر تلگرام است
    if contact.user_id == user_id:
        users_db[user_id] = {
            "phone": contact.phone_number,
            "is_vip": False,  # به‌صورت پیش‌فرض رایگان است
            "api_key": ""
        }
        
        web_app_button = KeyboardButton(
            text="🚀 ورود به مینی‌اپ معامله‌گر", 
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
        reply_markup = ReplyKeyboardMarkup([[web_app_button]], resize_keyboard=True)
        
        await update.message.reply_text(
            "✅ شماره موبایل شما با موفقیت تایید و حساب کاربری ساخته شد!\n\n"
            "اکنون می‌توانید وارد مینی‌اپ شوید.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ خطایی رخ داد! لطفاً فقط از دکمه زیر برای ارسال شماره خودتان استفاده کنید.")

# ---------------------------------------------------------
# بخش ۲: APIها برای مینی‌اپ و دریافت سیگنال تریدینگ‌ویو
# ---------------------------------------------------------
@app.route('/')
def home():
    return "Trading Bot Core Server is Online!"

# API ارسال تاریخچه سیگنال‌ها به مینی‌اپ (برای جلب اعتماد و نمایش شفاف)
@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify({"success": True, "history": signals_history})

# Webhook دریافت سیگنال از تریدینگ‌ویو (اجرای سریع)
@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400
        
    # این بخش سیگنال رو پردازش می‌کنه و همزمان برای کاربران VIP می‌فرسته
    # data format example: {"symbol": "BTCUSDT", "action": "BUY", "price": 66000}
    symbol = data.get("symbol")
    action = data.get("action")
    
    # اضافه کردن به تاریخچه عمومی
    signals_history.insert(0, {
        "id": len(signals_history) + 1,
        "symbol": symbol,
        "type": action,
        "entry": data.get("price"),
        "exit": "-",
        "profit_percent": 0.0,
        "status": "ACTIVE"
    })
    
    return jsonify({"status": "success", "message": "Signal received and routing to VIP accounts"}), 200

if __name__ == '__main__':
    # راه‌اندازی ربات تلگرام
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    
    # اجرا
    application.run_polling()
