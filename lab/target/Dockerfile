FROM wazuh/wazuh-agent:4.14.7
RUN dnf install -y nftables iptables iproute openssh-server shadow-utils python3 procps-ng \
    && dnf clean all && useradd -m lab-user && mkdir -p /run/sshd /srv/lab \
    && ssh-keygen -A && echo 'AI-SOC disposable response target' > /srv/lab/index.html
COPY lab/target/init.sh /etc/cont-init.d/99-lab
COPY lab/target/http-run /etc/services.d/lab-http/run
COPY lab/target/ssh-run /etc/services.d/lab-ssh/run
RUN chmod +x /etc/cont-init.d/99-lab /etc/services.d/lab-http/run /etc/services.d/lab-ssh/run
