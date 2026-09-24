from werkzeug.exceptions import NotFound

from odoo import models
from odoo.http import request

from odoo.addons.dms_certify_host.hosts import is_check_host

PORTAL_PREFIX = "/_check"
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
