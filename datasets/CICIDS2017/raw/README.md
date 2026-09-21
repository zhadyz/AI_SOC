# Dataset provenance

The old `MachineLearningCSV.md5` was an HTML 404 response, not a checksum; it has
been removed. Do not use it to validate data.

The reproducible multiclass benchmark uses `GeneratedLabelledFlows.zip` from the
[bencorn CICIDS2017 mirror](https://huggingface.co/datasets/bencorn/CICIDS2017/blob/main/csvs/GeneratedLabelledFlows.zip).
The original dataset and citation instructions are available from
[UNB](https://www.unb.ca/cic/datasets/ids-2017.html). The mirror is not an official
UNB endpoint. Its downloaded archive matches the mirror's LFS SHA-256:

`7bdbef286f8893f31c6db12105fa097fa5c2dcc6733179037a08129d150ea27a`

`scripts/benchmark_models.py` verifies this hash before opening the archive,
normalizes the documented CICFlowMeter column aliases, and requires every one of
the serving model's 77 features. The separate MachineLearningCSV variant omits
Protocol and cannot meet that contract without inventing measurements.

Large archives/CSVs are excluded from Git. This installation keeps downloads in
`../../work/dataset/csvs` relative to the repository and the trained research bundle
in `models/bundles/cicids2017-multiclass-20260904`.
