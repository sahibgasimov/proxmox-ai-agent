# Agent Architecture and Capabilities

## Overview

This agent is designed to perform common Proxmox VE tasks via natural-language commands. It leverages the Proxmox REST API, which exposes endpoints for provisioning and managing VMs (e.g., POST `/nodes/{node}/qemu` to create a virtual machine ([How to create a VM with proxmox API ?](https://forum.proxmox.com/threads/how-to-create-a-vm-with-proxmox-api.144071/#:~:text=The%20API%20is%20well%20described,viewer))). The agent translates user instructions into API calls using a Python wrapper.

## Components

- **Language model interface** – Parses user input and determines the appropriate action, such as creating a VM or configuring networking. This can be implemented with OpenAI, Gemini or another LLM, optionally orchestrated with n8n, which provides templates for conversational Proxmox management ([Proxmox AI agent with n8n and generative AI integration](https://n8n.io/workflows/2749-proxmox-ai-agent-with-n8n-and-generative-ai-integration/#:~:text=Proxmox%20AI%20agent%20with%20n8n,n8n%20and%20Generative%20AI%20Integration)).
- **API client** – Uses the `proxmoxer` Python library to authenticate and call Proxmox endpoints ([GitHub - proxmoxer/proxmoxer: python wrapper for ...](https://github.com/proxmoxer/proxmoxer#:~:text=GitHub%20,PBS)). `proxmoxer` abstracts HTTP requests and handles authentication tokens.
- **Action functions** – Encapsulate specific tasks (create VM, add SSH key, clone template, etc.) and call the appropriate API endpoints. For example, `create_vm()` would call `POST /nodes/{node}/qemu` with the desired parameters.
- **State and validation** – Maintains context, checks user input, and asks for confirmation before destructive actions.

## Setup

1. **API token**: In the Proxmox UI, navigate to *Datacenter → Permissions → API Tokens* and create a token with the least privileges necessary.
2. **Environment**: Install Python 3 and the `proxmoxer` library. Configure environment variables or a config file with your Proxmox host, token ID/secret and default node.
3. **LLM**: Configure your language model provider and credentials. In n8n, you can create a workflow that routes messages through a generative model and then triggers HTTP requests to Proxmox ([Proxmox AI agent with n8n and generative AI integration](https://n8n.io/workflows/2749-proxmox-ai-agent-with-n8n-and-generative-ai-integration/#:~:text=Proxmox%20AI%20agent%20with%20n8n,n8n%20and%20Generative%20AI%20Integration)).

## Capabilities

The agent currently supports:

- **Create VM** – Provision a VM by supplying CPU cores, memory, disk size and optional ISO/template. This uses the `nodes/{node}/qemu` endpoint ([How to create a VM with proxmox API ?](https://forum.proxmox.com/threads/how-to-create-a-vm-with-proxmox-api.144071/#:~:text=The%20API%20is%20well%20described,viewer)).
- **SSH setup** – Inject an SSH public key into a VM via cloud‑init or by updating authorized keys.
- **Configuration** – Adjust VM resources, network interfaces, or disk allocations through corresponding API calls.
- **Status queries** – Return the status of nodes, VMs and tasks.

These functions can be expanded as needed by adding new action functions.

## Security Considerations

- Limit the scope of the API token to only necessary privileges.
- Validate all user commands to prevent unintended resource changes.
- Store credentials securely (e.g., use environment variables or secret managers).
