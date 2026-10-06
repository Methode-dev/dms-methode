Changelog
=========

.. note::

   This page is reconstructed from the manifest version and the scripts under
   ``migrations/``, which are the only record of this addon's history in the
   repository. Versions that needed no data migration left no trace and
   therefore have no entry here — the gaps are gaps in the evidence, not
   quiet releases. The first recorded step is 19.0.3.0.0.

19.0.6.0.0
----------

Changed
^^^^^^^

* **Validity is counted from issuance, not from the movement date.**
  ``valid_until`` is now ``issued_on`` plus the window, and the three choices
  are relabelled accordingly. The document is what expires, and it starts
  existing when it is sealed: a letter produced three weeks before the call
  used to arrive with three weeks of its life already spent, and one produced
  after a delay could be born expired. A draft now has no expiry at all, which
  is right — the portal does not speak about drafts.

  **No migration, deliberately.** ``valid_until`` is stored, so certificates
  already issued keep the date they were issued with; rewriting them would
  change what the portal says about paper already in circulation. The new rule
  applies to anything sealed from here on, and to an existing entry the moment
  its issuance or window is touched.

  The constraint refusing a document that expired before its movement date is
  **gone**. Under the old vocabulary it could only mean a mistyped date; under
  this one it is an ordinary situation an operator should be able to see.

* **The stamp can go in any of the four corners**, not just the two at the
  foot. ``stamp_position`` is a field on the entry, defaulting from the house
  style in Settings, so a producing module can carry through the choice an
  operator made on its own screen. A top corner reserves its strip at the head
  of the page when the page has to make room, so the setting means the same
  thing whichever corner is chosen.

Added
^^^^^

* **A** ``CONFIDENTIAL`` **marking.** Six choices now; it says how the paper is
  to be handled rather than what it is for, and it is what
  ``operations_certify`` marks a Letter of Invitation with.

* **The watermark can be restricted to a page range** — ``marked_pages`` on the
  entry, empty meaning every page as before. It exists because one file can hold
  several documents while carrying one certificate: a manifeste filed together
  with its movement's covering letter must not come out watermarked as though it
  were the letter. The guilloche and the microtext are not ranged — they are
  features of the file and claim nothing about which document inside it is
  certified. See :ref:`sealing-marked-pages`.

* ``issuer_label`` — the issuer as the back office prints them, account id
  included, so two people with the same name can be told apart when a document
  is queried months later. Deliberately **not** in ``_get_public_values()``: an
  embassy is told who issued a document, not what their account id is.

* **The verdict is reached by a scroll rather than a jump.** The result renders
  below the lookup form and the redirect carries ``#result``; the stylesheet now
  makes that smooth, inside a ``prefers-reduced-motion`` guard so anyone who
  asked their system for less motion keeps the jump.

19.0.5.0.0
----------

Removed
^^^^^^^

* **The four generic document types stopped shipping** — *Visa*, *Certificate*,
  *Attestation* and *Other*. They were carried over from the Selection that
  preceded :doc:`reference/models/dms_certificate_type`, and they were
  categories rather than documents anybody issues. Their only real effect was
  to fill :guilabel:`Stamp on generation` in Settings with entries
  corresponding to nothing, sitting next to the entries that correspond to
  real documents.

  This module now ships **no** document types at all, on purpose: what a
  document *is* belongs to whoever produces it. See
  :doc:`handbook/issuing`.

  The migration removes a retired type only when nothing references it. One
  that is genuinely in use is kept and logged, because whatever it labels is
  printed on a page somewhere and the verification page has to keep being able
  to say what that document is — so renaming or archiving it is a judgement
  call left to an administrator rather than something an upgrade decides. See
  :doc:`reference/migrations`.

19.0.4.0.0
----------

Changed
^^^^^^^

* **Document types became records.** ``document_type``, a Selection on
  ``dms.certificate``, became ``type_id`` pointing at the new
  ``dms.certificate.type`` model, so an administrator can decide *per kind of
  document* whether it is stamped on generation — which a hard-coded Selection
  cannot express.

Migration
^^^^^^^^^

The post-migrate script carries two decisions worth knowing about, both
documented at length in :doc:`reference/migrations`:

