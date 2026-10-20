# AMAZON FINANCE OPEN SOURCE

[Español](README.md) · **English**

Publisher: [MartinMS-es](https://github.com/MartinMS-es).

A local Windows 10/11 x64 application for Amazon seller financial reporting using SP-API. Analyze sales, Amazon fees, identified taxes and payouts, archive original reports and export data for accounting. Supports Spanish and English, with 23 marketplaces across EU, NA and FE.

**Every installation starts empty.** No seller, company, transactions, documents, users or credentials are included. Each user creates their own local login and registers and authorizes their own private Amazon application. This is an independent project, not an official Amazon product.

## Install and use

Download the Windows installer from [Releases](https://github.com/MartinMS-es/amazon-finance-open-source/releases). Python and Node are not required by the end user.

Follow the [English installation guide](INSTALLATION-GUIDE-EN.md) or the [Spanish installation guide](GUIA-INSTALACION.md). The installer is not publisher-signed; verify the download source and the release SHA-256 checksums. See the guide for local certificate setup, password/TOTP authentication and Amazon authorization.

Your data remains on your PC. Internet access is required to communicate with Amazon. There is no project-hosted backend or telemetry service.

## Run from source

Requirements: Windows x64, Python 3.12, Node.js 22 and npm.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
npm run typecheck
npm run build
python desktop_app.py
```

The launcher sets up local HTTPS and opens `https://127.0.0.1:18766/`. Keep the control window open while using the app; closing it stops the local server. The app does not open router ports or publish an Internet-facing service.

## Build the Windows installer

Install Inno Setup 6.7.3 from https://jrsoftware.org/isdl.php, activate your Python environment and run:

```powershell
.\scripts\build-windows.ps1 -InnoCompiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

PyInstaller bundles Python, encryption, QR generation and the web assets. The installer is created at `..\Instalador\AMAZON-FINANCE-OPEN-SOURCE-Setup-1.0.0.exe`.

## Tests

```powershell
npm run typecheck
npm run build
npm run test:i18n
python tests/test_global_markets.py
python tests/test_local_security.py
python tests/test_local_auth.py
python tests/test_amazon_connector.py
python tests/test_analysis.py
python tests/test_treasury.py
python tests/test_payment_reconciliation.py
python tests/test_product_sales.py
python tests/test_accountant_export.py
python scripts/audit-release.py
```

Tests use synthetic local data and do not require an Amazon account. The installer has been tested in an isolated local Windows installation, not on a separate clean Windows machine.

## Data, accounting and availability

- Different currencies are never added together.
- Transfers are cash movements, not additional profit.
- Identified taxes do not establish tax payable or prove deductibility; accounting review is required.
- The provisional result excludes product costs, external operating costs and corporate income tax.
- Historical reports, invoices and restricted data depend on Amazon's permissions and retention policies. Complete historical coverage is not guaranteed.
- Lists may be partial. The accounting ZIP uses all saved records matching the selected dates and marketplaces, with warnings for missing data. Missing invoices or amounts are never fabricated.

Private data is stored at `%LOCALAPPDATA%\AmazonFinanceOpenSource\data`. Never upload it, credentials, certificates or private reports to GitHub. DPAPI secrets are tied to the Windows profile; read the installation guide before backing up or moving to another PC.

## License and security

Project code is available under the [MIT license](LICENSE). Third-party components retain their own licenses; see [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt). See [SECURITY.md](SECURITY.md) for security and data-isolation notes and [CHANGELOG.md](CHANGELOG.md) for release notes.
