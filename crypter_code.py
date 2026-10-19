# -*- coding: utf-8 -*-
"""
Protège le code source de l'application (anti-vol de code).

Usage :
    python crypter_code.py ["MotDePasse"]     (si absent -> mot de passe par défaut)

1. Chaque fichier .py est COMPILÉ en bytecode (.pyc) : le source n'est pas lisible.
2. Le bytecode est ensuite CHIFFRÉ avec une clé dérivée du mot de passe
   (PBKDF2-HMAC-SHA256, 400 000 itérations) + un sel aléatoire (Fernet).
3. Résultat dans build_code/ : fichiers .enc (illisibles) + manifest.json
   (liste des fichiers, sel) + key.bin (clé de déchiffrement embarquée).

Le mot de passe est défini UNE SEULE FOIS ici (par défaut si non précisé). Il
est le MÊME sur toutes les machines. La clé de déchiffrement (key.bin) est
embarquée dans l'exe : l'application s'ouvre SANS saisie de mot de passe à
chaque lancement, et déplacer l'application la fait fonctionner partout avec
ce même mot de passe configuré.
"""
import os
import sys
import json
import shutil
import tempfile
import base64
import secrets
import py_compile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'build_code')
ITERATIONS = 400000

# Mot de passe de protection (défini par défaut, UNE SEULE FOIS). Il est le
# MÊME sur toutes les machines et part avec l'application.
DEFAULT_PASSWORD = 'jobs_test_1234'
PACKAGES = [
    'accounts', 'categories', 'clients', 'equipe', 'facturation',
    'facturer', 'fournisseurs', 'produits', 'rapports',
    'services', 'societe', 'stock', 'superadmin', 'taux',
]
SKIP_DIRS = {'__pycache__'}


def collect_files():
    files = []
    for pkg in PACKAGES:
        base = os.path.join(ROOT, pkg)
        if not os.path.isdir(base):
            print('AVERTISSEMENT : package introuvable, ignoré :', pkg)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith('.py'):
                    rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                    files.append(rel.replace(os.sep, '/'))
    return sorted(files)


def compiler_bytecode(src):
    """Compile un fichier .py en bytecode .pyc (renvoie les octets, sans écrire)."""
    with tempfile.NamedTemporaryFile(suffix='.pyc', delete=False) as tf:
        tmp = tf.name
    try:
        py_compile.compile(src, cfile=tmp, doraise=True)
        with open(tmp, 'rb') as fh:
            return fh.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    password = (sys.argv[1] if len(sys.argv) > 1
                else os.environ.get('FACTURATION_MASTER_PASSWORD') or DEFAULT_PASSWORD)
    password = password.strip()
    if len(password) < 4:
        print('ERREUR : le mot de passe doit contenir au moins 4 caractères.')
        sys.exit(1)

    salt = secrets.token_bytes(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=ITERATIONS)
    key_token = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    cipher = Fernet(key_token)

    files = collect_files()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)

    compile_errors = []
    for rel in files:
        src = os.path.join(ROOT, rel)
        dst = os.path.join(OUT, rel + '.enc')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            data = compiler_bytecode(src)
        except Exception as exc:
            compile_errors.append('%s : %s' % (rel, exc))
            continue
        with open(dst, 'wb') as fh:
            fh.write(cipher.encrypt(data))

    if compile_errors:
        print('ERREURS DE COMPILATION :')
        for err in compile_errors:
            print('  -', err)
        sys.exit(1)

    manifest = {
        'files': files,
        'sel': base64.b64encode(salt).decode('ascii'),
        'iterations': ITERATIONS,
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh)

    # Clé de déchiffrement embarquée (key.bin) : l'application s'ouvre sans
    # saisie à chaque lancement et fonctionne partout après déplacement.
    with open(os.path.join(OUT, 'key.bin'), 'w', encoding='ascii') as fh:
        fh.write(key_token.decode('ascii'))

    print('OK : %d fichiers compilés en bytecode puis chiffrés (Fernet/PBKDF2) dans build_code/' % len(files))
    print('Aucun fichier source .py n\'est présent.')
    print('Mot de passe de protection : "%s" (défini une seule fois, identique sur toutes les machines).' % password)
    print('Clé embarquée (key.bin) : plus de demande de mot de passe à chaque lancement.')
    print('Portable : déplacer l\'application conserve ce même mot de passe configuré.')


if __name__ == '__main__':
    main()
