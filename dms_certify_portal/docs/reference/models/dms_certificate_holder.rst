dms.certificate.holder
======================

.. py:currentmodule:: odoo.addons.dms_certify_portal.models.dms_certificate_holder

Source: :ghsrc:`models/dms_certificate_holder.py`

.. py:class:: DmsCertificateHolder

   Bases: ``odoo.models.Model`` directly — no ``_inherit``. No chatter either:
   the thread for everything that happens to a document lives on
   :doc:`dms_certificate`.

   :Odoo model: ``dms.certificate.holder`` — ``self.env["dms.certificate.holder"]``
   :Description: Certified Document Holder
   :Order: ``sequence, id``
   :Constraints: none declared

   One row per person the document names, and the secret that opens it.

   A letter of invitation names a whole crew, so a certificate has as many
   holders as the page has lines, and **any** of them opens it: the agent at the
   counter has one seafarer in front of them and reads that seafarer's passport
   off the page. That is why the second factor is checked against a *set* of
   rows rather than against one credential on the certificate, and why
   :py:meth:`DmsCertificate._match
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._match>`
   walks the holders.

   This model carries two jobs that look unrelated and are not: it is the
   **access control** for a lookup (the hashes), and it is the **map** of where
   each person's details sit on the page (the boxes), which is what lets a
   confirm-only lookup blank everyone but the person who opened it. Both exist
   because the portal has to answer a stranger about a named individual without
   telling them about anyone else.

.. contents::
   :local:
   :depth: 2

Module constants
----------------

.. _dms_certificate_holder-PASSPORT_KEY_PARAM:

.. py:data:: PASSPORT_KEY_PARAM
   :type: str
   :value: "dms_certify_portal.passport_key"

   The ``ir.config_parameter`` key holding the HMAC pepper. Generated once, at
   install, by ``post_init_hook`` (:doc:`../hooks`) as
   ``secrets.token_urlsafe(48)``; it never leaves the database and is never
   shown in the UI.

   .. warning::

      **Lose it and every stored hash becomes unverifiable.** Not degraded —
      unverifiable: the hashes cannot be recomputed from anything the portal
      holds, so no document opens again until the crew is re-entered and
      re-hashed from a trusted source. Back it up with the filestore, and treat
      restoring a filestore without the database (or the reverse) as a
      recoverable-data question rather than a technicality.

      Rotate it only through a migration that re-hashes from somewhere trusted.
      :py:meth:`DmsCertificateHolder._keyed_hash` raises rather than silently
      producing hashes under a new key. Test:
      ``test_the_hashes_are_keyed_to_this_instance``.

Fields
------

Identity on the page
^^^^^^^^^^^^^^^^^^^^

These four are printed on the document and shown back on the verification page,
so the agent can confirm the person in front of them is the one that matched.

.. py:attribute:: DmsCertificateHolder.certificate_id
   :type: fields.Many2one

   → ``dms.certificate``, ``required=True, ondelete="cascade", index=True``

   ``cascade`` rather than ``restrict``: a holder row has no meaning without the
   document that names them, and the document itself is protected from deletion
   by :py:meth:`DmsCertificate._unlink_except_issued
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._unlink_except_issued>`,
   which is where that guard belongs.

.. py:attribute:: DmsCertificateHolder.sequence
   :type: fields.Integer

   ``default=10``. Keeps the list in the order the page prints it.

.. py:attribute:: DmsCertificateHolder.name
   :type: fields.Char

   ``string="Surname", required=True``

   The only required identity field. A crew line may lack a rank or a date of
   birth; it always has a surname, and without one there is nothing to redact
   by value if the measured boxes go stale.

.. py:attribute:: DmsCertificateHolder.first_name
   :type: fields.Char

.. py:attribute:: DmsCertificateHolder.date_of_birth
   :type: fields.Date

   Also hashable as a second factor — see
   :py:attr:`~DmsCertificateHolder.dob_hash`.

.. py:attribute:: DmsCertificateHolder.rank
   :type: fields.Char

   Fed to the redaction pass, and shown in the ``matched`` block of
   :py:meth:`DmsCertificate._get_public_values
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._get_public_values>`.

