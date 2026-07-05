#!/usr/bin/env bash
# Launch the interactive custom Proxmox agent CLI in a one-off container.
set -euo pipefail
cd "$(dirname "$0")"
exec docker compose up -d  agent-cli "$@"
