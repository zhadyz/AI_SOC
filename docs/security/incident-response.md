# Incident Response Playbooks for AI-SOC

## Executive Summary

This document provides comprehensive incident response playbooks for Security Operations Center (SOC) teams using AI-SOC. Based on NIST Cybersecurity Framework, MITRE ATT&CK, and 2025 SOC best practices, these playbooks cover detection, analysis, containment, eradication, recovery, and post-incident activities.

---

## Table of Contents

1. [Incident Response Framework](#1-incident-response-framework)
2. [SOC Playbooks](#2-soc-playbooks)
3. [Technical Runbooks](#3-technical-runbooks)
4. [Escalation Procedures](#4-escalation-procedures)
5. [Training Materials](#5-training-materials)

---

## 1. Incident Response Framework

### 1.1 NIST Incident Response Lifecycle

```
┌─────────────┐
│ Preparation │ ← Establish IR capability
└──────┬──────┘
       │
┌──────▼────────────────┐
│ Detection & Analysis  │ ← Identify and investigate incidents
└──────┬────────────────┘
       │
┌──────▼─────────────────────────────────┐
│ Containment, Eradication & Recovery    │ ← Limit damage and restore
└──────┬─────────────────────────────────┘
       │
┌──────▼──────────────┐
│ Post-Incident       │ ← Learn and improve
└─────────────────────┘
```

### 1.2 Incident Severity Classification

| Severity | Definition | Examples | Response Time |
|----------|-----------|----------|---------------|
| **P0 - Critical** | Active breach, data exfiltration, ransomware | Confirmed data breach, active ransomware encryption, C2 communication | **Immediate** (<15 min) |
| **P1 - High** | Successful exploit, elevated privileges | Successful phishing, malware infection, privilege escalation | **<1 hour** |
| **P2 - Medium** | Attempted exploit, suspicious activity | Failed login attempts, port scanning, suspicious traffic | **<4 hours** |
| **P3 - Low** | Policy violations, informational alerts | Password policy violation, outdated software | **<24 hours** |

### 1.3 Stakeholder Roles

```yaml
stakeholders:
  incident_commander:
    name: "Senior Security Analyst"
    responsibilities:
      - Overall incident coordination
      - Decision-making authority
      - Stakeholder communication
    contact: "oncall-commander@company.com"

  technical_lead:
    name: "SOC Team Lead"
    responsibilities:
      - Technical investigation
      - Evidence collection
      - Remediation execution
    contact: "soc-lead@company.com"

  communications_lead:
    name: "PR/Communications"
    responsibilities:
      - Internal communications
      - Customer notifications
      - Media relations
    contact: "pr@company.com"

  legal_counsel:
    name: "Legal Team"
    responsibilities:
      - Regulatory compliance
      - Legal implications
      - Law enforcement coordination
    contact: "legal@company.com"

  executive_sponsor:
    name: "CISO"
    responsibilities:
      - Executive decisions
      - Resource allocation
      - Board communications
    contact: "ciso@company.com"
```

---

## 2. SOC Playbooks

### 2.1 Malware Infection Playbook

**MITRE ATT&CK Techniques**: T1204 (User Execution), T1059 (Command and Scripting Interpreter)

```yaml
playbook: malware_infection
severity: P1
ttps: [T1204, T1059, T1486, T1547]

detection:
  indicators:
    - Antivirus alert triggered
    - Suspicious process execution
    - Unusual network connections
    - File modifications in system directories
    - Registry key modifications

  ai_soc_queries:
    - "Analyze this antivirus alert for malware behavior"
    - "What are the indicators of compromise for this process?"
    - "Generate threat intelligence report for hash: [SHA256]"

response_phases:
  1_preparation:
    actions:
      - Ensure endpoint detection tools are operational
      - Verify isolation procedures documented
      - Confirm backup systems functional
      - Review malware analysis sandbox ready

  2_detection_analysis:
    immediate_actions:
      - Collect initial alert details (hostname, username, timestamp, malware family)
      - Query AI-SOC for threat analysis
      - Check VirusTotal for hash reputation
      - Review process tree and parent process
      - Identify network connections and C2 servers
      - Collect memory dump if available

    ai_soc_prompts:
      - "Analyze malware alert: [paste alert details]"
      - "What lateral movement techniques might this malware use?"
      - "Suggest investigation steps for [malware family]"

    investigation_steps:
      - Check for additional compromised hosts
      - Review authentication logs for compromised accounts
      - Analyze network traffic for data exfiltration
      - Identify patient zero (initial infection vector)
      - Determine scope of infection

  3_containment:
    immediate_containment:
      - Isolate infected host from network
      - Disable compromised user accounts
      - Block C2 domains/IPs at firewall
      - Quarantine malicious files
      - Snapshot system for forensics

    short_term_containment:
      - Deploy network segmentation
      - Apply temporary firewall rules
      - Monitor for lateral movement
      - Implement enhanced logging

    long_term_containment:
      - Rebuild compromised systems
      - Patch vulnerabilities exploited
      - Update detection signatures
      - Strengthen access controls

  4_eradication:
    actions:
      - Remove malware from all infected systems
      - Delete malicious registry keys
      - Remove persistence mechanisms
      - Clean temporary files and caches
      - Verify complete removal with multiple AV tools
      - Patch vulnerabilities used for initial access

    verification:
      - Full system scan with updated signatures
      - Memory analysis for fileless malware
      - Network monitoring for C2 traffic
      - Behavioral analysis for 72 hours

  5_recovery:
    actions:
      - Restore systems from clean backups
      - Reset credentials for affected accounts
      - Re-enable network access gradually
      - Monitor for 7 days post-recovery
      - User awareness training

    validation:
      - System integrity checks
      - Application functionality tests
      - Network connectivity verification
      - User acceptance testing

  6_post_incident:
    actions:
      - Document timeline of events
      - Identify root cause
      - Update detection rules
      - Improve security controls
      - Conduct lessons learned session
      - Update incident response procedures

    metrics:
      - Time to detect (MTTD)
      - Time to contain
      - Time to eradicate
      - Time to recover (MTTR)
      - Estimated impact (systems affected, data compromised)

tools:
  - EDR (CrowdStrike, SentinelOne)
  - Network monitoring (Wireshark, Zeek)
  - Sandbox (Any.Run, Joe Sandbox)
  - Threat intel (VirusTotal, MISP)
  - AI-SOC for analysis and recommendations

communication:
  internal:
    - Notify IT operations
    - Update incident management system
    - Brief executive team if P0/P1
  external:
    - Customer notification if data breach
    - Regulatory reporting if required
    - Law enforcement if criminal activity
```

---

### 2.2 Phishing Attack Playbook

**MITRE ATT&CK Techniques**: T1566 (Phishing), T1204 (User Execution)

```yaml
playbook: phishing_attack
severity: P1-P2
ttps: [T1566.001, T1566.002, T1204]

detection:
  indicators:
    - User reports suspicious email
    - Email security gateway alert
    - Credential submission to fake login page
    - Attachment execution detected

response_phases:
  1_immediate_actions:
    within_15_minutes:
      - Collect phishing email (headers, body, attachments)
      - Identify sender email and domain
      - Search for similar emails in organization
      - Query AI-SOC for threat analysis

    ai_soc_prompts:
      - "Analyze this phishing email: [paste email headers and body]"
      - "Is domain [suspicious-domain.com] malicious?"
      - "What are common phishing indicators I should look for?"

  2_analysis:
    email_analysis:
      - Review email headers (SPF, DKIM, DMARC)
      - Analyze sender reputation
      - Check links for known phishing sites
      - Detonate attachments in sandbox
      - Search for similar campaigns

    scope_determination:
      - Count recipients in organization
      - Identify who opened email
      - Identify who clicked links
      - Identify who submitted credentials
      - Check for follow-on malware infections

  3_containment:
    immediate:
      - Quarantine email from all mailboxes
      - Block sender domain/email
      - Block malicious URLs
      - Disable compromised accounts
      - Reset passwords for affected users

    email_remediation:
      # PowerShell script for O365
      - Purge: "Search-Mailbox -Identity * -SearchQuery 'subject:\"[PHISHING SUBJECT]\"' -DeleteContent"
      - Block: "New-TransportRule -Name 'Block Phishing Domain' -SenderDomainIs 'evil.com' -DeleteMessage $true"

  4_recovery:
    actions:
      - Re-enable accounts after password reset
      - Monitor for suspicious activity
      - Conduct phishing awareness training
      - Test users with simulated phishing

  5_prevention:
    actions:
      - Update email security rules
      - Enable Advanced Threat Protection
      - Implement DMARC policy
      - Deploy anti-phishing banners
      - Schedule security awareness training

communication_template: |
  Subject: Security Alert - Phishing Email

  A phishing email has been identified in our environment:

  Subject: [PHISHING SUBJECT]
  From: [SENDER]
  Received: [TIMESTAMP]

  ACTIONS REQUIRED:
  1. DO NOT click links or open attachments
  2. DELETE the email immediately
  3. Report to IT Security if you clicked links
  4. Change password if you submitted credentials

  IT Security is actively removing this email.

  Questions? Contact: security@company.com
```

---

### 2.3 Ransomware Playbook

**MITRE ATT&CK Techniques**: T1486 (Data Encrypted for Impact), T1490 (Inhibit System Recovery)

```yaml
playbook: ransomware
severity: P0
ttps: [T1486, T1490, T1489, T1490]

detection:
  indicators:
    - Multiple file encryption alerts
    - Ransom note files detected
    - High volume of file modifications
    - Shadow copies deleted
    - Backup systems disabled
    - Suspicious PowerShell/WMI activity

  critical_actions:
    within_5_minutes:
      - Activate incident commander
      - Isolate affected systems IMMEDIATELY
      - Disable network shares
      - Snapshot running systems
      - Alert executive team

response_phases:
  1_immediate_containment:
    priority_1:
      - Disconnect infected systems from network (physical disconnection preferred)
      - Disable Wi-Fi and Bluetooth
      - Power off systems showing encryption activity
      - Block lateral movement at firewall

    priority_2:
      - Identify ransomware variant (ransom note, file extensions)
      - Determine initial infection vector
      - Identify patient zero
      - Map affected systems

    do_not:
      - DO NOT pay ransom (yet)
      - DO NOT delete ransom notes (evidence)
      - DO NOT reboot encrypted systems
      - DO NOT restore from backups yet (may reinfect)

  2_analysis:
    ransomware_identification:
      - Collect ransom note
      - Identify file extension (.locked, .encrypted, etc.)
      - Check ID Ransomware (https://id-ransomware.malwarehunterteam.com/)
      - Query AI-SOC for variant analysis
      - Check No More Ransom for decryptors

    ai_soc_prompts:
      - "Identify ransomware variant from this ransom note: [paste note]"
      - "Is there a decryptor available for [RANSOMWARE_NAME]?"
      - "What are the typical attack vectors for [RANSOMWARE_NAME]?"

    scope_assessment:
      - Count encrypted systems
      - Identify critical systems affected
      - Assess backup integrity
      - Estimate data loss
      - Determine business impact

  3_eradication:
    before_recovery:
      - Remove ransomware from all systems
      - Patch vulnerabilities exploited
      - Remove attacker persistence mechanisms
      - Change all credentials
      - Verify complete remediation

    verification:
      - Full network scan for ransomware
      - Behavioral monitoring for 7 days
      - Verify backups are clean

  4_recovery:
    decision_tree:
      pay_ransom:
        consider_if:
          - No clean backups available
          - Critical systems affected
          - Decryptor not available
          - Business continuity at risk
        cautions:
          - No guarantee of decryption
          - Funds criminals
          - May violate regulations
          - Report to law enforcement first

      restore_from_backups:
        preferred_if:
          - Clean backups available
          - Backups verified intact
          - RTO acceptable
        steps:
          - Rebuild systems from clean images
          - Restore data from last clean backup
          - Apply all security patches
          - Change all passwords
          - Test functionality
          - Gradual re-connection to network

    recovery_priority:
      tier_1: [Active Directory, Email, File Servers]
      tier_2: [Business Applications, Databases]
      tier_3: [Workstations, Non-Critical Systems]

  5_post_incident:
    forensics:
      - Preserve evidence (disk images, memory dumps, logs)
      - Document timeline
      - Identify root cause
      - Determine initial access method

    improvements:
      - Implement immutable backups
      - Deploy EDR on all endpoints
      - Enable Controlled Folder Access
      - Disable SMBv1
      - Restrict PowerShell execution
      - Implement application whitelisting
      - Network segmentation
      - Privileged Access Management (PAM)

law_enforcement:
  reporting:
    - FBI IC3 (ic3.gov)
    - Local FBI field office
    - Secret Service (for financial crimes)

  preserve_evidence:
    - Disk forensic images
    - Memory dumps
    - Network packet captures
    - Ransom note (screenshot + file)
    - Bitcoin wallet addresses
    - Communication with attackers

communication:
  executive_briefing: |
    RANSOMWARE INCIDENT - EXECUTIVE BRIEF

    STATUS: [ACTIVE/CONTAINED/RESOLVED]
    SEVERITY: P0 - Critical

    IMPACT:
    - Systems affected: [COUNT]
    - Critical systems: [LIST]
    - Data encrypted: [ESTIMATE]
    - Business impact: [DESCRIPTION]

    ACTIONS TAKEN:
    - Isolated infected systems
    - Identified ransomware variant: [NAME]
    - Assessed backup integrity
    - Notified law enforcement

    NEXT STEPS:
    - [TIMELINE FOR RECOVERY]
    - Decision on ransom payment needed by: [TIME]

    ESTIMATED RECOVERY: [HOURS/DAYS]

  customer_notification: |
    Subject: Security Incident Notification

    We are writing to inform you of a security incident affecting our systems.
    On [DATE], we detected ransomware activity on our network.

    IMMEDIATE ACTIONS TAKEN:
    - Isolated affected systems
    - Engaged cybersecurity experts
    - Notified law enforcement
    - Initiated recovery procedures

    YOUR DATA:
    [IMPACT ON CUSTOMER DATA]

    NEXT STEPS:
    We are working around the clock to restore services.
    Updates will be provided every [FREQUENCY] at [URL].

    QUESTIONS:
    Contact our incident response team: incident@company.com

metrics:
  - Time from encryption start to detection
  - Time from detection to isolation
  - Number of systems encrypted
  - Percentage of data lost
  - Ransom amount demanded
  - Recovery time
  - Total cost (ransom + recovery + downtime)
```

---

### 2.4 Data Breach Playbook

**MITRE ATT&CK Techniques**: T1048 (Exfiltration Over Alternative Protocol), T1567 (Exfiltration Over Web Service)

```yaml
playbook: data_breach
severity: P0
ttps: [T1048, T1567, T1041, T1537]

detection:
  indicators:
    - Unusual outbound data transfers
    - Database queries of entire tables
    - Access to sensitive files by unauthorized users
    - Data uploaded to cloud storage
    - Dark web monitoring alert

regulatory_requirements:
  gdpr:
    notification_deadline: 72 hours
    authority: Data Protection Authority
    customer_notification: Without undue delay

  ccpa:
    notification_deadline: Without unreasonable delay
    authority: California Attorney General
    customer_notification: Required

  hipaa:
    notification_deadline: 60 days
    authority: HHS Office for Civil Rights
    customer_notification: Required

response_phases:
  1_immediate_actions:
    within_15_minutes:
      - Activate incident commander
      - Notify CISO and legal team
      - Preserve evidence (logs, network captures)
      - Initiate chain of custody documentation

  2_analysis:
    determine_scope:
      - What data was accessed?
      - What data was exfiltrated?
      - How many records affected?
      - What types of PII/PHI involved?
      - Who accessed the data?
      - When did access occur?
      - How was data exfiltrated?

    ai_soc_prompts:
      - "Analyze this database access log for data exfiltration: [paste log]"
      - "What are common data exfiltration techniques?"
      - "How can I identify the scope of a data breach?"

  3_containment:
    immediate:
      - Block attacker access
      - Disable compromised accounts
      - Revoke API keys/tokens
      - Quarantine affected systems
      - Enable enhanced monitoring

  4_eradication:
    actions:
      - Remove attacker access methods
      - Patch vulnerabilities
      - Change all credentials
      - Review access controls

  5_notification:
    internal:
      - Executive team (immediate)
      - Legal counsel (immediate)
      - PR/Communications (within 1 hour)
      - Affected departments

    regulatory:
      - Determine notification requirements
      - Draft regulatory notification
      - Submit within deadlines

    customer:
      - Identify affected individuals
      - Draft notification letter
      - Offer credit monitoring services
      - Establish call center for questions

    customer_notification_template: |
      [COMPANY LETTERHEAD]

      [DATE]

      Dear [CUSTOMER NAME],

      We are writing to notify you of a data security incident that may have affected your personal information.

      WHAT HAPPENED:
      On [DATE], we discovered that an unauthorized party gained access to our systems and accessed customer data.

      WHAT INFORMATION WAS INVOLVED:
      The following information may have been accessed:
      - [LIST SPECIFIC DATA ELEMENTS]

      WHAT WE ARE DOING:
      - Immediately secured our systems
      - Engaged cybersecurity experts
      - Notified law enforcement
      - Implemented additional security measures

      WHAT YOU CAN DO:
      - Monitor your accounts for suspicious activity
      - Place fraud alert with credit bureaus
      - Review credit reports
      - Enroll in complimentary credit monitoring (see below)

      FREE CREDIT MONITORING:
      We are offering 12 months of complimentary credit monitoring services.
      Enrollment code: [CODE]
      Instructions: [URL]

      FOR MORE INFORMATION:
      Dedicated hotline: 1-800-XXX-XXXX
      Website: [URL]
      Email: databreach@company.com

      We sincerely apologize for this incident and any inconvenience.

      Sincerely,
      [EXECUTIVE NAME]
      [TITLE]

  6_post_incident:
    improvements:
      - Implement Data Loss Prevention (DLP)
      - Enable database activity monitoring
      - Implement least privilege access
      - Encrypt sensitive data at rest
      - Conduct access review
      - Security awareness training

documentation:
  required:
    - Forensic report
    - Timeline of events
    - Scope of compromise
    - Regulatory notifications sent
    - Customer notifications sent
    - Remediation actions taken
    - Legal hold notices
    - Insurance claim documentation

legal_considerations:
  - Attorney-client privilege
  - Engage breach coach
  - Cyber insurance notification
  - Potential litigation
  - Regulatory investigations
```

---

### 2.5 Insider Threat Playbook

**MITRE ATT&CK Techniques**: T1078 (Valid Accounts), T1530 (Data from Cloud Storage Object)

```yaml
playbook: insider_threat
severity: P1-P2
ttps: [T1078, T1530, T1213, T1074]

detection:
  indicators:
    - Unusual data access by employee
    - Large file downloads
    - Access to systems outside normal duties
    - After-hours access
    - Use of personal cloud storage
    - Resignation letter filed + increased activity

  behavioral_indicators:
    - Dissatisfaction with employer
    - Financial difficulties
    - Recent disciplinary action
    - Job searching activities
    - Unusual hours or location

response_phases:
  1_immediate_actions:
    sensitive:
      - Engage HR and legal FIRST
      - Document all actions meticulously
      - Preserve evidence carefully
      - Avoid alerting suspect initially

  2_investigation:
    covert_monitoring:
      - Review access logs discreetly
      - Monitor current activity without alerting user
      - Identify what data was accessed
      - Determine if data was exfiltrated
      - Interview colleagues discreetly

    ai_soc_prompts:
      - "What are normal data access patterns for [JOB ROLE]?"
      - "Analyze this user behavior log for anomalies: [paste log]"
      - "What are common insider threat indicators?"

  3_containment:
    if_malicious:
      - Coordinate with HR for termination
      - Disable access during termination meeting
      - Collect company devices immediately
      - Escort from premises
      - Change shared passwords
      - Review access to sensitive systems

    if_accidental:
      - Provide additional training
      - Implement technical controls
      - Monitor for recurrence

  4_legal_actions:
    - Notify law enforcement if criminal
    - Pursue civil action for damages
    - Send cease and desist letter
    - Request return of company data

  5_prevention:
    - User and Entity Behavior Analytics (UEBA)
    - Data Loss Prevention (DLP)
    - Privileged Access Management (PAM)
    - Regular access reviews
    - Separation of duties
    - Exit procedures for departing employees
```

---

## 3. Technical Runbooks

### 3.1 Network Traffic Analysis Runbook

**Goal**: Analyze network traffic for suspicious activity

```bash
#!/bin/bash
# runbooks/analyze_network_traffic.sh

set -e

PCAP_FILE="$1"
SUSPICIOUS_IP="$2"

echo "=== Network Traffic Analysis Runbook ==="

# 1. Extract basic statistics
echo "[*] Extracting basic statistics..."
capinfos "$PCAP_FILE"

# 2. Find top talkers
echo "[*] Top talkers (source IPs):"
tshark -r "$PCAP_FILE" -q -z ip_srcdst,tree

# 3. Identify protocols
echo "[*] Protocol hierarchy:"
tshark -r "$PCAP_FILE" -q -z io,phs

# 4. Search for suspicious IP
if [ -n "$SUSPICIOUS_IP" ]; then
  echo "[*] Traffic to/from suspicious IP: $SUSPICIOUS_IP"
  tshark -r "$PCAP_FILE" -Y "ip.addr == $SUSPICIOUS_IP"
fi

# 5. Look for beaconing (C2 communication)
echo "[*] Checking for beaconing behavior..."
tshark -r "$PCAP_FILE" -T fields -e frame.time_epoch -e ip.src -e ip.dst -e frame.len \
  | awk '{print $1,$2,$3,$4}' \
  | sort \
  | uniq -c \
  | sort -rn \
  | head -20

# 6. Extract DNS queries
echo "[*] DNS queries:"
tshark -r "$PCAP_FILE" -Y "dns.qry.name" -T fields -e dns.qry.name | sort | uniq -c | sort -rn | head -20

# 7. Look for data exfiltration (large transfers)
echo "[*] Large data transfers (>10MB):"
tshark -r "$PCAP_FILE" -q -z conv,ip | awk '$6 > 10000000 {print}'

# 8. Check for suspicious ports
echo "[*] Uncommon destination ports:"
tshark -r "$PCAP_FILE" -T fields -e tcp.dstport -e udp.dstport | sort | uniq -c | sort -rn | head -20

echo "[*] Analysis complete. Review findings above."
```

---

### 3.2 Log Analysis Runbook

**Goal**: Analyze logs for security events

```python
# runbooks/analyze_logs.py
import re
from collections import Counter
from datetime import datetime

def analyze_auth_logs(log_file: str):
    """Analyze authentication logs for suspicious activity"""

    failed_logins = Counter()
    successful_logins = Counter()
    sudo_commands = []
    suspicious_ips = set()

    with open(log_file, 'r') as f:
        for line in f:
            # Failed login attempts
            if 'Failed password' in line:
                match = re.search(r'from (\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    ip = match.group(1)
                    failed_logins[ip] += 1

                    # Flag IPs with >10 failed attempts
                    if failed_logins[ip] > 10:
                        suspicious_ips.add(ip)

            # Successful logins
            if 'Accepted password' in line:
                match = re.search(r'for (\w+) from (\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    user = match.group(1)
                    ip = match.group(2)
                    successful_logins[(user, ip)] += 1

            # Sudo commands
            if 'sudo:' in line and 'COMMAND=' in line:
                match = re.search(r'COMMAND=(.*)', line)
                if match:
                    sudo_commands.append(match.group(1))

    # Report findings
    print("=== Authentication Log Analysis ===\n")

    print("[!] Suspicious IPs (>10 failed logins):")
    for ip in suspicious_ips:
        print(f"  {ip}: {failed_logins[ip]} failed attempts")

    print("\n[*] Top failed login sources:")
    for ip, count in failed_logins.most_common(10):
        print(f"  {ip}: {count}")

    print("\n[*] Successful logins:")
    for (user, ip), count in successful_logins.most_common(10):
        print(f"  {user} from {ip}: {count} times")

    print("\n[*] Recent sudo commands:")
    for cmd in sudo_commands[-20:]:
        print(f"  {cmd}")

# Usage
analyze_auth_logs('/var/log/auth.log')
```

---

## 4. Escalation Procedures

### 4.1 Escalation Matrix

| Severity | L1 Analyst | L2 Analyst | SOC Manager | CISO | CEO |
|----------|-----------|-----------|-------------|------|-----|
| **P3 - Low** | Investigate | Notify if needed | - | - | - |
| **P2 - Medium** | Initial triage | Investigate | Notify | - | - |
| **P1 - High** | Immediate escalation | Lead investigation | Coordinate | Notify | - |
| **P0 - Critical** | Immediate escalation | Support | Incident Commander | Notify immediately | Notify within 1 hour |

### 4.2 Escalation Triggers

**Automatic Escalation to L2**:
- P1 or P0 incidents
- Data breach suspected
- Malware outbreak (>5 systems)
- Ransomware detected
- C2 communication confirmed

**Automatic Escalation to SOC Manager**:
- P0 incidents
- Multi-stage attack detected
- Critical infrastructure affected
- Media attention likely
- Regulatory reporting required

**Automatic Escalation to CISO**:
- Confirmed data breach
- Active ransomware encryption
- Nation-state actor suspected
- Regulatory deadline approaching

**Automatic Escalation to CEO**:
- Public data breach (>1000 records)
- Ransomware affecting operations
- Potential PR crisis
- Law enforcement involvement
- Shareholder impact

### 4.3 Communication Templates

**Escalation Email Template**:

```
To: [ESCALATION CONTACT]
Subject: [P0/P1/P2] Security Incident - [SHORT DESCRIPTION]
Priority: HIGH

INCIDENT SUMMARY:
- Severity: [P0/P1/P2]
- Incident ID: [ID]
- Detection Time: [TIMESTAMP]
- Systems Affected: [COUNT/LIST]

DESCRIPTION:
[Brief description of incident]

CURRENT STATUS:
[What has been done so far]

IMPACT:
[Business impact and scope]

NEXT STEPS:
[Planned actions]

INCIDENT COMMANDER:
[Name, Phone, Email]

UPDATES:
[URL to incident tracking system]

[Your Name]
[Title]
```

---

## 5. Training Materials

### 5.1 SOC Analyst Training: Using AI-SOC

**Module 1: Introduction to AI-SOC**
- What is AI-SOC?
- How LLMs assist threat analysis
- Limitations and responsible use
- When to use AI vs manual analysis

**Module 2: Effective Prompting Techniques**

```
POOR PROMPT:
"What is this alert?"

GOOD PROMPT:
"Analyze this Suricata alert for potential SQL injection attack:
Alert: ET WEB_SERVER SQL Injection SELECT FROM
Source IP: 185.220.101.45
Destination IP: 10.0.1.50:443
Payload: GET /api/users?id=1'+OR+'1'='1

Questions:
1. Is this a true positive or false positive?
2. What is the severity of this attack?
3. What immediate actions should I take?
4. What additional investigation should I perform?"
```

**Module 3: Alert Triage Workflow**

```python
# SOC analyst workflow with AI-SOC
def triage_alert(alert_id: str):
    """Standard alert triage procedure"""

    # 1. Gather alert context
    alert = get_alert_details(alert_id)

    # 2. Query AI-SOC for initial analysis
    ai_analysis = ai_soc.analyze(
        f"""Analyze this security alert:

        Alert Type: {alert['type']}
        Severity: {alert['severity']}
        Source: {alert['source_ip']}
        Destination: {alert['dest_ip']}
        Timestamp: {alert['timestamp']}
        Description: {alert['description']}

        Provide:
        1. True/False positive assessment
        2. Threat severity (Low/Medium/High/Critical)
        3. Recommended immediate actions
        4. Investigation steps
        """
    )

    # 3. Manual validation
    if ai_analysis['confidence'] < 0.8:
        # Low confidence - manual review required
        assign_to_human(alert_id)
    else:
        # High confidence - proceed with AI recommendation
        if ai_analysis['verdict'] == 'false_positive':
            close_alert(alert_id, reason=ai_analysis['reason'])
        else:
            escalate_alert(alert_id, findings=ai_analysis)

    # 4. Document decision
    document_triage(alert_id, ai_analysis, analyst_notes)
```

**Module 4: Common Use Cases**

1. **Phishing Email Analysis**
```
Prompt: "Analyze this email for phishing indicators:
From: security@micr0soft.com
Subject: Urgent: Verify your account
Body: [paste email body]
Attachments: invoice.pdf.exe

Is this legitimate? What are the red flags?"
```

2. **Log Analysis**
```
Prompt: "Analyze these failed login attempts:
[paste auth logs]

Questions:
1. Is this a brute force attack?
2. Should I block the source IP?
3. What additional logs should I review?"
```

3. **Malware Analysis**
```
Prompt: "Initial malware triage for SHA256:
[paste hash]

VirusTotal: 45/70 detections
Top labels: Trojan.Generic, Emotet, Downloader

What is this malware likely doing? What hosts should I check for infection?"
```

### 5.2 Incident Response Tabletop Exercise

**Scenario**: Ransomware Attack

```yaml
exercise: ransomware_tabletop
duration: 90 minutes
participants:
  - SOC analysts
  - Incident response team
  - IT operations
  - Management

timeline:
  t_minus_72h:
    event: "Phishing email sent to employees"
    question: "What detection capabilities would catch this?"

  t_minus_24h:
    event: "User clicks link, malware downloaded"
    question: "What alerts would fire? Who investigates?"

  t_0:
    event: "Ransomware begins encrypting files on file server"
    question: "What immediate actions do you take?"

  t_plus_15m:
    event: "50 workstations now encrypted, ransom note appears"
    question: "Who do you notify? What containment steps?"

  t_plus_1h:
    event: "Attackers demand $500k Bitcoin, 48-hour deadline"
    question: "Do you pay? What's your recovery plan?"

  t_plus_4h:
    event: "Backups discovered to be offline (ransomware disabled them 24h ago)"
    question: "Now what? How does this change your approach?"

  t_plus_24h:
    event: "Attackers threaten to publish stolen data if not paid"
    question: "Legal implications? Customer notification?"

discussion_topics:
  - What went well?
  - What could be improved?
  - What tools/processes are missing?
  - What training is needed?
  - How can we prevent this?
```

---

## 6. SOC Metrics Dashboard

```yaml
soc_metrics:
  alert_volume:
    - Total alerts per day
    - Alerts by severity
    - Alerts by source

  triage_efficiency:
    - Mean Time to Triage (MTT)
    - False positive rate
    - Alert closure rate

  incident_response:
    - MTTD (Mean Time to Detect): Target <2 hours
    - MTTI (Mean Time to Investigate): Target <4 hours
    - MTTC (Mean Time to Contain): Target <1 hour
    - MTTR (Mean Time to Recover): Target <24 hours

  ai_soc_usage:
    - Queries per day
    - Average confidence score
    - Manual override rate
    - Time saved per analyst

  team_performance:
    - Alerts per analyst per shift
    - Escalation rate
    - SLA compliance
    - Training completion rate
```

---

## 7. Resources & References

### Tools
- **SIEM**: Splunk, QRadar, Sentinel, OpenSearch
- **EDR**: CrowdStrike, SentinelOne, Microsoft Defender
- **Network**: Wireshark, Zeek, Suricata
- **Threat Intel**: MISP, VirusTotal, AlienVault OTX
- **Forensics**: Autopsy, Volatility, FTK Imager

### Frameworks
- **NIST Cybersecurity Framework**: https://www.nist.gov/cyberframework
- **MITRE ATT&CK**: https://attack.mitre.org/
- **SANS Incident Response**: https://www.sans.org/incident-response/

### Training
- **SANS SEC595**: Applied Data Science for Cybersecurity
- **SANS FOR508**: Advanced Incident Response
- **EC-Council CEH**: Certified Ethical Hacker
- **GIAC GCIH**: GIAC Certified Incident Handler

---

*Document Version*: 1.0
*Last Updated*: 2025-10-22
*Author*: The Didact (AI Research Specialist)
*Classification*: Internal Use
