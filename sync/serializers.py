"""Serialisation / deserialisation des enregistrements sync.

Format d'un enregistrement (JSON) :
  {
    'label': 'facturer.Facture',
    'sync_uuid': '<uuid>',
    'sync_updated_at': '2026-...T...',
    'numero': 'FN/1/2026',           # champs simples
    'client__sync_uuid': '<uuid>',   # FK resolues par sync_uuid
    ...
  }
"""
import json
import uuid

from django.db import models
from django.utils.dateparse import parse_date, parse_datetime

from .registry import SYNC_REGISTRY


def _is_date_field(field):
    return isinstance(field, (models.DateField, models.DateTimeField))


def to_record(obj, label):
    spec = SYNC_REGISTRY[label]
    data = {
        'label': label,
        'sync_uuid': str(obj.sync_uuid) if obj.sync_uuid else None,
        'sync_updated_at': obj.sync_updated_at.isoformat() if obj.sync_updated_at else None,
    }
    for f in spec['fields']:
        val = getattr(obj, f)
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        data[f] = val
    for attr in spec['fk']:
        rel = getattr(obj, attr)
        data[f'{attr}__sync_uuid'] = str(rel.sync_uuid) if (rel and getattr(rel, 'sync_uuid', None)) else None
    return data


def from_record(data, societe, apply_uuid=True):
    """Retourne une instance (non sauvegardee) a upsert-er.

    Regles anti-doublon :
      - meme sync_uuid -> mise a jour de l'enregistrement existant.
      - sinon, si un enregistrement existant a deja le meme 'numero' (pour les
        factures) et est deja ENVOYE, on renvoie None (on ne recopie pas le
        doublon ; le doublon est ignore).
    """
    from django.utils import timezone

    label = data['label']
    spec = SYNC_REGISTRY[label]
    model = spec['model']
    sync_uuid = data.get('sync_uuid')

    obj = None
    if sync_uuid:
        obj = model.objects.filter(sync_uuid=sync_uuid, societe=societe).first()

    if obj is None:
        # Anti-doublon par numero pour les factures deja envoyees
        if 'numero' in spec['fields'] and data.get('numero'):
            dup = model.objects.filter(
                societe=societe, numero=data['numero'],
                obr_mode_envoye=data.get('obr_mode_envoye', False),
                statut_obr='ENVOYE',
            ).first()
            if dup:
                return None
        obj = model(societe=societe)

    obj.societe = societe
    if sync_uuid:
        obj.sync_uuid = sync_uuid

    for f in spec['fields']:
        if f == 'sync_uuid' or f not in data:
            continue
        val = data[f]
        field = model._meta.get_field(f)
        if _is_date_field(field) and isinstance(val, str) and val:
            val = parse_datetime(val) if isinstance(field, models.DateTimeField) else parse_date(val)
        setattr(obj, f, val)

    for attr, rel_label in spec['fk'].items():
        fk_uuid = data.get(f'{attr}__sync_uuid')
        if fk_uuid:
            rel_model = SYNC_REGISTRY[rel_label]['model']
            rel = rel_model.objects.filter(sync_uuid=fk_uuid, societe=societe).first()
            setattr(obj, attr, rel)
        else:
            # ne pas ecraser une FK existante avec None si l'objet est nouveau
            if obj.pk is None:
                setattr(obj, attr, None)

    return obj