.. py:attribute:: DmsCertificateHolder.display_name_public
   :type: fields.Char

   ``compute="_compute_display_name_public"``

   *"First Surname"*, falling back to the surname alone. The one name string the
   public page is given, so the page never has to decide on name ordering
   itself.

   Computed by ``_compute_display_name_public()`` — ``@api.depends("name",
   "first_name")``. Not stored; it is a presentation of two columns already in
   the row.

The credential
^^^^^^^^^^^^^^

.. _dms_certificate_holder-passport_number:

.. py:attribute:: DmsCertificateHolder.passport_number
   :type: fields.Char

   ``copy=False, groups="dms_certify_portal.group_certify_manager"``

   .. admonition:: The number is stored, and the hash beside it is the access control
      :class: important

      These two coexist on purpose, and the split of responsibility between
      them is the decision:

      * the **keyed hash** is what a lookup is matched against. Matching never
        touches this column (:py:meth:`DmsCertificateHolder._stored_factor_hash`).
      * the **stored number** is for the operator who has to correct a typo. A
        crew list typed from a scanned manifest will contain a wrong character,
        the agent at the embassy will report that the document does not open,
        and somebody at the desk has to be able to look at what is recorded and
        see where it differs from the page. With only a hash, the only remedy is
        re-entry from scratch — which is re-typing from the same scan.

      The number is not uniquely held here either: it is already printed inside
      the sealed PDF in the same DMS, and on the crew contact. The registry is
      not the only copy, so hashing it here would buy less than it costs.

      It does mean **a database dump contains passport numbers**. Treat the dump
      accordingly, and read
      :doc:`../../handbook/security-and-privacy` before going live.

   ``groups=`` is the other half: *Certification: Agent* has read access to the
   whole registry and still cannot read this column — Odoo drops a
   group-restricted field out of the read entirely. Only *Certification:
   Registrar* sees it. Tests:
   ``test_reading_a_passport_needs_more_than_agent_access``,
   ``test_the_passport_number_reads_back``.

.. py:attribute:: DmsCertificateHolder.passport_hash
   :type: fields.Char

   ``readonly=True, copy=False, index=True,
   groups="dms_certify_portal.group_certify_manager"``

   HMAC of the whole normalised passport number. Matched when the certificate's
   second factor is ``pptfull``, and the value
   :py:meth:`DmsCertificateHolder._survives` tests every surviving word against.

.. py:attribute:: DmsCertificateHolder.passport4_hash
   :type: fields.Char

   ``readonly=True, copy=False, index=True,
   groups="dms_certify_portal.group_certify_manager"``

   HMAC of the **last four** characters. Matched when the second factor is
   ``ppt4``, which is the default: four characters is what an agent can read off
   a faxed page and type without a mistake.

.. py:attribute:: DmsCertificateHolder.dob_hash
   :type: fields.Char

   ``readonly=True, copy=False, index=True,
   groups="dms_certify_portal.group_certify_manager"``

   HMAC of the date of birth as ``DDMMYYYY``.

.. note::

   **Three hashes, one per mode, all maintained at once.** The issuer can switch
   a document from *last 4* to *full passport* to *date of birth* after it has
   been issued without the crew being entered again, because the hash the new
   mode needs is already there. That is the entire reason for keeping three
   columns rather than one hash of whichever factor is currently selected. Test:
   ``test_switching_the_second_check_needs_no_re_entry``.

   They are group-restricted alongside the number. A hash of a four-character
   string is not a secret from anybody who can run a wordlist, so treating them
   as less sensitive than the plaintext would be a mistake.

   All three carry ``index=True``. Nothing in this module searches them —
   :py:meth:`DmsCertificate._match
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._match>`
   walks ``holder_ids`` in Python — so the indexes serve no query here.

Where this person appears on the page
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:attribute:: DmsCertificateHolder.redaction_boxes
   :type: fields.Text

   ``readonly=True, copy=False``

   JSON list of rectangles, in the source document's own coordinates, where this
   person's details were found by ``seal.locate()`` at registration time. Read
   only through :py:meth:`DmsCertificateHolder._boxes`, never directly.

.. _dms_certificate_holder-boxes_source_hash:

.. py:attribute:: DmsCertificateHolder.boxes_source_hash
   :type: fields.Char

   ``readonly=True, copy=False``

   The fingerprint of the document those rectangles were measured against.

   This field is what makes the measurement *falsifiable*. Coordinates alone
   cannot say which version of a document they describe, so a document
   regenerated underneath them would be redacted at the places the old one had
   its crew lines — which is to say, at the wrong places, silently. Storing the
   hash turns that into a detectable condition.

