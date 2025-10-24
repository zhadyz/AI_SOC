# CICIDS2017 Baseline Models - Evaluation Report
**Generated:** 2025-10-13 18:51:02
**Mission:** OPERATION ML-BASELINE
**Agent:** HOLLOWED_EYES

## Executive Summary

This report presents the performance evaluation of three baseline machine learning models trained on the CICIDS2017 intrusion detection dataset for binary classification (BENIGN vs ATTACK).

## Model Performance Comparison

| Model | Accuracy | Precision | Recall | F1-Score | FP Rate | Inference Time |
|-------|----------|-----------|--------|----------|---------|----------------|
| Random Forest | 99.28% | 99.29% | 99.28% | 99.28% | 0.25% | 0.0008ms |
| Xgboost | 99.21% | 99.23% | 99.21% | 99.21% | 0.09% | 0.0003ms |
| Decision Tree | 99.10% | 99.13% | 99.10% | 99.11% | 0.24% | 0.0002ms |

## Detailed Model Results

### Random Forest

**Classification Metrics:**
- Accuracy: 99.28%
- Precision: 99.29%
- Recall: 99.28%
- F1-Score: 99.28%
- False Positive Rate: 0.25%

**Performance Characteristics:**
- Training Time: 2.57s
- Average Inference Time: 0.0008ms/sample
- Model Size: 2.93MB

**Confusion Matrix:**
```
[[ 8840    22]
 [  282 32858]]
```

- True Negatives (BENIGN correctly identified): 8,840
- False Positives (BENIGN incorrectly flagged as ATTACK): 22
- False Negatives (ATTACK missed): 282
- True Positives (ATTACK correctly detected): 32,858

### Xgboost

**Classification Metrics:**
- Accuracy: 99.21%
- Precision: 99.23%
- Recall: 99.21%
- F1-Score: 99.21%
- False Positive Rate: 0.09%

**Performance Characteristics:**
- Training Time: 0.79s
- Average Inference Time: 0.0003ms/sample
- Model Size: 0.18MB

**Confusion Matrix:**
```
[[ 8854     8]
 [  325 32815]]
```

- True Negatives (BENIGN correctly identified): 8,854
- False Positives (BENIGN incorrectly flagged as ATTACK): 8
- False Negatives (ATTACK missed): 325
- True Positives (ATTACK correctly detected): 32,815

### Decision Tree

**Classification Metrics:**
- Accuracy: 99.10%
- Precision: 99.13%
- Recall: 99.10%
- F1-Score: 99.11%
- False Positive Rate: 0.24%

**Performance Characteristics:**
- Training Time: 5.22s
- Average Inference Time: 0.0002ms/sample
- Model Size: 0.03MB

**Confusion Matrix:**
```
[[ 8841    21]
 [  355 32785]]
```

- True Negatives (BENIGN correctly identified): 8,841
- False Positives (BENIGN incorrectly flagged as ATTACK): 21
- False Negatives (ATTACK missed): 355
- True Positives (ATTACK correctly detected): 32,785

## Best Model Recommendation

**Highest Accuracy:** Random Forest (99.28%)

**Best F1-Score:** Random Forest (99.28%)

**Fastest Inference:** Decision Tree (0.0002ms/sample)

**Recommendation for Production:**

The following model(s) meet all performance targets: Random Forest, Xgboost, Decision Tree

