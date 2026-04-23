# VA Backpay Estimator

A local Flask web app for estimating VA disability backpay, combined ratings, and Special Monthly Compensation (SMC) — built for VA-accredited representatives, VSOs, and attorneys. Integrates with the same `ClientFolders` layout as [va-form-filler](https://github.com/jerome403/va-form-filler) so calculations save directly into a client's folder.

## Features

### Calculators
- **Backpay Calculator** — Month-by-month COLA-adjusted estimation (2020–2026), staged ratings, dependents (spouse+A&A, children under 18, school-age 18–23, parents), CSV export.
- **Combined Rating Calculator** — VA whole-person method with bilateral factor, condition labels, inline what-if dropdowns, raw and rounded % always visible.
- **SMC Calculator** — Full SMC ladder (K, S, L, L½, M, M½, N, N½, O, R.1, R.2, T) with Barry v. McDonough bumps, K stacking, and combination escalations.
- **SMC Backpay + Representative Fee** — Retroactive SMC transition math (e.g., 100% → R.1) with attorney/VSO fee breakdown (20% standard, 25%, 33.33% attorney max, or custom).
- **What-If Comparison** — Two rating scenarios side-by-side over any date range.

### Client Folder Integration
- Pulls client list from the shared `ClientFolders` parent directory (same one va-form-filler uses).
- Auto-reads `Client_Data.txt` to display the veteran's name and VA file number in the header.
- "Save to Client Folder" button on every result panel writes a self-contained HTML report to `{ClientFolder}/Calculations/{type}_{timestamp}.html`. Open the saved HTML in a browser and Print → Save as PDF for a final filing copy.
- "Open Folder" button launches Explorer on the client's Calculations folder.

## Stack

- Python 3.12 + Flask (≥3.0)
- Vanilla HTML/CSS/JS frontend (single-page, all calculation logic runs in-browser)
- No database — clients are literally the subfolders in `ClientFolders`

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5001.

**On Windows:** double-click `Start_VA_Backpay_Estimator.bat`.

## Client Folders convention

By default the app looks for `../ClientFolders` (sibling to the project directory). Override with an environment variable:

```bash
set CLIENT_FOLDERS_BASE=C:\path\to\your\ClientFolders
python app.py
```

Each client folder should be named for the client (e.g., `Smith, John`). Reports are saved to `{ClientFolder}/Calculations/`. If the app finds a `Client_Data.txt` inside the client folder (written by va-form-filler), it reads `FirstName`, `LastName`, `FileNumber`, and `DOB*` fields to populate the report header.

## Project layout

```
va-backpay-estimator/
├── app.py                          # Flask backend (client API + report save)
├── templates/
│   └── index.html                  # Calculator UI (all tabs + JS logic)
├── static/                         # (empty — all styles inline in index.html)
├── requirements.txt
├── Start_VA_Backpay_Estimator.bat  # Windows launcher
└── README.md
```

## Rate Data

Official VA compensation rates 2020–2026, effective Dec 1 of prior year through Nov 30.

**Sources:**
- [VA.gov Veteran Compensation Rates](https://www.va.gov/disability/compensation-rates/veteran-rates/)
- [VA.gov Special Monthly Compensation Rates](https://www.va.gov/disability/compensation-rates/special-monthly-compensation-rates/)
- 38 CFR 3.350 (bump rules)
- *Barry v. McDonough*, 21 Vet.App. 1 (2021)

## Disclaimer

This is an **estimation tool only**. Actual VA backpay amounts may differ based on individual circumstances. Consult VA at 1-800-827-1000 or an accredited VSO/attorney for official calculations. Not affiliated with the U.S. Department of Veterans Affairs.

## License

MIT
