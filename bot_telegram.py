import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ai_agent import chat_agent, load_system_prompt

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")

if ALLOWED_USER_ID:
    ALLOWED_USER_ID = int(ALLOWED_USER_ID)

# Chat sessions
sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return
    sessions[chat_id] = [{"role": "system", "content": load_system_prompt()}]
    await update.message.reply_text("Custom Proxmox Telegram Agent started! Ask me anything.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return
        
    if chat_id not in sessions:
        sessions[chat_id] = [{"role": "system", "content": load_system_prompt()}]
        
    user_text = update.message.text
    # Run blocking chat completions loop in separate thread
    reply = await asyncio.to_thread(chat_agent, user_text, sessions[chat_id])
    await update.message.reply_text(reply)

def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set.")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Starting custom Telegram bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
