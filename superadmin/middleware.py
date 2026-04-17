# superadmin/middleware.py — VERSION CORRIGÉE
"""
MIDDLEWARES DE SÉCURITÉ — Système de facturation Burundi
=========================================================

✅  ARCHITECTURE CORRIGÉE :
    - Utilisateur est défini dans superadmin/models.py (plus dans maintenance)
    - Societe est défini dans societe/models.py et importé dans superadmin
    - Le champ FK `utilisateur.societe` pointe vers societe.models.Societe
    - Le module `maintenance` n'est plus nécessaire pour ces middlewares

    Si vous venez d'une ancienne version, exécutez :
        python manage.py makemigrations
        python manage.py migrate

    Le superadmin/views.py a aussi été mis à jour pour lier
    le chef à sa société au moment du setup.

ORDRE DANS settings.py :
--------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'superadmin.middleware.SecurityHeadersMiddleware',       ← 2ème
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'superadmin.middleware.LicenceMiddleware',               ← après Auth
    'superadmin.middleware.RateLimitMiddleware',             ← après Auth
    'superadmin.middleware.AuditLogMiddleware',              ← avant Messages
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
"""

import logging
import time
from django.utils import timezone

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('superadmin.security')


# ═══════════════════════════════════════════════════════════════
#  UTILITAIRES
# ═══════════════════════════════════════════════════════════════

