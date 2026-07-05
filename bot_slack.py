import os
import asyncio
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from ai_agent import chat_agent, load_system_prompt

BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
ALLOWED_USER_ID = os.getenv("SLACK_ALLOWED_USER_ID") or os.getenv("TELEGRAM_ALLOWED_USER_ID")

app = AsyncApp(token=BOT_TOKEN)
sessions = {}

@app.event("message")
async def handle_message_events(body, say):
    event = body.get("event", {})
    user_id = event.get("user")
    channel_id = event.get("channel")
    text = event.get("text")
    
    # Ignore messages from bots
    if event.get("bot_id") or not text:
        return
        
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        return
        
    if channel_id not in sessions:
        sessions[channel_id] = [{"role": "system", "content": load_system_prompt()}]
        
    # Run blocking completions loop in thread
    reply = await asyncio.to_thread(chat_agent, text, sessions[channel_id])
    await say(reply)

async def main():
    if not BOT_TOKEN or not APP_TOKEN:
        print("Error: SLACK_BOT_TOKEN or SLACK_APP_TOKEN is not set.")
        return
    handler = AsyncSocketModeHandler(app, APP_TOKEN)
    print("Starting custom Slack bot (Socket Mode)...")
    await handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())
