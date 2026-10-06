dms.certificate.revoke
======================

.. py:currentmodule:: odoo.addons.dms_certify_portal.wizards.dms_certificate_revoke

Source: :ghsrc:`wizards/dms_certificate_revoke.py`

.. py:class:: DmsCertificateRevoke

   Bases: ``odoo.models.TransientModel`` directly — no ``_inherit``.

   :Odoo model: ``dms.certificate.revoke`` — ``self.env["dms.certificate.revoke"]``
   :Description: Revoke a certified document
   :Order: inherited default; nothing to sort
   :Constraints: none declared — ``required=True`` on ``reason`` does the work

   A dialog whose entire purpose is to make somebody type a sentence.

   .. admonition:: The reason is not paperwork
      :class: important

      It is **printed on the public refusal notice**. An agent at an embassy
      holding a genuine-looking paper reads it, verbatim, as the explanation for
      why they must turn it away — see
      :py:meth:`DmsCertificate._get_public_values
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._get_public_values>`,
      which exposes ``revoke_reason`` only while ``public_state == 'revoked'``.

      That is why a header button calling
      :ref:`action_revoke() <dms_certificate-action_revoke>` directly would be
      the wrong design even though the method accepts ``reason=None``. The
      method's fallback is *"No reason recorded."*, which is a legitimate value
      for a revocation performed in a migration script and a useless one on a
      page an embassy is reading.

      Revocation being **irreversible** is the second reason for the stop. There
      is no un-revoke; the state is terminal and
      :py:meth:`DmsCertificate.certify
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.certify>`
      refuses to re-seal a revoked record.

   Only three fields, two of which are there so the dialog can name the
   document it is about. A transient model rather than a context-carrying
   action because ``required=True`` on a field is the only mechanism that
   actually blocks an empty value at the client.

.. contents::
   :local:
   :depth: 2

Fields
------

.. py:attribute:: DmsCertificateRevoke.certificate_id
   :type: fields.Many2one

   → ``dms.certificate``, ``required=True, ondelete="cascade", readonly=True``

   What is being withdrawn. ``readonly=True`` and invisible on the form: the
   record is resolved from the context by
   :py:meth:`~DmsCertificateRevoke.default_get`, not chosen, so offering a
   picker would only create a way to revoke the wrong document from the right
   row.

   ``ondelete="cascade"`` is the correct direction for a transient: an
   abandoned wizard row must not keep a certificate alive, and
   :py:meth:`DmsCertificate._unlink_except_issued
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._unlink_except_issued>`
   is what stops an issued certificate being deleted in the first place.

.. py:attribute:: DmsCertificateRevoke.reference
   :type: fields.Char

   ``related="certificate_id.reference", readonly=True``

   Embedded mid-sentence in the dialog's warning so the dialog says which
   document it is about. A dialog opened from the wrong row is otherwise
   indistinguishable from one opened from the right one — see
   :doc:`../views/dms_certificate_revoke_views`.

   A ``related`` rather than a copy, so it cannot drift from the record it
   names.

.. _dms_certificate_revoke-reason:

.. py:attribute:: DmsCertificateRevoke.reason
   :type: fields.Char

   ``string="Reason", required=True,
   default=lambda self: _("Movement cancelled by the vessel operator.")``

   The sentence the embassy reads. ``required=True`` is the whole wizard.

   The default is deliberately **plausible rather than empty**, which cuts both
   ways and the view compensates for it. A plausible default is the common case
   typed for you — most revocations really are a cancelled movement — but it
   also means pressing :guilabel:`Revoke` without reading ships that sentence
   whatever actually happened. The form answers that by naming the audience in
   the placeholder (:guilabel:`Shown to the embassy on the refusal notice`)
   rather than by leaving the field blank, because a blank required field only
   teaches people to type a full stop.

   A ``Char``, not a ``Text``: this is one line on a refusal notice, and a
   field that invites three paragraphs would get three paragraphs.

   The default is wrapped in ``_()`` so it follows the *operator's* language at
   the moment they revoke. Note that it is then stored as a plain string and
   printed to the embassy as typed — the refusal notice shows the reason in
   whatever language it was written in, while the rest of the page follows the
   reader's choice. That is the only way round it can work: the sentence is
   free text nobody can translate later.

