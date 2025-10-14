"""
CICIDS2017 IDS - SAMPLE TRAINING (Quick Test)

This is a lightweight version that trains on a sample of the data for testing.
Use train_ids_model.py for full production training.

Author: HOLLOWED_EYES
Mission: OPERATION ML-BASELINE
"""

import sys
from pathlib import Path

# Import the main training module
sys.path.append(str(Path(__file__).parent))
from train_ids_model import (
    CICIDSDataLoader, ModelTrainer, generate_evaluation_report,
    DATASET_PATH, MODEL_PATH, EVAL_PATH, time, datetime
)


def main():
    """Run training on 10% sample for quick testing"""
    print("\n" + "="*80)
    print("CICIDS2017 INTRUSION DETECTION - SAMPLE TRAINING")
    print("="*80)
    print(f"Mission: OPERATION ML-BASELINE (Test Run)")
    print(f"Agent: HOLLOWED_EYES")
    print(f"Sample Size: 10% of dataset")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    pipeline_start = time.time()

    # Load 10% sample
    loader = CICIDSDataLoader(
        dataset_path=DATASET_PATH,
        binary_classification=True,
        sample_frac=0.10  # 10% sample (~210k records)
    )

    df = loader.load_all_csvs()
    X, y = loader.preprocess(df)
    X_train, X_test, y_train, y_test = loader.split_data(X, y, test_size=0.2)

    # Train models with smaller configurations
    trainer = ModelTrainer(X_train, X_test, y_train, y_test, loader.label_encoder)

    # Train with reduced complexity for speed
    print("\n" + "="*80)
    print("TRAINING BASELINE MODELS (SAMPLE)")
    print("="*80)

    results = []

    # Random Forest - fewer trees
    rf_model, rf_time = trainer.train_random_forest(n_estimators=50)
    rf_results = trainer.evaluate_model('random_forest', rf_model, rf_time)
    results.append(rf_results)

    # XGBoost - smaller depth
    xgb_model, xgb_time = trainer.train_xgboost(max_depth=6)
    xgb_results = trainer.evaluate_model('xgboost', xgb_model, xgb_time)
    results.append(xgb_results)

    # Decision Tree
    dt_model, dt_time = trainer.train_decision_tree(max_depth=15)
    dt_results = trainer.evaluate_model('decision_tree', dt_model, dt_time)
    results.append(dt_results)

    # Save models
    saved_files = trainer.save_models(loader.scaler, loader.feature_names)

    # Generate report
    report_file = generate_evaluation_report(results, loader.label_encoder, EVAL_PATH)

    pipeline_time = time.time() - pipeline_start

    print("\n" + "="*80)
    print("SAMPLE TRAINING COMPLETE")
    print("="*80)
    print(f"\nTotal execution time: {pipeline_time:.2f}s ({pipeline_time/60:.2f} minutes)")
    print(f"\nNote: This was a 10% sample. Run train_ids_model.py for full training.")
    print(f"\nArtifacts saved:")
    print(f"  Models: {MODEL_PATH}")
    print(f"  Report: {report_file}")
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
