# LC-Data: LC area txt to xlsx

A Streamlit app that post-processes the `.txt` peak table exported from Mnova's `exportPeaks.qs` script into a clean Excel table, ready to paste into a report.

**Hosted app:** https://lc-text-to-excel.streamlit.app/

## What it does

- Parses the `Sample Name`, `RT (mins)` and `Area` columns from the uploaded file.
- Pivots the data into one row per sample and one column per retention time.
- Optionally merges peaks that drift slightly between samples (within a configurable RT threshold).
- Optionally recalculates LCAP (%) from the peak areas — the LCAP column in the source file is not used, it is always derived by this app.
- Lets you pick which peaks to include, then export the table to `.xlsx`.
- Can additionally generate an "SP3" table (LCAP + RRT) for a chosen RT range and reference peak.

## Usage

1. Export your peak data from Mnova using `exportPeaks.qs` (see the in-app "Instructions" section for the full Mnova workflow).
2. Upload the resulting `.txt` file to the app.
3. Toggle peak merging and LCAP calculation as needed, then download the table.
4. Optionally set an RT range and reference peak to generate and download an SP3 table.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
