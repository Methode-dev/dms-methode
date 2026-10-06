ir_model_access
===============

Source: :ghsrc:`security/ir.model.access.csv`

Nine rows over five models and two groups. Read
:doc:`dms_certify_portal_groups` first for what
:ref:`group_certify_user <dms_certify_portal_groups-group_certify_user>`
(*Agent*) and
:ref:`group_certify_manager <dms_certify_portal_groups-group_certify_manager>`
(*Registrar*) are meant to be.

The matrix
----------

.. list-table::
   :header-rows: 1
   :widths: 30 20 10 10 10 10

   * - Model
     - Group
     - Read
     - Write
     - Create
     - Unlink
   * - :doc:`../models/dms_certificate`
     - :ref:`Agent <dms_certify_portal_groups-group_certify_user>`
     - Yes
     - No
     - No
     - No
   * - :doc:`../models/dms_certificate`
     - :ref:`Registrar <dms_certify_portal_groups-group_certify_manager>`
     - Yes
     - Yes
     - Yes
     - Yes
   * - :doc:`../models/dms_certificate_holder`
     - :ref:`Agent <dms_certify_portal_groups-group_certify_user>`
     - Yes
     - No
     - No
     - No
   * - :doc:`../models/dms_certificate_holder`
     - :ref:`Registrar <dms_certify_portal_groups-group_certify_manager>`
     - Yes
     - Yes
     - Yes
     - Yes
   * - :doc:`../models/dms_certificate_attempt`
     - :ref:`Agent <dms_certify_portal_groups-group_certify_user>`
     - Yes
     - No
     - No
     - No
   * - :doc:`../models/dms_certificate_attempt`
     - :ref:`Registrar <dms_certify_portal_groups-group_certify_manager>`
     - Yes
     - No
     - No
     - **Yes**
   * - :doc:`../models/dms_certificate_type`
     - :ref:`Agent <dms_certify_portal_groups-group_certify_user>`
     - Yes
     - No
     - No
     - No
   * - :doc:`../models/dms_certificate_type`
     - :ref:`Registrar <dms_certify_portal_groups-group_certify_manager>`
     - Yes
     - Yes
     - Yes
     - Yes
   * - :doc:`../wizards/dms_certificate_revoke`
     - :ref:`Registrar <dms_certify_portal_groups-group_certify_manager>`
     - Yes
     - Yes
     - Yes
     - Yes

Patterns worth naming
---------------------

**Read for the Agent, CRUD for the Registrar.** Four of the five models follow
that one shape, which is the two group names restated as permissions: an
operator consults the registry to answer a question, a registrar changes what it
says. There is no middle tier and no per-field write exception, so there is
never a question about which of the two a given screen needs.

**The attempt log is the exception, and it is read-and-unlink only — even for
the Registrar.** Nobody may write one and nobody may create one.

.. admonition:: Why create is denied to everybody
   :class: important

   Every row in :doc:`../models/dms_certificate_attempt` is written by
   :doc:`../controllers/verify` through
   ``self.sudo().create(...)`` in ``log()``, which bypasses
   ``ir.model.access`` entirely. The CSV therefore does not need to grant
   create — and granting it anyway would make the log forgeable from the UI by
   the one person whose actions it is partly there to evidence.

   It is both the audit trail *and* the throttle counter, so a hand-written row
   does not merely mislead a reader: it moves the rate limit. Inventing five
   failures against a reference locks that reference for everyone, and deleting
   them unlocks it.

   ``perm_unlink`` is granted because retention has to be enforceable by hand as
   well as by the daily cron (:doc:`../data/ir_cron`) — a data-protection
   request does not wait for a scheduled job.

**The Agent can read the holder rows but not the passport numbers on them.**
That is not in this file. ``passport_number``, ``passport_hash``,
``passport4_hash`` and ``dob_hash`` each carry
``groups='dms_certify_portal.group_certify_manager'`` on the field itself, so
an Agent's read never even includes those columns. The CSV row grants access to
the *model*; the field attributes decide what comes back. Looking only here
would tell you an Agent can read passports, and they cannot.

**The revoke wizard has a Registrar row and no Agent row at all.** Revocation is
irreversible and goes on the public page as a refusal notice with a reason
attached, so it is not something to make reachable and then guard with a check
inside the wizard. Without the ACL the action cannot be opened in the first
place. Contrast the usual Odoo habit of granting ``base.group_user`` full CRUD
on every ``TransientModel`` because it is only scratch state — true of most
wizards, not of this one.

**No row grants anything to** ``base.group_user``, ``base.group_portal`` **or**
``base.group_public``. An Odoo user with no certification group has no access to
this registry whatsoever, which is deliberate for a module whose records name
people and carry their document numbers. The absence of a public row is the more
load-bearing half; see :doc:`ir_rule`.

**Create on** ``dms.certificate`` **is for the standalone case.** In the normal
flow a producing module calls
:py:meth:`issue() <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.issue>`
under ``sudo`` and the ACL is never consulted. The row exists so a Registrar can
register a document nobody here generated — a scanned attestation dropped into
``source_attachment_id`` — from the UI, which is the same reason that field has
a picker at all.

Unlink is narrower than it looks
--------------------------------

Three models grant the Registrar ``perm_unlink``, and in two of them a guard in
Python stands behind it:

* ``dms.certificate`` — ``_unlink_except_issued()`` refuses anything in
  ``LIVE_STATES``, so the ACL reaches drafts only. Revoke instead.
* ``dms.certificate.type`` — ``_unlink_except_used()`` refuses a type that any
  certificate points at. Archive instead.

The ACL is the outer door and the ``@api.ondelete`` guard is the inner one. Do
not read a ``1`` in the last column as *"a registrar can delete issued
documents"*.

See also
--------

* :doc:`dms_certify_portal_groups` — the two groups and the field-level
  passport restriction
* :doc:`ir_rule` — the company scope, and the deliberate absence of a public ACL
* :doc:`../controllers/verify` — the ``sudo`` path that writes the attempt rows
  this file forbids anyone to create
* :doc:`../data/ir_cron` — the other half of attempt-log retention
* :doc:`../../handbook/administration` — who should hold which group
