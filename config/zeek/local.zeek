# ============================================================================
# Zeek Network Security Monitor Configuration
# ============================================================================
# Production-ready configuration for AI-SOC passive network monitoring
# Reference: https://docs.zeek.org/en/master/quickstart.html

##! Local site policy. Customize as appropriate.
##!
##! This file will not be overwritten when upgrading or reinstalling!

# Load the base scripts
@load base/frameworks/sumstats
@load base/protocols/conn
@load base/protocols/dns
@load base/protocols/http
@load base/protocols/ssl
@load base/protocols/ssh
@load base/protocols/smtp
@load base/protocols/ftp

# Load detection frameworks
@load policy/frameworks/files/detect-MHR
@load policy/frameworks/intel/seen
@load policy/frameworks/intel/do_notice
@load policy/frameworks/software/vulnerable
@load policy/frameworks/software/version-changes

# Load protocol-specific policies
@load policy/protocols/conn/known-hosts
@load policy/protocols/conn/known-services
@load policy/protocols/dhcp/software
@load policy/protocols/dns/detect-external-names
@load policy/protocols/ftp/detect
@load policy/protocols/http/detect-sqli
@load policy/protocols/http/detect-webapps
@load policy/protocols/http/software
@load policy/protocols/smb/log-cmds
@load policy/protocols/ssh/detect-bruteforcing
@load policy/protocols/ssh/geo-data
@load policy/protocols/ssh/interesting-hostnames
@load policy/protocols/ssl/known-certs
@load policy/protocols/ssl/validate-certs

# Load file analysis
@load policy/files/hash-all-files
@load policy/files/detect-MHR

# Load threat intelligence framework
@load policy/integration/collective-intel
@load policy/tuning/json-logs

# Network monitoring
@load policy/misc/scan

# Load additional scripts for enhanced detection
@load policy/protocols/ssl/weak-keys
@load policy/protocols/ssl/notary

# JSON output
@load tuning/json-logs.zeek

# Site-specific customization
redef Site::local_nets += {
    10.0.0.0/8,
    172.16.0.0/12,
    192.168.0.0/16
};

# Increase some resource limits for production
redef max_remote_events_processed = 500;

# Log rotation
@load base/frameworks/logging/writers/ascii
