# Handoff — Importation des factures historiques depuis Excel

> Document à destination d'un agent IA (ou développeur) pour **réimplémenter à l'identique**
> la fonctionnalité d'importation sur une autre instance (ex. version cPanel en ligne),
> sans casser l'application en production.

---

## 1. Objectif

Importer un fichier Excel `importation.xlsx` (historique de factures) dans le projet Django,
en créant des factures **exactement comme si elles avaient été envoyées à l'OBR**, **sans aucun
appel réseau**, en réutilisant le **moteur de calcul existant** du projet.

Résultat attendu : les montants en base reproduisent le fichier
`P.T HTTC + TVA + PF = PT TTC`.

---

## 2. Réponse à la question « faut-il une migration ? »

**NON.** Aucun champ / modèle n'est ajouté. Tout passe par les modèles existants.
Commande de contrôle (doit dire `No changes detected`) :

```bat
python manage.py makemigrations --check --dry-run
```

=> Aucun `migrate` n'est requis sur le serveur cPanel, donc **aucun risque de perturber
l'application en ligne** (changement de schéma évité).

---

## 3. Fichiers concernés

### À copier tel quel (aucune dépendance nouvelle hors `openpyxl`, déjà présent)

| Rôle | Chemin |
|---|---|
| Moteur d'import | `superadmin/importation.py` |
| Vue | `superadmin/views.py` → fonction `importation_factures` (ligne ~1253) |
| Route | `superadmin/urls.py` → `path('importation/', views.importation_factures, name='importation')` |
| Template | `templates/superadmin/importation.html` |
| Lien menu | `templates/base_superadmin.html` → `{% url 'superadmin:importation' %}` |

### Modèles réutilisés (NE PAS modifier)
`facturer.models.Facture`, `facturer.models.LigneFacture`, `produits.models.Produit`,
`clients.models.Client`, `societe.models.Societe`, `taux.models.TauxTVA/TauxTC/TauxPFL`,
`categories.models.Categorie`, `superadmin.models.Utilisateur`.

### Réglage mineur dans la vue
```python
IMPORTATION_DIR = os.path.join(settings.MEDIA_ROOT, 'importations')  # views.py:1249
```
Le dossier doit être **inscriptible** sur cPanel.

---

## 4. Le fichier Excel attendu

- Format `.xlsx`, feuille `Table 1` (sinon 1ʳᵉ feuille).
- **En-tête détecté automatiquement** : ligne contenant à la fois `numero` et un `client`.
- Colonnes (intitulés non sensibles à la casse/accents, espaces normalisés) :

**Obligatoires** : `Numero`, `Type de factures`, `Produit`, `Qtés`, `P.T HTTC`, `TVA`,
`PT TTC`, `Date`, `Client`.

**Optionnelles** : `Type de paiement`, `Status`, `Unité`, `P.U HTTC`, `TC`, `PF`, `OTT`,
`TSCE`, `NIF du Client`, `Devise`, `Auteur`.

- Lignes vides et lignes `TOTAL…` ignorées. Lignes de statut non `valide/valides` ignorées.
- Si un `Produit`, `Client`, `Taux` ou `Categorie` n'existe pas → **création automatique**.

---

## 5. Règle de calcul (point CRITIQUE — « Option B »)

Pour chaque ligne du fichier :

```
montant HT enregistré = P.T HTTC                       (la TC est DÉJÀ incluse)
taux TVA              = TVA / P.T HTTC × 100
taux PFL              = PF  / P.T HTTC × 100
prix unitaire (HT)    = P.T HTTC / Qtés
prix TVAC (ligne)     = prix_unitaire_ht × (1 + taux_TVA/100)
```

Conséquences voulues :
- La **TC n'est jamais appliquée une 2ᵉ fois** (elle est fondue dans le HT) → `taux_tc = 0`.
- Le **taux TVA est conservé ligne par ligne** (0 %, 10 % ou 18 %), même si le produit a un
  autre taux principal. Le taux dominé par produit ne sert qu'à la config produit/OBR.
- Cas particulier vérifié : `FN/25/2025` (Hébergement) → TVA = 0, TTC = `75999.95` exact.

**Pourquoi ce choix** : la TVA du fichier est calculée sur `P.T HTTC` ; pour reproduire
`P.T HTTC + TVA + PF = PT TTC` à l'identique, il faut donc enregistrer `P.T HTTC` comme base HT.

---

## 6. Logique du moteur (`superadmin/importation.py`)

Fonctions clés (fichier de 790 lignes) :

- `parse_fichier(path)` → lit l'Excel, construit `invoices`, `produits_rates`, `assujetti`,
  `errors`, `warnings`. Ne touche pas la base.
- `analyser_fichier(path, societe, mode)` → **preview** : compare aux numéros/clients/produits
  existants, renvoie doublons, nouveaux clients, nouveaux produits, aperçu. **N'écrit rien**.