Computes
--------

.. py:method:: DmsCertificateHolder._compute_display_name_public()

   Documented with its field above.

Hashing
-------

.. py:method:: DmsCertificateHolder._normalize(value)
   :classmethod:

   ``@api.model``. Upper-cases and strips everything that is not ``A-Z0-9``.

   Folds away the ways the same number gets typed at a counter — spaces,
   hyphens, the ``<`` fillers of a machine-readable zone, lower case. Applied to
   **both** sides, stored and submitted, so the two can never disagree about
   what counts as the same number. Test:
   ``test_separators_and_case_do_not_decide_the_outcome``.

.. _dms_certificate_holder-keyed_hash:

.. py:method:: DmsCertificateHolder._keyed_hash(value)
   :classmethod:

   ``@api.model``. ``hmac.new(pepper, value, sha256).hexdigest()``, or ``False``
   for an empty value.

   .. admonition:: The pepper is what makes hashing worth doing here
      :class: important

      The factor values are tiny. Four characters of a passport number is a few
      thousand possibilities; a plausible date of birth is a few tens of
      thousands. An unkeyed SHA-256 of one of those falls to an exhaustive
      sweep on a laptop in no time, so a bare digest in the table would be
      almost as good as the plaintext to anyone who got the table.

      With a key that is **not** in the table, it does not: the sweep needs the
      pepper, and the pepper is one ``ir.config_parameter`` row an attacker with
      a dump of this table may well not have. That is the whole security
      argument, and it is why
      :py:data:`PASSPORT_KEY_PARAM` is a backup item rather than an
      implementation detail.

   :raises UserError: when the parameter is missing, naming it and telling the
      reader to reinstall the module or restore it from backup. **It does not
      fall back to an unkeyed digest**, which would quietly write hashes nothing
      can later verify.

.. py:method:: DmsCertificateHolder._dob_digits(value)
   :classmethod:

   ``@api.model``. ``DDMMYYYY`` — exactly the shape the portal asks an agent to
   type, so the stored and submitted sides are the same string before hashing.
   Empty string for a missing date.

.. py:method:: DmsCertificateHolder._recompute_credentials()

   Rebuild all three hashes from :py:attr:`~DmsCertificateHolder.passport_number`
   and :py:attr:`~DmsCertificateHolder.date_of_birth`.

   ``passport4_hash`` is only written when the normalised number is at least
   four characters long; anything shorter gets ``False``, so a truncated entry
   fails to match rather than matching on a two-character prefix.

   Called from :py:meth:`DmsCertificateHolder.create` and
   :py:meth:`DmsCertificateHolder.write` rather than being an ``@api.depends``
   compute, because a compute that reads an ``ir.config_parameter`` and raises
   when it is missing is not something you want firing during an arbitrary read.

Matching
--------

.. py:method:: DmsCertificateHolder._stored_factor_hash(factor)

   The stored hash for *factor*, or ``''``. Never the plaintext. ``''`` rather
   than ``False`` so the caller's ``compare_digest`` has a string to work with.

.. py:method:: DmsCertificateHolder._submitted_factor_hash(factor, value)
   :classmethod:

   ``@api.model``. Hash what the agent typed, the way the stored side was
   hashed: normalise, take the last four characters under ``ppt4``, then
   :py:meth:`~DmsCertificateHolder._keyed_hash`.

   Taking the last four *after* normalising matters — ``AB 12 34 56`` and
   ``AB123456`` have to produce the same four characters.

   Also called with a random value by
   :py:meth:`DmsCertificate._match
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._match>`
   when no certificate was found, purely to spend the same time as a real
   comparison.

Redaction
---------

.. py:method:: DmsCertificateHolder._store_boxes(boxes, source_hash)

   Write the rectangles and the fingerprint they were measured against, under
   ``sudo`` — the fields are ``readonly``, and the caller may be running as the
   producing module's user.

.. _dms_certificate_holder-boxes:

