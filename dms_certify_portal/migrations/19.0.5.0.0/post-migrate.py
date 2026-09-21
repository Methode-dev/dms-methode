# -*- coding: utf-8 -*-
"""Drop the generic document types this module used to ship.

Visa / Certificate / Attestation / Other were carried over from the selection
that preceded the model, and they are not documents anybody issues — they were
categories. Their only effect was to fill the "Stamp on generation" list in
Settings with entries that do not correspond to anything, next to the documents
that do.

A type that is actually in use is left alone: whatever it labels is on a page
somewhere, and the verification page has to keep being able to say what it is.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

RETIRED_CODES = ('visa', 'certificate', 'attestation', 'other')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Type = env['dms.certificate.type'].sudo()

    retired = Type.with_context(active_test=False).search(
        [('code', 'in', RETIRED_CODES)])
    if not retired:
        return

    Certificate = env['dms.certificate'].sudo()
    dropped, kept = [], []
    for kind in retired:
        if Certificate.search_count([('type_id', '=', kind.id)]):
            kept.append(kind.code)
        else:
            dropped.append(kind.code)

    if dropped:
        Type.with_context(active_test=False).search(
            [('code', 'in', dropped)]).unlink()
        _logger.info("dms_certify_portal: removed unused generic document "
                     "types (%s)", ', '.join(dropped))
    if kept:
        _logger.info("dms_certify_portal: kept generic document types still in "
                     "use (%s); rename or archive them by hand", ', '.join(kept))
