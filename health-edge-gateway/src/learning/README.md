# Train the three FL models (cold path)

Pipeline per architecture: **EDA → preprocess → subject split → tune on val → train → evaluate on test**. NEWS2 cut-points are not trained here.

| Architecture | Model | Primary dataset | Model output |
|--------------|--------|-----------------|--------------|
| `arch.snn` | SNN LIF 12→32, leaky readout → 3 | WEDA-Fall (or same-schema synthetic) | sit_stand / walk / fall_like |
| `arch.sqi` | 1-hidden-layer MLP | PPG-DaLiA (label `\|ΔHR\|≤5` bpm) | `p_good` |
| `arch.trend` | 2-hidden-layer MLP | MIMIC-IV NEWS2 (or synthetic) | `p_det`; `L_trend≤2` |

Split **by subject**, never by window. WEDA ids are stratified so val and test both keep young subjects (the only ones with falls).

## Run

From `health-edge-gateway/`:

```text
set PYTHONPATH=src
python scripts/learning/verify_training_pipeline.py
python scripts/learning/train_models.py
python scripts/learning/train_models.py --arch arch.snn --epochs 12
```

If no real dataset is prepared, the pipeline builds synthetic corpora with the same features/labels. Artifacts: `artifacts/learning/arch_snn/` (`eda.md`, `eda.json`, `report.json`, `model.pt`).

## Attach a real dataset

You do **not** have to drop `windows.npz` by hand — use the importer (GitHub / UCI / Kaggle / CSV / local folder):

```text
python scripts/learning/import_dataset.py --list
python scripts/learning/import_dataset.py --dataset weda_fall
python scripts/learning/import_dataset.py --dataset ppg_dalia
python scripts/learning/import_dataset.py --dataset mimic_iv --from-csv exports/vitals.csv
```

Sources and `catalog.local.json`: `data/README.md`.

Or place a ready `windows.npz`:

```text
data/weda_fall/windows.npz     # X (N,100,6), y (N,), subject (N,)
data/ppg_dalia/windows.npz     # X (N,5), y=1 if |HR-HR_ref|<=5
data/mimic_iv/windows.npz      # X (N,13), y=1 if L_news rises after 2h
```

Then:

```text
python scripts/learning/train_models.py --data-dir data --no-synthetic
```

Downloads:

- WEDA-Fall: https://github.com/joaojtmarques/WEDA-FALL
- PPG-DaLiA: https://archive.ics.uci.edu/dataset/495/ppg+DaLiA
- MIMIC-IV: https://physionet.org/content/mimiciv/ (CITI required)

## From the FL client

```text
set FL_TRAIN=1
python src/learning/fl_client.py
```

The client trains locally, encodes weights / `Δw`, and `privacy_guard` rejects unexpected payloads. Updates are **not sent** to a server unless an aggregator is configured.