def _get_client_ip(request):
    """IP réelle du client (gère proxies et load balancers)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _is_exempt_path(path, prefixes):
    return any(path.startswith(p) for p in prefixes)


# ═══════════════════════════════════════════════════════════════
#  1. LICENCE MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class LicenceMiddleware(MiddlewareMixin):
    """
    Vérifie à chaque requête que l'utilisateur connecté appartient à
    une société dont la licence est encore valide.

    Si la licence est expirée ou absente → redirect vers /licence-expiree/

    ✅ Architecture :
       - Utilisateur est défini dans superadmin.models avec FK vers societe.models.Societe
       - On récupère la société via utilisateur.societe (FK directe)
       - En cas d'absence du FK, un fallback cherche la première société active
    """

    # URLs toujours accessibles (même sans licence valide)
    EXEMPT_PATHS = [
        '/setup/',
        '/accounts/',
        '/superadmin/',
        '/admin/',
        '/static/',
        '/media/',
        '/licence-expiree/',
        '/favicon.ico',
    ]

    def _get_societe(self, utilisateur):
        """
        Récupère la société liée à l'utilisateur.
        Méthode 1 : via FK utilisateur.societe  (✅ recommandée — définie dans superadmin.models)
        Méthode 2 : via la société active unique (fallback de secours)
        """
        # Méthode 1 — FK directe (la bonne pratique)
        societe = getattr(utilisateur, 'societe', None)
        if societe is not None:
            return societe

        # ⚠️ Méthode 2 — Fallback si societe est None (ex: superuser sans société liée).
        # Cherche la première société active liée à une CleActivation.
        # ✅ Ce bloc peut être supprimé si tous les utilisateurs ont un FK societe renseigné.
        try:
            from societe.models import Societe
            today = timezone.now()
            societe = Societe.objects.filter(
                cles_activation__statut='ACTIVE',
                cles_activation__date_debut__lte=today,
                cles_activation__date_fin__gte=today,
            ).first()
            return societe
        except Exception:
            return None

    def process_request(self, request):
        # 1. Chemins exemptés
        if _is_exempt_path(request.path, self.EXEMPT_PATHS):
            return None

        # 2. Utilisateur non connecté (géré par @login_required)
        if not request.user.is_authenticated:
            return None

        # 3. Superadmin Django → accès total
        if request.user.is_superuser:
            return None

        try:
            societe = self._get_societe(request.user)

            if societe is None:
                logger.warning(
                    f"[LICENCE] Utilisateur {request.user.username} sans société liée "
                    f"— IP: {_get_client_ip(request)}"
                )
                return redirect(settings.LOGIN_URL)

            # 4. Vérifier la licence active
            today = timezone.now()
            cle_active = societe.cles_activation.filter(
                statut='ACTIVE',
                date_debut__lte=today,
                date_fin__gte=today,
            ).first()

            if cle_active is None:
                # ── Diagnostic précis : distinguer "aucune clé" vs "clé expirée" ──
                from superadmin.models import CleActivation

                n_cles = societe.cles_activation.count()

                if n_cles == 0:
                    # ── CAS 1 : société sans aucune clé
                    # Arrive quand la société est créée via Django admin direct
                    # (et non via societe_creer qui appelle creer_essai() auto)
                    # Solution : créer la clé essai automatiquement
                    logger.warning(
                        f"[LICENCE] Société '{societe.nom}' sans aucune clé — "
                        f"création auto d'un essai 14j pour {request.user.username}"
                    )
                    cle_active = CleActivation.creer_essai(
                        societe, cree_par='middleware-auto'
                    )
                    request.societe        = societe
                    request.cle_active     = cle_active
                    request.jours_restants = cle_active.jours_restants
                    request._licence_warning = (
                        f"⚠️ Essai gratuit 14 jours démarré automatiquement. "
                        f"Expire le {cle_active.date_fin.strftime('%d/%m/%Y')}."
                    )
                    return None  # laisser passer

                else:
                    # ── CAS 2 : des clés existent mais aucune n'est ACTIVE
                    derniere_cle = societe.cles_activation.order_by('-date_fin').first()
                    statut_reel  = derniere_cle.statut if derniere_cle else 'AUCUNE'

                    logger.warning(
                        f"[LICENCE] Aucune licence valide (statut={statut_reel}) — "
                        f"Société: '{societe.nom}' — User: {request.user.username} "
                        f"— IP: {_get_client_ip(request)}"
                    )
                    request.session['licence_societe'] = societe.nom
                    request.session['licence_statut']  = statut_reel
                    # ✅ CORRECTION : la vue licence_expiree est sous /superadmin/
                    # L'ancienne valeur par défaut '/licence-expiree/' menait à une 404.
                    # Utiliser le paramètre settings.LICENCE_EXPIRED_URL si défini,
                    # sinon pointer vers l'URL correcte /superadmin/licence-expiree/
                    expired_url = getattr(settings, 'LICENCE_EXPIRED_URL', '/superadmin/licence-expiree/')
                    return redirect(expired_url)

            # 5. Attacher les infos à la requête (pour les templates)
            request.societe        = societe
            request.cle_active     = cle_active
            request.jours_restants = cle_active.jours_restants

            # Avertissement si < 7 jours restants
            if request.jours_restants <= 7:
                request._licence_warning = (
                    f"⚠️ Votre licence expire dans {request.jours_restants} jour(s) "
                    f"(le {cle_active.date_fin.strftime('%d/%m/%Y')})."
                )

        except Exception as e:
            # Ne jamais bloquer l'accès sur une erreur technique du middleware
            logger.error(f"[LICENCE] Erreur inattendue dans le middleware: {e}", exc_info=True)

        return None


# ═══════════════════════════════════════════════════════════════
#  2. RATE LIMIT MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class RateLimitMiddleware(MiddlewareMixin):
    """
    Anti brute-force sur les endpoints sensibles.
    Bloque par IP après N tentatives POST dans une fenêtre glissante.
    Utilise Django Cache (LocMemCache ou Redis via django-redis).
    """

    PROTECTED_ENDPOINTS = {
        '/setup/':           ('ratelimit_setup', 'RATELIMIT_SETUP_MAX',  'RATELIMIT_SETUP_WINDOW'),
        '/accounts/login/':  ('ratelimit_login', 'RATELIMIT_LOGIN_MAX',  'RATELIMIT_LOGIN_WINDOW'),
    }

    def _get_config(self, endpoint_key):
        _, max_key, window_key = self.PROTECTED_ENDPOINTS[endpoint_key]
        defaults = {
            'RATELIMIT_SETUP_MAX':    5,
            'RATELIMIT_LOGIN_MAX':   10,
            'RATELIMIT_SETUP_WINDOW': 300,
            'RATELIMIT_LOGIN_WINDOW': 300,
        }
        return (
            getattr(settings, max_key,    defaults.get(max_key,    10)),
            getattr(settings, window_key, defaults.get(window_key, 300)),
        )

    def process_request(self, request):
        # Seulement sur les POST vers les endpoints protégés
        if request.method != 'POST':
            return None

        matched_endpoint = None
        for endpoint in self.PROTECTED_ENDPOINTS:
            if request.path.startswith(endpoint):
                matched_endpoint = endpoint
                break

        if matched_endpoint is None:
            return None

        ip = _get_client_ip(request)

        # IPs whitelistées (machine locale, admin réseau)
        whitelist = getattr(settings, 'SUPERADMIN_WHITELIST_IPS', ['127.0.0.1', '::1'])
        if ip in whitelist:
            return None

        cache_prefix, _, _ = self.PROTECTED_ENDPOINTS[matched_endpoint]
        max_attempts, window = self._get_config(matched_endpoint)
        cache_key = f"{cache_prefix}:{ip}"

        now      = time.time()
        attempts = cache.get(cache_key, [])

        # Nettoyer les tentatives hors de la fenêtre glissante
        attempts = [t for t in attempts if now - t < window]

        if len(attempts) >= max_attempts:
            wait_seconds = int(window - (now - attempts[0])) if attempts else window
            minutes      = wait_seconds // 60
            seconds      = wait_seconds % 60
            user = request.user.username if request.user.is_authenticated else 'anonyme'
            logger.warning(
                f"[RATE LIMIT] Bloqué: IP={ip} URL={request.path} "
                f"tentatives={len(attempts)} user={user} retry_in={wait_seconds}s"
            )

            # Réponse JSON si requête AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {'error': f"Trop de tentatives. Réessayez dans {minutes}m {seconds}s.",
                     'retry_after': wait_seconds},
                    status=429
                )

            # Réponse HTML
            html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Accès temporairement bloqué</title>
  <style>
    body {{ font-family: Arial, sans-serif; display:flex; justify-content:center;
           align-items:center; height:100vh; background:#f8f9fa; margin:0; }}
    .box {{ text-align:center; background:#fff; padding:40px 50px;
            border-radius:10px; box-shadow:0 4px 20px rgba(0,0,0,.12); max-width:420px; }}
    h2  {{ color:#dc3545; margin-bottom:10px; }}
    p   {{ color:#6c757d; }}
    .timer {{ font-size:1.6em; font-weight:bold; color:#343a40; margin:15px 0; }}
  </style>
</head>
<body>
  <div class="box">
    <h2>🚫 Accès temporairement bloqué</h2>
    <p>Trop de tentatives depuis votre adresse IP.</p>
    <p class="timer">Réessayez dans <strong>{minutes}m {seconds}s</strong></p>
    <p style="font-size:.85em;margin-top:20px;color:#adb5bd;">
      Si vous pensez que c'est une erreur, contactez l'administrateur.
    </p>
  </div>
</body>
</html>"""
            return HttpResponseForbidden(html, content_type='text/html; charset=utf-8')

        # Enregistrer cette tentative
        attempts.append(now)
        cache.set(cache_key, attempts, window)
        return None


