#!/bin/bash
set -eu
touch /var/log/ai-soc-lab.json
python3 - <<'PY'
from pathlib import Path
import subprocess
password = Path('/run/secrets/lab_password').read_text().strip()
subprocess.run(['chpasswd'], input='lab-user:' + password + '\n', text=True, check=True)
PY
cat > /etc/ssh/sshd_config.d/ai-soc-lab.conf <<'EOF'
Port 2222
PasswordAuthentication yes
PermitRootLogin no
AllowUsers lab-user
UsePAM no
EOF
nft list table inet ai_soc_lab >/dev/null 2>&1 || nft -f - <<'EOF'
table inet ai_soc_lab {
  set blocked_ips { type ipv4_addr; }
  chain input {
    type filter hook input priority -10; policy accept;
    ip saddr @blocked_ips drop
  }
}
EOF
