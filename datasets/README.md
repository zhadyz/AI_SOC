# Datasets for AI-Augmented SOC

This directory contains documentation and scripts for acquiring and processing cybersecurity datasets used in the AI-SOC project.

## 📦 Primary Datasets

### 1. CICIDS2017 (Recommended for MVP)

**Description:** Canadian Institute for Cybersecurity Intrusion Detection System dataset

**Specifications:**
- **Volume:** 2.8 million network flow records
- **Duration:** 5 days (July 3-7, 2017)
- **Attack Types:** Brute Force, Heartbleed, Botnet, DoS, DDoS, Web Attacks, Infiltration
- **Format:** CSV (machine learning ready), PCAP (full packets)
- **License:** Free for academic research

**Download Sources:**
- Official: https://www.unb.ca/cic/datasets/ids-2017.html
- Kaggle: https://www.kaggle.com/datasets/chethuhn/network-intrusion-dataset
- IEEE DataPort: https://ieee-dataport.org/documents/cicids2017

**Use Cases:**
- Alert triage validation
- Report generation training
- Classification benchmarking

---

### 2. UNSW-NB15

**Description:** University of New South Wales Network-Based 15 dataset

**Specifications:**
- **Volume:** 100 GB raw traffic
- **Attack Categories:** 9 types (Fuzzers, Analysis, Backdoors, DoS, Exploits, Generic, Reconnaissance, Shellcode, Worms)
- **Format:** PCAP, BRO files, Argus files, CSV
- **License:** Free for academic research (no commercial use)

**Download Sources:**
- Official: https://research.unsw.edu.au/projects/unsw-nb15-dataset
- Kaggle: https://www.kaggle.com/datasets/mrwellsdavid/unsw-nb15
- IEEE DataPort: https://dx.doi.org/10.21227/8vf7-s525

**Use Cases:**
- Multi-class threat classification
- Advanced alert triage
- Threat intelligence report generation

---

### 3. CICIoT2023

**Description:** Latest CIC IoT attack benchmark (2023-2024)

**Specifications:**
- **Release:** 2023, updated October 2024
- **Focus:** IoT-specific attacks
- **License:** Free for academic research

**Download Sources:**
- Official: https://www.unb.ca/cic/datasets/iotdataset-2023.html
- Kaggle: https://www.kaggle.com/datasets/mdabdulalemo/cic-iot-dataset2023-updated-2024-10-08

**Use Cases:**
- Modern threat detection validation
- IoT-specific log analysis
- Realistic attack scenario generation

---

### 4. LogHub-2.0

**Description:** 19 real-world system log datasets

**Specifications:**
- **Systems:** HDFS, Spark, BGL, Thunderbird, Windows, Linux, etc.
- **Format:** Raw log files + parsed templates
- **Size:** Variable per system
- **License:** Open source

**Download:**
```bash
git clone https://github.com/logpai/loghub.git
```

**Use Cases:**
- Log parsing algorithm validation
- Anomaly detection
- Log summarization training

---

## 📥 Quick Start

### Download CICIDS2017 (Recommended First Step)

```bash
# Option 1: Via Kaggle CLI
pip install kaggle
kaggle datasets download -d chethuhn/network-intrusion-dataset
unzip network-intrusion-dataset.zip -d CICIDS2017/

# Option 2: Manual download
# Visit https://www.unb.ca/cic/datasets/ids-2017.html
# Download CSV files
```

### Download LogHub

```bash
cd datasets/
git clone https://github.com/logpai/loghub.git
cd loghub/
# Logs are in loghub/*/
```

---

## 🔒 License Compliance

| Dataset | Academic Use | Commercial Use | Attribution Required |
|---------|--------------|----------------|---------------------|
| CICIDS2017 | ✅ Free | ⚠️ Check terms | ✅ Yes |
| UNSW-NB15 | ✅ Free | ❌ No | ✅ Yes |
| CICIoT2023 | ✅ Free | ⚠️ Check terms | ✅ Yes |
| LogHub | ✅ Free | ✅ Free (OSS) | ✅ Yes |

**Note:** This project is for academic research. For commercial deployment, verify licensing terms for each dataset.

---

## 📊 Dataset Statistics

### CICIDS2017 Attack Distribution

| Attack Type | Record Count | Percentage |
|-------------|--------------|------------|
| Benign | 2,273,097 | 81.34% |
| DoS/DDoS | 380,949 | 13.63% |
| Port Scan | 158,930 | 5.69% |
| Brute Force | 13,835 | 0.50% |
| Web Attack | 2,180 | 0.08% |
| Botnet | 1,966 | 0.07% |

### UNSW-NB15 Attack Categories

| Category | Description | Percentage |
|----------|-------------|------------|
| Normal | Benign traffic | 56.00% |
| Generic | Unknown attacks | 18.87% |
| Exploits | Vulnerability exploitation | 14.89% |
| Fuzzers | Fuzzing attacks | 8.51% |
| DoS | Denial of Service | 5.59% |
| Reconnaissance | Scanning | 4.66% |
| Analysis | Port scanning | 0.83% |
| Backdoor | Backdoor access | 0.73% |
| Shellcode | Shellcode injection | 0.47% |
| Worms | Worm propagation | 0.06% |

---

## 🛠️ Preprocessing Scripts

Coming soon:
- `download_cicids2017.sh` - Automated download script
- `preprocess_unsw.py` - Data cleaning and normalization
- `generate_synthetic.py` - Synthetic attack generation using AttackGen

---

## 📚 Citations

If you use these datasets in research, please cite:

**CICIDS2017:**
```bibtex
@inproceedings{sharafaldin2018toward,
  title={Toward generating a new intrusion detection dataset and intrusion traffic characterization},
  author={Sharafaldin, Iman and Lashkari, Arash Habibi and Ghorbani, Ali A},
  booktitle={ICISSp},
  pages={108--116},
  year={2018}
}
```

**UNSW-NB15:**
```bibtex
@article{moustafa2015unsw,
  title={UNSW-NB15: a comprehensive data set for network intrusion detection systems},
  author={Moustafa, Nour and Slay, Jill},
  journal={Military Communications and Information Systems Conference (MilCIS)},
  year={2015}
}
```

---

## ⚠️ Important Notes

1. **Large Files:** Datasets are NOT committed to Git (see `.gitignore`)
2. **Storage:** Reserve at least 200GB for all datasets
3. **Privacy:** Datasets contain anonymized traffic - no real PII
4. **Updates:** CIC releases new datasets annually - check for latest versions

---

**Need help?** Open an issue on GitHub or contact the project maintainers.
