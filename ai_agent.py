"""
ai_agent.py: Custom AI agent for managing Proxmox via natural-language commands using OpenAI and proxmoxer.
Modified to support modern OpenAI v1.x client and local Ollama LLM configurations.
"""

import os
import json
from urllib.parse import urlparse
from typing import Any
from proxmoxer import ProxmoxAPI
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

# Proxmox Host configuration mapping (supporting both schemes)
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

# Parse user, token_name from token_id
if PROXMOX_TOKEN_ID and "!" in PROXMOX_TOKEN_ID:
    user, token_name = PROXMOX_TOKEN_ID.split("!", 1)
else:
    user = PROXMOX_USER_RAW or "root@pam"
    token_name = PROXMOX_TOKEN_ID

print(f"Connecting to Proxmox at {host}:{port} as user '{user}' (token_name: '{token_name}')...")

# Initialize Proxmox connection using token
proxmox = ProxmoxAPI(
    host,
    port=port,
    user=user,
    token_name=token_name,
    token_value=PROXMOX_TOKEN_SECRET,
    verify_ssl=PROXMOX_VERIFY_SSL,
)

# Set up OpenAI client
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)

# Example function to create VM
def create_vm(node, vmid, name, memory=2048, cores=2, disk='32G', iso_storage='local', iso_file=''):
    """Create a new VM on given node with specified resources."""
    return proxmox.nodes(node).qemu.create(
        vmid=vmid,
        name=name,
        memory=memory,
        cores=cores,
        scsihw='virtio-scsi-pci',
        sata0=f"{iso_storage}:{disk}",
        ide2=f"{iso_storage}:iso/{iso_file},media=cdrom",
        net0='virtio,bridge=vmbr0'
    )

# Helper to determine if a guest is a QEMU VM or an LXC container
def get_guest_type(vmid):
    try:
        resources = proxmox.cluster.resources.get(type='vm')
        for r in resources:
            if r.get('vmid') == int(vmid):
                return r.get('type') # 'qemu' or 'lxc'
    except Exception:
        pass
    return 'qemu' # default fallback

# Example function to start VM/LXC
def start_vm(node, vmid):
    gtype = get_guest_type(vmid)
    if gtype == 'lxc':
        return proxmox.nodes(node).lxc(vmid).status.start.post()
    else:
        return proxmox.nodes(node).qemu(vmid).status.start.post()

# Example function to stop VM/LXC
def stop_vm(node, vmid):
    gtype = get_guest_type(vmid)
    if gtype == 'lxc':
        return proxmox.nodes(node).lxc(vmid).status.stop.post()
    else:
        return proxmox.nodes(node).qemu(vmid).status.stop.post()

# Example function to reboot VM/LXC
def reboot_vm(node, vmid):
    gtype = get_guest_type(vmid)
    if gtype == 'lxc':
        return proxmox.nodes(node).lxc(vmid).status.reboot.post()
    else:
        return proxmox.nodes(node).qemu(vmid).status.reboot.post()

# Example function to hard reset VM (QEMU only)
def reset_vm(node, vmid):
    gtype = get_guest_type(vmid)
    if gtype == 'qemu':
        return proxmox.nodes(node).qemu(vmid).status.reset.post()
    else:
        return {"error": "Reset is only supported for QEMU Virtual Machines."}




# Example function to list VMs and LXCs
def list_vms(node):
    qemu_list = proxmox.nodes(node).qemu.get()
    lxc_list = proxmox.nodes(node).lxc.get()
    # Format and combine lists
    for item in qemu_list:
        item['type'] = 'qemu'
    for item in lxc_list:
        item['type'] = 'lxc'
    return qemu_list + lxc_list

# Define available functions for AI to call
AVAILABLE_FUNCTIONS = {
    "create_vm": create_vm,
    "start_vm": start_vm,
    "stop_vm": stop_vm,
    "reboot_vm": reboot_vm,
    "reset_vm": reset_vm,
    "list_vms": list_vms,
}

