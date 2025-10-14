"""
CICIDS2017 Intrusion Detection System - ML Training Pipeline

This script trains baseline machine learning models for network intrusion detection
using the CICIDS2017 dataset. Implements binary classification (Normal vs Attack)
with options for multi-class attack categorization.

Architecture: Random Forest, XGBoost, Decision Tree
Target Metrics: >99% accuracy, <100ms inference latency, <1% false positive rate

Author: HOLLOWED_EYES
Mission: OPERATION ML-BASELINE
Date: 2025-10-13
"""

import os
import sys
import time
import glob
import pickle
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score
)
from sklearn.utils.class_weight import compute_class_weight
import xgboost as xgb

warnings.filterwarnings('ignore')

# Constants
PROJECT_ROOT = Path(r"C:\Users\Abdul\Desktop\Bari 2025 Portfolio\AI_SOC")
DATASET_PATH = PROJECT_ROOT / "datasets" / "CICIDS2017" / "raw"
MODEL_PATH = PROJECT_ROOT / "models"
EVAL_PATH = PROJECT_ROOT / "evaluation"

# Ensure directories exist
MODEL_PATH.mkdir(parents=True, exist_ok=True)
EVAL_PATH.mkdir(parents=True, exist_ok=True)

# Features to drop (non-predictive identifiers)
DROP_COLUMNS = ['Flow ID', 'Src IP', 'Dst IP', 'Timestamp', 'Src Port', 'Dst Port']


class CICIDSDataLoader:
    """Handles loading and preprocessing of CICIDS2017 dataset"""

    def __init__(self, dataset_path, binary_classification=True, sample_frac=None):
        self.dataset_path = Path(dataset_path)
        self.binary_classification = binary_classification
        self.sample_frac = sample_frac
        self.label_encoder = LabelEncoder()
        self.scaler = StandardScaler()
        self.feature_names = None

    def load_all_csvs(self):
        """Load all CSV files from the dataset directory"""
        print("\n" + "="*80)
        print("LOADING CICIDS2017 DATASET")
        print("="*80)

        csv_files = sorted(glob.glob(str(self.dataset_path / "*-WorkingHours.csv")))

        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {self.dataset_path}")

        print(f"\nFound {len(csv_files)} CSV files:")

        dfs = []
        total_records = 0

        for csv_file in csv_files:
            filename = Path(csv_file).name
            print(f"\n  Loading: {filename}...", end=" ", flush=True)

            try:
                # Read CSV with low_memory=False to avoid dtype warnings
                df = pd.read_csv(csv_file, low_memory=False)
                records = len(df)
                total_records += records
                dfs.append(df)

                print(f"OK - {records:,} records")

            except Exception as e:
                print(f"FAILED - Error: {e}")
                continue

        if not dfs:
            raise ValueError("No data loaded successfully")

        print(f"\n  Concatenating datasets...", end=" ", flush=True)
        combined_df = pd.concat(dfs, ignore_index=True)
        print(f"OK - Total: {total_records:,} records")

        # Apply sampling if specified
        if self.sample_frac and self.sample_frac < 1.0:
            print(f"\n  Sampling {self.sample_frac*100}% of data...", end=" ", flush=True)
            combined_df = combined_df.sample(frac=self.sample_frac, random_state=42)
            print(f"OK - {len(combined_df):,} records")

        return combined_df

    def preprocess(self, df):
        """Complete preprocessing pipeline"""
        print("\n" + "="*80)
        print("PREPROCESSING")
        print("="*80)

        initial_shape = df.shape
        print(f"\nInitial shape: {initial_shape[0]:,} rows × {initial_shape[1]} columns")

        # Step 1: Drop non-predictive columns
        print("\n1. Removing non-predictive features...", end=" ", flush=True)
        cols_to_drop = [col for col in DROP_COLUMNS if col in df.columns]
        df = df.drop(columns=cols_to_drop)
        print(f"OK - Dropped {len(cols_to_drop)} columns")

        # Step 2: Handle missing values
        print("2. Handling missing values...", end=" ", flush=True)
        missing_before = df.isnull().sum().sum()
        df = df.dropna()
        missing_after = df.isnull().sum().sum()
        print(f"OK - Removed {missing_before - missing_after} missing values")

        # Step 3: Handle infinite values
        print("3. Replacing infinite values...", end=" ", flush=True)
        df = df.replace([np.inf, -np.inf], np.nan)
        inf_count = df.isnull().sum().sum()
        df = df.fillna(0)
        print(f"OK - Replaced {inf_count} infinite values")

        # Step 4: Convert labels to binary if needed
        print("4. Processing labels...", end=" ", flush=True)

        if 'Label' not in df.columns and ' Label' in df.columns:
            df = df.rename(columns={' Label': 'Label'})

        original_labels = df['Label'].value_counts()
        print(f"\n   Original label distribution:")
        for label, count in original_labels.head(10).items():
            print(f"     {label}: {count:,}")
        if len(original_labels) > 10:
            print(f"     ... and {len(original_labels) - 10} more")

        if self.binary_classification:
            df['Label'] = df['Label'].apply(lambda x: 'BENIGN' if x == 'BENIGN' else 'ATTACK')
            print(f"\n   Converted to binary classification: BENIGN vs ATTACK")

        # Separate features and labels
        X = df.drop('Label', axis=1)
        y = df['Label']

        # Store feature names
        self.feature_names = X.columns.tolist()

        print(f"OK - Label processing complete")
        print(f"\n   Final label distribution:")
        for label, count in y.value_counts().items():
            print(f"     {label}: {count:,} ({count/len(y)*100:.2f}%)")

        # Step 5: Encode labels
        print("\n5. Encoding labels...", end=" ", flush=True)
        y_encoded = self.label_encoder.fit_transform(y)
        print(f"OK - Encoded {len(self.label_encoder.classes_)} classes")

        # Step 6: Feature scaling
        print("6. Scaling features...", end=" ", flush=True)
        X_scaled = self.scaler.fit_transform(X)
        print(f"OK - Scaled {X_scaled.shape[1]} features")

        print(f"\nFinal shape: {X_scaled.shape[0]:,} rows × {X_scaled.shape[1]} columns")

        return X_scaled, y_encoded

    def split_data(self, X, y, test_size=0.2, random_state=42):
        """Split data into train and test sets with stratification"""
        print("\n" + "="*80)
        print("TRAIN-TEST SPLIT")
        print("="*80)

        print(f"\nSplitting: {(1-test_size)*100:.0f}% train, {test_size*100:.0f}% test")
        print("Stratified sampling to preserve class distribution...", end=" ", flush=True)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        print("OK -")
        print(f"\nTrain set: {X_train.shape[0]:,} samples")
        print(f"Test set:  {X_test.shape[0]:,} samples")

        return X_train, X_test, y_train, y_test


