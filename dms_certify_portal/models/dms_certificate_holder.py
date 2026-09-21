# -*- coding: utf-8 -*-
"""The people a certified document names, and the secret that opens it."""

import hashlib
import hmac
import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PASSPORT_KEY_PARAM = 'dms_certify_portal.passport_key'


class DmsCertificateHolder(models.Model):
    """One row per person listed on the document.

    A letter of invitation names a whole crew, so a certificate has as many
    holders as the page has lines, and **any** of them opens it: the agent at
    the counter has one seafarer in front of them and reads that seafarer's
    passport off the page.

    The passport number is stored, and readable back by a certification
    registrar. That is a deliberate choice: the same numbers are already
    printed inside the sealed PDF in the same DMS and held on the crew contact,
    so this table is not the only copy, and an operator correcting a mistyped
    number should be able to see what is there. It does mean a database dump
    contains passport numbers — treat the dump accordingly.

    Three keyed hashes are kept alongside it, one per second-factor mode, so
    the issuer can switch a document from "last 4" to "full passport" without
    the crew being entered again, and so matching a lookup never compares
    plaintext.
    """

    _name = 'dms.certificate.holder'
    _description = "Certified Document Holder"
    _order = 'sequence, id'

    certificate_id = fields.Many2one(
        'dms.certificate', string="Certificate", required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)

    # Printed on the document, and shown back on the verification page so the
    # agent can confirm the person in front of them is the one that matched.
    name = fields.Char(string="Surname", required=True)
    first_name = fields.Char(string="First name")
    date_of_birth = fields.Date(string="Date of birth")
    rank = fields.Char(string="Rank")

    # Restricted to registrars: an agent with read access to the registry has
    # no business reading passport numbers out of it.
    passport_number = fields.Char(
        string="Passport number", copy=False,
        groups='dms_certify_portal.group_certify_manager',
        help="Printed on the document. Stored so it can be checked and "
             "corrected; matching a lookup always goes through the hashes "
             "below, never through this.")

    passport_hash = fields.Char(readonly=True, copy=False, index=True,
                                groups='dms_certify_portal.group_certify_manager')
    passport4_hash = fields.Char(readonly=True, copy=False, index=True,
                                 groups='dms_certify_portal.group_certify_manager')
    dob_hash = fields.Char(readonly=True, copy=False, index=True,
                           groups='dms_certify_portal.group_certify_manager')

    # Where this person's own details sit on the source document, in that
    # document's coordinates. Measured against a known version of it, so a
    # lookup blanks exactly those places instead of searching the page for
    # strings that may also appear in the letter body.
    redaction_boxes = fields.Text(readonly=True, copy=False)
    boxes_source_hash = fields.Char(
        readonly=True, copy=False,
        help="The document the boxes were measured against. If the document "
             "changes and this does not, the boxes are stale and must not be "
             "trusted.")

    display_name_public = fields.Char(compute='_compute_display_name_public')

    @api.depends('name', 'first_name')
    def _compute_display_name_public(self):
        for holder in self:
            holder.display_name_public = ' '.join(filter(None, [
                holder.first_name, holder.name])) or holder.name or ''

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------
    @api.model
    def _normalize(self, value):
        """Fold away the ways the same number gets typed at a counter."""
        return re.sub(r'[^A-Z0-9]', '', (value or '').upper())

    @api.model
    def _keyed_hash(self, value):
        """HMAC-SHA256 under the instance pepper.

        The pepper is what makes this worth doing at all: the factor values are
        short — four characters, or a date — so an unkeyed digest of one would
        fall to a wordlist instantly. With a key that is not in the table, it
        does not.
        """
        if not value:
            return False
        key = self.env['ir.config_parameter'].sudo().get_param(PASSPORT_KEY_PARAM)
        if not key:
            raise UserError(_(
                "The verification hashing key is missing. Reinstall the module "
                "or restore the '%s' system parameter from backup.",
                PASSPORT_KEY_PARAM))
        return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()

    @api.model
    def _dob_digits(self, value):
        """DDMMYYYY — the shape the portal asks an agent to type."""
        return value.strftime('%d%m%Y') if value else ''

    def _recompute_credentials(self):
        """Keep the hashes in step with what was entered."""
        for holder in self:
            passport = holder._normalize(holder.passport_number)
            holder.passport_hash = holder._keyed_hash(passport) if passport else False
            holder.passport4_hash = (
                holder._keyed_hash(passport[-4:]) if len(passport) >= 4 else False)
            digits = holder._dob_digits(holder.date_of_birth)
            holder.dob_hash = holder._keyed_hash(digits) if digits else False

    @api.model_create_multi
    def create(self, vals_list):
        holders = super().create(vals_list)
        holders._recompute_credentials()
        return holders

    def write(self, vals):
        result = super().write(vals)
        # The inner write only touches hash fields, which are not in this
        # guard, so it cannot loop.
        if 'passport_number' in vals or 'date_of_birth' in vals:
            self._recompute_credentials()
        return result

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _stored_factor_hash(self, factor):
        self.ensure_one()
        return {
            'pptfull': self.passport_hash,
            'ppt4': self.passport4_hash,
            'dob': self.dob_hash,
        }.get(factor) or ''

    @api.model
    def _submitted_factor_hash(self, factor, value):
        """Hash what the agent typed, the way the stored side was hashed."""
        normalized = self._normalize(value)
        if not normalized:
            return ''
        if factor == 'ppt4':
            normalized = normalized[-4:]
        return self._keyed_hash(normalized) or ''

    # ------------------------------------------------------------------
    # Where this person appears on the page
    # ------------------------------------------------------------------
    def _store_boxes(self, boxes, source_hash):
        self.ensure_one()
        self.sudo().write({
            'redaction_boxes': json.dumps(boxes or []),
            'boxes_source_hash': source_hash or False,
        })

    def _boxes(self, source_hash):
        """This person's boxes, or None if they cannot be trusted.

        None is not "nothing to hide" — it is "do not serve this page". The
        caller must fail closed on it, because the alternative is showing a
        document with somebody's passport still on it.
        """
        self.ensure_one()
        if not self.boxes_source_hash or self.boxes_source_hash != source_hash:
            return None
        try:
            return json.loads(self.redaction_boxes or '[]')
        except ValueError:
            return None

    def _survives(self, tokens):
        """Which of this person's details are still in *tokens*.

        The passport is checked by hashing each word the page still contains
        and comparing against the stored hash — the only way to look for
        something that was never kept.
        """
        self.ensure_one()
        found = []
        printed = {value for value in (self.name, self.first_name,
                                       self.passport_number) if value}
        for token in tokens:
            if token in printed:
                found.append(token)
                continue
            normalized = self._normalize(token)
            if not normalized:
                continue
            if self.passport_hash and hmac.compare_digest(
                    self.passport_hash, self._keyed_hash(normalized) or ''):
                found.append('<passport>')
        return found

    def _redaction_needles(self):
        """Every string of this holder that is printed on the document.

        Fed to the redaction pass, so the confirm-only copy shown on the portal
        carries no crew identity at all.
        """
        needles = []
        for holder in self:
            needles.extend(filter(None, [
                holder.name,
                holder.first_name,
                holder.rank,
                holder.passport_number,
                holder.date_of_birth and holder.date_of_birth.strftime('%d/%m/%Y'),
                holder.date_of_birth and holder.date_of_birth.strftime('%d-%m-%Y'),
            ]))
        return needles
