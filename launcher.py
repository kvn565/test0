# -*- coding: utf-8 -*-
"""
Lanceur de l'application Facturation (code source protégé, anti-vol).

- Développement :  python launcher.py   (exécution directe depuis les sources)
- Exe figé (PyInstaller onefile) :
    1. Déchiffre le code (bytecode .pyc chiffré, jamais de .py en clair) avec
       la clé embarquée dans build_code/key.bin.
    2. Lance le serveur + ouvre le navigateur en mode application autonome
       (Chrome/Edge --app) + petite fenêtre de contrôle (URL, réseau, arrêt)

Le mot de passe protège la LECTURE du code source :
- il est défini UNE SEULE FOIS lors de la construction (crypter_code.py),
- il est le MÊME sur toutes les machines (par défaut si non précisé),
- la clé de déchiffrement est EMBARQUÉE dans l'exe : plus de saisie de mot de
  passe à chaque lancement, et déplacer l'application la fait fonctionner
  partout avec ce même mot de passe configuré,
- le code est déchiffré dans un dossier temporaire, supprimé à la fermeture.

La base (db.sqlite3), media/ et logs/ vivent dans le dossier de l'exe.
"""
import os
import sys
import json
import base64
import shutil
import socket
import subprocess
import threading
import tempfile
import time
import urllib.request

from cryptography.fernet import Fernet

FROZEN = getattr(sys, 'frozen', False)

DEFAULT_PORT = 8000
MAX_PORT_ATTEMPTS = 10

LOCK = {'fh': None}


def app_dir():
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bundle_dir():
    return os.path.join(getattr(sys, '_MEIPASS', app_dir()), 'build_code')


def deja_en_cours():
    """Renvoie le port d'une instance déjà lancée, ou None."""
    for port in range(DEFAULT_PORT, DEFAULT_PORT + MAX_PORT_ATTEMPTS):
        try:
            with urllib.request.urlopen(
                    'http://127.0.0.1:%d/accounts/login/' % port, timeout=1.5):
                return port
        except Exception:
            continue
    return None


def verrou_application():
    """Une seule instance à la fois (Windows). True si l'instance peut démarrer."""
    try:
        import msvcrt
        lock_path = os.path.join(app_dir(), '.facturation.lock')
        fh = open(lock_path, 'a+')
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            LOCK['fh'] = fh
            return True
        except OSError:
            fh.close()
            return False
    except Exception:
        return True  # pas de verrou possible : on autorise (mode dégradé)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


BROWSER_CANDIDATS = [
    ('Google Chrome',    r'Google\Chrome\Application\chrome.exe',         True),
    ('Microsoft Edge',   r'Microsoft\Edge\Application\msedge.exe',        True),
    ('Brave',            r'BraveSoftware\Brave-Browser\Application\brave.exe', True),
    ('Vivaldi',          r'Vivaldi\Application\vivaldi.exe',              True),
    ('Opera',            r'Opera\launcher.exe',                           False),
    ('Mozilla Firefox',  r'Mozilla Firefox\firefox.exe',                  False),
]


def detect_browsers():
    """Renvoie la liste des navigateurs trouvés : [(nom, chemin, mode_app), ...]."""
    trouves = []
    for env in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA', 'APPDATA'):
        root = os.environ.get(env)
        if not root:
            continue
        for nom, rel, mode_app in BROWSER_CANDIDATS:
            chemin = os.path.join(root, rel)
            if os.path.exists(chemin) and not any(c == chemin for _, c, _ in trouves):
                trouves.append((nom, chemin, mode_app))
    return trouves


def config_path():
    return os.path.join(app_dir(), 'config.json')