class ModelTrainer:
    """Trains and evaluates multiple ML models"""

    def __init__(self, X_train, X_test, y_train, y_test, label_encoder):
        self.X_train = X_train
        self.X_test = X_test
        self.y_train = y_train
        self.y_test = y_test
        self.label_encoder = label_encoder
        self.models = {}
        self.results = {}

    def compute_class_weights(self):
        """Compute class weights for imbalanced dataset"""
        classes = np.unique(self.y_train)
        weights = compute_class_weight('balanced', classes=classes, y=self.y_train)
        return dict(zip(classes, weights))

    def train_random_forest(self, n_estimators=100):
        """Train Random Forest classifier"""
        print("\n" + "="*80)
        print("TRAINING: RANDOM FOREST")
        print("="*80)

        print(f"\nConfiguration:")
        print(f"  n_estimators: {n_estimators}")
        print(f"  class_weight: balanced")
        print(f"  n_jobs: -1 (use all CPU cores)")

        print(f"\nTraining on {self.X_train.shape[0]:,} samples...", end=" ", flush=True)
        start_time = time.time()

        model = RandomForestClassifier(
            n_estimators=n_estimators,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        model.fit(self.X_train, self.y_train)

        train_time = time.time() - start_time
        print(f"OK - Completed in {train_time:.2f}s")

        self.models['random_forest'] = model
        return model, train_time

    def train_xgboost(self, max_depth=10):
        """Train XGBoost classifier"""
        print("\n" + "="*80)
        print("TRAINING: XGBOOST")
        print("="*80)

        # Compute scale_pos_weight for imbalanced data
        class_weights = self.compute_class_weights()
        if len(class_weights) == 2:
            scale_pos_weight = class_weights[1] / class_weights[0]
        else:
            scale_pos_weight = 1.0

        print(f"\nConfiguration:")
        print(f"  max_depth: {max_depth}")
        print(f"  scale_pos_weight: {scale_pos_weight:.2f}")
        print(f"  objective: binary:logistic")

        print(f"\nTraining on {self.X_train.shape[0]:,} samples...", end=" ", flush=True)
        start_time = time.time()

        model = xgb.XGBClassifier(
            max_depth=max_depth,
            scale_pos_weight=scale_pos_weight,
            objective='binary:logistic',
            random_state=42,
            n_jobs=-1,
            verbosity=0
        )
        model.fit(self.X_train, self.y_train)

        train_time = time.time() - start_time
        print(f"OK - Completed in {train_time:.2f}s")

        self.models['xgboost'] = model
        return model, train_time

    def train_decision_tree(self, max_depth=20):
        """Train Decision Tree classifier"""
        print("\n" + "="*80)
        print("TRAINING: DECISION TREE")
        print("="*80)

        print(f"\nConfiguration:")
        print(f"  max_depth: {max_depth}")
        print(f"  class_weight: balanced")

        print(f"\nTraining on {self.X_train.shape[0]:,} samples...", end=" ", flush=True)
        start_time = time.time()

        model = DecisionTreeClassifier(
            max_depth=max_depth,
            class_weight='balanced',
            random_state=42
        )
        model.fit(self.X_train, self.y_train)

        train_time = time.time() - start_time
        print(f"OK - Completed in {train_time:.2f}s")

        self.models['decision_tree'] = model
        return model, train_time

    def evaluate_model(self, model_name, model, train_time):
        """Comprehensive model evaluation"""
        print("\n" + "-"*80)
        print(f"EVALUATION: {model_name.upper()}")
        print("-"*80)

        # Predictions
        print("\nMaking predictions...", end=" ", flush=True)
        start_time = time.time()
        y_pred = model.predict(self.X_test)
        inference_time = time.time() - start_time
        avg_inference_ms = (inference_time / len(self.X_test)) * 1000
        print(f"OK -")

        # Classification metrics
        accuracy = accuracy_score(self.y_test, y_pred)
        precision = precision_score(self.y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(self.y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(self.y_test, y_pred, average='weighted', zero_division=0)

        # Confusion matrix
        cm = confusion_matrix(self.y_test, y_pred)

        # Calculate false positive rate
        if len(cm) == 2:
            tn, fp, fn, tp = cm.ravel()
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        else:
            fpr = None

        # Try to get model size
        try:
            model_bytes = len(pickle.dumps(model))
            model_size_mb = model_bytes / (1024 * 1024)
        except:
            model_size_mb = None

        results = {
            'model_name': model_name,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'confusion_matrix': cm,
            'false_positive_rate': fpr,
            'train_time_sec': train_time,
            'inference_time_sec': inference_time,
            'avg_inference_ms': avg_inference_ms,
            'model_size_mb': model_size_mb,
            'predictions': y_pred
        }

        # Print metrics
        print(f"\nPerformance Metrics:")
        print(f"  Accuracy:   {accuracy*100:6.2f}%")
        print(f"  Precision:  {precision*100:6.2f}%")
        print(f"  Recall:     {recall*100:6.2f}%")
        print(f"  F1-Score:   {f1*100:6.2f}%")
        if fpr is not None:
            print(f"  FP Rate:    {fpr*100:6.2f}%")

        print(f"\nPerformance Characteristics:")
        print(f"  Training time:       {train_time:8.2f}s")
        print(f"  Total inference:     {inference_time:8.2f}s")
        print(f"  Avg inference:       {avg_inference_ms:8.4f}ms/sample")
        if model_size_mb:
            print(f"  Model size:          {model_size_mb:8.2f}MB")

        print(f"\nConfusion Matrix:")
        print(cm)

        self.results[model_name] = results
        return results

    def train_and_evaluate_all(self):
        """Train and evaluate all models"""
        print("\n" + "="*80)
        print("BASELINE MODEL TRAINING PIPELINE")
        print("="*80)

        all_results = []

        # Random Forest
        rf_model, rf_train_time = self.train_random_forest(n_estimators=100)
        rf_results = self.evaluate_model('random_forest', rf_model, rf_train_time)
        all_results.append(rf_results)

        # XGBoost
        xgb_model, xgb_train_time = self.train_xgboost(max_depth=10)
        xgb_results = self.evaluate_model('xgboost', xgb_model, xgb_train_time)
        all_results.append(xgb_results)

        # Decision Tree
        dt_model, dt_train_time = self.train_decision_tree(max_depth=20)
        dt_results = self.evaluate_model('decision_tree', dt_model, dt_train_time)
        all_results.append(dt_results)

        return all_results

    def save_models(self, scaler, feature_names):
        """Save all trained models and preprocessing objects"""
        print("\n" + "="*80)
        print("SAVING MODELS AND ARTIFACTS")
        print("="*80)

        artifacts = [
            ('random_forest', self.models.get('random_forest'), 'random_forest_ids.pkl'),
            ('xgboost', self.models.get('xgboost'), 'xgboost_ids.pkl'),
            ('decision_tree', self.models.get('decision_tree'), 'decision_tree_ids.pkl'),
            ('scaler', scaler, 'scaler.pkl'),
            ('label_encoder', self.label_encoder, 'label_encoder.pkl'),
            ('feature_names', feature_names, 'feature_names.pkl')
        ]

        saved_files = []

        for name, obj, filename in artifacts:
            if obj is not None:
                filepath = MODEL_PATH / filename
                print(f"\nSaving {name}...", end=" ", flush=True)

                try:
                    with open(filepath, 'wb') as f:
                        pickle.dump(obj, f)

                    file_size = filepath.stat().st_size / (1024 * 1024)
                    print(f"OK - {file_size:.2f}MB")
                    saved_files.append(str(filepath))

                except Exception as e:
                    print(f"FAILED - Error: {e}")

        print(f"\nTotal artifacts saved: {len(saved_files)}")
        return saved_files


def generate_evaluation_report(results, label_encoder, output_path):
    """Generate comprehensive markdown evaluation report"""
    print("\n" + "="*80)
    print("GENERATING EVALUATION REPORT")
    print("="*80)

    report = []
    report.append("# CICIDS2017 Baseline Models - Evaluation Report\n")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**Mission:** OPERATION ML-BASELINE\n")
    report.append(f"**Agent:** HOLLOWED_EYES\n\n")

    report.append("## Executive Summary\n\n")
    report.append("This report presents the performance evaluation of three baseline machine learning models ")
    report.append("trained on the CICIDS2017 intrusion detection dataset for binary classification ")
    report.append("(BENIGN vs ATTACK).\n\n")

    # Performance comparison table
    report.append("## Model Performance Comparison\n\n")
    report.append("| Model | Accuracy | Precision | Recall | F1-Score | FP Rate | Inference Time |\n")
    report.append("|-------|----------|-----------|--------|----------|---------|----------------|\n")

    for result in results:
        name = result['model_name'].replace('_', ' ').title()
        acc = result['accuracy'] * 100
        prec = result['precision'] * 100
        rec = result['recall'] * 100
        f1 = result['f1_score'] * 100
        fpr = result['false_positive_rate'] * 100 if result['false_positive_rate'] else 0
        inf_time = result['avg_inference_ms']

        report.append(f"| {name} | {acc:.2f}% | {prec:.2f}% | {rec:.2f}% | {f1:.2f}% | {fpr:.2f}% | {inf_time:.4f}ms |\n")

    report.append("\n")

    # Detailed results per model
    report.append("## Detailed Model Results\n\n")

    for result in results:
        model_name = result['model_name'].replace('_', ' ').title()
        report.append(f"### {model_name}\n\n")

        report.append("**Classification Metrics:**\n")
        report.append(f"- Accuracy: {result['accuracy']*100:.2f}%\n")
        report.append(f"- Precision: {result['precision']*100:.2f}%\n")
        report.append(f"- Recall: {result['recall']*100:.2f}%\n")
        report.append(f"- F1-Score: {result['f1_score']*100:.2f}%\n")
        if result['false_positive_rate']:
            report.append(f"- False Positive Rate: {result['false_positive_rate']*100:.2f}%\n")
        report.append("\n")

        report.append("**Performance Characteristics:**\n")
        report.append(f"- Training Time: {result['train_time_sec']:.2f}s\n")
        report.append(f"- Average Inference Time: {result['avg_inference_ms']:.4f}ms/sample\n")
        if result['model_size_mb']:
            report.append(f"- Model Size: {result['model_size_mb']:.2f}MB\n")
        report.append("\n")

        report.append("**Confusion Matrix:**\n")
        report.append("```\n")
        cm = result['confusion_matrix']
        report.append(str(cm) + "\n")
        report.append("```\n\n")

        # Interpret confusion matrix for binary classification
        if len(cm) == 2:
            tn, fp, fn, tp = cm.ravel()
            report.append(f"- True Negatives (BENIGN correctly identified): {tn:,}\n")
            report.append(f"- False Positives (BENIGN incorrectly flagged as ATTACK): {fp:,}\n")
            report.append(f"- False Negatives (ATTACK missed): {fn:,}\n")
            report.append(f"- True Positives (ATTACK correctly detected): {tp:,}\n")
            report.append("\n")

    # Best model recommendation
    report.append("## Best Model Recommendation\n\n")

    # Find best model based on F1-score and inference time
    best_accuracy = max(results, key=lambda x: x['accuracy'])
    best_f1 = max(results, key=lambda x: x['f1_score'])
    fastest = min(results, key=lambda x: x['avg_inference_ms'])

    report.append(f"**Highest Accuracy:** {best_accuracy['model_name'].replace('_', ' ').title()} ")
    report.append(f"({best_accuracy['accuracy']*100:.2f}%)\n\n")

    report.append(f"**Best F1-Score:** {best_f1['model_name'].replace('_', ' ').title()} ")
    report.append(f"({best_f1['f1_score']*100:.2f}%)\n\n")

    report.append(f"**Fastest Inference:** {fastest['model_name'].replace('_', ' ').title()} ")
    report.append(f"({fastest['avg_inference_ms']:.4f}ms/sample)\n\n")

    report.append("**Recommendation for Production:**\n\n")

    # Check if any model meets all targets
    targets_met = []
    for result in results:
        meets_targets = (
            result['accuracy'] >= 0.99 and
            result['avg_inference_ms'] < 100 and
            (result['false_positive_rate'] or 0) < 0.01
        )
        if meets_targets:
            targets_met.append(result['model_name'])

    if targets_met:
        report.append(f"The following model(s) meet all performance targets: ")
        report.append(", ".join([m.replace('_', ' ').title() for m in targets_met]))
        report.append("\n\n")
    else:
        report.append("Note: Some performance targets were not fully met. Consider:\n")
        report.append("- Hyperparameter tuning\n")
        report.append("- Feature engineering\n")
        report.append("- Ensemble methods\n\n")

    # Save report
    output_file = output_path / "baseline_models_report.md"
    print(f"\nWriting report to: {output_file}...", end=" ", flush=True)

    with open(output_file, 'w') as f:
        f.write(''.join(report))

    print("OK -")
    print(f"Report saved: {output_file}")

    return str(output_file)


def main():
    """Main training pipeline execution"""
    print("\n" + "="*80)
    print("CICIDS2017 INTRUSION DETECTION - ML TRAINING PIPELINE")
    print("="*80)
    print(f"Mission: OPERATION ML-BASELINE")
    print(f"Agent: HOLLOWED_EYES")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    pipeline_start = time.time()

    # Step 1: Load and preprocess data
    loader = CICIDSDataLoader(
        dataset_path=DATASET_PATH,
        binary_classification=True,
        sample_frac=None  # Use full dataset - set to 0.1 for testing
    )

    df = loader.load_all_csvs()
    X, y = loader.preprocess(df)
    X_train, X_test, y_train, y_test = loader.split_data(X, y, test_size=0.2)

    # Step 2: Train and evaluate models
    trainer = ModelTrainer(X_train, X_test, y_train, y_test, loader.label_encoder)
    results = trainer.train_and_evaluate_all()

    # Step 3: Save models
    saved_files = trainer.save_models(loader.scaler, loader.feature_names)

    # Step 4: Generate evaluation report
    report_file = generate_evaluation_report(results, loader.label_encoder, EVAL_PATH)

    # Summary
    pipeline_time = time.time() - pipeline_start

    print("\n" + "="*80)
    print("PIPELINE EXECUTION COMPLETE")
    print("="*80)
    print(f"\nTotal execution time: {pipeline_time:.2f}s ({pipeline_time/60:.2f} minutes)")
    print(f"\nArtifacts saved:")
    print(f"  Models: {MODEL_PATH}")
    print(f"  Evaluation: {report_file}")

    print(f"\n" + "="*80)
    print("MISSION STATUS: SUCCESS")
    print("="*80)

    return results


if __name__ == "__main__":
    try:
        results = main()
        sys.exit(0)
    except Exception as e:
        print(f"\n\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
