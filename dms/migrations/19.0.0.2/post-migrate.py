# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Access group members were only computed when the access group itself
    was saved, so users added to its Odoo groups afterwards are missing and
    get "no write access" on DMS files. Recompute every group once."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["dms.access.group"]._recompute_users()
