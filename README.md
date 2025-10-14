# AI-Augmented SOC (Security Operations Center)

> **Open-source AI-powered Security Operations Center using LLMs and Multi-Agent Orchestration**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

## 🎯 Project Vision

Building the **world's first comprehensive open-source AI-augmented SOC** that combines mature security tools (Wazuh, TheHive, Suricata) with cutting-edge LLM technology (Foundation-Sec-8B, LLaMA 3.1) to automate log summarization, alert triage, and incident report generation.

**Mission:** Make enterprise-grade AI-powered security operations accessible to organizations of all sizes.

---

## 🚀 Key Features

- **🤖 AI-Powered Alert Triage**: LLM-based analysis using Foundation-Sec-8B (Cisco's security-optimized model)
- **📊 Automated Log Summarization**: LibreLog integration processing millions of logs efficiently
- **📝 Intelligent Report Generation**: AGIR/AttackGen for automated incident reporting
- **🔗 RAG-Enhanced Context**: ChromaDB vector database for hallucination-free threat intelligence
- **🛡️ Full SIEM/SOAR Stack**: Wazuh + OpenSearch + TheHive + Cortex + Shuffle
- **🐳 Docker Compose Deployment**: One-command deployment for rapid setup
- **🔒 Privacy-First**: Local LLM deployment (Ollama) - no data leaves your infrastructure
- **📈 Measurable Impact**: Target 80% MTTD reduction, 5x alert throughput increase

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                              │
│  Wazuh Dashboard | TheHive UI | Shuffle Workflows | Grafana     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  AI/LLM LAYER                                                    │
│  Ollama (Foundation-Sec-8B, LLaMA 3.1) | LangGraph | ChromaDB   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  APPLICATION LAYER                                               │
│  Alert Triage | Log Summarization | Report Generation | RAG     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  SIEM & SOAR LAYER                                               │
│  Wazuh | TheHive | Cortex | Shuffle                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                      │
│  OpenSearch | Cassandra | Redis | PostgreSQL                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  COLLECTION LAYER                                                │
│  Suricata | Zeek | Wazuh Agents | Filebeat                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📚 Research Foundation

This project implements findings from the research paper:
**"AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation"**
*Srinivas et al., California State University, San Bernardino*

Key implementations:
- **Log Summarization**: LibreLog (2.7x faster than alternatives)
- **Alert Triage**: LangChain agents + ChromaDB RAG (30-40% hallucination reduction)
- **Threat Intelligence**: CyLens-inspired CTI analysis
- **Report Generation**: AGIR automation (42.6% time reduction)

---

## 🛠️ Technology Stack

### Core Infrastructure
- **SIEM**: Wazuh 4.x + OpenSearch
- **SOAR**: TheHive + Cortex + Shuffle
- **Network Monitoring**: Suricata + Zeek
- **Containerization**: Docker + Docker Compose

### AI/LLM Components
- **LLM Platform**: Ollama
- **Primary Model**: Foundation-Sec-8B (Cisco, security-optimized)
- **Secondary Models**: LLaMA 3.1 8B, Mistral 7B
- **Orchestration**: LangChain + LangGraph
- **Vector DB**: ChromaDB
- **Log Parsing**: LibreLog

### Development
- **Language**: Python 3.10+
- **API Framework**: FastAPI
- **Testing**: Pytest
- **Datasets**: CICIDS2017, UNSW-NB15, CICIoT2023

---

## 🚦 Project Status

**Current Phase**: Foundation (Phase 1 of 5)
**Progress**: 20%
**Latest Update**: 2025-10-13

### Roadmap

#### ✅ Phase 1: Foundation (Weeks 1-2)
- [x] Research intelligence gathering
- [x] Dataset identification & evaluation
- [x] Architecture design
- [ ] Core SIEM deployment (Wazuh + OpenSearch)
- [ ] Network monitoring setup (Suricata + Zeek)

#### 🔄 Phase 2: SOAR Integration (Week 3)
- [ ] TheHive + Cortex deployment
- [ ] Shuffle orchestration platform
- [ ] End-to-end alert workflow

#### 📋 Phase 3: AI Layer (Weeks 4-5)
- [ ] Ollama deployment
- [ ] Foundation-Sec-8B integration
- [ ] Alert triage service (MVP)
- [ ] ChromaDB RAG implementation

#### 🚀 Phase 4: Advanced Features (Weeks 6-8)
- [ ] Log summarization service
- [ ] Report generation automation
- [ ] Multi-agent LLM collaboration
- [ ] Evaluation & benchmarking

#### 🎯 Phase 5: Production Hardening (Month 3+)
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Documentation completion
- [ ] Community engagement

---

## 📊 Datasets

### Primary Datasets

| Dataset | Size | Use Case | Status |
|---------|------|----------|--------|
| **CICIDS2017** | 2.8M records | Alert triage, report generation | ✅ Evaluated |
| **UNSW-NB15** | 100GB | Multi-class classification | ✅ Evaluated |
| **CICIoT2023** | Variable | Modern IoT threats | ✅ Evaluated |
| **LogHub-2.0** | 19 systems | Log parsing, anomaly detection | ✅ Evaluated |

See [datasets/README.md](datasets/README.md) for download instructions.

---

## 🎯 Success Metrics

### Target Performance (vs Baseline)

| Metric | Baseline | Target | Improvement |
|--------|----------|--------|-------------|
| **MTTD (Critical Alerts)** | 2.5 hours | <30 min | 80% faster |
| **MTTR** | 4 hours | 1.5 hours | 62% faster |
| **False Positive Rate** | 45% | <25% | 44% reduction |
| **Alert Throughput** | 50/day | 250/day | 5x increase |
| **F1 Score (Classification)** | N/A | >0.90 | - |
| **BERTScore (Summarization)** | N/A | >0.85 | - |

---

## 🤝 Contributing

We welcome contributions! This is an open-source community project.

**Areas for Contribution:**
- 🐛 Bug fixes and testing
- 📚 Documentation improvements
- 🔧 Tool integrations
- 🧪 Benchmarking and evaluation
- 💡 Feature enhancements

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📜 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

**Key Points:**
- ✅ Free for commercial and academic use
- ✅ Modification and redistribution allowed
- ✅ Patent grant included
- ⚠️ No warranty provided

---

## 🙏 Acknowledgments

**Research Foundation:**
- California State University, San Bernardino
- Srinivas et al. - "AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation"

**Core Technologies:**
- Wazuh Project
- Cisco Foundation AI (Foundation-Sec-8B)
- Meta AI (LLaMA)
- TheHive Project
- Shuffle.io
- Ollama

**Datasets:**
- Canadian Institute for Cybersecurity (CIC)
- UNSW Canberra
- LogPAI Research Group

---

## 📞 Contact & Community

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Q&A, ideas, and community chat
- **Project Lead**: Abdul Bari (abdul.bari8019@coyote.csusb.edu)

---

## ⭐ Star History

If you find this project useful, please consider starring it to show your support!

---

**Built with 🛡️ by the AI-SOC community**

*Making enterprise-grade AI-powered security accessible to everyone.*
