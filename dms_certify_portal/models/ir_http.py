from werkzeug.exceptions import NotFound

from odoo import models
from odoo.http import request

from odoo.addons.dms_certify_host.hosts import is_check_host

PORTAL_PREFIX = "/_check"
# Only the asset bundles. The translation routes Odoo's front-end JS fetches on
# every page load (/website/translations, /web/webclient/translations) are NOT
# passed through on purpose, and their 404 — with "Error while fetching
# translations" in the console — is expected on the check host.
#
# The portal does not use Odoo's front-end framework: verify.js is a plain
# script and every string is rendered server-side. Let the translations
# through and the framework boots one step further, into Owl compiling its
# templates with new Function(), which the check host's CSP refuses because it
# carries no 'unsafe-eval' (see nginx.conf.template). Allowing eval on a public
# anti-forgery page to make a framework the page does not need start cleanly
# is the wrong trade; the 404 stops it earlier, before any CSP violation.
PASSTHROUGH = ("/web/assets/",)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _match(cls, path_info):
        if request and is_check_host():
            if not path_info.startswith(PASSTHROUGH):
                path_info = PORTAL_PREFIX + ("" if path_info == "/" else path_info)
        elif path_info == PORTAL_PREFIX or path_info.startswith(PORTAL_PREFIX + "/"):
            # The internal namespace does not exist outside check.*.
            raise NotFound()
        return super()._match(path_info)

    @classmethod
    def _serve_fallback(cls):
        if request and is_check_host():
            return None
        return super()._serve_fallback()
