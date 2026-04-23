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

## Security

The app is designed to run **local-only** and handle PII/PHI (veteran SSN, file numbers, DOB, claim records) responsibly. Threat model and mitigations below.

### What the app enforces

| Defense | Implementation | Blocks |
|---|---|---|
| Loopback-only bind | Server listens on `127.0.0.1:5001` exclusively | Network-level access from other machines |
| Host header check | `before_request` rejects any `Host` that isn't `127.0.0.1:5001` or `localhost:5001` | DNS rebinding attacks |
| Origin check on POSTs | `before_request` rejects cross-origin `Origin` headers | CSRF / malicious webpage POSTs |
| Path traversal guard | `resolve_client_path()` rejects `/`, `\`, `..`, null bytes; `realpath` containment check against `CLIENT_FOLDERS_BASE` | Reading or writing files outside the client folder |
| Forced `Calculations` subfolder | `/api/open-folder` computes the target server-side, never opens user-supplied paths | Arbitrary file open / code execution via `os.startfile` |
| Payload size cap | 10 MB limit on report bodies | DoS via oversized POST |
| Security headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` | Clickjacking, MIME sniffing |
| Waitress WSGI | Production HTTP parser when available, no debug mode possible | Header smuggling / debug-shell exploitation |

### System-level security checklist (do once)

Run these on every workstation that will use the app.

#### Windows

- [ ] **BitLocker on system drive** — run an elevated PowerShell and verify:
  ```powershell
  manage-bde -status C:
  ```
  If `Protection Status: Protection Off`, enable it via **Settings → Privacy & security → Device encryption** (Windows Home) or **Control Panel → BitLocker Drive Encryption** (Pro).

- [x] **Screen lock after idle** — configured by this project's setup. Verify:
  ```powershell
  Get-ItemProperty 'HKCU:\Control Panel\Desktop' | Select-Object ScreenSaveActive, ScreenSaveTimeOut, ScreenSaverIsSecure
  ```
  Should show `1 / 600 / 1` (active, 10-min timeout, require password).

- [ ] **Lock on sleep/wake** — in an elevated PowerShell:
  ```powershell
  powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_NONE CONSOLELOCK 1
  powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_NONE CONSOLELOCK 1
  ```

- [ ] **Windows Defender enabled & up-to-date** — `Get-MpComputerStatus | Select AntivirusEnabled, AntispywareEnabled, RealTimeProtectionEnabled`

- [ ] **OneDrive Known Folder Move off for Downloads** (optional) — keeps downloaded PDFs local only, not auto-synced.

#### Linux

- [ ] **LUKS disk encryption** — usually set at install; verify with `lsblk -f` (look for `crypto_LUKS` on your root partition).

- [ ] **Screen lock after idle** — GNOME: `gsettings set org.gnome.desktop.session idle-delay 600 && gsettings set org.gnome.desktop.screensaver lock-enabled true && gsettings set org.gnome.desktop.screensaver lock-delay 0`. KDE: Settings → Workspace Behavior → Screen Locking.

- [ ] **Firewall allows loopback only** — `ufw status verbose` (default allow on `lo` is fine; deny incoming on everything else).

### Operational hygiene

- [ ] Close the browser tab when you're done with the app (don't leave it open for days).
- [ ] Do not expose `127.0.0.1:5001` through SSH tunnels, `ngrok`, etc. unless you know why.
- [ ] Quarterly: `pip install -U -r requirements.txt` and review the changelog for Flask/Waitress.
- [ ] When sharing screenshots, blur client names and file numbers.

### What's *not* implemented (by design, for a solo local practitioner)

- **User authentication** — adds no real protection if a walk-up attacker can also read the bat file. Relies on Windows screen lock + BitLocker instead.
- **HTTPS on localhost** — loopback traffic never touches the network card; TLS here would be decoration.
- **Audit log** — filesystem `mtime` on `{Client}/Calculations/*.html` already records every report generated.
- **Rate limiting** — single-user local app.

## Disclaimer

This is an **estimation tool only**. Actual VA backpay amounts may differ based on individual circumstances. Consult VA at 1-800-827-1000 or an accredited VSO/attorney for official calculations. Not affiliated with the U.S. Department of Veterans Affairs.

## License

MIT
