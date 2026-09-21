# -*- coding: utf-8 -*-
import logging
import os
import secrets

from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)

PASSPORT_KEY_PARAM = 'dms_certify_portal.passport_key'


def post_init_hook(env):
    _generate_passport_key(env)
    activate_portal_languages(env)


def _generate_passport_key(env):
    """Generate the HMAC pepper used to hash the second check.

    This key never leaves the database and is never exposed in the UI. If it is
    lost, every stored hash becomes unverifiable and the documents have to be
    re-issued. Back it up with the filestore, and rotate it only with a
    migration that re-hashes from a trusted source.
    """
    icp = env['ir.config_parameter'].sudo()
    if not icp.get_param(PASSPORT_KEY_PARAM):
        icp.set_param(PASSPORT_KEY_PARAM, secrets.token_urlsafe(48))
        _logger.info("dms_certify_portal: generated a new passport hashing key")


def portal_language_codes():
    """The two-letter codes this module ships portal copy for, plus English.

    Read off the i18n folder rather than hard-coded, so dropping an ``es.po``
    beside ``fr.po`` is all it takes to offer Spanish at the counter.
    """
    codes = {'en'}
    path = get_module_path('dms_certify_portal')
    i18n = os.path.join(path or '', 'i18n')
    if os.path.isdir(i18n):
        codes.update(
            name[:-3] for name in os.listdir(i18n) if name.endswith('.po'))
    return codes


def activate_portal_languages(env):
    """Make sure the languages the portal is translated into are installed.

    Without this the switcher has nothing to switch to: a fresh database has
    only English active, so the French copy shipped with this module would sit
    in the file and never reach a page. Activating a language is a
    database-wide change, and it is reversible from Settings.
    """
    Lang = env['res.lang'].sudo()
    active = set(Lang.search([('active', '=', True)]).mapped('code'))
    for code in sorted(portal_language_codes()):
        if any(existing.split('_')[0] == code for existing in active):
            continue
        # fr -> fr_FR, pt -> pt_PT: the plain-country variant, falling back to
        # whatever variant this Odoo knows about.
        candidates = [f'{code}_{code.upper()}'] + [
            lang.code for lang in Lang.with_context(active_test=False).search(
                [('code', '=like', f'{code}\\_%')])
        ]
        for candidate in candidates:
            if Lang._activate_lang(candidate):
                _logger.info("dms_certify_portal: activated %s for the portal",
                             candidate)
                break
        else:
            _logger.warning(
                "dms_certify_portal: no installable language found for '%s'; "
                "the portal will not offer it", code)
