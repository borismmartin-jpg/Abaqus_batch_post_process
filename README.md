# Abaqus Batch Post Process (Version 2.0.0-wip)

This repository is now prepared as **Version 2.0.0-wip** (work in progress).

## What is included

- `Inp_generator.html`: Interactive generator for Abaqus `.inp` models (I-beam bending scenarios).
- `run_batch.py`: Batch runner for submitting multiple `.inp` files to Abaqus.
- `Post.py`: Abaqus ODB post-processing script for curve extraction, summary metrics, and stress image export.

## Versioning

- Current WIP version: **2.0.0-wip**
- Source-of-truth version file: `VERSION`

## Prerequisites

1. Abaqus installed and runnable from command line.
2. Python environment compatible with your Abaqus installation.
3. For `run_batch.py`, `tkinter` must be available.
4. For `Post.py`, run inside Abaqus Python environment because it depends on:
   - `abaqus`
   - `abaqusConstants`
   - `odbAccess`

## User Guidelines

## 1) Generate `.inp` files (optional)

1. Open `Inp_generator.html` in a browser.
2. Configure bending type, section size, material, corrosion settings, and mesh settings.
3. Generate and export one or more `.inp` files.
4. Place the generated `.inp` files into a working folder.

## 2) Run batch analysis

Update the settings at the top of `run_batch.py`:

- `ABAQUS_CMD`: Full path to `abaqus.bat` (Windows) or Abaqus command wrapper.
- `cpus`: Number of CPU cores per job.
- `memory`: Abaqus memory setting (for example `"90%"`).
- `run_in_background`:
  - `False` (recommended): sequential blocking run.
  - `True`: launches jobs in background.

Then run:

```bash
python run_batch.py
```

When prompted, choose the folder containing `.inp` files.

Behavior:
- Script scans all `.inp` files in the selected folder.
- If a corresponding `.sta` file already contains `COMPLETED SUCCESSFULLY`, the job is skipped.
- Otherwise, the job is submitted with the configured resources.

## 3) Post-process ODB results

Update `Post.py` user settings:

- `folder_path`: Directory containing `.odb` files.
- `step_name`: Analysis step to read.
- `target_load`: Reference load used for LPF to load conversion.
- `peeq_threshold`: First-yield detection threshold.
- Output controls:
  - `output_summary`
  - `output_curves_folder`
  - `output_images_folder`
  - `target_LPFs_for_image`

Run from Abaqus command line (example):

```bash
abaqus cae noGUI=Post.py
```

Outputs:
- `SUMMARY_RESULTS.csv`: one-row-per-job summary.
- `CURVES/*.csv`: displacement-load curves.
- `IMAGES/*.png`: stress contour images at requested LPF values.

## Typical workflow

1. Create/collect `.inp` files.
2. Run `run_batch.py` to execute all jobs.
3. Confirm `.odb` files are generated.
4. Run `Post.py` for metric extraction and report generation.
5. Archive inputs, outputs, and settings for traceability.

## Notes

- `Post.py` assumes specific node/element set names (`MIDSPAN_SET` and `ELSETS`). Ensure your models contain these sets, or adjust the names in script settings.
- The post-process script falls back to first analysis step when `step_name` is not found.
- Stress image export relies on Abaqus session/viewport APIs and therefore must be executed in Abaqus context.