Overrides
---------

.. py:method:: DmsCertificateRevoke.default_get(fields_list)
   :classmethod:

   ``@api.model``. ``super()``, then pick up ``active_id`` as
   :py:attr:`~DmsCertificateRevoke.certificate_id` — but **only when**
   ``active_model == 'dms.certificate'``.

   The model guard is the part worth naming. ``active_id`` is set by whatever
   view launched the action, and an ``act_window`` with
   ``binding_model_id`` left open can be reached from a context that has
   nothing to do with certificates; without the check the wizard would open
   pre-filled with the id of an unrelated record of a different model, which
   ``required=True`` would happily accept as a valid ``Many2one`` because the id
   number exists. The action record sets ``binding_model_id`` to ``False``
   explicitly (:doc:`../views/dms_certificate_revoke_views`), and this is the
   matching guard in Python.

   ``setdefault`` rather than assignment, so an explicit ``default_certificate_id``
   in the context still wins — which is how a caller that is not a list view
   opens the dialog.

   No ``active_ids``: revocation is one document at a time. Each revocation has
   its own reason, and a batch dialog would either ask for one sentence to cover
   several documents or ask for several sentences in one form. The first is
   wrong on the notice; the second is a list view.

Actions
-------

.. py:method:: DmsCertificateRevoke.action_revoke()

   ``ensure_one()``, delegate to
   :ref:`DmsCertificate.action_revoke(reason=self.reason)
   <dms_certificate-action_revoke>`, then close the dialog with
   ``{'type': 'ir.actions.act_window_close'}``.

   .. admonition:: It writes no state of its own
      :class: important

      Four lines, and three of them are the delegation. The wizard does not set
      ``state``, does not stamp ``revoked_on`` or ``revoked_uid``, does not post
      to the thread and does not touch the sealed bytes. Everything that
      happens on a revocation happens in one method on the certificate.

      That is what keeps **one revocation path**. A revocation performed from a
      migration script, from a producing module, from the shell or from this
      dialog produces the same state, the same chatter entry and the same public
      notice, because there is only one implementation to be consistent with.
      Had the wizard written the fields itself there would be two, and the
      second one would be the one that forgot the thread.

      ``action_revoke`` on the certificate also accepts the reason through a
      ``revoke_reason`` context key. This wizard does not use it — it passes the
      value as an argument — but that is why the method has the fallback chain
      it does.

   Returning ``act_window_close`` rather than a reloading action is what leaves
   the operator on the certificate form they started from, with the chatter
   entry the delegation just posted visible on the next read.

   :raises UserError: nothing here, but see
      :ref:`DmsCertificate.action_revoke() <dms_certificate-action_revoke>` for
      what it does and does not guard.

See also
--------

* :doc:`../models/dms_certificate` —
  :ref:`action_revoke() <dms_certificate-action_revoke>`, the single revocation
  path, and why revoking deliberately does **not** re-stamp the document
* :doc:`../views/dms_certificate_revoke_views` — the dialog, the warning above
  the field, and the header button that opens it
* :doc:`../controllers/verify` — what a lookup against a revoked reference
  returns
* :doc:`../../handbook/verification` and :ref:`verification-refusals` — the
  refusal notice this reason is printed on
* :doc:`../../handbook/issuing` — revocation in the context of the rest of the
  lifecycle
* :doc:`../../development/testing` — ``test_the_revoke_wizard_carries_the_reason_through``,
  ``test_revoking_posts_the_reason_the_embassy_will_read``
