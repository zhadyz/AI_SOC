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
Port 12222
ListenAddress 127.0.0.1
PasswordAuthentication yes
PermitRootLogin no
AllowUsers lab-user
UsePAM no
EOF
mkdir -p /run/ai-soc
if [ ! -f /run/ai-soc/blocked-ips.json ]; then
  echo '[]' > /run/ai-soc/blocked-ips.json
fi
chmod 600 /run/ai-soc/blocked-ips.json
