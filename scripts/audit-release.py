"""Fail if private runtime files, old company identifiers or credentials leak."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
excluded = {'.git', 'node_modules', '__pycache__', 'build', 'dist', '.venv'}
problems = []
count = 0
for file in root.rglob('*'):
    relative = file.relative_to(root)
    if any(part in excluded for part in relative.parts) or not file.is_file():
        continue
    # Unit-test state is temporary and never part of a source release.
    if relative.parts[0] == 'tests' and len(relative.parts) > 1:
        if len(relative.parts) > 2:
            continue
    if file.suffix.lower() in {'.sqlite', '.dpapi', '.pem', '.cer', '.pfx', '.png', '.pdf', '.lnk'} or 'local-data' in relative.parts:
        problems.append(str(relative) + ': private/runtime file')
        continue
    raw = file.read_bytes()
    if file.name == 'audit-release.py':
        continue
    patterns = [bytes.fromhex('79647279'), rb'C:[/\\]Users[/\\][^/\\\s]+', bytes.fromhex('32366234643135642d303736662d343832312d623734392d656238363064323931303533'), rb'Atzr\|[A-Za-z0-9_-]{30,}', rb'amzn1\.oa2-cs\.v1\.[a-zA-Z0-9]{20,}', rb'-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----']
    if any(re.search(pattern, raw, re.I) for pattern in patterns):
        problems.append(str(relative) + ': private identifier or secret signature')
    count += 1
if problems:
    print('\n'.join(problems))
    sys.exit(1)
print(f'PASS: {count} source/web files scanned; no private state or old company identifiers.')
