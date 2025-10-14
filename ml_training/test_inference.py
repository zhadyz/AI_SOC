"""
Test script for IDS inference API

Tests the trained models with sample predictions and validates performance.

Author: HOLLOWED_EYES
Mission: OPERATION ML-BASELINE
"""

import pickle
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(r"C:\Users\Abdul\Desktop\Bari 2025 Portfolio\AI_SOC")
MODEL_PATH = PROJECT_ROOT / "models"


def test_model_loading():
    """Test if all models can be loaded"""
    print("="*80)
    print("TEST: MODEL LOADING")
    print("="*80)

    models = ['random_forest_ids.pkl', 'xgboost_ids.pkl', 'decision_tree_ids.pkl']
    artifacts = ['scaler.pkl', 'label_encoder.pkl', 'feature_names.pkl']

    all_files = models + artifacts
    loaded = []
    failed = []

    for filename in all_files:
        filepath = MODEL_PATH / filename
        print(f"\nLoading {filename}...", end=" ")

        if not filepath.exists():
            print(f"FAILED - File not found")
            failed.append(filename)
            continue

        try:
            with open(filepath, 'rb') as f:
                obj = pickle.load(f)
            print(f"OK - Success")
            loaded.append(filename)
        except Exception as e:
            print(f"FAILED - Error: {e}")
            failed.append(filename)

    print(f"\n\nResults:")
    print(f"  Loaded: {len(loaded)}/{len(all_files)}")
    print(f"  Failed: {len(failed)}/{len(all_files)}")

    return len(failed) == 0


def test_sample_predictions():
    """Test predictions with sample data"""
    print("\n" + "="*80)
    print("TEST: SAMPLE PREDICTIONS")
    print("="*80)

    # Load artifacts
    with open(MODEL_PATH / 'random_forest_ids.pkl', 'rb') as f:
        rf_model = pickle.load(f)

    with open(MODEL_PATH / 'scaler.pkl', 'rb') as f:
        scaler = pickle.load(f)

    with open(MODEL_PATH / 'label_encoder.pkl', 'rb') as f:
        label_encoder = pickle.load(f)

    with open(MODEL_PATH / 'feature_names.pkl', 'rb') as f:
        feature_names = pickle.load(f)

    print(f"\nModel: Random Forest")
    print(f"Features: {len(feature_names)}")
    print(f"Classes: {label_encoder.classes_}")

    # Create sample feature vectors
    samples = [
        ("Normal traffic (all zeros)", np.zeros(len(feature_names))),
        ("Normal traffic (small values)", np.random.uniform(0, 1, len(feature_names))),
        ("Suspicious traffic (high values)", np.random.uniform(10, 100, len(feature_names))),
        ("Attack traffic (extreme values)", np.random.uniform(1000, 10000, len(feature_names)))
    ]

    print(f"\n{'Sample':<35} {'Prediction':<15} {'Confidence':<12} {'Time (ms)':<12}")
    print("-" * 80)

    import time

    for name, features in samples:
        # Scale features
        X = features.reshape(1, -1)
        X_scaled = scaler.transform(X)

        # Predict
        start = time.time()
        y_pred = rf_model.predict(X_scaled)[0]
        y_proba = rf_model.predict_proba(X_scaled)[0]
        inference_time = (time.time() - start) * 1000

        # Decode
        predicted_class = label_encoder.inverse_transform([y_pred])[0]
        confidence = np.max(y_proba)

        print(f"{name:<35} {predicted_class:<15} {confidence:<12.4f} {inference_time:<12.4f}")

    return True


def test_api_endpoint():
    """Test if API can start (doesn't actually start server)"""
    print("\n" + "="*80)
    print("TEST: API ENDPOINT VALIDATION")
    print("="*80)

    try:
        # Just import to check if it's valid
        from inference_api import app, load_models

        print("\nOK - API module imports successfully")
        print("OK - FastAPI app created")

        # Try to load models
        load_models()
        print("OK - Models loaded for API")

        return True

    except Exception as e:
        print(f"\nFAILED - Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("INFERENCE API TESTING SUITE")
    print("="*80)
    print("Mission: OPERATION ML-BASELINE")
    print("Agent: HOLLOWED_EYES")
    print("="*80)

    tests = [
        ("Model Loading", test_model_loading),
        ("Sample Predictions", test_sample_predictions),
        ("API Endpoint", test_api_endpoint)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\nFAILED - Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "OK - PASSED" if result else "FAILED - FAILED"
        print(f"{test_name:<30} {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nOK - ALL TESTS PASSED")
        return 0
    else:
        print(f"\nFAILED - {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
