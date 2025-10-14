#!/usr/bin/env python3
"""
CICIDS2017 Dataset Validation Script
Analyzes dataset structure, record counts, and label distributions
"""

import csv
import os
from collections import Counter
from pathlib import Path

def analyze_csv_file(filepath):
    """Analyze a single CSV file"""
    print(f"\n{'='*60}")
    print(f"Analyzing: {os.path.basename(filepath)}")
    print(f"{'='*60}")

    labels = []
    row_count = 0
    column_count = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        column_count = len(headers)

        for row in reader:
            row_count += 1
            if 'Label' in row:
                labels.append(row['Label'])

    # Calculate statistics
    label_dist = Counter(labels)

    print(f"Total records: {row_count:,}")
    print(f"Total columns: {column_count}")
    print(f"\nLabel Distribution:")
    for label, count in sorted(label_dist.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / row_count) * 100
        print(f"  {label:20s}: {count:8,} ({percentage:5.2f}%)")

    return {
        'filename': os.path.basename(filepath),
        'row_count': row_count,
        'column_count': column_count,
        'labels': dict(label_dist),
        'headers': headers
    }

def main():
    raw_dir = Path(r"C:\Users\Abdul\Desktop\Bari 2025 Portfolio\AI_SOC\datasets\CICIDS2017\raw")
    csv_files = sorted(raw_dir.glob("*-WorkingHours.csv"))

    if not csv_files:
        print("No CSV files found!")
        return

    all_results = []
    total_records = 0
    all_labels = Counter()

    # Analyze each file
    for csv_file in csv_files:
        result = analyze_csv_file(csv_file)
        all_results.append(result)
        total_records += result['row_count']
        all_labels.update(result['labels'])

    # Print overall summary
    print(f"\n{'='*60}")
    print("OVERALL DATASET SUMMARY")
    print(f"{'='*60}")
    print(f"Total CSV files: {len(csv_files)}")
    print(f"Total records across all files: {total_records:,}")
    print(f"Columns per file: {all_results[0]['column_count']}")
    print(f"\nOverall Label Distribution:")
    for label, count in sorted(all_labels.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_records) * 100
        print(f"  {label:20s}: {count:8,} ({percentage:5.2f}%)")

    print(f"\nColumn Names ({all_results[0]['column_count']} total):")
    for i, header in enumerate(all_results[0]['headers'], 1):
        print(f"  {i:2d}. {header}")

    # Attack categories count
    attack_categories = [label for label in all_labels.keys() if label != 'BENIGN']
    print(f"\nTotal Attack Categories: {len(attack_categories)}")
    print("Attack Types:")
    for attack in sorted(attack_categories):
        print(f"  - {attack}")

if __name__ == "__main__":
    main()
