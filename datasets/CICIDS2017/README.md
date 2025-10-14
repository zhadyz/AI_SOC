# CICIDS2017 Dataset - Intrusion Detection Evaluation Dataset

## Overview

The **CICIDS2017** (Canadian Institute for Cybersecurity Intrusion Detection System 2017) dataset is a comprehensive, labeled network intrusion detection dataset created by the University of New Brunswick's Canadian Institute for Cybersecurity. This is the **improved version** with corrected ground-truth labeling, additional features, and removed corrupted entries.

## Dataset Acquisition

### Source Information

- **Official Source**: Canadian Institute for Cybersecurity, University of New Brunswick
- **Improved Version From**: [Troubleshooting an Intrusion Detection Dataset Research](https://intrusion-detection.distrinet-research.be/WTMC2021/)
- **Download Date**: October 13, 2025
- **Dataset Version**: Improved CICIDS2017 (November 2021)
- **Compressed Size**: 318 MB
- **Extracted Size**: ~1.1 GB

### Improvements in This Version

This improved version addresses several issues found in the original CICIDS2017 dataset:

1. **Corrected Ground-Truth Labeling**: Fixed mislabeled attack instances
2. **Additional Features**: Enhanced feature set for better detection
3. **Data Cleaning**: Removed corrupted entries and records with NaN values
4. **Quality Assurance**: Validated data integrity across all files

### Citation

If you use this dataset in your research, please cite:

**Original Dataset**:
```
Sharafaldin, I., Lashkari, A. H., & Ghorbani, A. A. (2018).
Toward generating a new intrusion detection dataset and intrusion traffic characterization.
In 4th International Conference on Information Systems Security and Privacy (ICISSP),
Portugal, January 2018.
```

**Improved Version**:
```
Engelen, G., Rimmer, V., & Joosen, W. (2021).
Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study.
In 2021 IEEE Security and Privacy Workshops (SPW) (pp. 7-12). IEEE.
```

## Dataset Statistics

### File Structure

| File Name | Records | Size | Description |
|-----------|---------|------|-------------|
| `Monday-WorkingHours.csv` | 371,749 | 199 MB | Normal traffic baseline |
| `Tuesday-WorkingHours.csv` | 322,003 | 171 MB | Brute force attacks (FTP, SSH) |
| `Wednesday-WorkingHours.csv` | 496,779 | 279 MB | DoS/DDoS attacks + Heartbleed |
| `Thursday-WorkingHours.csv` | 362,368 | 180 MB | Web attacks + Infiltration |
| `Friday-WorkingHours.csv` | 547,915 | 270 MB | Botnet + Port scanning + DDoS |
| **Total** | **2,100,814** | **~1.1 GB** | **5 days of network traffic** |

### Overall Label Distribution

| Label | Count | Percentage |
|-------|-------|------------|
| BENIGN | 1,657,693 | 78.91% |
| PortScan | 159,151 | 7.58% |
| DoS Hulk | 158,469 | 7.54% |
| DDoS | 95,123 | 4.53% |
| DoS GoldenEye | 7,567 | 0.36% |
| DoS slowloris | 4,001 | 0.19% |
| FTP-Patator | 3,973 | 0.19% |
| DoS Slowhttptest - Attempted | 3,369 | 0.16% |
| SSH-Patator | 2,980 | 0.14% |
| DoS Slowhttptest | 1,742 | 0.08% |
| DoS slowloris - Attempted | 1,731 | 0.08% |
| Bot - Attempted | 1,470 | 0.07% |
| Web Attack - Brute Force - Attempted | 1,214 | 0.06% |
| Bot | 738 | 0.04% |
| Web Attack - XSS - Attempted | 652 | 0.03% |
| DoS Hulk - Attempted | 593 | 0.03% |
| Web Attack - Brute Force | 151 | 0.01% |
| DoS GoldenEye - Attempted | 80 | <0.01% |
| Infiltration | 32 | <0.01% |
| Web Attack - XSS | 27 | <0.01% |
| Infiltration - Attempted | 16 | <0.01% |
| Web Attack - Sql Injection | 12 | <0.01% |
| FTP-Patator - Attempted | 11 | <0.01% |
| Heartbleed | 11 | <0.01% |
| SSH-Patator - Attempted | 8 | <0.01% |

### Attack Categories (24 Types)

The dataset includes **24 distinct attack categories** plus benign traffic:

**Brute Force Attacks:**
- FTP-Patator (3,973 samples)
- SSH-Patator (2,980 samples)
- Web Attack - Brute Force (151 samples)

**Denial of Service (DoS) Attacks:**
- DoS Hulk (158,469 samples)
- DoS GoldenEye (7,567 samples)
- DoS slowloris (4,001 samples)
- DoS Slowhttptest (1,742 samples)

**Distributed Denial of Service (DDoS):**
- DDoS (95,123 samples)

**Web Attacks:**
- Web Attack - XSS (27 samples)
- Web Attack - SQL Injection (12 samples)

**Advanced Attacks:**
- Botnet (738 samples)
- PortScan (159,151 samples)
- Infiltration (32 samples)
- Heartbleed (11 samples)

**Note**: The dataset also includes "Attempted" variations of several attack types, representing attack attempts that were detected or failed.

## Features

The dataset contains **84 columns** with **83 features** plus 1 label column:

### Network Flow Identifiers
1. Flow ID
2. Src IP
3. Src Port
4. Dst IP
5. Dst Port
6. Protocol
7. Timestamp

### Flow Duration & Packet Statistics
8. Flow Duration
9. Total Fwd Packet
10. Total Bwd packets
11. Total Length of Fwd Packet
12. Total Length of Bwd Packet

### Packet Length Statistics
13-20. Fwd/Bwd Packet Length (Max, Min, Mean, Std)
45-49. Packet Length (Min, Max, Mean, Std, Variance)

### Flow Timing Statistics
21-36. Flow IAT, Fwd IAT, Bwd IAT (Mean, Std, Max, Min, Total)
76-83. Active/Idle Time Statistics (Mean, Std, Max, Min)

### Protocol Flags
37-40. Fwd/Bwd PSH and URG Flags
50-57. TCP Flags (FIN, SYN, RST, PSH, ACK, URG, CWR, ECE)

### Packet Header Information
41-44. Fwd/Bwd Header Length and Packets/s

### Flow Rate Statistics
21-22. Flow Bytes/s, Flow Packets/s
43-44. Fwd/Bwd Packets/s

### Advanced Flow Features
58-61. Down/Up Ratio, Average Packet Size, Segment Size Avg
62-67. Bulk Transfer Statistics
68-75. Subflow Statistics and Window Bytes

### Label
84. **Label** - Attack type or "BENIGN"

All features are extracted using the **CICFlowMeter** tool, which processes network packet captures (PCAPs) and generates bidirectional flow statistics.

## Data Collection Methodology

### Network Environment
- **Duration**: 5 days (July 3-7, 2017, Monday-Friday)
- **Time**: 9:00 AM - 5:00 PM each day
- **Network Configuration**:
  - 12 different machines
  - Multiple operating systems (Windows, Ubuntu, Mac OS X)
  - Includes firewall, switches, routers
  - Realistic network topology

### Attack Execution
- **Monday**: Baseline normal traffic only
- **Tuesday**: Brute force attacks (FTP, SSH)
- **Wednesday**: DoS variants + Heartbleed
- **Thursday**: Web attacks + Infiltration attempts
- **Friday**: Botnet activity + Port scanning + DDoS

### Traffic Types
- **Protocols**: HTTP, HTTPS, FTP, SSH, Email protocols
- **Applications**: Web browsing, email, file transfer, SSH sessions
- **Attack Tools**: Various penetration testing and attack tools

## Preprocessing Requirements

### 1. Data Loading

```python
import pandas as pd

# Load individual day
df = pd.read_csv('raw/Monday-WorkingHours.csv')

# Load all days
import glob
csv_files = glob.glob('raw/*-WorkingHours.csv')
df_list = [pd.read_csv(f) for f in csv_files]
df_combined = pd.concat(df_list, ignore_index=True)
```

### 2. Essential Preprocessing Steps

#### A. Handle Missing Values
```python
# Check for missing values
print(df.isnull().sum())

# Strategy: Drop or impute based on feature importance
df = df.dropna()  # Or use imputation
```

#### B. Remove Non-Feature Columns
```python
# Remove identifiers not useful for ML
df = df.drop(['Flow ID', 'Src IP', 'Dst IP', 'Timestamp'], axis=1)
```

#### C. Handle Infinite Values
```python
# Replace infinite values
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df.fillna(0, inplace=True)
```

#### D. Encode Labels
```python
from sklearn.preprocessing import LabelEncoder

le = LabelEncoder()
df['Label'] = le.fit_transform(df['Label'])

# Save label mapping
label_mapping = dict(zip(le.classes_, le.transform(le.classes_)))
```

#### E. Feature Scaling
```python
from sklearn.preprocessing import StandardScaler

X = df.drop('Label', axis=1)
y = df['Label']

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
```

### 3. Handling Class Imbalance

The dataset is highly imbalanced (78.91% benign, 21.09% attacks). Consider:

**Option 1: Undersampling Majority Class**
```python
from imblearn.under_sampling import RandomUnderSampler

rus = RandomUnderSampler(random_state=42)
X_res, y_res = rus.fit_resample(X, y)
```

**Option 2: Oversampling Minority Classes**
```python
from imblearn.over_sampling import SMOTE

smote = SMOTE(random_state=42)
X_res, y_res = smote.fit_resample(X, y)
```

**Option 3: Class Weights**
```python
from sklearn.utils.class_weight import compute_class_weight

class_weights = compute_class_weight('balanced',
                                      classes=np.unique(y),
                                      y=y)
```

### 4. Feature Selection

Due to high dimensionality (83 features), consider:

```python
from sklearn.feature_selection import SelectKBest, f_classif

# Select top k features
selector = SelectKBest(f_classif, k=50)
X_selected = selector.fit_transform(X, y)
```

### 5. Train-Test Split

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42, stratify=y
)
```

## Known Issues & Considerations

### 1. Class Imbalance
- **BENIGN** dominates at 78.91%
- Some attack types have < 100 samples
- Requires careful handling for model training

### 2. Feature Correlation
- Many features are highly correlated
- Consider dimensionality reduction (PCA) or feature selection

### 3. Computational Requirements
- 2.1M records may require significant RAM
- Consider batch processing or sampling for initial experiments

### 4. Temporal Considerations
- Data collected over consecutive days
- Some attack patterns may be temporally correlated
- Use time-aware splitting if needed

### 5. Real-World Application
- Dataset from 2017 - attack patterns may have evolved
- Combine with newer datasets for production systems
- Validate on real network traffic before deployment

## Recommended Preprocessing Pipeline

```python
# Complete preprocessing pipeline
def preprocess_cicids2017(df):
    # 1. Drop non-feature columns
    df = df.drop(['Flow ID', 'Src IP', 'Dst IP', 'Timestamp'], axis=1)

    # 2. Handle infinite and missing values
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.fillna(0, inplace=True)

    # 3. Separate features and labels
    X = df.drop('Label', axis=1)
    y = df['Label']

    # 4. Encode labels
    le = LabelEncoder()
    y = le.fit_transform(y)

    # 5. Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 6. Handle imbalance (SMOTE)
    smote = SMOTE(random_state=42)
    X_res, y_res = smote.fit_resample(X_scaled, y)

    # 7. Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_res, y_res, test_size=0.2, random_state=42, stratify=y_res
    )

    return X_train, X_test, y_train, y_test, le, scaler
