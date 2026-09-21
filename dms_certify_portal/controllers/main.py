# -*- coding: utf-8 -*-
import hmac
import logging
import secrets
import time

from odoo import http
from odoo.http import request

from ..hooks import portal_language_codes

_logger = logging.getLogger(__name__)

SESSION_TOKEN = 'dms_certify_token'
SESSION_DOC = 'dms_certify_doc_id'
SESSION_HOLDER = 'dms_certify_holder_id'
SESSION_EXPIRY = 'dms_certify_expiry'
SESSION_ERROR = 'dms_certify_error'
SESSION_NOTICE = 'dms_certify_notice'
SESSION_REFERENCE = 'dms_certify_reference'
SESSION_LANG = 'dms_certify_lang'

NO_STORE = [
    ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
    ('Pragma', 'no-cache'),
    ('X-Robots-Tag', 'noindex, nofollow, noarchive'),
    # Keeps the reference out of the Referer header sent to any link target.
    ('Referrer-Policy', 'no-referrer'),
]


class DmsCertifyPortalController(http.Controller):
    """Anonymous document verification.

    Flow is POST-Redirect-GET on purpose: the second check is submitted in a
    POST body, matched, and then discarded. It never reaches a URL, so it never
    lands in browser history, in a Referer header, or in an access log.

    Everything the result page shows comes from ``_get_public_values()`` — a
    plain dict. The templates never receive a recordset, so a later edit cannot
    walk from the portal into business records.
    """

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------
    def _client_ip(self):
        """Requires Odoo to run with ``--proxy-mode`` behind the reverse proxy,
        otherwise every request looks like it comes from the proxy itself and
        the rate limit becomes a global one."""
        return request.httprequest.remote_addr

    def _param(self, name, default):
        value = request.env['ir.config_parameter'].sudo().get_param(
            'dms_certify_portal.%s' % name, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _text_param(self, name, default=''):
        return request.env['ir.config_parameter'].sudo().get_param(
            'dms_certify_portal.%s' % name, default)

    def _bool_param(self, name, default='True'):
        return self._text_param(name, default) in ('True', 'true', '1')

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    def _install_language(self, wanted=None):
        """Resolve a two-letter choice against the languages actually installed.

        There is no ``http_routing`` here, so no ``/fr/verify`` prefix: the
        choice rides a query parameter and then sticks to the session. Falling
        back to whatever is installed matters — forcing ``fr_FR`` on a database
        that has not loaded it renders the source strings and looks broken.
        """
        Lang = request.env['res.lang'].sudo()
        active = Lang.search([('active', '=', True)])
        codes = active.mapped('code')
        wanted = (wanted or request.session.get(SESSION_LANG)
                  or self._text_param('default_lang', 'fr'))
        for code in codes:
            if code.split('_')[0] == wanted.split('_')[0]:
                return code
        return request.env.context.get('lang') or 'en_US'

    def _language_values(self, current):
        """The toggle.

        Only the languages the portal is actually written in — a database with
        six languages installed for the back office should not offer an embassy
        six buttons, five of which lead to an English page.
        """
        supported = portal_language_codes()
        Lang = request.env['res.lang'].sudo()
        options = []
        for lang in Lang.search([('active', '=', True)], order='name'):
            short = lang.code.split('_')[0]
            if short not in supported:
                continue
            options.append({
                'code': lang.code,
                'short': short.upper(),
                'active': lang.code == current,
                'url': '/verify?lang=%s' % short,
            })
        return options

    def _use_language(self, requested=None):
        code = self._install_language(requested)
        request.session[SESSION_LANG] = code
        request.update_context(lang=code)
        return code

    # ------------------------------------------------------------------
    # Captcha (soft dependency on google_recaptcha)
    # ------------------------------------------------------------------
    def _captcha_ok(self, token):
        """The hook returns True when no site key is configured, so an
        unconfigured instance still works. The signature has moved between Odoo
        versions — check ``google_recaptcha/models/ir_http.py`` if this ever
        starts failing silently."""
        IrHttp = request.env['ir.http'].sudo()
        verifier = getattr(IrHttp, '_verify_recaptcha_token', None)
        if verifier is None:
            return True
        try:
            return verifier(self._client_ip(), token, action='dms_certify')
        except TypeError:
            return verifier(token, action='dms_certify')
        except Exception:  # noqa: BLE001 - never let the captcha 500 the page
            _logger.exception("dms_certify_portal: captcha verification failed")
            return False

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _portal_company(self):
        """The organisation the public page presents itself as.

        Configurable, because an embassy is looking at one organisation
        whichever of its companies issued the document in front of them — and
        because a public request resolves to whatever company the public user
        happens to default to, which is nobody's decision.
        """
        Company = request.env['res.company'].sudo()
        chosen = Company.browse(
            int(self._text_param('company_id', '0') or 0)).exists()
        return chosen or request.env.company

    def _company_values(self):
        """Plain data, like everything else the public templates receive.

        The company record itself stays out of the templates: one dot from it
        sits a partner, and from there a bank account.
        """
        company = self._portal_company()
        return {
            'name': company.name or '',
            'street': company.street or '',
            'street2': company.street2 or '',
            'zip': company.zip or '',
            'city': company.city or '',
            'email': company.email or '',
            'phone': company.phone or '',
        }

    def _chrome(self, lang):
        """Values every page of the portal needs."""
        prefix = self._text_param('reference_prefix', 'ICS') or 'ICS'
        return {
            'languages': self._language_values(lang) if lang else [],
            # Drives the input mask, so a prefix of another length still
            # formats as the printed reference does.
            'reference_groups': [len(prefix), 4, 3, 4, 2],
            'reference_sample': '%s-2026-DKK-4KQ7-9B' % prefix,
            'company': self._company_values(),
        }

    def _format_reference(self, value):
        """Group a reference the way it is printed.

        The page has to give back what the agent typed, not the stripped form
        the lookup used — otherwise a refusal answers a careful reader with a
        run-on string and invites them to mistype it again. The browser mask
        does the same thing live; this is what makes it right without it.
        """
        groups = self._chrome(None)['reference_groups']
        raw = request.env['dms.certificate']._normalize_reference(value)
        out, at = [], 0
        for size in groups:
            if at >= len(raw):
                break
            out.append(raw[at:at + size])
            at += size
        if at < len(raw):
            out.append(raw[at:])
        return '-'.join(out)

    def _form_values(self, lang, **extra):
        error = request.session.pop(SESSION_ERROR, None)
        reference = request.session.pop(SESSION_REFERENCE, '')
        attempts_left = None
        if error and reference:
            # Telling an agent who mistyped that they have three goes left is
            # worth far more than the sliver it gives someone guessing, who can
            # count their own failures anyway.
            attempts_left = request.env['dms.certificate.attempt'].sudo(
            ).reference_attempts_left(
                request.env['dms.certificate']._normalize_reference(reference))
        values = dict(self._chrome(lang), **{
            'error_code': error,
            'reference': reference,
            'attempts_left': attempts_left,
            'recaptcha_site_key': request.env['ir.config_parameter'].sudo(
            ).get_param('recaptcha_public_key', ''),
        })
        values.update(extra)
        return values

    def _render(self, template, values, headers=None):
        response = request.render(template, values)
        for key, value in NO_STORE + (headers or []):
            response.headers[key] = value
        return response

    def _fail(self, code, reference=None):
        """Refuse, carrying a reason *code* rather than a sentence.

        The wording lives in the template with the rest of the portal's copy.
        Odoo's exporter does not walk Python source in this layout, so a
        sentence built here would be invisible to the translation export and
        would sit in English on a French page for ever.
        """
        request.session[SESSION_ERROR] = code
        if reference:
            # Give back the reference so only the second check is retyped.
            request.session[SESSION_REFERENCE] = self._format_reference(reference)
        return request.redirect('/verify')

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------
    def _clear_session(self):
        for key in (SESSION_TOKEN, SESSION_DOC, SESSION_HOLDER, SESSION_EXPIRY):
            request.session.pop(key, None)

    def _session_document(self, token):
        """Resolve a result token against the session.

        Returns ``(certificate, holder)`` — the holder matters because it is
        what the page is allowed to name, and what scopes a confirm-only result
        to the one person the agent actually checked.
        """
        empty = (request.env['dms.certificate'].browse(),
                 request.env['dms.certificate.holder'].browse())
        stored = request.session.get(SESSION_TOKEN)
        doc_id = request.session.get(SESSION_DOC)
        expiry = request.session.get(SESSION_EXPIRY) or 0

        if not stored or not doc_id:
            return empty
        if time.time() > expiry:
            self._clear_session()
            return empty
        if not hmac.compare_digest(str(stored), str(token or '')):
            return empty
        document = request.env['dms.certificate'].sudo().browse(doc_id).exists()
        if not document:
            return empty
        holder = request.env['dms.certificate.holder'].sudo().browse(
            request.session.get(SESSION_HOLDER) or 0).exists()
        if holder and holder.certificate_id != document:
            holder = request.env['dms.certificate.holder'].browse()
        return document, holder

    def _tell_the_desk(self, reference_key, outcome, minutes=0, document=None):
        """Post a lookup onto the certificate it was aimed at.

        A failure names no document by definition, so the certificate is looked
        up by reference: an operator wants to know that someone is failing to
        open *their* document, which is exactly the case where the reference is
        right and the second check is not.
        """
        certificate = document
        if certificate is None:
            certificate = request.env['dms.certificate'].sudo().search(
                [('reference_key', '=', reference_key)], limit=1)
        if certificate:
            certificate._notify_verification(outcome, minutes=minutes)

    # ------------------------------------------------------------------
    # The form
    # ------------------------------------------------------------------
    @http.route('/verify', type='http', auth='public',
                methods=['GET'], readonly=True)
    def verify_form(self, lang=None, **kw):
        code = self._use_language(lang)
        return self._render('dms_certify_portal.verify_form',
                            self._form_values(code))

    @http.route('/verify/d/<string:reference>', type='http', auth='public',
                methods=['GET'], readonly=True)
    def verify_form_prefilled(self, reference, lang=None, **kw):
        """Landing page for the QR code printed on the document.

        The QR carries the reference itself rather than a second token, which
        is what makes scanning and retyping exactly equivalent — the printed
        line says so in as many words. It is not a credential either way:
        whoever photographs the document gets this URL, so the second check
        still gates the result.

        Nothing is looked up here. Echoing the scanned value straight back into
        the form keeps this route silent about whether the reference exists.
        """
        code = self._use_language(lang)
        return self._render(
            'dms_certify_portal.verify_form',
            self._form_values(code, reference=(reference or '')[:32]))

    # ------------------------------------------------------------------
    # The submission
    # ------------------------------------------------------------------
    @http.route('/verify', type='http', auth='public',
                methods=['POST'], csrf=True, readonly=False)
    def verify_submit(self, reference=None, passport=None, **kw):
        code = self._use_language(kw.get('lang'))
        Attempt = request.env['dms.certificate.attempt'].sudo()
        Document = request.env['dms.certificate'].sudo()

        ip = self._client_ip()
        ua = request.httprequest.user_agent.string if request.httprequest.user_agent else ''
        reference = Document._normalize_reference(reference)

        if Attempt.is_throttled(ip):
            Attempt.log(reference, ip, ua, outcome='throttled')
            return self._render('dms_certify_portal.verify_throttled', dict(
                self._chrome(code), window_minutes=self._param('window_minutes', 15),
                locked_reference=False))

        # The per-reference lock. Separate from the address limit on purpose:
        # repeated failures against one reference mean someone is guessing at
        # one specific document, and moving to another address must not help.
        locked_for = Attempt.reference_lock_left(reference)
        if locked_for:
            Attempt.log(reference, ip, ua, outcome='locked')
            self._tell_the_desk(reference, 'locked', minutes=locked_for)
            return self._render('dms_certify_portal.verify_throttled', dict(
                self._chrome(code), window_minutes=locked_for,
                locked_reference=True))

        if not self._captcha_ok(kw.get('recaptcha_token_response')):
            Attempt.log(reference, ip, ua, outcome='captcha')
            return self._fail('captcha', reference)

        if not reference or not passport:
            Attempt.log(reference, ip, ua, outcome='no_match')
            return self._fail('incomplete', reference)

        doc, holder = Document._match(reference, passport)

        if not doc:
            Attempt.log(reference, ip, ua, outcome='no_match')
            self._tell_the_desk(reference, 'no_match')
            # One reason for every negative outcome. Splitting "unknown
            # reference" from "wrong second check" would turn this form into an
            # oracle for enumerating valid references.
            return self._fail('no_match', reference)

        Attempt.log(reference, ip, ua, outcome='matched', document=doc)
        doc._register_verification()
        self._tell_the_desk(reference, 'matched', document=doc)

        # Hand out a fresh, session-bound token and get the second check out of
        # the request cycle.
        token = secrets.token_urlsafe(32)
        request.session[SESSION_TOKEN] = token
        request.session[SESSION_DOC] = doc.id
        request.session[SESSION_HOLDER] = holder.id
        request.session[SESSION_EXPIRY] = time.time() + self._param(
            'session_minutes', 15) * 60
        return request.redirect('/verify/%s' % token)

    # ------------------------------------------------------------------
    # The result
    # ------------------------------------------------------------------
    @http.route('/verify/<string:token>', type='http', auth='public',
                methods=['GET'], readonly=True)
    def verify_result(self, token, lang=None, **kw):
        code = self._use_language(lang)
        doc, holder = self._session_document(token)
        if not doc:
            return self._fail('expired')

        # Whitelisted plain data. The template never receives the recordset.
        return self._render('dms_certify_portal.verify_result', dict(
            self._chrome(code),
            doc=doc._get_public_values(holder),
            token=token,
            notice=request.session.pop(SESSION_NOTICE, None),
            allow_download=self._bool_param('allow_download'),
            expires_in=self._param('session_minutes', 15),
        ))

    @http.route('/verify/<string:token>/page/<int:page>', type='http',
                auth='public', methods=['GET'], readonly=True)
    def verify_page_image(self, token, page, **kw):
        """One page of the document, rasterised.

        An image rather than the PDF: a viewer carries its own save, print and
        text extraction, none of which pass back through this gate. Comparing
        the screen with the paper needs no more than a picture.
        """
        doc, holder = self._session_document(token)
        if not doc:
            return request.not_found()
        # The holder is what scopes the page: under confirm-only disclosure the
        # copy is built to hide everyone except the person who opened it.
        image = doc._public_page_image(max(0, page - 1), holder=holder)
        if not image:
            return request.not_found()
        return request.make_response(image, headers=[
            ('Content-Type', 'image/png'),
            ('Content-Length', len(image)),
        ] + NO_STORE)

    @http.route('/verify/<string:token>/file', type='http', auth='public',
                methods=['GET'], readonly=True)
    def verify_download(self, token, **kw):
        """Stream the sealed file through our own gate.

        Never link ``/web/content/<id>``: that route is readable by anyone who
        knows the id as soon as the attachment is public, which detaches the
        file from the second check entirely.
        """
        if not self._bool_param('allow_download'):
            return request.not_found()

        doc, holder = self._session_document(token)
        raw = doc and doc._public_bytes(holder)
        if not raw:
            return request.not_found()

        filename = '%s.pdf' % doc.reference.replace('/', '-')
        return request.make_response(raw, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', http.content_disposition(filename)),
            ('Content-Length', len(raw)),
        ] + NO_STORE)

    @http.route('/verify/<string:token>/mismatch', type='http', auth='public',
                methods=['POST'], csrf=True, readonly=False)
    def verify_mismatch(self, token, **kw):
        """"The paper does not match."

        The most valuable thing this portal can collect. A document that
        verifies while the paper in front of the agent differs from it is
        either a forgery built on a real reference or a stale copy, and either
        way somebody at the issuing desk needs to know within minutes.
        """
        self._use_language()
        doc, _holder = self._session_document(token)
        if not doc:
            return request.redirect('/verify')
        request.env['dms.certificate.attempt'].sudo().log(
            doc.reference_key, self._client_ip(),
            request.httprequest.user_agent.string if request.httprequest.user_agent else '',
            outcome='mismatch', document=doc)
        doc._notify_verification('mismatch')
        request.session[SESSION_NOTICE] = 'mismatch_reported'
        return request.redirect('/verify/%s' % token)
