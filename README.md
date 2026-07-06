# proxmox-ai-agent  
AI-powered assistant for managing Proxmox Virtual Environment using natural-language commands.  

```mermaid
graph TD
    User["User (Slack / Telegram / CLI)"]
    Telegram["Telegram Cloud API"]
    Slack["Slack Cloud API (Socket Mode)"]
    
    subgraph Standalone Containerized Stack
        TelegramBot["Telegram Bot Service (bot_telegram.py)"]
        SlackBot["Slack Bot Service (bot_slack.py)"]
        CLI["Interactive CLI Service (ai_agent.py)"]
        CoreAgent["Agent Completions Core (ai_agent.py)"]
    end
    
    LLM["LLM Backend (OpenAI / Local Ollama)"]
    ProxmoxAPI["Proxmox VE REST API"]
    ProxmoxCluster["Proxmox VE Cluster Nodes"]

    User <-->|Chat / API| Telegram
    User <-->|Chat / Socket Mode| Slack
    
    Telegram <--> TelegramBot
    Slack <--> SlackBot
    User <-->|Interactive terminal| CLI
    
    TelegramBot --> CoreAgent
    SlackBot --> CoreAgent
    CLI --> CoreAgent
    
    CoreAgent <-->|Chat Completions & Tool Spec| LLM
    CoreAgent <-->|Proxmoxer Library calls| ProxmoxAPI
    ProxmoxAPI <-->|Execute VM / LXC operations| ProxmoxCluster
```

## Overview  
This repository contains an AI agent that interacts with the Proxmox VE REST API to perform tasks like creating VMs, Monitoring VM's and host's, obtaining SSH access and applying configuration changes. The agent uses a language model to parse user requests and maps them to API calls via the `proxmoxer` Python library. Optionally, workflows can be orchestrated with n8n for conversational interactions.  

## Files  
- `agents.md` – describes the agent architecture, capabilities and setup.  
- `diagram.md` – contains a Mermaid diagram illustrating the system architecture.  

## Getting Started  
1. Configure Proxmox credentials, OpenAI/Ollama LLM keys, and Slack/Telegram tokens in `.env` (see env.example file).
2. **Build and Run Services (Slack, Telegram, & Monitor)**:
   ```bash
   docker compose build
   docker compose up -d
   ```
   *Note: If you do not want to run a particular application (e.g. you want the Telegram bot and Monitor but not the Slack bot), simply comment out (grey out using `#`) that service definition in `docker-compose.yml` before building and starting the containers.*

3. **Interactive CLI Mode**:
   ```bash
   docker compose run --rm agent-cli
   ```



## Bot Setup Summary

### Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) -> `/newbot` -> get `TELEGRAM_BOT_TOKEN`.
2. Message [@userinfobot](https://t.me/userinfobot) -> get your user ID -> set `TELEGRAM_ALLOWED_USER_ID`.

### Slack Bot (Socket Mode)
1. Create a Bot App on [api.slack.com/apps](https://api.slack.com/apps).
2. Enable **Socket Mode** -> get App-Level token (`xapp-...`) -> set `SLACK_APP_TOKEN`.
3. Enable **Event Subscriptions** -> subscribe to `message.channels`, `message.groups`, and `app_mention`.
4. In **OAuth & Permissions**, add bot token scopes (`chat:write`, `commands`, `im:history`, `im:read`, `im:write`, `app_mentions:read`) -> Install App -> get Bot User token (`xoxb-...`) -> set `SLACK_BOT_TOKEN`.
5. Profile -> Copy Member ID -> set `SLACK_ALLOWED_USER_ID`.

## Chat Commands
You can interact with the agent using natural language. To reboot a guest:
* **Slack DM or Channel**: Send a message directly to the bot:
  ```text
  reboot joplin-server
  stop jenkins
  reboot VMID 107
  restart fileserver
  ```
  *(If in a public channel, prepend your message with `@BotName`)*


## LLM Configuration & Capabilities

### Supported Backends
Configure one of the following blocks in `.env`:
* **OpenAI (Cloud)**: Set `OPENAI_API_KEY` and `OPENAI_MODEL` (e.g., `gpt-4o`).
* **Ollama (Local)**: Set `OPENAI_API_KEY=ollama`, `OPENAI_BASE_URL` (e.g., `http://<ip>:11434/v1`), and `OPENAI_MODEL` (e.g., `qwen2.5:14b`).

### Agent Capabilities
* **Automatic Name Resolution**: Translates guest names and aliases (including typos) to their actual VMID and node using the embedded `memory.md` context.
* **Unified Power Operations**: Start, stop, and reboot VMs and LXC containers.
* **LXC/QEMU Auto-Detection**: Dynamically checks guest types via Proxmox cluster resources to execute the correct start/stop/reboot commands and prevent API errors.
* **Standalone Resource Monitoring**: Automatically evaluates CPU, memory, and disk usage for all cluster nodes, VMs, and containers, sending alerts directly to Slack and Telegram when thresholds are crossed.


## Architecture  
A high-level architecture diagram is provided in `diagram.md` using Mermaid syntax. The agent receives natural-language commands, interprets them with a language model, and calls the Proxmox API to perform tasks like VM creation, SSH access and configuration.