```

## Usage Examples

### Binary Classification (Normal vs Attack)
```python
# Simplify to binary classification
df['Label'] = df['Label'].apply(lambda x: 0 if x == 'BENIGN' else 1)
```

### Multi-Class Classification
```python
# Keep all 25 categories (24 attacks + benign)
# Use original labels
```

### Specific Attack Type Detection
```python
# Filter for specific attack types
dos_attacks = df[df['Label'].str.contains('DoS')]
```

## Validation Script

A validation script is provided at `validate_dataset.py` to:
- Verify dataset integrity
- Display record counts per file
- Show label distributions
- List all features

Run with:
```bash
python validate_dataset.py
```

## Directory Structure

```
datasets/CICIDS2017/
├── README.md                           # This file
├── validate_dataset.py                 # Dataset validation script
├── raw/                                # Raw CSV files
│   ├── Monday-WorkingHours.csv        # 371,749 records
│   ├── Tuesday-WorkingHours.csv       # 322,003 records
│   ├── Wednesday-WorkingHours.csv     # 496,779 records
│   ├── Thursday-WorkingHours.csv      # 362,368 records
│   ├── Friday-WorkingHours.csv        # 547,915 records
│   └── improved_dataset.zip           # Original archive (318MB)
└── processed/                          # For preprocessed data (create as needed)
    ├── X_train.npy
    ├── X_test.npy
    ├── y_train.npy
    ├── y_test.npy
    ├── label_encoder.pkl
    └── scaler.pkl
