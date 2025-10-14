# AI-SOC Project Structure

## Overview
This document describes the organization of the AI-Augmented Security Operations Center (AI-SOC) repository.

## Directory Structure

```
AI_SOC/
├── .claude/                    # Claude Code agent memory and reports
│   └── memory/                 # Agent execution history and state
├── config/                     # Service configuration files
│   ├── wazuh-manager/          # Wazuh SIEM configuration
│   ├── wazuh-indexer/          # OpenSearch configuration
│   ├── wazuh-dashboard/        # Dashboard configuration
│   ├── suricata/               # IPS rules and configuration
│   ├── zeek/                   # Network analysis scripts
│   └── filebeat/               # Log forwarding configuration
├── datasets/                   # Training and evaluation datasets
│   └── CICIDS2017/             # Network intrusion detection dataset
│       ├── README.md           # Dataset documentation
│       ├── DATASET_VALIDATION_REPORT.md
│       ├── validate_dataset.py
│       └── raw/                # Raw CSV files (gitignored)
├── docker-compose/             # Container orchestration
│   ├── phase1-siem-core-windows.yml  # SIEM stack
│   ├── dev-environment.yml     # Development tools
│   ├── ai-services.yml         # AI/ML services
│   └── README.md               # Deployment documentation
├── docs/                       # Project documentation
│   ├── SECURITY_BASELINE.md    # Security audit report
│   └── architecture/           # Architecture diagrams
├── evaluation/                 # Model evaluation reports
│   └── baseline_models_report.md
├── ml_training/                # Machine learning pipeline
│   ├── train_ids_model.py      # Main training script
│   ├── train_ids_model_sample.py  # 10% sample training
│   ├── inference_api.py        # FastAPI inference endpoint
│   ├── test_inference.py       # Test suite
│   ├── Dockerfile              # ML inference container
│   ├── requirements.txt        # Python dependencies
│   ├── README.md               # Training documentation
│   └── TRAINING_REPORT.md      # Performance metrics
├── models/                     # Trained ML models
│   ├── random_forest_ids.pkl   # Production model (99.28% accuracy)
│   ├── xgboost_ids.pkl         # Lightweight alternative
│   ├── decision_tree_ids.pkl   # Interpretable baseline
│   ├── scaler.pkl              # Feature scaler
│   ├── label_encoder.pkl       # Label encoder
│   └── feature_names.pkl       # Feature list
├── scripts/                    # Utility scripts
│   ├── generate-certs.sh       # SSL certificate generation (Linux)
│   └── generate-certs.ps1      # SSL certificate generation (Windows)
├── services/                   # AI service implementations
│   ├── alert-triage/           # LLM-powered alert analysis
│   ├── log-summarization/      # Log aggregation service
│   ├── rag-service/            # RAG with MITRE ATT&CK
│   ├── common/                 # Shared utilities
│   └── README.md               # Service documentation
├── tests/                      # Test suites
│   └── test_security_audit.py  # Security validation tests
├── .env.example                # Environment template
├── .gitignore                  # Git exclusions
├── LICENSE                     # Apache 2.0
├── README.md                   # Project overview
├── ROADMAP.md                  # Development roadmap
└── STRUCTURE.md                # This file
```

## Key Components

### 1. **Machine Learning Pipeline** (`ml_training/`)
- Complete IDS training pipeline on CICIDS2017
- 99.28% accuracy intrusion detection
- Sub-millisecond inference
- FastAPI inference endpoint
- Docker deployment ready

### 2. **AI Services** (`services/`)
- **Alert Triage:** LLM-powered security alert analysis
- **RAG Service:** Context retrieval from MITRE ATT&CK
- **Log Summarization:** Automated log aggregation
- **Common Library:** Shared utilities (Ollama client, security, metrics)

### 3. **SIEM Infrastructure** (`docker-compose/`, `config/`)
- Wazuh Manager + OpenSearch (SIEM core)
- Suricata + Zeek (network monitoring)
- Filebeat (log forwarding)
- Production-grade SSL/TLS configuration

### 4. **Documentation** (`docs/`, `evaluation/`)
- Security baseline audit
- Model performance reports
- Deployment guides
- Architecture documentation

## Data Flow

```
Network Traffic → Suricata/Zeek → Wazuh Manager → OpenSearch
                                       ↓
                                 Alert Triage (LLM)
                                       ↓
                                 ML Inference API → Classification
                                       ↓
                                 RAG Service → MITRE ATT&CK Context
                                       ↓
                                   TheHive (Case Management)
```

## Getting Started

1. **Prerequisites:** Docker, Docker Compose, 12GB+ RAM, 6+ CPU cores
2. **Dataset:** Download CICIDS2017 (see `datasets/CICIDS2017/README.md`)
3. **Configuration:** Copy `.env.example` to `.env` and configure
4. **Deployment:** See `docker-compose/README.md` for deployment instructions
5. **Training:** Run `python ml_training/train_ids_model.py` to train models
6. **Testing:** Run `pytest tests/` to validate security utilities

## Development Workflow

1. All service code goes in `services/`
2. Training scripts go in `ml_training/`
3. Configuration files go in `config/`
4. Documentation goes in `docs/`
5. Tests go in `tests/`
6. Deployment configs go in `docker-compose/`

## Internal Files (.internal/ - gitignored)
- Agent execution scripts
- Deployment reports
- Research papers and diagrams
- Development notes

## Contact

**Project Lead:** Abdul Bari
**Email:** abdul.bari8019@coyote.csusb.edu
**GitHub:** https://github.com/zhadyz/AI_SOC

## License

Apache 2.0 - See LICENSE file
