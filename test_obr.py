import requests
from datetime import datetime

# ─── CONFIG ──────────────────────────────
obr_system_id = "ws400286975001136"   # fourni par OBR
obr_password = r"two5\N9M"            # fourni par OBR
access_username = obr_system_id
client_nif = "4002052753"             # NIF du client à tester

# URLs OBR
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

# ─── GENERATION IDENTIFIANT FACTURE ──────────────────────────────
today = datetime.now()
num_facture_seq = "0001"  # pour test
identifiant_facture = f"FN/{obr_system_id}/{client_nif}/{today.strftime('%d%m')}/{num_facture_seq}"
print("Identifiant généré :", identifiant_facture)

# ─── PAYLOAD FACTURE ──────────────────────────────
payload = {
    "invoice_number": f"FAC-{today.strftime('%Y%m%d')}-001",
    "invoice_date": today.strftime("%Y-%m-%d %H:%M:%S"),
    "tp_type": "2",
    "tp_name": "SOCIETE TEST",
    "tp_TIN": "400286975001136",          # NIF société correcte
    "tp_trade_number": "12345678",
    "tp_postal_number": "1234",
    "tp_phone_number": "79999999",
    "tp_address_province": "Bujumbura",
    "tp_address_commune": "Mukaza",
    "tp_address_quartier": "Quartier Test",
    "tp_address_avenue": "Avenue Test",
    "tp_address_number": "12",
    "vat_taxpayer": "1",
    "ct_taxpayer": "1",
    "tl_taxpayer": "0",
    "tp_fiscal_center": "001",
    "tp_activity_sector": "001",
    "tp_legal_form": "SARL",
    "payment_type": "1",
    "customer_name": "CLIENT TEST",
    "customer_TIN": client_nif,
    "customer_address": "Rue Test 123",
    "vat_customer_payer": "1",
    "invoice_type": "FN",
    "invoice_currency": "BIF",
    "cancelled_invoice_ref": "",
    "cn_motif": "",
    "invoice_identifier": identifiant_facture,
    "invoice_items": [
        {
            "item_designation": "Produit Test",
            "item_quantity": 1,
            "item_price": 1000,
            "item_ct": 0,
            "item_tl": 0,
            "item_price_nvat": 1000,
            "vat": 0,
            "item_price_wvat": 1000,
            "item_total_amount": 1000
        }
    ]
}

# ─── ENVOI FACTURE ──────────────────────────────
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.post(invoice_url, json=payload, headers=headers, verify=False)

# ─── ANALYSE RÉPONSE ──────────────────────────────
try:
    resp_data = response.json()
except Exception:
    resp_data = None

if response.status_code == 200 and resp_data and resp_data.get("success"):
    print("✅ Facture acceptée par l'OBR !")
    print("Identifiant électronique :", resp_data.get("electronic_signature"))
else:
    print("❌ Facture rejetée par l'OBR !")
    print("Status HTTP :", response.status_code)
    if resp_data:
        print("Message OBR :", resp_data.get("msg"))
        print("Détails :", resp_data.get("result"))
    else:
        print("Réponse brute :", response.text)