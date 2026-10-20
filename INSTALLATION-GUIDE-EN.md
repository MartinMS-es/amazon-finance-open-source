# AMAZON FINANCE OPEN SOURCE — installation

[Guía en español](GUIA-INSTALACION.md) · **English** · [English README](README.en.md)

1. On Windows 10/11 x64, run `AMAZON-FINANCE-OPEN-SOURCE-Setup-1.0.0.exe`. Choose language and installation directory. Python and Node are included/not required by the end user. The executable has no commercial publisher signature; verify the source and SHA-256 checksum before using it.
2. Open the desktop shortcut. Keep the control window open while using the app. Your browser opens `https://127.0.0.1:18766/`. Closing the control window stops the local server.
3. First launch generates a unique local TLS certificate and adds it to the current Windows user's certificate store. No shared private key is shipped. Create your password and configure a TOTP authenticator. There is no default account, password or sample company.
4. Register and self-authorize your own private Amazon SP-API application in https://solutionproviderportal.amazon.com/sellingpartner/developerconsole . Follow https://developer-docs.amazon/sp-api/docs/registering-your-application . Approval and restricted tax/invoice roles are managed by Amazon.
5. In Amazon Connection select EU, NA or FE and enter your own LWA Client ID, Client Secret and Refresh Token. Credentials are encrypted for your Windows user using DPAPI. Each additional region requires the appropriate authorization. Available marketplaces depend on your seller account.
6. Request financial periods and reports. The initial database is empty. Historical availability and throttling depend on Amazon. Review coverage, errors and unclassified entries before relying on totals.
7. The overview defaults to the first day of the current month through today. Choose English using the language selector. Use Accounting export to download all saved records and available documents for selected dates and marketplaces.

Program files default to `%LOCALAPPDATA%\Programs\AmazonFinanceOpenSource`. Private data stays in `%LOCALAPPDATA%\AmazonFinanceOpenSource\data`. Nothing is hosted by this project. Internet is required to communicate with Amazon.

Close the app before backing up the data directory or updating. DPAPI secrets are tied to the Windows profile; copying files alone does not recover credentials on another PC. Set up a new login and reconnect Amazon there. Never upload the private directory to GitHub.

Uninstall through Windows Settings → Apps. Private data and the local certificate are retained to avoid data loss; remove them manually only after checking your backup. The certificate is named **AMAZON FINANCE OPEN SOURCE local** in the current user's certificate manager (`certmgr.msc`).

Different currencies are never added together. Transfers are cash movements, not extra profit. Identified taxes are not a tax return or proof of deductibility. The provisional result excludes product/external costs and corporate income tax. No guarantee of complete historical invoices or reports is made. This is an independent project, not an official Amazon product.
