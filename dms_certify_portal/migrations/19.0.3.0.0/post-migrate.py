# -*- coding: utf-8 -*-
"""Activate the portal's languages on an instance that predates them.

post_init_hook only runs on install, so a database that already had this module
needs the same step on upgrade — otherwise the language switcher has nothing to
switch to and the French copy shipped with the module never reaches a page.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.dms_certify_portal.hooks import activate_portal_languages

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    activate_portal_languages(api.Environment(cr, SUPERUSER_ID, {}))
    _logger.info("dms_certify_portal: portal languages checked")