.. py:method:: DmsCertificateHolder._boxes(source_hash)

   :returns: the list of rectangles, or ``None``.

   .. admonition:: ``None`` means *untrusted*, not *nothing to hide*
      :class: important

      ``None`` is returned when the stored
      :py:attr:`~DmsCertificateHolder.boxes_source_hash` is missing or does not
      equal *source_hash*, and when the JSON will not parse. In every one of
      those cases the honest statement is "I do not know where this person is on
      this document".

      An empty list ``[]`` is a different answer — *measured, and this person
      appears nowhere* — and it is the one case where redacting nothing is
      correct. Conflating the two is how a page gets served with a crew line
      still on it, so **the caller must fail closed on ``None``**.
      :py:meth:`DmsCertificate._public_bytes
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._public_bytes>`
      does: it collects every such holder into ``unmeasured`` and redacts them
      by value instead, then re-checks the result. Tests:
      ``test_stale_positions_fall_back_to_searching``,
      ``test_a_document_with_no_positions_recorded_is_still_safe``.

.. py:method:: DmsCertificateHolder._survives(tokens)

   :returns: a list of this person's details still present in *tokens* — the
      offending strings, with a leaked passport reported as the literal
      ``'<passport>'`` so the number never reaches a log line.

   The closed-loop check behind step 3 of
   :py:meth:`DmsCertificate._public_bytes
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._public_bytes>`.
   Two passes over every word the redacted page still contains:

   * **exact match** against the surname, first name and stored passport
     number;
   * **hashed match** — each surviving word is normalised, run through
     :py:meth:`~DmsCertificateHolder._keyed_hash`, and compared with
     ``hmac.compare_digest`` against
     :py:attr:`~DmsCertificateHolder.passport_hash`.

   The second pass is the interesting one. It is **the only way to look for
   something that was never kept**: a passport number passed in as a redaction
   secret and deliberately not stored still has a hash here, so the page can be
   searched for it without the module ever holding it. That is what makes
   "never store it" and "prove it is gone" compatible claims.

   Note the scope. The check looks for names and passports; it does **not** look
   for rank or date of birth, although
   :py:meth:`~DmsCertificateHolder._redaction_needles` offers both to the
   redaction pass. A surviving rank is not identifying on its own, and a date in
   a sentence would make the check fire on documents that are fine.

.. py:method:: DmsCertificateHolder._redaction_needles()

   Every string of these holders that is printed on the document: surname, first
   name, rank, passport number, and the date of birth in both ``DD/MM/YYYY`` and
   ``DD-MM-YYYY``.

   Two date formats because the needles have to match whatever the *producing
   module's* report template chose to print, which this module does not know.

   Used twice, for two different purposes: by
   :py:meth:`DmsCertificate.stash_redaction
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.stash_redaction>`
   to *measure* positions, and by
   :py:meth:`DmsCertificate._public_bytes
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._public_bytes>`
   as the fallback when a measurement cannot be trusted. Unlike the other
   methods here it iterates ``self``, so it works on a whole recordset.

Overrides
---------

.. py:method:: DmsCertificateHolder.create(vals_list)

   ``@api.model_create_multi``. ``super()``, then
   :py:meth:`~DmsCertificateHolder._recompute_credentials` on the new rows — so
   a holder created through
   :py:meth:`DmsCertificate.issue
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.issue>`
   is immediately matchable without the caller knowing hashes exist.

.. py:method:: DmsCertificateHolder.write(vals)

   ``super()``, then re-hash **only** when ``passport_number`` or
   ``date_of_birth`` was in *vals*.

   No recursion guard is needed and none is used: the inner write touches the
   three hash fields, none of which is in the condition, so the second pass
   cannot trigger a third.

See also
--------

* :doc:`../../handbook/concepts` and :ref:`concepts-second-factor` — why there
  is a second check at all, and why it is per person
* :ref:`sealing-redaction` — the redaction pipeline this model feeds
* :doc:`../../handbook/security-and-privacy` — what is held, for how long, and
  who can read it
* :doc:`dms_certificate` — :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._match`,
  :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._public_bytes`
  and :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.stash_redaction`
* :doc:`../tools/seal` — ``locate``, ``redact_boxes``, ``redact`` and
  ``text_tokens``
* :doc:`../hooks` — where the pepper comes from
* :doc:`../security/dms_certify_portal_groups` — Agent against Registrar
* :doc:`../../development/testing` — ``test_certificate.py``, the *credentials*
  and *redaction* classes
