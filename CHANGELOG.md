# 1.0.0 — 2026-10-20

- First standalone Windows installer and clean source distribution.
- Empty initial database, individual Windows data directory, no preconfigured seller.
- Local HTTPS, password and TOTP, per-user DPAPI credentials.
- Spanish/English interface and 23 Amazon marketplaces across EU, NA and FE.
- Financial overview, product sales, original report downloads and accounting ZIP export.
- Overview defaults to the first day of the current month through today.
- No hosted project backend. Amazon access requires the user's own private SP-API authorization.

Limitations: the Windows installer is not publisher-signed. Tests cover a controlled local installation, not a separate clean Windows machine. Amazon historical data, invoices and restricted permissions depend on the user's account. Financial figures remain provisional where classifications or source data are incomplete.
