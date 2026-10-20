"""Single-user local password + RFC 6238 TOTP. State encrypted by Windows DPAPI."""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import struct
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

from amazon_local import protect


def totp(secret, step, digits=6):
    key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
    digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
    return str(value % (10 ** digits)).zfill(digits)


def match_code(secret, value, last_step=-1, now=None):
    value = str(value).strip()
    if not re.fullmatch(r'\d{6}', value):
        return None
    step = int((time.time() if now is None else now) // 30)
    for candidate in (step, step - 1, step + 1):
        if candidate > last_step and hmac.compare_digest(totp(secret, candidate), value):
            return candidate
    return None


def password_record(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 200:
        raise ValueError('La contraseña debe tener entre 12 y 200 caracteres.')
    if not all((re.search(r'[a-z]', password), re.search(r'[A-Z]', password), re.search(r'\d', password), re.search(r'[^\w\s]', password))):
        raise ValueError('Incluye mayúsculas, minúsculas, números y un carácter especial.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return {'salt': salt.hex(), 'hash': digest.hex()}


def check_password(password, record):
    if not isinstance(password, str) or len(password) > 200:
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(record['salt']), n=16384, r=8, p=1)
    return hmac.compare_digest(digest.hex(), record['hash'])


class LocalAuth:
    def __init__(self, data, sessions):
        self.data, self.sessions = Path(data), sessions
        self.path = self.data / 'local-auth.dpapi'
        self.failure_path = self.data / 'auth-attempts.dpapi'
        self.lock = threading.RLock()
        self.pending = {}

    def read(self, path):
        return json.loads(protect(path.read_bytes(), True)) if path.exists() else None

    def write(self, path, value):
        temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            with temporary.open('xb') as output:
                output.write(protect(json.dumps(value).encode()))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def status(self):
        with self.lock:
            record = self.read(self.path)
            return {'configured': bool(record), 'mfa': bool(record), 'password_min_length': 12, 'max_password_days': 365, 'single_user': True}

    def begin(self, ticket):
        with self.lock:
            if self.path.exists():
                raise ValueError('El acceso ya está configurado. Inicia sesión con contraseña y código.')
            # A launcher ticket is required for initial enrollment, never for normal login.
            self.sessions.exchange(ticket)
            seed = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
            token = secrets.token_urlsafe(32)
            self.pending = {hashlib.sha256(token.encode()).hexdigest(): {'secret': seed, 'expires': time.time() + 600, 'tries': 0}}
            uri = 'otpauth://totp/' + quote('AMAZON FINANCE OPEN SOURCE:Local user', safe='') + '?secret=' + seed + '&issuer=AFOS%20Finance&algorithm=SHA1&digits=6&period=30'
            # Generate QR locally. No external QR service receives the secret.
            vendor = str(Path(__file__).resolve().parent / 'vendor/mfa')
            if vendor not in sys.path:
                sys.path.insert(0, vendor)
            import qrcode
            import qrcode.image.svg
            qr = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=6, border=4)
            image = io.BytesIO()
            qr.save(image)
            return {'enrollment': token, 'secret': seed, 'qr': 'data:image/svg+xml;base64,' + base64.b64encode(image.getvalue()).decode(), 'expires_seconds': 600}

    def setup(self, body):
        with self.lock:
            if self.path.exists():
                raise ValueError('El acceso ya está configurado.')
            key = hashlib.sha256(str(body.get('enrollment', '')).encode()).hexdigest()
            pending = self.pending.get(key)
            if not pending or pending['expires'] < time.time() or pending['tries'] >= 5:
                raise ValueError('Configuración caducada. Vuelve a abrir el acceso directo.')
            pending['tries'] += 1
            record = password_record(body.get('password', ''))
            step = match_code(pending['secret'], body.get('code', ''))
            if step is None:
                raise ValueError('Código incorrecto. Comprueba la hora automática del móvil y usa el código actual.')
            record.update(secret=pending['secret'], last_step=step, password_changed=time.time(), history=[])
            self.write(self.path, record)
            self.pending.clear()
            self.sessions.clear()
            return self.sessions.create()

    def verify(self, body):
        record = self.read(self.path)
        if not record:
            raise ValueError('Primero configura el acceso desde el acceso directo de Windows.')
        attempts = self.read(self.failure_path) or {'failures': 0, 'until': 0}
        if attempts['until'] > time.time():
            raise ValueError('Acceso bloqueado temporalmente. Espera treinta minutos antes de reintentar.')
        step = match_code(record['secret'], body.get('code', ''), record.get('last_step', -1))
        if not check_password(body.get('password', ''), record) or step is None:
            attempts['failures'] += 1
            if attempts['failures'] >= 5:
                attempts.update(failures=0, until=time.time() + 1800)
            self.write(self.failure_path, attempts)
            raise ValueError('Contraseña o código incorrecto. Un código ya usado no puede repetirse.')
        self.write(self.failure_path, {'failures': 0, 'until': 0})
        record['last_step'] = step
        self.write(self.path, record)
        return record

    def login(self, body):
        with self.lock:
            record = self.verify(body)
            if time.time() - record['password_changed'] >= 365 * 86400:
                raise ValueError('Debes renovar la contraseña. Marca Cambiar contraseña y usa un código nuevo.')
            return self.sessions.create()

    def change(self, body):
        with self.lock:
            record = self.verify(body)
            new_password = body.get('new_password', '')
            new_record = password_record(new_password)
            if any(check_password(new_password, previous) for previous in [record] + record.get('history', [])):
                raise ValueError('Usa una contraseña distinta de las cinco anteriores y espera un código nuevo.')
            history = [{'salt': record['salt'], 'hash': record['hash']}] + record.get('history', [])
            record.update(new_record, history=history[:5], password_changed=time.time())
            self.write(self.path, record)
            self.sessions.clear()
            return self.sessions.create()


AUTH_HTML = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Acceso protegido · AMAZON FINANCE OPEN SOURCE</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f5f2;color:#21362a;font:15px/1.55 Arial,sans-serif;min-height:100vh;display:grid;place-items:center}main{width:min(520px,94vw);margin:25px auto;background:#fff;border:1px solid #dfe7df;border-radius:16px;padding:30px;box-shadow:0 20px 80px #24442d10}h1{font-size:27px;line-height:1.2}small,.muted{color:#66776c}label{display:block;margin:16px 0 5px;font-weight:600;font-size:13px}input:not([type=checkbox]){width:100%;padding:12px;border:1px solid #becfbe;border-radius:7px;font:inherit}button{padding:13px 18px;border:0;border-radius:7px;background:#285b3a;color:#fff;font:inherit;cursor:pointer;width:100%;margin-top:18px}button:disabled{opacity:.5}.error{color:#a22525;background:#fff0ee;padding:10px;border-radius:6px}.key{overflow-wrap:anywhere;padding:10px;background:#f1f5ef;user-select:all}#qr{width:230px;max-width:100%;display:block;margin:10px auto}[hidden]{display:none!important}</style>
<main><small>AMAZON FINANCE OPEN SOURCE · SOLO EN ESTE PC</small><h1 id="heading">Acceso protegido</h1><p id="description" class="muted">Comprobando la configuración local…</p><div id="enroll" hidden><p>1. Abre tu aplicación autenticadora en el móvil y añade una cuenta escaneando este QR. También puedes introducir la clave manualmente como cuenta TOTP de 6 dígitos, cada 30 segundos.</p><img id="qr" alt="QR de vinculación de tu autenticador"><details><summary>Mostrar clave para configuración manual</summary><p id="key" class="key"></p></details><p>2. Crea una contraseña exclusiva para AMAZON FINANCE OPEN SOURCE e introduce el código de tu móvil. El QR y la clave son secretos: no los compartas.</p></div>
<form id="form" hidden><label id="password-label" for="password">Contraseña</label><input id="password" type="password" required maxlength="200" autocomplete="current-password"><div id="confirmation" hidden><label for="confirm">Repite la contraseña</label><input id="confirm" type="password" maxlength="200" autocomplete="new-password"></div><div id="change-option" hidden><label><input type="checkbox" id="change"> Cambiar contraseña</label></div><div id="new-password-section" hidden><label for="new-password">Nueva contraseña</label><input id="new-password" type="password" maxlength="200" autocomplete="new-password"><label for="new-confirm">Repite la nueva contraseña</label><input id="new-confirm" type="password" maxlength="200" autocomplete="new-password"></div><label for="code">Código de tu autenticador</label><input id="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" placeholder="6 dígitos" required><p id="policy" class="muted" hidden>Mínimo 12 caracteres, con mayúsculas, minúsculas, números y un carácter especial. Renovación anual. Conserva acceso a tu autenticador: no hay recuperación automática.</p><button id="submit">Entrar</button></form><button id="logout" type="button" hidden>Cerrar sesión actual</button><p id="error" class="error" role="alert" hidden></p><small>La contraseña y el código se verifican en este ordenador. No se usa ningún servicio externo para generar el QR o validar el acceso. Si el autenticador ofrece copia en la nube, esa función es independiente: puedes mantenerla desactivada.</small></main>
<script>
const el=id=>document.getElementById(id);let enrollment=null;const ticket=new URLSearchParams(location.hash.slice(1)).get('ticket');history.replaceState(null,'','/access');
async function call(path,body){const r=await fetch('/api/auth/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const b=await r.json();if(!r.ok)throw Error(b.error||'No se pudo completar la operación.');return b;}
function error(e){el('error').hidden=false;el('error').textContent=e.message;}
async function init(){try{const s=await call('status');el('logout').hidden=!s.authenticated;if(s.configured){el('description').textContent='Introduce tu contraseña y el código del autenticador del móvil.';el('change-option').hidden=false;}else{el('heading').textContent='Configura tu acceso en dos pasos';el('description').textContent='Usuario único: Martín. La configuración se guarda cifrada para tu usuario de Windows.';if(!ticket)throw Error('Para configurar el acceso, cierra esta pestaña y abre el acceso directo AMAZON FINANCE OPEN SOURCE del escritorio.');const e=await call('begin',{ticket});enrollment=e.enrollment;el('qr').src=e.qr;el('key').textContent=e.secret;el('enroll').hidden=false;el('confirmation').hidden=false;el('confirm').required=true;el('policy').hidden=false;el('password').autocomplete='new-password';el('submit').textContent='Activar contraseña y autenticador';}el('form').hidden=false;}catch(e){error(e);}}
el('change').onchange=()=>{const v=el('change').checked;el('new-password-section').hidden=!v;el('new-password').required=v;el('new-confirm').required=v;el('policy').hidden=!v;el('submit').textContent=v?'Guardar nueva contraseña':'Entrar';};
el('logout').onclick=async()=>{try{await call('logout',{});location.replace('/access');}catch(e){error(e);}};
el('form').onsubmit=async event=>{event.preventDefault();el('error').hidden=true;el('submit').disabled=true;try{const password=el('password').value;const code=el('code').value;let path='login',body={password,code};if(enrollment){if(password!==el('confirm').value)throw Error('Las contraseñas no coinciden.');path='setup';body.enrollment=enrollment;}else if(el('change').checked){if(el('new-password').value!==el('new-confirm').value)throw Error('Las nuevas contraseñas no coinciden.');path='change';body.new_password=el('new-password').value;}await call(path,body);location.replace('/');}catch(e){error(e);el('code').value='';}finally{el('submit').disabled=false;}};init();
</script><script src="/i18n-auth.js" defer></script></html>'''.encode('utf-8')
