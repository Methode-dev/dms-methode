dms_certify_portal_groups
=========================

Source: :ghsrc:`security/dms_certify_portal_groups.xml`

Four records to define two groups, plus one line that grants the stronger of
them to the administrator. Read this before :doc:`ir_model_access` and
:doc:`ir_rule` — both are meaningless without knowing what
:ref:`group_certify_user <dms_certify_portal_groups-group_certify_user>` and
:ref:`group_certify_manager <dms_certify_portal_groups-group_certify_manager>`
are for.

The category and the privilege
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 26 44

   * - External id
     - Model
     - What it is
   * - ``module_category_certify``
     - ``ir.module.category``
     - *Certification*, sequence 90 — the heading on the user form
   * - ``privilege_certify``
     - ``res.groups.privilege``
     - *Document certification*, sequence 90, pointing at the category
   * - ``group_certify_user``
     - ``res.groups``
     - *Certification: Agent*
   * - ``group_certify_manager``
     - ``res.groups``
     - *Certification: Registrar*

.. admonition:: Why there are four records and not two
   :class: important

   Odoo 19 restructured groups. ``res.groups.category_id`` is gone: a group now
   points at a ``res.groups.privilege`` record through ``privilege_id``, and it
   is the *privilege* that carries the ``ir.module.category`` link. The
   privilege is the thing rendered as one selector on the user form, with the
   groups beneath it as its levels.

   So the 18.0 shape — two ``res.groups`` records each naming a category — does
   not load on 19 at all, and a port of this file from an older addon is the
   likeliest reason for an install failure here. Both the category and the
   privilege exist only so the two groups appear under a sensible heading
   instead of under *Extra Rights*.

Groups
------

.. _dms_certify_portal_groups-group_certify_user:

``group_certify_user`` — *Certification: Agent*
   *"Can look up certificates in the back office."*

   Read-only throughout: the registry, the people listed on a document, the
   document types, the attempt log. Everything an operator needs to answer
   *"what did we issue and has anyone checked it?"* and nothing that changes an
   answer.

   This is also the group the record rule in :doc:`ir_rule` is attached to, and
   the group the :guilabel:`Consular` root menu is gated on
   (:doc:`../views/menus`).

.. _dms_certify_portal_groups-group_certify_manager:

``group_certify_manager`` — *Certification: Registrar*
   *"Can publish and revoke certificates, and see passport hashes."*

   ``implied_ids`` links
   :ref:`group_certify_user <dms_certify_portal_groups-group_certify_user>`, so
   a Registrar can do everything an Agent can. Full CRUD on the registry, the
   holders and the types; the revoke wizard; and — the part that is not in the
   access matrix at all — the four ``groups=`` field attributes on
   :doc:`../models/dms_certificate_holder`.

   .. important::

      **Only a Registrar can read a passport number.** It is not an ACL
      decision but a field-level one:
      ``passport_number``, ``passport_hash``, ``passport4_hash`` and
      ``dob_hash`` each declare
      ``groups='dms_certify_portal.group_certify_manager'``, which keeps them
      out of the SQL an Agent's read even issues. An Agent opening a
      certificate sees the crew's names and ranks and no document numbers.

      That is why the comment says *"and see passport hashes"* rather than
      *"and see passports"*: the hashes are as sensitive as the numbers,
      because a hash plus a guess is a confirmation.

Both groups carry a ``comment``, which is what the user form shows as the
tooltip under the selector. It is the only in-product explanation of the split,
so keep it true if the permissions change.

Granted to the administrator at install
---------------------------------------

.. code-block:: xml

   <record id="base.user_admin" model="res.users">
       <field name="group_ids" eval="[Command.link(ref('group_certify_manager'))]"/>
   </record>

Writing onto ``base.user_admin`` rather than extending
``base.group_system.implied_ids``: a Settings user is not automatically a
registrar of consular documents, and tying the two together would mean every
future systems administrator silently acquiring the right to read passport
numbers. One named user gets it, and whoever installed the module can then grant
it deliberately.

.. note::

   ``res.users.groups_id`` was renamed to ``group_ids`` in Odoo 19. The old
   spelling raises on load, which is the second reason a port of this file from
   an 18.0 addon fails.

Nobody else, on purpose
-----------------------

``base.group_public`` and ``base.group_portal`` are granted **nothing** — not a
group here, not an ACL row in :doc:`ir_model_access`, not a record rule in
:doc:`ir_rule`. The public verification page runs as the public user and reaches
the registry only through ``sudo`` inside the controller. The reasoning is on
:doc:`ir_rule`, and it is the single most important decision in this directory.

See also
--------

* :doc:`ir_model_access` — the nine CRUD rows these two groups carry
* :doc:`ir_rule` — the company scope, and why there is no public ACL
* :doc:`../models/dms_certificate_holder` — the four field-level
  ``groups=`` restrictions
* :doc:`../views/menus` — the root gated on the Agent group, Configuration on
  the Registrar group
* :doc:`../../handbook/administration` — which of the two a real person should
  get