* **It reads the old column, not the new one.** Adding a required column makes
  Odoo fill every existing row with the field's default *before* the script
  runs, so by the time it executes every certificate already claims to be
  *Other*. The retired ``document_type`` column is the only surviving record of
  what each one actually was.
* **A code this module does not recognise is left alone, not guessed at.** The
  producing module owns that vocabulary and declares its own types when it
  loads, which happens after this script; it picks those certificates up then.
  The count is logged rather than silently dropped.

19.0.3.0.0
----------

Fixed
^^^^^

* **The portal's languages are now activated on upgrade, not only on install.**
  ``post_init_hook`` runs on install alone, so a database that already had the
  module never got the step — leaving the language switcher with nothing to
  switch to and the French copy shipped in ``i18n/fr.po`` unable to reach a
  page. The same ``activate_portal_languages`` the hook calls now runs from a
  post-migrate script as well. See :doc:`reference/hooks`.

Initial release
---------------

No migration script predates 19.0.3.0.0, so the shape of the module at first
release is recorded here from the code rather than from a changelog entry.

Sealing
^^^^^^^

* A post-process on finished PDF bytes — diagonal marking, guilloche border,
  microtext footer, and a block carrying the QR code, the reference and the
  document's fingerprint. No report template is touched, so a re-stamp costs no
  re-render and a document nobody here generated can be sealed the same way.
* The printed fingerprint is the **pre-seal** hash of the source, which is what
  makes it checkable against the original.
* Seal house style configurable centrally: opacity, angle, size, tile or single,
  colour, guilloche, microtext, QR corner, band mode.
* ``tools/seal.py`` holds every stamping concern and no ORM at all. See
  :doc:`reference/tools/seal`.

Verification
^^^^^^^^^^^^

* A public, account-free page on a host of its own, served through
  ``dms_certify_host`` rather than by depending on ``website``. See
  :ref:`limits-no-website`.
* Two inputs: the reference printed beside the QR code, plus the second check
  the issuer chose — the last four characters of a listed passport, the whole
  number, or a listed date of birth.
* POST-Redirect-GET, so a passport never lands in browser history, a
  ``Referer`` header or an access log.
* One error message for every failure, so the form cannot be used to enumerate
  valid references.
* Constant-time comparison, with a throwaway hash computed on a miss so an
  unknown reference and a wrong passport cost roughly the same wall time.
* Non-sequential, high-entropy references in a Crockford base32 alphabet that
  drops ``I``, ``L``, ``O`` and ``U``.
* Redaction under confirm-only disclosure, rebuilt per lookup from positions
  measured at registration, then re-checked for what should have gone —
  **failing closed** if anything survived. See :ref:`sealing-redaction`.

Registry and audit
^^^^^^^^^^^^^^^^^^

* ``dms.certificate`` with its holders, lifecycle states, validity window and
  revocation, carrying ``mail.thread`` as an audit trail.
* Passport numbers stored alongside a keyed HMAC hash — the hash is the access
  control, the stored number is for the operator correcting a typo. Readable by
  a registrar, not by an agent.
* ``dms.certificate.attempt`` recording every lookup, with two independent
  limits: per address, and per reference from **any** address.
* The desk told about the lookups that matter, and shown *"An external user"*
  rather than an address.

Integration
^^^^^^^^^^^

* ``issue()`` as the entry point, plus ``stash_redaction()`` for registering a
  document before it is sealed.
* Three documented override points — ``_certify_source``,
  ``_generate_reference``, ``_get_public_values``. See
  :ref:`issuing-override-points`.
* ``_get_public_values()`` as the security boundary: plain data, never a
  recordset.

Security
^^^^^^^^

* Two groups, *Certification: Agent* and *Certification: Registrar*.
* Deliberately **no** public or portal ACL — the controller is the only door.
  See :doc:`reference/security/ir_rule`.
* A multi-company record rule on certificates.
* A per-instance HMAC pepper generated at install.
* ``google_recaptcha`` as a soft dependency, picked up with no code change.

Other
^^^^^

* French translation of the public portal surface.
* A daily cron purging the attempt log on a configurable retention.