def charger_config():
    try:
        with open(config_path(), 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def sauver_config(donnees):
    try:
        with open(config_path(), 'w', encoding='utf-8') as fh:
            json.dump(donnees, fh)
    except Exception:
        pass


def find_browser():
    """Navigateur à utiliser : celui configuré par l'utilisateur, sinon le premier trouvé."""
    cfg = charger_config()
    choisi = cfg.get('navigateur')
    for nom, chemin, mode_app in detect_browsers():
        if chemin == choisi:
            return (nom, chemin, mode_app)
    for nom, chemin, mode_app in detect_browsers():
        return (nom, chemin, mode_app)
    return None


def open_app_window(url, browser=None):
    """Ouvre url dans le navigateur choisi (mode application si supporté)."""
    if browser is None:
        browser = find_browser()
    if browser:
        nom, chemin, mode_app = browser
        try:
            if mode_app:
                subprocess.Popen([
                    chemin,
                    '--app=' + url,
                    '--proxy-bypass-list=<-loopback>',
                ])
            else:
                subprocess.Popen([chemin, url])
            return
        except Exception:
            pass
    import webbrowser
    webbrowser.open(url)


# ─────────────────────────────────────────────────────────────────
#  PROTECTION DU CODE SOURCE (mot de passe unique, défini à la construction)
# ─────────────────────────────────────────────────────────────────
# Le mot de passe protège UNIQUEMENT le code source :
#  - il est défini UNE SEULE FOIS par crypter_code.py (avant la livraison),
#  - il est le MÊME sur toutes les machines (par défaut si non précisé),
#  - la clé de déchiffrement est embarquée (build_code/key.bin) : PAS de
#    demande de mot de passe à chaque lancement ; déplacer l'application la
#    fait fonctionner partout avec ce même mot de passe configuré,
#  - le code est déchiffré dans un dossier temporaire (supprimé à la fermeture).

ITERATIONS = 400000

# Mot de passe de protection (défini par défaut, UNE SEULE FOIS). Doit être le
# même que celui défini dans crypter_code.py.
DEFAULT_PASSWORD = 'jobs_test_1234'


def deriver_cle(password, salt, iterations=ITERATIONS):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=iterations)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8'))))


def nom_pyc(rel):
    """Convertit un chemin .py en chemin bytecode .pyc."""
    return rel[:-3] + '.pyc' if rel.endswith('.py') else rel


def charger_cle(bundle):
    """Renvoie l'objet Fernet de déchiffrement.

    La clé embarquée (build_code/key.bin) est utilisée en priorité ; à défaut,
    on la re-dérive depuis le mot de passe par défaut (compatibilité).
    """
    key_path = os.path.join(bundle, 'key.bin')
    if os.path.exists(key_path):
        with open(key_path, 'r', encoding='ascii') as fh:
            token = fh.read().strip()
        return Fernet(token.encode('ascii'))
    with open(os.path.join(bundle, 'manifest.json'), 'r', encoding='utf-8') as fh:
        manifest = json.load(fh)
    salt = base64.b64decode(manifest['sel'])
    iterations = int(manifest.get('iterations', ITERATIONS))
    return deriver_cle(DEFAULT_PASSWORD, salt, iterations)


def decrypt_bundle(bundle, cipher):
    """Déchiffre tout le code du bundle dans un dossier temporaire.

    None si le bundle est corrompu.
    """
    tmp = None
    try:
        with open(os.path.join(bundle, 'manifest.json'), 'r', encoding='utf-8') as fh:
            manifest = json.load(fh)

        tmp = tempfile.mkdtemp(prefix='facturation_')
        for rel in manifest['files']:
            with open(os.path.join(bundle, rel + '.enc'), 'rb') as fh:
                data = cipher.decrypt(fh.read())
            out = os.path.join(tmp, nom_pyc(rel))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'wb') as fh:
                fh.write(data)
        return tmp
    except Exception:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return None


def show_error(message):
    if not FROZEN:
        print(message)
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Facturation', message)
        root.destroy()
    except Exception:
        pass


