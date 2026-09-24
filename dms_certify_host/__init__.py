import logging

from odoo import http

from .hosts import parent_of_check_host

_logger = logging.getLogger(__name__)


def post_load():
    """Make check.<host> select the same database as <host>.

    Odoo resolves the database from the host through dbfilter (%h / %d), so
    check.erp.domain would look for a database matching 'check'. We hand
    db_filter the parent host instead. Must run before any request picks a
    database, hence server_wide_modules.
    """
    original = http.db_filter
    if getattr(original, "_dms_check_host", False):
        return

    def db_filter(dbs, host=None):
        if host is None and http.request:
            host = http.request.httprequest.environ.get("HTTP_HOST", "")
        return original(dbs, host=parent_of_check_host(host) or host)

    db_filter._dms_check_host = True
    http.db_filter = db_filter
    _logger.info("dms_certify_host: check.* hosts use their parent host's database")
