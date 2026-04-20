# VA Disability Backpay Estimator

A single-file, offline-capable web calculator for estimating VA disability backpay, combined ratings, and Special Monthly Compensation (SMC) — built for VA-accredited representatives, VSOs, and veterans.

Open `va-backpay-estimator.html` in any modern browser. No server, no install, no internet required. All calculations happen locally in your browser.

## Features

### Backpay Calculator
- Month-by-month calculation with COLA adjustments (2020–2026 official VA rates)
- Staged ratings (different ratings over different periods)
- Previous rating subtraction for rating increases
- Dependent adjustments: spouse (with/without A&A), children under 18, school-age children 18–23, dependent parents
- CSV export and print-friendly results

### Combined Rating Calculator
- VA whole-person method (not simple addition)
- **Condition labeling** — name each disability (e.g., "PTSD", "Left Knee")
- **Inline What-If** — explore "what if PTSD went from 50% to 70%?" with live delta
- **Raw + rounded** results always visible
- **Bilateral factor** — 10% adjustment for paired extremities (both knees, both arms, etc.)
- Handles 0% service-connected ratings

### SMC Calculator
- Full SMC ladder: K, S, L, L½, M, M½, N, N½, O, R.1, R.2, T
- Barry v. McDonough bump rules (f)(3) half-step and (f)(4) full-step
- K award stacking (up to 3) with O-rate caps for L–O combinations
- Combination escalations (2× SMC-L → SMC-O, etc.)
- Dependent adjustments
- Level reference guide

### SMC Backpay + Representative Fee
- Estimate retroactive SMC compensation from effective date to decision date
- Prior compensation can be a standard VA rating OR a prior SMC level
- **Representative fee calculator** — 20% standard, 25%, 33.33% attorney max, or custom
- Breakdown showing rep fee amount and veteran's net receipt
- Month-by-month table with COLA year transitions
- CSV export including rep fee breakdown

### What-If Comparison Tab
- Compare two rating scenarios side-by-side over any date range
- Independent dates from the main Backpay Calculator
- All ratings 10%–100%

## Rate Data

Official VA compensation rates 2020–2026, effective Dec 1 of prior year through Nov 30.

**Sources:**
- [VA.gov Veteran Compensation Rates](https://www.va.gov/disability/compensation-rates/veteran-rates/)
- [VA.gov Special Monthly Compensation Rates](https://www.va.gov/disability/compensation-rates/special-monthly-compensation-rates/)
- 38 CFR 3.350 (bump rules)
- Barry v. McDonough, 21 Vet.App. 1 (2021)

## Disclaimer

This is an **estimation tool only**. Actual VA backpay amounts may differ based on individual circumstances. Consult VA at 1-800-827-1000 or an accredited VSO/attorney for official calculations. Not affiliated with the U.S. Department of Veterans Affairs.

## Usage

1. Open `va-backpay-estimator.html` in your browser
2. Optionally create a desktop shortcut pointing to the file
3. Works offline — all logic runs client-side

## License

MIT
