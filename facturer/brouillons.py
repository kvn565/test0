class LigneFacture(models.Model):
    facture         = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    produit         = models.ForeignKey(Produit, on_delete=models.PROTECT, null=True, blank=True)
    service         = models.ForeignKey(Service, on_delete=models.PROTECT, null=True, blank=True)
    designation     = models.CharField(max_length=250, verbose_name="Désignation")
    quantite        = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Qté vendue")
    taux_tva        = models.DecimalField(max_digits=5, decimal_places=2, default=18, verbose_name="TVA %")
    prix_vente_tvac = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prix TVAC unitaire")

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.designation

    # ====================== CALCULS CONFORMES ======================
    @property
    def prix_ht(self):
        """Prix unitaire HTVA"""
        if self.taux_tva and self.taux_tva > 0:
            return (self.prix_vente_tvac / (Decimal('1') + self.taux_tva / Decimal('100'))).quantize(Decimal('0.01'))
        return self.prix_vente_tvac.quantize(Decimal('0.01'))

    @property
    def montant_ht(self):
        """Montant HT de la ligne"""
        return (self.prix_ht * self.quantite).quantize(Decimal('0.01'))

    @property
    def montant_tva(self):
        """Montant de la TVA de la ligne"""
        return (self.montant_ht * self.taux_tva / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def montant_ttc(self):
        """Montant TTC de la ligne"""
        return (self.montant_ht + self.montant_tva).quantize(Decimal('0.01'))

    # Pour compatibilité avec ton code existant
    @property
    def prix_ttc(self):
        return self.prix_vente_tvac
#clculer

    def recalculer_totaux(self):
        """Recalcule les totaux de la facture de manière fiable et conforme"""
        lignes = self.lignes.all()

        total_ht = Decimal('0')
        total_tva = Decimal('0')
        total_ttc = Decimal('0')

        for ligne in lignes:
            total_ht += ligne.montant_ht
            total_tva += ligne.montant_tva
            total_ttc += ligne.montant_ttc

        # Mise à jour explicite + arrondi propre
        Facture.objects.filter(pk=self.pk).update(
            total_ht=total_ht.quantize(Decimal('0.01')),
            total_tva=total_tva.quantize(Decimal('0.01')),
            total_ttc=total_ttc.quantize(Decimal('0.01')),
        )

        # Refresh complet de l'objet
        self.refresh_from_db(fields=['total_ht', 'total_tva', 'total_ttc'])





#ajouter:@login_required
@require_POST
def ajax_ajouter_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    facture_id = payload.get('facture_id')
    if not facture_id:
        return JsonResponse({'ok': False, 'error': 'facture_id manquant'}, status=400)

    facture = get_object_or_404(Facture, pk=facture_id, societe=societe)

    try:
        quantite = Decimal(str(payload.get('quantite') or '0')).quantize(Decimal('0.01'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Quantité invalide'}, status=400)

    if quantite <= 0:
        return JsonResponse({'ok': False, 'error': 'La quantité doit être supérieure à 0'}, status=400)

    produit_id = payload.get('produit_id')
    service_id = payload.get('service_id')

    if not (produit_id or service_id):
        return JsonResponse({'ok': False, 'error': 'Produit ou service requis'}, status=400)

    try:
        with transaction.atomic():
            produit = None
            service = None
            stock_avant = Decimal('0')
            stock_apres = Decimal('0')

            if produit_id:
                produit = get_object_or_404(
                    Produit.objects.select_for_update(),
                    pk=produit_id,
                    societe=societe
                )

                stock_avant = produit.stock_disponible

                if facture.lignes.filter(produit_id=produit_id).exists():
                    return JsonResponse({
                        'ok': False,
                        'error': 'Ce produit est déjà présent dans cette facture.'
                    }, status=400)

                # Ajustement du stock
                if facture.type_facture in ['FN', 'FA']:
                    try:
                        produit.ajuster_stock(
                            quantite=quantite,
                            type_facture=facture.type_facture,
                            facture=facture
                        )
                    except Exception as stock_err:
                        logger.error(f"Erreur ajustement stock {facture.type_facture} - Produit {produit.designation} (Qté: {quantite}): {stock_err}")
                        raise

                designation = produit.designation
                prix_ttc = Decimal(str(produit.prix_vente_tvac or 0))
                taux_tva = Decimal(str(produit.taux_tva_valeur or 18))

            else:
                service = get_object_or_404(Service, pk=service_id, societe=societe)
                designation = service.designation
                prix_ttc = Decimal(str(service.prix or 0))
                taux_tva = Decimal(str(service.taux_tva.valeur if getattr(service.taux_tva, 'valeur', None) else 18))

            # Création de la ligne
            ligne = LigneFacture.objects.create(
                facture=facture,
                designation=designation,
                prix_vente_tvac=prix_ttc,
                quantite=quantite,
                taux_tva=taux_tva,
                produit=produit,
                service=service,
            )

            # ====================== CALCUL ET SAUVEGARDE FORCÉE DES TOTAUX ======================
            facture.recalculer_totaux()                    # Calcul des totaux
            facture.save()                                 # Sauvegarde explicite
            facture = Facture.objects.get(pk=facture.pk)   # Rechargement complet de l'objet

            # ====================== CALCUL DYNAMIQUE DU STOCK ======================
            if produit:
                produit.refresh_from_db()
                stock_avant = produit.stock_disponible

                if facture.type_facture == 'FN':
                    stock_apres = stock_avant - quantite
                elif facture.type_facture == 'FA':
                    stock_apres = stock_avant + quantite
                else:
                    stock_apres = stock_avant

    except ValueError as ve:
        return JsonResponse({'ok': False, 'error': str(ve)}, status=400)
    except Exception as e:
        logger.exception(f"Erreur lors de l'ajout de ligne sur facture {facture_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur serveur lors de l\'ajout de ligne'}, status=500)

    return JsonResponse({
        'ok': True,
        'ligne_id': ligne.pk,
        'designation': ligne.designation,
        'quantite': float(ligne.quantite),
        'prix_ttc': float(ligne.prix_vente_tvac),
        'taux_tva': int(ligne.taux_tva),
        'total_ht': float(facture.total_ht or 0),
        'total_tva': float(facture.total_tva or 0),
        'total_ttc': float(facture.total_ttc or 0),
        'stock_avant': float(stock_avant),
        'stock_apres': float(stock_apres),
        'produit_id': produit.pk if produit else None,
    })