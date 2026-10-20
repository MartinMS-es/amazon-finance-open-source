"""HTTPS y sesiones para una instalación privada de Windows."""
import base64
import datetime
import hashlib
import hmac
import ipaddress
import json
import secrets
import ssl
import threading
import time
import uuid
from pathlib import Path
from http.cookies import SimpleCookie
from amazon_local import protect


def secret(data):
    path = Path(data) / 'session-secret.dpapi'
    if not path.exists():
        try:
            with path.open('xb') as output:
                output.write(protect(secrets.token_bytes(32)))
        except FileExistsError:
            pass
    return protect(path.read_bytes(), True)


def ticket(key):
    payload = base64.urlsafe_b64encode(json.dumps({'time': int(time.time()), 'nonce': secrets.token_hex(24)}).encode()).decode()
    return payload + '.' + hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


class Sessions:
    def __init__(self, key):
        self.key, self.used, self.sessions = key, {}, {}
        self.lock = threading.Lock()

    def create(self):
        with self.lock:
            current = time.time()
            self.sessions = {k: expiry for k, expiry in self.sessions.items() if expiry > current}
            session = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(session.encode()).hexdigest()] = current + 1800
            return session

    def clear(self):
        with self.lock:
            self.sessions.clear()

    def revoke(self, cookie):
        try:
            parsed = SimpleCookie(cookie or '')
            value = parsed['__Host-afos_session'].value
            with self.lock:
                self.sessions.pop(hashlib.sha256(value.encode()).hexdigest(), None)
        except (KeyError, ValueError):
            pass

    def exchange(self, value):
        with self.lock:
            current = time.time()
            self.used = {k: expiry for k, expiry in self.used.items() if expiry > current}
            self.sessions = {k: expiry for k, expiry in self.sessions.items() if expiry > current}
            try:
                if len(value)>2048: raise ValueError()
                payload, signature = value.split('.')
                expected = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, expected): raise ValueError()
                issued = json.loads(base64.urlsafe_b64decode(payload))['time']
                if not 0 <= current - issued <= 60 or value in self.used: raise ValueError()
            except Exception:
                raise ValueError('Acceso caducado o no válido. Abre la herramienta desde su acceso directo.')
            self.used[value] = current + 65
            session = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(session.encode()).hexdigest()] = current + 1800
            return session

    def valid(self, cookie):
        try:
            parsed = SimpleCookie(cookie or '')
            value = parsed['__Host-afos_session'].value
            digest = hashlib.sha256(value.encode()).hexdigest()
            with self.lock:
                return self.sessions.get(digest, 0) > time.time()
        except Exception:
            return False


def prepare_tls(data):
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    folder = Path(data) / 'tls'
    folder.mkdir(exist_ok=True)
    cert_path, key_path = folder / 'localhost.pem', folder / 'localhost-key.dpapi'
    if cert_path.exists() or key_path.exists():
        if not (cert_path.exists() and key_path.exists()): raise ValueError('Certificado local incompleto')
        return cert_path
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'AMAZON FINANCE OPEN SOURCE local')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    encrypted = protect(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.write_bytes(encrypted)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / 'localhost.cer').write_bytes(cert.public_bytes(serialization.Encoding.DER))
    return cert_path


def tls_context(data):
    folder = Path(data) / 'tls'
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    temporary = folder / ('key-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as output:
            output.write(protect((folder / 'localhost-key.dpapi').read_bytes(), True))
        context.load_cert_chain(str(folder / 'localhost.pem'), str(temporary))
    finally:
        temporary.unlink(missing_ok=True)
    return context


LOGIN_HTML = b'''<!doctype html><html lang="es"><meta charset="utf-8"><title>Acceso AFOS</title><body><p id="state">Abriendo tu espacio local...</p><script>
const t=new URLSearchParams(location.hash.slice(1)).get('ticket');history.replaceState(null,'','/access');
if(!t){document.getElementById('state').textContent='Abre AMAZON FINANCE OPEN SOURCE desde su acceso directo para iniciar una sesion.';}
else fetch('/api/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticket:t})}).then(async r=>{if(!r.ok)throw Error();location.replace('/');}).catch(()=>document.getElementById('state').textContent='Acceso caducado. Vuelve a abrir el acceso directo.');
</script></body></html>'''
