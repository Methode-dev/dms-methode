# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models


class ResGroups(models.Model):
    _inherit = "res.groups"

    def write(self, vals):
        res = super().write(vals)
        if {"user_ids", "all_user_ids", "implied_ids"} & vals.keys():
            self.env["dms.access.group"]._recompute_users()
        return res
