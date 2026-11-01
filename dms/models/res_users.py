# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        self.env["dms.access.group"]._recompute_users()
        return users

    def write(self, vals):
        res = super().write(vals)
        if {"group_ids", "active"} & vals.keys():
            self.env["dms.access.group"]._recompute_users()
        return res
