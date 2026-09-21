# -*- coding: utf-8 -*-
"""The kinds of document this registry knows how to certify.

A model rather than a selection, for two reasons. A producing module adds its
documents as data records instead of overriding a method, so the list grows
without code. And the choices that vary by *kind* of document rather than by
individual document — whether generating one stamps it automatically, and in
time its default validity or disclosure — have somewhere to live that an
administrator can reach from Settings.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DmsCertificateType(models.Model):
    _name = 'dms.certificate.type'
    _description = "Certified Document Type"
    _order = 'sequence, name'

    _code_unique = models.Constraint(
        'UNIQUE(code)',
        "Another document type already uses this code.",
    )

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True, copy=False,
        help="Stable identifier a producing module refers to. The label above "
             "can be renamed and translated freely; this cannot.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    auto_stamp = fields.Boolean(
        string="Stamp on generation", default=False,
        help="When a producing module generates a document of this kind, "
             "register it for verification straight away, as a draft. It still "
             "has to be sealed by hand.")

    certificate_count = fields.Integer(compute='_compute_certificate_count')

    @api.depends()
    def _compute_certificate_count(self):
        counts = dict(self.env['dms.certificate']._read_group(
            [('type_id', 'in', self.ids)], ['type_id'], ['__count']))
        for record in self:
            record.certificate_count = counts.get(record, 0)

    # ------------------------------------------------------------------
    @api.model
    def _get_by_code(self, code):
        """Resolve a producing module's key to a type, or an empty recordset."""
        if not code:
            return self.browse()
        return self.with_context(active_test=False).search(
            [('code', '=', code)], limit=1)

    @api.model
    def _auto_stamp_codes(self):
        return set(self.search([('auto_stamp', '=', True)]).mapped('code'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used(self):
        used = self.env['dms.certificate'].sudo().search_count(
            [('type_id', 'in', self.ids)])
        if used:
            raise UserError(_(
                "This type is on %s certified documents. Archive it instead, "
                "so those documents keep saying what they are.", used))
