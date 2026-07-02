import os
import logging
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend
from django.template.loader import render_to_string
from django.utils import timezone

from weasyprint import HTML

logger = logging.getLogger(__name__)


def generer_pdf_devis(devis, request):
    from .models import Devis, LigneDevis

    lignes = devis.lignes_devis.select_related('produit', 'service', 'taux_tva').all()

    montant_lettres = ''
    try:
        from num2words import num2words
        montant_lettres = num2words(
            int(round(devis.total_ttc or 0)), lang='fr'
        ).capitalize() + f" {devis.devise.lower()}."
    except Exception:
        montant_lettres = f"{devis.total_ttc or 0} {devis.devise}"

    context = {
        'devis': devis,
        'lignes': lignes,
        'societe': devis.societe,
        'montant_lettres': montant_lettres,
        'now': timezone.now(),
    }

    html_string = render_to_string('devis/print.html', context)
    weasy_html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

    pdf_dir = os.path.join(settings.MEDIA_ROOT, "devis")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"devis_{devis.pk}.pdf")
    weasy_html.write_pdf(target=pdf_path)

    return pdf_path


def envoyer_devis_email(devis, email_destinataire, message, request):
    from .models import Devis

    societe = devis.societe

    sujet = f"Proforma {devis.display_numero} de {societe.nom}"
    corps = render_to_string('devis/email_body.html', {
        'devis': devis,
        'societe': societe,
        'message_perso': message or '',
        'url_public': request.build_absolute_uri(
            f"/devis/public/{devis.uuid_public}/"
        ),
    })

    pdf_path = generer_pdf_devis(devis, request)

    smtp_email = societe.smtp_email or settings.EMAIL_HOST_USER
    smtp_password = societe.smtp_password or settings.EMAIL_HOST_PASSWORD

    if societe.smtp_email:
        backend = EmailBackend(
            host='smtp.gmail.com',
            port=587,
            username=smtp_email,
            password=smtp_password,
            use_tls=True,
            fail_silently=False,
        )
    else:
        backend = EmailBackend(
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=settings.EMAIL_USE_TLS,
            fail_silently=False,
        )

    email = EmailMessage(
        subject=sujet,
        body=corps,
        from_email=smtp_email,
        to=[email_destinataire],
        connection=backend,
    )
    email.content_subtype = 'html'
    email.attach_file(pdf_path)

    try:
        email.send()
        Devis.objects.filter(pk=devis.pk).update(
            email_envoye=True,
            date_envoi_email=timezone.now(),
        )
        logger.info(f"Devis {devis.display_numero} envoyé par email à {email_destinataire}")
        return True, None
    except Exception as e:
        logger.exception(f"Erreur envoi email devis {devis.pk}")
        return False, str(e)
