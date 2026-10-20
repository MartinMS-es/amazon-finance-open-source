# Security and data isolation

The desktop application serves HTTPS on loopback only. Passwords and TOTP protect application sessions. Amazon credentials and private keys use Windows DPAPI for the current user. Each installation generates its own certificate and initial database. No telemetry or project cloud backend is configured.

Use an individual Windows account, keep Windows updated, lock the screen and protect the device and backups. Authentication inside the app does not protect an already compromised Windows session. A local app is still subject to Amazon's SP-API security and access requirements.

Do not include account data, credentials, screenshots of tokens or original private reports in public issues. Report problems with synthetic examples and sanitized error messages. The repository contains no shared Amazon authorization.

The installer intentionally preserves user data on uninstall. Read the installation guide for data paths, certificate handling and recovery limitations.
