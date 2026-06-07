# Copyright 2020 Creu Blanca
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class DmsDirectory(models.Model):
    _inherit = "dms.directory"

    parent_id = fields.Many2one(default=lambda self: self._default_parent())

    @api.model
    def _default_parent(self):
        return self.env.context.get("default_parent_directory_id", False)

    @api.constrains("res_id", "is_root_directory", "storage_id", "res_model")
    def _check_resource(self):
        for directory in self:
            if directory.storage_id.save_type == "attachment":
                continue
            if (
                directory.is_root_directory
                and directory.storage_id.model_ids
                and not directory.res_id
            ):
                raise ValidationError(
                    _("Directories of this storage must be related to a record")
                )
            if not directory.res_id:
                continue
            if self.search(
                [
                    ("storage_id", "=", directory.storage_id.id),
                    ("id", "!=", directory.id),
                    ("res_id", "=", directory.res_id),
                    ("res_model", "=", directory.res_model),
                ],
                limit=1,
            ):
                raise ValidationError(
                    _("This record is already related in this storage")
                )

    @api.model
    def _build_documents_view_directory(self, directory):
        return {
            "id": f"directory_{directory.id}",
            "text": directory.name,
            "icon": "fa fa-folder-o",
            "type": "directory",
            "data": {"odoo_id": directory.id, "odoo_model": "dms.directory"},
            "children": directory.count_elements > 0,
        }

    @api.model
    def _check_parent_field(self):
        if self._parent_name not in self._fields:
            raise TypeError(f"The parent ({self._parent_name}) field does not exist.")

    @api.model
    def search_read_parents(
        self, domain=False, fields=None, offset=0, limit=None, order=None
    ):
        """This method finds the top level elements of the hierarchy
        for a given search query.

        :param domain: a search domain <reference/orm/domains> (default: empty list)
        :param fields: a list of fields to read (default: all fields of the model)
        :param offset: the number of results to ignore (default: none)
        :param limit: maximum number of records to return (default: all)
        :param order: a string to define the sort order of the query
             (default: none)
        :returns: the top level elements for the given search query
        """
        if not domain:
            domain = []
        records = self.search_parents(
            domain=domain, offset=offset, limit=limit, order=order
        )
        if not records:
            return []
        if fields and fields == ["id"]:
            return [{"id": record.id} for record in records]
        result = records.read(fields)
        if len(result) <= 1:
            return result
        index = {vals["id"]: vals for vals in result}
        return [index[record.id] for record in records if record.id in index]

    @api.model
    def search_parents(
        self, domain=False, offset=0, limit=None, order=None, count=False
    ):
        """This method finds the top level elements of the
        hierarchy for a given search query.

        :param domain: a search domain <reference/orm/domains> (default: empty list)
        :param offset: the number of results to ignore (default: none)
        :param limit: maximum number of records to return (default: all)
        :param order: a string to define the sort order of the query
             (default: none)
        :param count: counts and returns the number of matching records
             (default: False)
        :returns: the top level elements for the given search query
        """
        if not domain:
            domain = []
        res = self._search_parents(
            domain=domain, offset=offset, limit=limit, order=order, count=count
        )
        return res if count else self.browse(res)

    @api.model
    def _search_parents(
        self, domain=False, offset=0, limit=None, order=None, count=False
    ):
        if not domain:
            domain = []
        self._check_parent_field()
        self.check_access("read")
        if Domain(domain).is_false():
            return 0 if count else []
        # ``search`` already applies the domain, ir.rules and access rights
        # (replacing the former _where_calc/_apply_ir_rules internals, which
        # were removed/reworked in Odoo 19).
        matching = self.search(domain, order=order)
        matching_ids = set(matching.ids)
        parent_field = self._parent_name
        # A record is a root of the filtered hierarchy when it has no parent,
        # or its parent is not part of the matching set (inaccessible or out of
        # the domain), so it must be shown as a top level node.
        roots = matching.filtered(
            lambda rec: not rec[parent_field]
            or rec[parent_field].id not in matching_ids
        )
        if count:
            return len(roots)
        if offset:
            roots = roots[offset:]
        if limit:
            roots = roots[:limit]
        return roots.ids