def prepare_code():
    """Prépare le code : déchiffre automatiquement avec la clé embarquée.

    Retourne le dossier de code déchiffré, ou None en développement.
    """
    if not FROZEN:
        return None  # dev : exécution depuis les sources

    bundle = bundle_dir()
    manifest_path = os.path.join(bundle, 'manifest.json')
    if not os.path.exists(manifest_path):
        show_error('Fichiers de code introuvables (build_code manquant).')
        sys.exit(1)

    try:
        cipher = charger_cle(bundle)
        code_dir = decrypt_bundle(bundle, cipher)
    except Exception:
        code_dir = None
    if code_dir is None:
        show_error('Impossible de déchiffrer le code (bundle corrompu).')
        sys.exit(1)
    sys.path.insert(0, code_dir)
    return code_dir


def wait_http(url, timeout=30):
    """Attend que le serveur écoute sur le port (connexion TCP acceptée).

    Plus rapide qu'une requête HTTP complète : le navigateur s'ouvre dès que
    le serveur accepte les connexions, le rendu de la page se fait ensuite.
    """
    from urllib.parse import urlparse
    p = urlparse(url)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection((p.hostname, p.port), timeout=2)
            s.close()
            return True
        except Exception:
            time.sleep(0.2)
    return False


def run_migrations():
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', '--noinput', verbosity=0)


def start_server(port):
    from waitress import create_server
    from django.core.wsgi import get_wsgi_application

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facturation.settings')
    application = get_wsgi_application()
    server = create_server(application, host='0.0.0.0', port=port, threads=8)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_elevated(params):
    """Lance netsh avec élévation UAC (runas), sans fenêtre console."""
    try:
        h = ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'netsh', params, None, 0)
        return h > 32
    except Exception:
        return False


def firewall_rule_exists(port):
    rule = 'Facturation App %s' % port
    try:
        r = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=%s' % rule],
            capture_output=True, text=True, creationflags=0x08000000,
        )
        return 'No rules match' not in r.stdout
    except Exception:
        return False


def add_firewall_rule(port, allow_elevation=True):
    rule = 'Facturation App %s' % port
    try:
        existing = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=%s' % rule],
            capture_output=True, text=True, creationflags=0x08000000,
        )
        if 'No rules match' in existing.stdout:
            args = ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                    'name=%s' % rule, 'dir=in', 'action=allow', 'protocol=TCP',
                    'localport=%d' % port]
            r = subprocess.run(args, capture_output=True, text=True, creationflags=0x08000000)
            if r.returncode == 0:
                return True
            # Échec (droits insuffisants) -> élévation UAC ciblée (netsh seul)
            if allow_elevation and not is_admin():
                if run_elevated(' '.join(args[1:])):
                    time.sleep(1)
                    return firewall_rule_exists(port)
            return False
        return True
    except Exception:
        return False


def verifier_os():
    """Limite l'application à Windows 8, 10 ou 11. Renvoie (ok, message)."""
    if sys.platform != 'win32':
        return False, 'Cette application fonctionne uniquement sous Windows 8, 10 ou 11.'
    try:
        v = sys.getwindowsversion()
    except Exception:
        return True, ''
    if (v.major, v.minor) < (6, 2):  # avant Windows 8
        return False, ('Cette application nécessite Windows 8, 10 ou 11.\n'
                       'Système détecté : Windows %d.%d.' % (v.major, v.minor))
    return True, ''


def creer_raccourci():
    """Crée automatiquement les raccourcis Bureau + menu Démarrer (exe figé).

    Appelé au premier lancement : l'icône apparaît sans rien installer.
    """
    if not FROZEN:
        return
    try:
        import ctypes
        exe = os.path.abspath(sys.executable)
        nom = 'Facturation v4.lnk'
        icone = os.path.join(app_dir(), 'icone.ico')
        icone = icone if os.path.exists(icone) else exe + ',0'

        def dossier_special(csidl):
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0:
                return buf.value
            return ''

        chemins = set()
        for csidl in (0x0000, 0x0010):  # Bureau
            d = dossier_special(csidl)
            if d:
                chemins.add(d)
        d = dossier_special(0x0002)  # Menu Démarrer
        if d:
            chemins.add(d)

        def besoin_de_mise_a_jour(chemin):
            if os.path.exists(chemin):
                try:
                    with open(chemin, 'rb') as fh:
                        return exe.encode('utf-16-le') not in fh.read()
                except Exception:
                    return True
            return True

        for dossier in chemins:
            cible = os.path.join(dossier, nom)
            if not besoin_de_mise_a_jour(cible):
                continue
            cmd = (
                "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
                "$s.TargetPath='%s';$s.WorkingDirectory='%s';"
                "$s.IconLocation='%s';$s.Description='Facturation v4';$s.Save()"
                % (cible.replace("'", "''"), exe.replace("'", "''"),
                   os.path.dirname(exe).replace("'", "''"), icone.replace("'", "''"))
            )
            subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                            '-Command', cmd], capture_output=True, timeout=30)
    except Exception:
        pass


