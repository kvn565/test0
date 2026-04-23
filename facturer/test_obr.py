import requests
from datetime import datetime
import warnings

# ─── IGNORER WARNING HTTPS ──────────────────────────────
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ─── CONFIG ──────────────────────────────
obr_system_id = "ws400286975001136"
obr_password = r"two5\N9M"
access_username = obr_system_id

client_nif = "4002052753"
company_nif = "4002869750"

company_name = "BLANSA CAMPANY"
client_name = "BURUNDI JOBS GROUP"

# ─── URLS OBR ──────────────────────────────
login_url = "https://ebms.obr.gov.bi:9443/ebms_api/login/"
invoice_url = "https://ebms.obr.gov.bi:9443/ebms_api/addInvoice_confirm/"

# ─── LOGIN ──────────────────────────────
login_payload = {
    "username": access_username,
    "password": obr_password
}

login_resp = requests.post(login_url, json=login_payload, verify=False)
login_data = login_resp.json()

if not login_data.get("success"):
    raise Exception(f"Erreur login OBR : {login_data.get('msg')}")

token = login_data['result']['token']
print("✅ Connexion réussie")

# ─────────────────────────────────────────
# GENERATION FACTURE
# ─────────────────────────────────────────

now = datetime.now()

invoice_number = "0001/2026"
invoice_date = now.strftime("%Y-%m-%d %H:%M:%S")

# ─── IDENTIFIANT FACTURE (FORMAT OBR CORRECT) ──────────────────────────────
invoice_identifier = f"{company_nif}/{obr_system_id}/{now.strftime('%Y%m%d%H%M%S')}/{invoice_number}"

print("Identifiant facture :", invoice_identifier)

# ─────────────────────────────────────────
# CALCUL MONTANTS
# ─────────────────────────────────────────

quantity = 1
price = 10000

price_nvat = quantity * price
vat = price_nvat * 0.18
price_wvat = price_nvat + vat
total_amount = price_wvat

# ─────────────────────────────────────────
# PAYLOAD FACTURE
# ─────────────────────────────────────────

payload = {

    "invoice_number": invoice_number,
    "invoice_date": invoice_date,
    "invoice_type": "FN",

    "tp_type": "1",
    "tp_name": company_name,
    "tp_TIN": company_nif,
    "tp_trade_number": "00001",
    "tp_postal_number": "0000",
    "tp_phone_number": "62000000",

    "tp_address_province": "GITEGA",
    "tp_address_commune": "GITEGA",
    "tp_address_quartier": "MAGARAMA",
    "tp_address_avenue": "AVENUE PRINCIPALE",
    "tp_address_number": "",

    "vat_taxpayer": "1",
    "ct_taxpayer": "0",
    "tl_taxpayer": "0",

    "tp_fiscal_center": "DGC",
    "tp_activity_sector": "SERVICE MARCHAND",
    "tp_legal_form": "SU",

    "payment_type": "1",
    "invoice_currency": "BIF",

    "customer_name": client_name,
    "customer_TIN": client_nif,
    "customer_address": "BUJUMBURA",

    "vat_customer_payer": "1",

    "cancelled_invoice_ref": "",
    "invoice_ref": "",
    "cn_motif": "",

    "invoice_identifier": invoice_identifier,

    "invoice_items": [
        {
            "item_designation": "SERVICE INFORMATIQUE",
            "item_quantity": str(quantity),
            "item_price": str(price),

            "item_ct": "0",
            "item_tl": "0",
            "item_ott_tax": "0",
            "item_tsce_tax": "0",

            "item_price_nvat": str(price_nvat),
            "vat": str(vat),

            "item_price_wvat": str(price_wvat),
            "item_total_amount": str(total_amount)
        }
    ]
}

# ─────────────────────────────────────────
# ENVOI FACTURE
# ─────────────────────────────────────────

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.post(
    invoice_url,
    headers=headers,
    json=payload,
    verify=False
)

# ─────────────────────────────────────────
# REPONSE OBR
# ─────────────────────────────────────────

print("Status HTTP :", response.status_code)

try:
    resp = response.json()
    print("Réponse OBR :", resp)
except:
    print("Réponse brute :", response.text)