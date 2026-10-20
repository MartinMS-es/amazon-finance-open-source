"""Windows desktop launcher; every installation starts with its own empty state."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading
import urllib.request
import webbrowser

NAME = 'AMAZON FINANCE OPEN SOURCE'
PORT = 18766
URL = f'https://127.0.0.1:{PORT}/'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    data = (args.data_dir or Path(os.environ['LOCALAPPDATA']) / 'AmazonFinanceOpenSource' / 'data').resolve()
    if args.smoke_test and not args.data_dir:
        raise ValueError('A separate --data-dir is required for a smoke test')
    data.mkdir(parents=True, exist_ok=True)
    os.environ['AFOS_DATA_DIR'] = str(data)
    os.environ['AFOS_SECURE'] = '1'
    os.environ['AFOS_PORT'] = str(PORT)
    # Never inherit Amazon credentials from the developer or another application.
    for key in list(os.environ):
        if key.startswith('AMAZON_'):
            del os.environ[key]
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\AmazonFinanceOpenSourceDesktop')
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, 'La aplicación ya está abierta. / The application is already running.', NAME, 0)
        return
    if not args.smoke_test:
        # Limit the new private data folder to this user, SYSTEM and administrators.
        sid = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], creationflags=0x08000000).decode().split(',')[-1].strip().strip('"')
        subprocess.run(['icacls', str(data), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'], check=True, capture_output=True, creationflags=0x08000000)
    from local_security import prepare_tls
    prepare_tls(data)
    if not args.smoke_test:
        cert = data / 'tls' / 'localhost.cer'
        subprocess.run(['certutil', '-user', '-addstore', 'Root', str(cert)], check=True, capture_output=True, creationflags=0x08000000)
    (data / 'secure-enabled').touch()
    import local_server as backend
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(('127.0.0.1', PORT), backend.Handler)
    server.socket = backend.tls_context(data).wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if args.smoke_test:
        context = ssl.create_default_context(cafile=str(data / 'tls' / 'localhost.pem'))
        def get(path):
            with urllib.request.urlopen(URL + path, context=context, timeout=15) as response:
                return response.read()
        health = json.loads(get('api/health'))
        assert health['local'] and health['secure']
        assert b'AMAZON FINANCE OPEN SOURCE' in get('access')
        assert get('app.js')
        with backend.conn() as database:
            assert database.execute('select count(*) from records').fetchone()[0] == 0
            assert database.execute('select count(*) from documents').fetchone()[0] == 0
        assert backend.AMAZON.configured_regions() == []
        assert not (data / 'local-auth.dpapi').exists()
        (data / 'smoke-result.json').write_text(json.dumps({'https':True,'blankDatabase':True,'noAmazonCredentials':True,'assets':True}),encoding='utf-8')
        server.shutdown()
        server.server_close()
        return
    backend.AMAZON.start()
    import tkinter as tk
    root = tk.Tk()
    root.title(NAME)
    root.geometry('560x220')
    root.resizable(False, False)
    tk.Label(root, text=NAME, font=('Segoe UI', 15, 'bold')).pack(pady=(24, 12))
    tk.Label(root, text='Aplicación local activa · Local application running\nTus datos permanecen en este PC / Your data stays on this PC', font=('Segoe UI', 10)).pack()
    tk.Button(root, text='Abrir aplicación / Open application', command=lambda:webbrowser.open(URL), width=40).pack(pady=15)
    def close():
        server.shutdown()
        server.server_close()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    webbrowser.open(URL)
    root.mainloop()
    ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if '--smoke-test' in sys.argv:
            try:
                destination = Path(sys.argv[sys.argv.index('--data-dir') + 1])
                import traceback
                (destination / 'smoke-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            finally:
                sys.exit(1)
        ctypes.windll.user32.MessageBoxW(None, str(error), NAME, 0x10)
        sys.exit(1)
