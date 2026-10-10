import os

# Read once at import: the value has to be known before any database exists,
# so it comes from the process environment, never from ir.config_parameter.
# An empty value falls back to the default rather than matching every host.
CHECK_PREFIX = (os.environ.get("DMS_CHECK_HOST_PREFIX") or "check.").strip().lower()


def parent_of_check_host(host):
    """'check.erp.domain:443' -> 'erp.domain:443'. Anything that is not a
    check host -> None."""
    if not host:
        return None
    name, sep, port = host.partition(":")
    name = name.lower()
    if name.startswith(CHECK_PREFIX) and len(name) > len(CHECK_PREFIX):
        return name[len(CHECK_PREFIX):] + sep + port
    return None


def is_check_host(host=None):
    if host is None:
        from odoo.http import request
        host = request.httprequest.host if request else ""
    return parent_of_check_host(host) is not None
