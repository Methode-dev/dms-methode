dms.certificate.type
====================

.. py:currentmodule:: odoo.addons.dms_certify_portal.models.dms_certificate_type

Source: :ghsrc:`models/dms_certificate_type.py`

.. py:class:: DmsCertificateType

   Bases: ``odoo.models.Model`` directly — no ``_inherit``.

   :Odoo model: ``dms.certificate.type`` — ``self.env["dms.certificate.type"]``
   :Description: Certified Document Type
   :Order: ``sequence, name``
   :Constraints: ``_code_unique`` — ``UNIQUE(code)``; ``_unlink_except_used``

   What kind of document a certificate stands for — *Letter of Invitation*,
   *Letter of Guarantee*, whatever the producing module issues. It is the
   string the public page shows under the reference, so it has to be a real
   document name and not a category.

   .. admonition:: A model, not a Selection, and this module ships none
      :class: important

      Two decisions, and they are the same decision twice.

      **A model**, because a producing module adds its documents as data
      records rather than by overriding a method or xpath-ing a selection list,
      so the vocabulary grows without code. And because the choices that vary
      by *kind* of document rather than by individual document — today
      :py:attr:`~DmsCertificateType.auto_stamp`, in time a default validity or
      disclosure — need somewhere to live that an administrator can reach from
      :menuselection:`Consular --> Configuration --> Document types`.

      **None shipped.** There is no ``data/dms_certificate_type.xml`` and
      nothing in ``__manifest__.py``'s ``data`` list seeds one. What a document
      *is* belongs to whoever produces it; a generic fallback would fill the
      registry, the public page and the :guilabel:`Stamp on generation` list
      with entries nobody issues. The module used to ship *Visa*, *Certificate*,
      *Attestation* and *Other*, carried over from the Selection this model
      replaced, and the 19.0.5.0.0 migration deletes exactly those where they
      are unused — see :doc:`../migrations`.

      The consequence is that :py:attr:`DmsCertificate.type_id
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.type_id>`
      is ``required=True`` with **no default**, so a fresh install cannot issue
      anything until somebody declares a type. That is intentional; see
      :doc:`../../handbook/quickstart`.

.. contents::
   :local:
   :depth: 2

Fields
------

Identity
^^^^^^^^

The split between a renameable label and a frozen key is the whole shape of
this model, so the form says so in as many words
(:doc:`../views/dms_certificate_type_views`).

.. _dms_certificate_type-name:

.. py:attribute:: DmsCertificateType.name
   :type: fields.Char

   ``required=True, translate=True``

   What the verification page prints. ``translate=True`` because that page is
   read in French by an embassy and in English by whoever typed it, and the two
   are not the same reader — test
   ``test_the_public_page_shows_the_type_s_name`` pins that the public dict
   carries this field and not the code.

.. _dms_certificate_type-code:

