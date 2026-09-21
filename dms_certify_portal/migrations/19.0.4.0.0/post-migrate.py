# -*- coding: utf-8 -*-
"""Move certificates from the old document_type selection onto type records.

The selection became a model so an administrator can decide, per kind of
document, which ones are stamped automatically. Odoo leaves the old column in
place, so the values are still there to map — and it cannot have filled the new
required column on upgrade, because the type records only come into existence
with this version's data file.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'dms_certificate' AND column_name = 'document_type'
    """)
    if not cr.fetchone():
        return

    # Not "where type_id is null": adding a required column makes Odoo fill
    # every existing row with the field's default *before* this script runs,
    # so by now they all say "Other". The old column is the only record of
    # what they actually were.
    cr.execute("""
        SELECT id, document_type FROM dms_certificate
         WHERE document_type IS NOT NULL AND document_type != ''
    """)
    rows = cr.fetchall()
    if not rows:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Type = env['dms.certificate.type'].sudo()
    cache = {}
    moved, orphaned = 0, 0

    for certificate_id, code in rows:
        if code not in cache:
            cache[code] = Type._get_by_code(code)
        kind = cache[code]
        if not kind:
            # A code this module knows nothing about. The producing module
            # that owns that vocabulary declares its types when it loads,
            # which happens after this, and picks these up then.
            orphaned += 1
            continue
        cr.execute("UPDATE dms_certificate SET type_id = %s WHERE id = %s",
                   (kind.id, certificate_id))
        moved += 1

    if orphaned:
        _logger.info(
            "dms_certify_portal: %s certificates carry a document type this "
            "module does not declare; the module that produced them maps "
            "them when it loads", orphaned)
    _logger.info("dms_certify_portal: moved %s certificates onto document types",
                 moved)
