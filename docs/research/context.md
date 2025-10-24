# Research Context

## Academic Foundation

This implementation is part of ongoing cybersecurity research at California State University, San Bernardino. The project validates findings from the comprehensive survey "AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation" through production deployment.

## Survey Research Background

The foundational survey paper examined 500+ academic and preprint publications (2022-2025) using PRISMA methodology to systematically review the application of Large Language Models and autonomous AI agents in Security Operations Center tasks.

### Research Team

**Student Researchers:**
- Siddhant Srinivas
- Brandon Kirk
- Julissa Zendejas
- Michael Espino
- Matthew Boskovich
- Abdul Bari

**Faculty Advisors:**
- Dr. Khalil Dajani
- Dr. Nabeel Alzahrani

**Institution:**
School of Computer Science & Engineering
California State University, San Bernardino

## Eight SOC Tasks Identified

The survey identified eight critical Security Operations Center functions where AI/ML integration demonstrates measurable impact:

1. **Log Summarization** - Automated processing and condensation of high-volume security log data
2. **Alert Triage** - Intelligent prioritization and classification of security alerts
3. **Threat Intelligence** - Integration and analysis of external threat feeds
4. **Ticket Handling** - Automated incident ticket creation and routing
5. **Incident Response** - Coordinated response workflows and remediation
6. **Report Generation** - Automated creation of security reports
7. **Asset Discovery and Management** - Continuous inventory of network assets
8. **Vulnerability Management** - Systematic identification and remediation

## Implementation Scope

This AI-SOC platform implements **three of the eight** surveyed tasks:

✅ **Alert Triage** (ML Inference + Alert Triage Service)
✅ **Threat Intelligence** (RAG Service with MITRE ATT&CK)
✅ **Log Summarization** (Wazuh SIEM + ML Analysis)

## Research Questions

This implementation addresses:

**RQ1**: Can ML models achieve production-grade performance (>95% accuracy, <1% false positive rate) on contemporary intrusion detection datasets?

**RQ2**: What are the practical challenges in integrating ML inference pipelines with traditional SIEM infrastructure?

**RQ3**: To what extent can deployment complexity be reduced through automation while maintaining system reliability?

**RQ4**: What validation methodologies are necessary to ensure production readiness of AI-enhanced security systems?

## Key Findings

1. **Integration Friction Confirmed** - 40% of development time spent on SIEM integration challenges
2. **Deployment Automation Effective** - Reduced deployment from 2-3 hours to <15 minutes
3. **ML Performance Validated** - Achieved 99.28% accuracy exceeding survey benchmarks
4. **Novel Challenges Discovered** - Docker volume persistence, health check accuracy, service dependency ordering

[Read the complete survey paper →](survey-paper.md)