```

## Performance Benchmarks

### Baseline Results from Literature

| Model | Accuracy | Precision | Recall | F1-Score |
|-------|----------|-----------|--------|----------|
| Random Forest | 99.7% | 99.6% | 99.7% | 99.6% |
| Decision Tree | 99.5% | 99.4% | 99.5% | 99.4% |
| SVM | 98.2% | 98.1% | 98.2% | 98.1% |
| Neural Network | 99.8% | 99.7% | 99.8% | 99.7% |
| KNN | 97.5% | 97.3% | 97.5% | 97.4% |

**Note**: These are general benchmarks. Your results will vary based on preprocessing and model configuration.

## Integration with AI-SOC Pipeline

### 1. Training Phase
- Use this dataset to train intrusion detection models
- Validate against test set
- Save trained models for deployment

### 2. Feature Engineering
- Extract same 83 features from live traffic using CICFlowMeter
- Ensure feature consistency with training data

### 3. Real-Time Detection
- Process live network flows
- Apply trained model for classification
- Generate alerts for detected attacks

### 4. Continuous Learning
- Periodically retrain with new attack patterns
- Combine with other datasets (CICIDS2018, UNSW-NB15)
- Implement feedback loop for false positives

## Additional Resources

- **Original Dataset Page**: https://www.unb.ca/cic/datasets/ids-2017.html
- **Improved Version**: https://intrusion-detection.distrinet-research.be/WTMC2021/
- **CICFlowMeter Tool**: https://github.com/ahlashkari/CICFlowMeter
- **Research Papers**: See citations above
- **Kaggle Mirrors**: Search for "CICIDS2017" on Kaggle for preprocessed versions

## License

The dataset is provided for academic and research purposes. Please respect the original creators' work and cite appropriately in any publications.

## Validation Status

- **Dataset Integrity**: VERIFIED
- **Record Count**: 2,100,814 (matches expected)
- **Feature Count**: 84 (83 features + 1 label)
- **Label Distribution**: VALIDATED
- **File Format**: CSV with proper headers
- **Missing Values**: Minimal (addressed in improved version)
- **Last Validated**: October 13, 2025

---

**Dataset prepared for AI-SOC Project**
**THE DIDACT - Strategic Intelligence Division**
*Operation Dataset-Phoenix - COMPLETE*