# Chat function definitions for OpenAI function calling (legacy format)
FUNCTION_DEFS = [
    {
        "name": "create_vm",
        "description": "Create a new virtual machine on a Proxmox node.",
        "parameters": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Proxmox node name"},
                "vmid": {"type": "integer", "description": "Unique ID for the VM"},
                "name": {"type": "string", "description": "Name of the new VM"},
                "memory": {"type": "integer", "description": "RAM in megabytes"},
                "cores": {"type": "integer", "description": "Number of CPU cores"},
                "disk": {"type": "string", "description": "Disk size (e.g. '32G')"},
                "iso_storage": {"type": "string", "description": "Storage location for ISO"},
                "iso_file": {"type": "string", "description": "ISO filename"},
            },
            "required": ["node", "vmid", "name"],
        },
    },
    {
        "name": "start_vm",
        "description": "Start a virtual machine or LXC container.",
        "parameters": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Proxmox node name (e.g. 'proxmox04')"},
                "vmid": {"type": "integer", "description": "ID of the VM or container"},
            },
            "required": ["node", "vmid"],
        },
    },
    {
        "name": "stop_vm",
        "description": "Stop a virtual machine or LXC container.",
        "parameters": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Proxmox node name (e.g. 'proxmox04')"},
                "vmid": {"type": "integer", "description": "ID of the VM or container"},
            },
            "required": ["node", "vmid"],
        },
    },
    {
        "name": "reboot_vm",
        "description": "Reboot a virtual machine or LXC container.",
        "parameters": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Proxmox node name (e.g. 'proxmox04')"},
                "vmid": {"type": "integer", "description": "ID of the VM or container"},
            },
            "required": ["node", "vmid"],
        },
    },
    {
        "name": "reset_vm",
        "description": "Perform a hard reset (pull plug and restart) on a QEMU virtual machine.",
        "parameters": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Proxmox node name (e.g. 'proxmox04')"},
                "vmid": {"type": "integer", "description": "ID of the virtual machine"},
            },
            "required": ["node", "vmid"],
        },
    },
    {
        "name": "list_vms",
        "description": "List all VMs and LXC containers on a node.",
        "parameters": {
            "type": "object",
            "properties": {"node": {"type": "string", "description": "Proxmox node name (e.g. 'proxmox04')"}},
            "required": ["node"],
        },
    },
]

# Convert legacy functions format to modern tools format
TOOLS = [{"type": "function", "function": f} for f in FUNCTION_DEFS]

def load_system_prompt() -> str:
    prompt = (
        "You are a helpful Proxmox assistant. You can create, start, stop, and list VMs or LXC containers "
        "using Proxmoxer API tools. Always check the system prompt context for guest IDs and node mapping.\n\n"
    )
    # Load memory.md if it exists
    paths_to_try = ["/app/memory.md", "memory.md", "../memory.md"]
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    prompt += "# memory.md\n" + f.read()
                break
            except Exception:
                pass
    return prompt

def chat_agent(user_input: str, messages: list[dict[str, Any]]) -> str:
    messages.append({"role": "user", "content": user_input})
    
    # Call OpenAI API with tools
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    
    reply = response.choices[0].message
    if reply.tool_calls:
        messages.append(reply)
        for tc in reply.tool_calls:
            func_name = tc.function.name
            arguments = json.loads(tc.function.arguments or "{}")
            print(f"\n[TOOL CALL] Executing {func_name} with arguments: {arguments}")
            try:
                result = AVAILABLE_FUNCTIONS[func_name](**arguments)
            except Exception as e:
                result = f"Error executing function: {e}"
            
            # Add function response to chat history
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": func_name,
                "content": str(result),
            })
            print(f"[TOOL RESULT] {result}")
            
        # Follow up turn after tool calls
        follow_up = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )
        assistant_reply = follow_up.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply
    else:
        assistant_reply = reply.content
        messages.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

def run_agent(system_prompt: str | None = None):
    """Run an interactive loop reading user input and performing tasks via Proxmox."""
    system_prompt = system_prompt or load_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
            
        reply = chat_agent(user_input, messages)
        print(f"Assistant: {reply}\n")

if __name__ == "__main__":
    run_agent()

