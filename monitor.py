import os
import asyncio
import logging
from urllib.parse import urlparse
from proxmoxer import ProxmoxAPI
from telegram import Bot
from slack_bolt.app.async_app import AsyncApp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("proxmox-ai-agent.monitor")

# Config parameters
MONITOR_ENABLED = os.getenv("MONITOR_ENABLED", "True") == "True"
MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "900"))
MONITOR_THRESHOLD = float(os.getenv("MONITOR_THRESHOLD", "80"))
HYSTERESIS = 5.0
WORSEN_STEP = 10.0

# Alert Targets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_ALERT_CHANNEL_ID = os.getenv("SLACK_ALERT_CHANNEL_ID")

# Proxmox API Connection
PROXMOX_HOST_RAW = os.getenv("PROXMOX_HOST") or os.getenv("PVE_BASE_URL")
PROXMOX_TOKEN_ID = os.getenv("PROXMOX_TOKEN_ID") or os.getenv("PVE_TOKEN_ID")
PROXMOX_TOKEN_SECRET = os.getenv("PROXMOX_TOKEN_SECRET") or os.getenv("PVE_TOKEN_SECRET")
PROXMOX_USER_RAW = os.getenv("PROXMOX_USER")
PROXMOX_VERIFY_SSL = os.getenv("PROXMOX_VERIFY_SSL", "False") == "True" or os.getenv("PVE_VERIFY_SSL", "False") == "True"

# Parse Host and Port
if PROXMOX_HOST_RAW and PROXMOX_HOST_RAW.startswith("http"):
    parsed = urlparse(PROXMOX_HOST_RAW)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
else:
    host = PROXMOX_HOST_RAW
    port = 8006

# Parse user, token_name
if PROXMOX_TOKEN_ID and "!" in PROXMOX_TOKEN_ID:
    user, token_name = PROXMOX_TOKEN_ID.split("!", 1)
else:
    user = PROXMOX_USER_RAW or "root@pam"
    token_name = PROXMOX_TOKEN_ID

proxmox = ProxmoxAPI(
    host,
    port=port,
    user=user,
    token_name=token_name,
    token_value=PROXMOX_TOKEN_SECRET,
    verify_ssl=PROXMOX_VERIFY_SSL,
)

# Initialize Notifiers
telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
slack_app = AsyncApp(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None

async def send_alert(message: str):
    log.info(f"Dispatching Alert: {message}")
    # Send to Telegram
    if telegram_bot and TELEGRAM_ALLOWED_USER_ID:
        try:
            await telegram_bot.send_message(chat_id=int(TELEGRAM_ALLOWED_USER_ID), text=message)
        except Exception as e:
            log.error(f"Failed to send Telegram alert: {e}")
            
    # Send to Slack
    if slack_app and SLACK_ALERT_CHANNEL_ID:
        try:
            await slack_app.client.chat_postMessage(channel=SLACK_ALERT_CHANNEL_ID, text=message)
        except Exception as e:
            log.error(f"Failed to send Slack alert: {e}")

def evaluate_resources() -> dict[str, tuple[str, float]]:
    """Poll Proxmox resources and evaluate CPU, RAM, Disk percentages."""
    metrics = {}
    try:
        resources = proxmox.cluster.resources.get()
    except Exception as e:
        log.error(f"Failed to fetch Proxmox cluster resources: {e}")
        return metrics

    for res in resources:
        res_type = res.get("type")
        if res_type not in ("node", "qemu", "lxc"):
            continue
            
        status = res.get("status")
        if status != "running":
            continue
            
        name = res.get("name") or res.get("node") or f"ID {res.get('vmid')}"
        res_id = f"{res_type}/{res.get('vmid') or res.get('node')}"
        
        # 1. CPU check
        cpu = res.get("cpu")
        if cpu is not None:
            cpu_pct = float(cpu) * 100
            metrics[f"{res_id}/cpu"] = (f"{res_type} '{name}' CPU", cpu_pct)
            
        # 2. Memory check
        mem = res.get("mem")
        maxmem = res.get("maxmem")
        if mem is not None and maxmem and maxmem > 0:
            mem_pct = (float(mem) / float(maxmem)) * 100
            metrics[f"{res_id}/mem"] = (f"{res_type} '{name}' Memory", mem_pct)
            
        # 3. Disk check
        disk = res.get("disk")
        maxdisk = res.get("maxdisk")
        if disk is not None and maxdisk and maxdisk > 0:
            disk_pct = (float(disk) / float(maxdisk)) * 100
            metrics[f"{res_id}/disk"] = (f"{res_type} '{name}' Disk", disk_pct)
            
    return metrics

async def run_monitor():
    if not MONITOR_ENABLED:
        log.info("Monitor disabled in config.")
        return
        
    if not (telegram_bot or slack_app):
        log.error("No Telegram or Slack credentials found. Monitor aborting.")
        return

    clear_at = MONITOR_THRESHOLD - HYSTERESIS
    active_alerts = {} # key -> (value, label)
    
    log.info(
        f"Monitor running: interval={MONITOR_INTERVAL_SECONDS}s, "
        f"threshold={MONITOR_THRESHOLD}%, clear_at={clear_at}%"
    )
    
    while True:
        try:
            # Evaluate current values
            metrics = evaluate_resources()
            
            for key, (label, value) in metrics.items():
                prev = active_alerts.get(key)
                if value >= MONITOR_THRESHOLD:
                    if prev is None:
                        await send_alert(f"⚠️ {label} at {value:.0f}% (≥ {MONITOR_THRESHOLD:.0f}%)")
                        active_alerts[key] = (value, label)
                    elif value >= prev[0] + WORSEN_STEP:
                        await send_alert(f"🔺 {label} rising: {value:.0f}% (was {prev[0]:.0f}%)")
                        active_alerts[key] = (value, label)
                elif prev is not None and value < clear_at:
                    await send_alert(f"✅ Resolved: {label} back to {value:.0f}% (< {clear_at:.0f}%)")
                    active_alerts.pop(key, None)
                    
        except Exception as e:
            log.exception(f"Exception in monitoring cycle: {e}")
            
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        log.info("Monitor stopped.")