- `importer_fichier(path, societe, mode, user)` → **écriture** réelle, `transaction.atomic()`
  par facture, idempotent (un numéro déjà en base est `skipped_existing`).

Helpers : `_norm`, `_clean`, `_to_decimal` (gère virgule/point, espaces, `\u00a0`),
`_parse_datetime`, `_index`, `_taux`, `_dominer`, `_read_rows` (openpyxl `read_only`),
`_get_or_create_*`, `_activer_assujettissement`, `_resoudre_categorie`, `_creer_facture`,
`_creer_ligne`.

### ⚠️ Piège majeur — `LigneFacture.save()` force le taux du produit
`LigneFacture.save()` réapplique `produit.taux_tva` et recalcule HT/TVA depuis `prix_vente_tvac`.
Pour préserver le taux **réel de la ligne**, `_creer_ligne` fait :

```python
ligne_obj.save()                       # passage par le moteur du projet
LigneFacture.objects.filter(pk=ligne_obj.pk).update(   # override en DB
    taux_tva=taux_tva, prix_vente_tvac=prix_tvac, prix_unitaire_ht=pu_ht,
)
# puis on réaligne l'instance en mémoire et on purge les caches de propriétés
```

Ne pas oublier `facture.recalculer_totaux()` après les lignes.

### Facture créée
`statut_obr='ENVOYE'`, `applique_tva=True`, `invoice_identifier` construit via
`_build_identifier`, `date_envoi_obr`/`obr_registered_date` = date de la facture,
`message_obr` explicite « Importé depuis un fichier Excel ».

### Société
`_activer_assujettissement` active `assujeti_tva` (et `tc`/`pfl` si détectés) selon le fichier.
`assujetti` est calculé **par ligne** dans `parse_fichier`.

---

## 7. Flux de la vue (2 étapes — ne pas « simplifier »)

1. **GET** → formulaire (société + fichier).
2. **POST `action=preview`** → `analyser_fichier` : affiche résultats + bouton
   **« Confirmer l'importation »**.
3. **POST `action=import`** → `importer_fichier` : écrit en base, puis supprime le fichier
   temporaire importé dans `MEDIA_ROOT/importations/`.

Le fichier uploadé est stocké temporairement sous
`import_{YYYYmmdd_HHMMSS}_{user_pk}.xlsx`, contrôlé par préfixe/suffixe avant import.

> UX : le bouton d'import **n'apparaît qu'après l'analyse**. Le 1ᵉʳ bouton visible est
> **« Analyser le fichier »**. C'est volontaire (sécurité : preview avant écriture).

Mode : **PRODUCTION uniquement** (`mode = True` codé en dur, sélecteur retiré).

---

## 8. Personnaliser pour une autre instance (checklist cPanel)

1. Copier les 5 fichiers de la section 3 (ou seulement le moteur + vue + url + template).
2. Vérifier que `openpyxl` est dans `requirements` (déjà le cas ici).
3. Vérifier `MEDIA_ROOT` inscriptible et que `MEDIA_ROOT/importations/` peut être créé.
4. Contrôler les noms de champs modèles identiques (`statut_obr`, `obr_mode_envoye`,
   `assujeti_tva/tc/pfl`, `cree_par`, `taux_*_valeur`, etc.).
5. `python manage.py makemigrations --check --dry-run` → doit dire `No changes detected`.
6. Aucun `migrate` à lancer. Déployer.
7. Tester : analyse → confirmer → ré-import (doit ignorer les doublons).

---

## 9. Résultats des tests (référence)

Avec `importation.xlsx` fourni :
- **610 factures**, **1032 lignes**, **210 clients**, **24 produits**, **0 erreur**.
- Ré-import : **610 ignorées** (idempotent). `taux_created = 2` (0 % et 10 %).
- Comparaison ligne à ligne : 811 exactes, **221 écarts ≤ 0,055 BIF** (arrondi 2 décimales
  de l'Excel) — total écart **2,509 BIF** sur ≈1,645 milliard. **Ce ne sont pas des erreurs.**

---

## 10. Pièges d'environnement rencontrés (à éviter)

- Windows console cp1252 → utiliser `set PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` pour les
  prints/manage.py.
- Ne **jamais** modifier `facturation/settings.py` (DB MySQL de prod). Pour tester en local,
  utiliser un settings SQLite **temporaire isolé**.
- Le code vérifie `os.remove(chemin)` en `finally` : s'assurer des droits sur le dossier temp.

---

## 11. Résumé « en une phrase »

> On lit l'Excel, on enregistre `P.T HTTC` comme base HT, on dérive le taux TVA par ligne
> (`TVA / P.T HTTC`), on crée la facture via le moteur existant avec `statut_obr='ENVOYE'`,
> le tout sans migration ni appel OBR, en preview puis confirmation.