# ═══════════════════════════════════════════════════════════════
#  3. SECURITY HEADERS MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Ajoute les en-têtes HTTP de sécurité modernes à chaque réponse :
      - Content-Security-Policy
      - X-Content-Type-Options
      - X-Frame-Options
      - Referrer-Policy
      - Permissions-Policy
      - Strict-Transport-Security (production uniquement)
    """

    def process_response(self, request, response):
        # Sources CSP supplémentaires si vous utilisez des CDN spécifiques
        extra = getattr(settings, 'CSP_EXTRA_SOURCES', '')

        csp = '; '.join([
            f"default-src 'self' {extra}".strip(),
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com",
            "img-src 'self' data: blob:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ])
        response['Content-Security-Policy']  = csp
        response['X-Content-Type-Options']   = 'nosniff'
        response['X-Frame-Options']          = 'DENY'
        response['Referrer-Policy']          = 'strict-origin-when-cross-origin'
        response['Permissions-Policy']       = (
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        )

        # HSTS — uniquement en production (quand DEBUG=False et HTTPS activé)
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

        # Supprimer les en-têtes révélant la techno
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)

        return response


# ═══════════════════════════════════════════════════════════════
#  4. AUDIT LOG MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class AuditLogMiddleware(MiddlewareMixin):
    """
    Journal de sécurité dans logs/security.log :
      - Accès aux zones sensibles (/superadmin/, /setup/, /admin/)
      - Erreurs HTTP 403 / 500 et POST vers 404
      - Patterns d'injection SQL / XSS dans les paramètres
    """

    SENSITIVE_PATHS = ['/setup/', '/superadmin/cles/', '/admin/']

    SUSPICIOUS_PATTERNS = [
        '<script', 'javascript:', 'onerror=', 'onload=',
        "' OR ",   "1=1",         "' --",     "'; DROP",
        '../',     '..\\',        'etc/passwd',
    ]

    def _detect_injection(self, request):
        values = list(request.GET.values())
        if request.method == 'POST':
            safe_skip = {'csrfmiddlewaretoken', 'password', 'chef_password1', 'chef_password2', 'obr_password'}
            values += [v for k, v in request.POST.items() if k not in safe_skip]
        combined = ' '.join(str(v) for v in values).lower()
        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern.lower() in combined:
                return pattern
        return None

    def process_request(self, request):
        ip   = _get_client_ip(request)
        user = request.user.username if request.user.is_authenticated else 'anonyme'

        # Détecter les injections
        bad = self._detect_injection(request)
        if bad:
            logger.error(
                f"[INJECTION] Pattern '{bad}' détecté — "
                f"URL: {request.path} — User: {user} — IP: {ip} — Method: {request.method}"
            )

        # Logger les accès aux zones sensibles
        if _is_exempt_path(request.path, self.SENSITIVE_PATHS):
            logger.info(f"[ACCÈS SENSIBLE] {request.method} {request.path} — User: {user} — IP: {ip}")

        return None

    def process_response(self, request, response):
        ip   = _get_client_ip(request)
        user = request.user.username if request.user.is_authenticated else 'anonyme'

        if response.status_code == 403:
            logger.warning(f"[403] {request.path} — User: {user} — IP: {ip}")
        elif response.status_code == 404 and request.method == 'POST':
            logger.warning(f"[404 POST suspect] {request.path} — User: {user} — IP: {ip}")
        elif response.status_code == 500:
            logger.error(f"[500] {request.path} — User: {user} — IP: {ip}")

        return response