.. py:attribute:: DmsCertificateType.code
   :type: fields.Char

   ``required=True, index=True, copy=False``

   The stable identifier a producing module passes to
   :py:meth:`DmsCertificateType._get_by_code`. Deliberately **not**
   ``translate=True`` and deliberately not the thing shown on the page: the
   label above can be renamed and translated freely, this cannot, because
   another module's Python refers to it.

   ``index=True`` for the lookup; ``copy=False`` because a duplicated type with
   the same code would fail ``_code_unique`` anyway and an empty code is the
   more useful failure.

   .. note::

      The constraint is declared the Odoo 19 way — ``_code_unique =
      models.Constraint('UNIQUE(code)', "Another document type already uses
      this code.")`` on the class body, not an entry in ``_sql_constraints``.
      Test: ``test_codes_are_unique``.

.. py:attribute:: DmsCertificateType.sequence
   :type: fields.Integer

   ``default=10``. Orders the list and therefore the type picker on a
   certificate. Edited through the handle widget.

.. py:attribute:: DmsCertificateType.active
   :type: fields.Boolean

   ``default=True``

   Archiving is the supported way to retire a kind of document, because
   deleting one is not — see :py:meth:`DmsCertificateType._unlink_except_used`.
   An archived type still resolves through
   :py:meth:`~DmsCertificateType._get_by_code` and still labels the documents
   already issued under it; what it stops is appearing in the picker for new
   ones.

Behaviour
^^^^^^^^^

.. _dms_certificate_type-auto_stamp:

.. py:attribute:: DmsCertificateType.auto_stamp
   :type: fields.Boolean

   ``string="Stamp on generation", default=False``

   When a producing module generates a document of this kind, register it for
   verification straight away — **as a draft**. Sealing stays a separate,
   deliberate act, which is why the help says so: a registered draft has no
   printed reference and answers no lookup
   (:py:data:`LIVE_STATES <odoo.addons.dms_certify_portal.models.dms_certificate.LIVE_STATES>`),
   so turning this on cannot accidentally publish anything.

   ``default=False``, so a type declared by a producing module opts in rather
   than out.

   Editable from two places on purpose — the tick on this model's own list, and
   the :guilabel:`Stamp on generation` checkbox list in
   :menuselection:`Settings --> General Settings`
   (:py:attr:`ResConfigSettings.certify_auto_stamp_type_ids
   <odoo.addons.dms_certify_portal.models.res_config_settings.ResConfigSettings.certify_auto_stamp_type_ids>`).
   The flag lives here rather than in a system parameter so a producing module
   can ship a sensible value with its own data record and an administrator can
   change it without either side knowing about the other.

.. py:attribute:: DmsCertificateType.certificate_count
   :type: fields.Integer

   ``compute="_compute_certificate_count"``

   How many certificates carry this type. Shown on the list and the form, and
   the number that decides whether :py:meth:`~DmsCertificateType._unlink_except_used`
   will let you delete it.

   Computed by ``_compute_certificate_count()`` with an **empty**
   ``@api.depends()``. The decorator is there and its argument list is
   deliberately blank: the count is a ``_read_group`` over ``dms.certificate``
   keyed on ``type_id`` — a field on a *different* model, which ``@api.depends``
   cannot express — so there is nothing to react to and the field is recomputed
   on load instead. Writing the empty decorator rather than omitting it is the
   statement that the absence was considered.

   .. note::

      ``_read_group`` in Odoo 19 returns **recordsets** as group keys, not ids,
      which is why the compute reads ``counts.get(record, 0)`` and not
      ``counts.get(record.id, 0)``. Keying the dict by id here would silently
      count zero for every row.

Computes
--------

.. py:method:: DmsCertificateType._compute_certificate_count()

   Documented with its field above.

Resolution
----------

.. _dms_certificate_type-get_by_code:

.. py:method:: DmsCertificateType._get_by_code(code)
   :classmethod:

   ``@api.model``. A producing module's key to a type record, or an empty
   recordset for an unknown or empty *code*.

   :param str code: the value of :py:attr:`~DmsCertificateType.code`.
   :returns: ``dms.certificate.type``, at most one record.

   Searched ``with_context(active_test=False)``, so an **archived** type still
   resolves. That is the point: a module that has been registering ``loi``
   documents for a year must not start creating them with no type the day
   somebody archives the record, and the 19.0.4.0.0 migration
   (:doc:`../migrations`) relies on the same behaviour to map a retired
   selection value onto a type that may already have been archived.

   Returns an empty recordset rather than raising, because the only caller that
   can do anything useful with the failure is the one that owns the vocabulary.
   The migration treats an empty result as *orphaned* and logs the code for the
   producing module to pick up when it loads.

.. py:method:: DmsCertificateType._auto_stamp_codes()
   :classmethod:

   ``@api.model``. The set of :py:attr:`~DmsCertificateType.code` values whose
   type has :py:attr:`~DmsCertificateType.auto_stamp` set.

   **Nothing in this addon calls it.** It exists for the producing module,
   which knows what it has just generated and asks this set whether to register
   it — a set of codes rather than a recordset because the caller is holding a
   string, not a record.

   Unlike :py:meth:`~DmsCertificateType._get_by_code` this searches with the
   default ``active_test``, so **archiving a type also stops it being stamped
   automatically.** That asymmetry is deliberate on the resolution side and
   worth knowing here: archiving is the switch that takes a kind of document
   out of circulation without disturbing the ones already issued.

   .. note::

      :py:meth:`ResConfigSettings.get_values
      <odoo.addons.dms_certify_portal.models.res_config_settings.ResConfigSettings.get_values>`
      runs the equivalent search with ``active_test=False``, so an archived type
      with the flag still set appears ticked in Settings while no longer being
      stamped. The settings page shows the flag; this method shows the effect.

Guards
------

.. py:method:: DmsCertificateType._unlink_except_used()

   ``@api.ondelete(at_uninstall=False)``

   :raises UserError: when any certificate carries one of these types, naming
      the count and telling the reader to archive instead *"so those documents
      keep saying what they are"*.

   Deleting a type in use would leave issued documents unable to say what they
   are, on a page whose whole job is to say so — and
   :py:attr:`DmsCertificate.type_id
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.type_id>`
   is ``ondelete="restrict"``, so the database would refuse anyway with a
   message nobody can act on. This turns that into a sentence with a remedy in
   it.

   The count is taken under ``sudo()``. That is not decoration: ``dms.certificate``
   carries a company record rule (:doc:`../security/ir_rule`), so an unprivileged
   count would read *unused* for a type that only labels another company's
   documents, and the delete would then fail at the foreign key instead.

   ``at_uninstall=False`` so uninstalling the module is still possible. Test:
   ``test_a_type_in_use_cannot_be_deleted``.

See also
--------

* :doc:`dms_certificate` — :py:attr:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.type_id`
  and ``type_code``, and why the type has no default
* :doc:`res_config_settings` — the :guilabel:`Stamp on generation` list and why
  it is not a system parameter
* :doc:`../views/dms_certificate_type_views` — the editable list, the form and
  the action
* :doc:`../views/res_config_settings_views` — the other place ``auto_stamp`` is
  ticked
* :doc:`../migrations` — 19.0.4.0.0 maps the retired ``document_type``
  selection onto these records; 19.0.5.0.0 removes the generic ones
* :doc:`../../handbook/administration` — declaring the types an operation
  actually issues
* :doc:`../../handbook/issuing` — declaring them from a producing module, as
  data