def journaliser_etape(base, nom, t0):
    """Écrit le temps cumulé depuis le lancement (logs/startup.log)."""
    try:
        with open(os.path.join(base, 'logs', 'startup.log'), 'a', encoding='utf-8') as fh:
            fh.write('%s : %.1fs\n' % (nom, time.time() - t0))
    except Exception:
        pass


def main():
    t0 = time.time()
    ok, msg = verifier_os()
    if not ok:
        show_error(msg)
        sys.exit(1)

    base = app_dir()
    os.environ['FACTURATION_RUN_DIR'] = base
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facturation.settings')
    for folder in ('logs', 'media'):
        os.makedirs(os.path.join(base, folder), exist_ok=True)

    threading.Thread(target=creer_raccourci, daemon=True).start()

    if not verrou_application():
        port = deja_en_cours()
        if port:
            open_app_window('http://127.0.0.1:%d' % port)
        return

    code_dir = None
    try:
        code_dir = prepare_code()
        journaliser_etape(base, 'code dechiffre', t0)
        run_migrations()
        journaliser_etape(base, 'migrations faites', t0)

        port = DEFAULT_PORT
        server = None
        for attempt in range(MAX_PORT_ATTEMPTS):
            try:
                server = start_server(port)
                break
            except OSError:
                port += 1
        if server is None:
            print('Aucun port disponible')
            sys.exit(1)
        journaliser_etape(base, 'serveur demarre (port %d)' % port, t0)

        local_url = 'http://127.0.0.1:%d' % port
        if wait_http(local_url):
            open_app_window(local_url)
        journaliser_etape(base, 'navigateur ouvert', t0)

        if FROZEN:
            show_control_window(server, port, local_url)
        else:
            print('App lancée : %s' % local_url)
            print('Réseau local : http://%s:%d  (Ctrl+C pour arrêter)' % (lan_ip(), port))
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                server.close()
    except SystemExit:
        raise
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        try:
            with open(os.path.join(base, 'logs', 'erreur.log'), 'a', encoding='utf-8') as fh:
                fh.write('\n==== %s ====\n%s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), tb))
        except Exception:
            pass
        show_error('Erreur au démarrage :\n%s\n\nDétails : logs/erreur.log' % exc)
        sys.exit(1)
    finally:
        if code_dir:
            shutil.rmtree(code_dir, ignore_errors=True)


def show_control_window(server, port, local_url):
    try:
        import tkinter as tk
        from tkinter import ttk
        from tkinter import font as tkfont
    except Exception:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.close()
        return

    ip = lan_ip()
    browsers = detect_browsers()
    cfg = charger_config()
    navigateur_choisi = cfg.get('navigateur')

    def navigateur_selectionne():
        idx = combo.current()
        if idx > 0:
            nom, chemin, mode_app = browsers[idx - 1]
            return (nom, chemin, mode_app)
        return None

    def reopen():
        open_app_window(local_url, navigateur_selectionne())

    def stop():
        server.close()
        root.after(50, root.destroy)

    def firewall():
        if add_firewall_rule(port):
            lbl_reseau.config(text='Réseau autorisé  (http://%s:%d)' % (ip, port), fg='#1a6b3a')
        else:
            lbl_reseau.config(
                text='Autorisation refusée — recliquer « Autoriser réseau »',
                fg='#b71c1c')

    def sur_choix_navigateur(event=None):
        sel = navigateur_selectionne()
        if sel:
            sauver_config({'navigateur': sel[1]})
        else:
            sauver_config({})

    root = tk.Tk()
    root.title('Facturation — Application')
    root.geometry('440x290')
    root.resizable(False, False)
    for candidate in (
        os.path.join(app_dir(), 'icone.ico'),
        os.path.join(getattr(sys, '_MEIPASS', app_dir()), 'assets', 'icone.ico'),
        os.path.join(app_dir(), 'assets', 'icone.ico'),
    ):
        if os.path.exists(candidate):
            try:
                root.iconbitmap(candidate)
            except Exception:
                pass
            break

    title_font = tkfont.Font(family='Segoe UI', size=13, weight='bold')
    lbl_font = tkfont.Font(family='Segoe UI', size=10)
    small_font = tkfont.Font(family='Segoe UI', size=9)

    tk.Label(root, text='Facturation', font=title_font, fg='#0d3c8a').pack(pady=(14, 2))
    tk.Label(root, text='Application lancée en arrière-plan.', font=small_font, fg='#8a9aaa').pack()

    row1 = tk.Frame(root)
    row1.pack(pady=(10, 0))
    tk.Label(row1, text='Ce PC : ', font=lbl_font).pack(side='left')
    tk.Label(row1, text=local_url, font=lbl_font, fg='#0d3c8a', cursor='hand2').pack(side='left')

    # Autorisation réseau : tentative silencieuse (si admin déjà), sinon état affiché
    if not firewall_rule_exists(port):
        add_firewall_rule(port, allow_elevation=False)
    if firewall_rule_exists(port):
        _reseau_txt = 'Réseau autorisé  (http://%s:%d)' % (ip, port)
        _reseau_fg = '#1a6b3a'
    else:
        _reseau_txt = 'Réseau NON autorisé — cliquer « Autoriser réseau »'
        _reseau_fg = '#b71c1c'

    row2 = tk.Frame(root)
    row2.pack(pady=(4, 0))
    tk.Label(row2, text='Réseau : ', font=lbl_font).pack(side='left')
    lbl_reseau = tk.Label(row2, text=_reseau_txt, font=lbl_font, fg=_reseau_fg, cursor='hand2')
    lbl_reseau.pack(side='left')
    lbl_reseau.bind('<Button-1>',
                    lambda e: open_app_window('http://%s:%d' % (ip, port), navigateur_selectionne()))

    noms = ['Par défaut (Windows)'] + [b[0] for b in browsers]
    def index_navigateur():
        for i, (nom, chemin, _) in enumerate(browsers):
            if chemin == navigateur_choisi:
                return i + 1
        return 0

    row3 = tk.Frame(root)
    row3.pack(pady=(4, 0))
    tk.Label(row3, text='Navigateur : ', font=lbl_font).pack(side='left')
    combo = ttk.Combobox(row3, values=noms, state='readonly', width=24)
    combo.current(index_navigateur())
    combo.pack(side='left')
    combo.bind('<<ComboboxSelected>>', sur_choix_navigateur)

    btns = tk.Frame(root)
    btns.pack(pady=(10, 8))
    tk.Button(btns, text='Ouvrir', command=reopen, width=12,
              bg='#0d3c8a', fg='white', relief='flat', font=lbl_font).pack(side='left', padx=4)
    tk.Button(btns, text='Autoriser réseau', command=firewall, width=16,
              bg='#e8f1ff', fg='#0d3c8a', relief='flat', font=lbl_font).pack(side='left', padx=4)
    tk.Button(btns, text='Quitter', command=stop, width=10,
              bg='#fdecea', fg='#b71c1c', relief='flat', font=lbl_font).pack(side='left', padx=4)

    root.protocol('WM_DELETE_WINDOW', stop)
    root.mainloop()


if __name__ == '__main__':
    main()
