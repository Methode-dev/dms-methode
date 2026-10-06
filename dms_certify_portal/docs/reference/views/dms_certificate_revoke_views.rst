dms_certificate_revoke_views
============================

**Model:** :doc:`dms.certificate.revoke <../wizards/dms_certificate_revoke>`

Source: :ghsrc:`views/dms_certificate_revoke_views.xml`. One form, one action.
Loaded **before** :doc:`dms_certificate_views`, because the certificate form's
header binds ``action_dms_certificate_revoke`` by xmlid and the record has to
exist by then.

Structure
---------

.. code-block:: text

   form "Revoke document"          (no <sheet> — it is a dialog)
     div.alert.alert-warning  role="alert"
       "Revoking <reference> is permanent. Anyone checking it from now on is
        told not to accept it, and given the reason below."
     group
       certificate_id   invisible="1"
       reason           placeholder "Shown to the embassy on the refusal notice"
     footer
       [Revoke]  btn-danger  → action_revoke
       [Cancel]  btn-secondary  special="cancel"

Record ids
----------

.. list-table::
   :header-rows: 1
   :widths: 44 22 34

   * - External id
     - Kind
     - Notes
   * - ``view_dms_certificate_revoke_form``
     - ``ir.ui.view``
     - Dialog form, no sheet
   * - ``action_dms_certificate_revoke``
     - ``ir.actions.act_window``
     - ``target="new"``, ``binding_model_id`` explicitly ``False``

Decisions worth naming
----------------------

**A wizard rather than a button, because of the reason.** ``action_revoke`` on
the certificate takes a reason, and that reason is not an internal note — it is
printed on the refusal notice an embassy reads. ``reason`` is ``required=True``
with a plausible default (*"Movement cancelled by the vessel operator."*), so a
header button with no dialog would ship that default on every revocation,
whatever actually happened. The placeholder names the audience instead:
:guilabel:`Shown to the embassy on the refusal notice`.

**The warning is above the field, not beside the button.** The consequence —
permanent, and visible to every future reader — is what the operator needs before
typing, not after. ``<field name="reference" readonly="1" class="oe_inline"/>``
is embedded mid-sentence so the dialog names the document it is about; a dialog
opened from the wrong row is otherwise indistinguishable from the right one.

**``btn-danger`` on the confirm and no ``btn-primary`` anywhere.** There is no
safe default action in this dialog, so nothing is styled as one. :guilabel:`Cancel`
uses ``special="cancel"`` and therefore discards the transient record without
reaching Python at all.

.. admonition:: ``binding_model_id`` is set to ``False`` on purpose
   :class: important

   .. code-block:: xml

      <field name="binding_model_id" eval="False"/>

   Without this, Odoo is free to infer a binding from the wizard's own model and
   offer :guilabel:`Revoke document` in the :guilabel:`Action` cog menu — from a
   list, over a multi-selection. Revoking a page of certificates in one gesture,
   all with the same reason, is not an operation this module wants to make
   available. The only way in is the header button on one open certificate.

**``certificate_id`` is on the form and invisible.** It is filled from the
context the header button passes (``active_model`` / ``active_id``), and
``reference`` is a related field reading through it — so the field has to be
loaded for the alert to have anything to print.

See also
--------

* :doc:`../wizards/dms_certificate_revoke` — the default, and what
  ``action_revoke`` does to the sealed bytes (nothing)
* :doc:`dms_certificate_views` — the header button, and the
  :guilabel:`Revocation` group that appears afterwards
* :doc:`../templates` — ``verify_result``, which is where the reason is read
* :doc:`../../handbook/issuing` — withdrawing a document
