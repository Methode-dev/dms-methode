# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class DmsCertificateAttempt(models.Model):
    """Every hit on the public form, successful or not.

    Doubles as the throttle counter and the audit trail, and there are two
    counters, not one:

    - **per address**, which stops one client hammering the whole registry;
    - **per reference**, which is what actually protects a document. With the
      second check set to the last four characters of a passport there are
      only a few thousand possibilities, so a handful of tries against one
      reference has to be enough to shut it — for everyone, from anywhere.

    It deliberately stores no form of the submitted secret, not even a hash: a
    per-attempt hash would let anyone with table access correlate attempts
    across documents.
    """

    _name = 'dms.certificate.attempt'
    _description = "Document Verification Attempt"
    _order = 'create_date desc, id desc'
    _rec_name = 'reference_tried'

    reference_tried = fields.Char(string="Reference tried", index=True, readonly=True)
    document_id = fields.Many2one(
        'dms.certificate', string="Matched document", readonly=True,
        ondelete='set null', index=True)
    ip_address = fields.Char(string="IP address", index=True, readonly=True)
    user_agent = fields.Char(string="User agent", readonly=True)
    success = fields.Boolean(string="Matched", index=True, readonly=True)
    requester_label = fields.Char(
        string="Requester", compute='_compute_requester_label',
        help="What the desk is shown about who looked the document up.")

    outcome = fields.Selection(
        [('matched', "Matched"),
         ('no_match', "No match"),
         ('throttled', "Blocked by rate limit"),
         ('locked', "Blocked, reference locked"),
         ('captcha', "Failed the captcha"),
         ('mismatch', "Reported as not matching the paper")],
        string="Outcome", readonly=True, index=True)

    def _compute_requester_label(self):
        """Who looked it up, as the desk sees it.

        The address is kept — the rate limit and the audit trail both need it —
        but it is not what the desk is shown. An IP tells an operations manager
        nothing they can act on, and resolving it to "Consulate of France,
        Yangon" would mean either a third-party lookup service or a
        hand-maintained list of embassy ranges. Neither is worth it yet.
        """
        for attempt in self:
            attempt.requester_label = _("An external user")

    # ------------------------------------------------------------------
    @api.model
    def _param(self, name, default):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'dms_certify_portal.%s' % name, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @api.model
    def log(self, reference=None, ip_address=None, user_agent=None,
            outcome='no_match', document=None):
        """Write one attempt row. Always called with sudo from the controller."""
        return self.sudo().create({
            'reference_tried': (reference or '')[:64],
            'ip_address': (ip_address or '')[:45],
            'user_agent': (user_agent or '')[:256],
            'success': outcome == 'matched',
            'outcome': outcome,
            'document_id': document.id if document else False,
        })

    @api.model
    def is_throttled(self, ip_address):
        """True when this address has burned through its failure budget.

        The application-level net. Put a second one in front of Odoo (nginx
        ``limit_req``, Cloudflare) so a flood never reaches Python at all, and
        so the limit survives a bug in this method.
        """
        if not ip_address:
            return False
        max_failures = self._param('max_failures', 10)
        window = self._param('window_minutes', 15)
        since = fields.Datetime.now() - timedelta(minutes=window)
        count = self.sudo().search_count([
            ('ip_address', '=', ip_address),
            ('success', '=', False),
            ('outcome', 'in', ('no_match', 'captcha')),
            ('create_date', '>=', since),
        ])
        if count >= max_failures:
            _logger.warning(
                "dms_certify_portal: throttling %s after %s failed attempts in %s min",
                ip_address, count, window)
            return True
        return False

    @api.model
    def reference_lock_left(self, reference_key):
        """Minutes this reference stays locked, or 0 when it is open.

        Counted across every address on purpose. A locked reference is the
        signal that someone is guessing at one specific document, and letting
        them continue from a second address would make the limit theatre.
        """
        if not reference_key:
            return 0
        max_failures = self._param('max_reference_failures', 5)
        window = self._param('reference_lock_minutes', 30)
        since = fields.Datetime.now() - timedelta(minutes=window)
        attempts = self.sudo().search(
            [('reference_tried', '=', reference_key),
             ('success', '=', False),
             ('outcome', 'in', ('no_match', 'locked')),
             ('create_date', '>=', since)],
            order='create_date asc')
        if len(attempts) < max_failures:
            return 0
        # The clock runs from the failure that tripped the lock, so a caller
        # who keeps trying does not keep pushing their own release back.
        tripped = attempts[max_failures - 1].create_date
        left = (tripped + timedelta(minutes=window)) - fields.Datetime.now()
        minutes = int(left.total_seconds() // 60) + 1
        return max(0, minutes)

    @api.model
    def is_reference_locked(self, reference_key):
        return bool(self.reference_lock_left(reference_key))

    @api.model
    def reference_attempts_left(self, reference_key):
        """How many tries remain on this reference before it locks.

        Shown on the refusal page. Telling an agent who mistyped that they have
        three goes left is worth far more than the sliver it gives an attacker,
        who can count their own failures anyway.
        """
        max_failures = self._param('max_reference_failures', 5)
        if not reference_key:
            return max_failures
        window = self._param('reference_lock_minutes', 30)
        since = fields.Datetime.now() - timedelta(minutes=window)
        used = self.sudo().search_count([
            ('reference_tried', '=', reference_key),
            ('success', '=', False),
            ('outcome', 'in', ('no_match', 'locked')),
            ('create_date', '>=', since),
        ])
        return max(0, max_failures - used)

    # ------------------------------------------------------------------
    @api.model
    def _gc_attempts(self):
        """Cron: drop rows past the retention window.

        Retention is a data-protection decision, not a technical one. Ninety
        days is long enough to investigate an incident and short enough to
        defend; agree it with whoever signs off the processing record.
        """
        days = self._param('retention_days', 90)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        stale = self.sudo().search([('create_date', '<', cutoff)])
        count = len(stale)
        stale.unlink()
        if count:
            _logger.info("dms_certify_portal: vacuumed %s verification attempts", count)
        return count
