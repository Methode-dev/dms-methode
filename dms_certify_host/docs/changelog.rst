Changelog
=========

19.0.1.0.0
----------

Initial release.

There is no earlier history to record: the manifest has only ever declared
``19.0.1.0.0``, and the addon has no ``migrations/`` directory — it owns no
tables, so there has never been anything to migrate.

Added
^^^^^

* ``post_load`` hook wrapping ``odoo.http.db_filter`` so that
  ``check.<host>`` resolves to the same database as ``<host>``. Guarded by a
  ``_dms_check_host`` marker on the wrapper, so loading the module twice does
  not nest the patch.
* ``hosts.parent_of_check_host`` — strips the ``check.`` prefix, preserving the
  port, and returns ``None`` for anything that is not a check host.
* ``hosts.is_check_host`` — the predicate other addons import;
  ``dms_certify_portal`` uses it to confine the check host to the verification
  portal.
* One ``INFO`` log line at server start, as the evidence that the patch is
  live.
