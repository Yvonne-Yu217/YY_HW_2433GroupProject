# Group Project: Healthcare.gov Data Analysis

This repository contains code and notebooks for analyzing healthcare.gov public use files (PUFs). The primary notebook reads multiple CSVs from `data/healthcare.gov` and provides an initial exploratory analysis (heads, missing values, summaries) — including a focused analysis of `Rate_PUF.csv`.

## Dataset
Place the healthcare data files under:

```
data/healthcare.gov/
```

Expected files (already included in this workspace):
- `benefits-and-cost-sharing-puf.csv`
- `Plan_Attributes_PUF.csv`
- `Rate_PUF.csv`
- `service-area-puf.csv`

Note: large CSVs are ignored by default in `.gitignore`; if you want the CSVs tracked in git, update `.gitignore`.

## Files in this repo
- `untitled:Untitled-1.ipynb` — Notebook that reads the 4 CSVs and runs an analysis on `Rate_PUF.csv` (first rows, info, missing percentages, numeric summaries, and top values).
- `.gitignore` — ignores envs, notebook checkpoints, and CSV data files by default.
- `requirements.txt` — Python packages required to run the notebook.
- `LICENSE` — project license (MIT by default).

## How to run
1. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start Jupyter Lab / Notebook and open the notebook:

```bash
jupyter lab
# or
jupyter notebook
```

4. Run the notebook cells. The cell that reads the CSVs may take several seconds (or more) depending on CSV sizes.

## Notes and next steps
- `Rate_PUF.csv` is large (~2.4M rows in the provided copy). For heavier analyses, sample or chunk the data to avoid memory pressure.
- I can add a small script to export compact summaries (CSV/JSON) or add visualizations (histograms, boxplots by state/age) on request.

## License
This project is released under the MIT License — see `LICENSE`.
