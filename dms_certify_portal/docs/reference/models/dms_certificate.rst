dms.certificate
===============

.. py:currentmodule:: odoo.addons.dms_certify_portal.models.dms_certificate

Source: :ghsrc:`models/dms_certificate.py`

.. py:class:: DmsCertificate

   Bases: ``odoo.models.Model``, with ``_inherit = ['mail.thread',
   'mail.activity.mixin']`` — the thread and the activity list are part of what
   this model is for, not decoration.

   :Odoo model: ``dms.certificate`` — ``self.env["dms.certificate"]``
   :Description: Verifiable Certificate
   :Order: ``create_date desc, id desc``
   :Rec name: ``reference``
   :Constraints: ``_reference_unique`` — ``UNIQUE(reference_key)``;
      ``_check_dates``; ``_check_seal_text``; ``_unlink_except_issued``

   **This is not the document.** It is a thin, verifiable projection of a file
   that lives somewhere else — a ``dms.file``, an ``ir.attachment``, whatever
   the producing module points at — holding only what the public page is
   allowed to show plus the artifacts the portal serves. The separation is the
   whole security argument of the module: a bug in a QWeb template on the
   public host cannot walk from here into business records, because there is
   nothing here to walk to.

   The source file is never modified. Sealing is a post-process
   (:doc:`../tools/seal`) that reads the source and writes a *copy* owned by
   this record, which is why a re-stamp costs no re-render, why a scanned
   attestation nobody here generated can be sealed the same way, and why
   revoking a document does not touch a byte of it.

   The thread lives on the certificate rather than on the document it stands
   for: certification is what the desk is being told about, and a producing
   module can always mirror a message onto its own record. See
   :doc:`../static/certificate_chatter` for what that thread is allowed to
   accept.

.. contents::
   :local:
   :depth: 2

Module constants
----------------

.. _dms_certificate-REFERENCE_ALPHABET:

.. py:data:: REFERENCE_ALPHABET
   :type: str
   :value: "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

   Crockford base32 — the full alphabet minus ``I``, ``L``, ``O`` and ``U``.

   The reason is transcription, not cryptography. An agent at a counter is
   retyping this off a printed page that has frequently been scanned or faxed
   on the way, and in that condition ``1``/``I`` and ``0``/``O`` are the same
   glyph. Dropping the four ambiguous letters means there is no wrong answer to
   guess at. ``U`` goes with them, as Crockford has it, to keep accidental
   obscenities out of a reference somebody has to read aloud down a phone line.

   .. important::

      The public page states in so many words that those four letters are never
      used, so an agent knows a shape they are unsure of cannot be one of them.
      **Change the alphabet and you have to change that sentence** — see
      :doc:`../templates`.

   Thirty-two characters is five bits each; see
   :py:data:`REFERENCE_GROUPS` for how many of them there are.

.. _dms_certificate-REFERENCE_GROUPS:

.. py:data:: REFERENCE_GROUPS
   :type: tuple[int, int]
   :value: (4, 2)

   The random part of a reference, as hyphen-separated groups: four characters,
   then two. Six characters of :py:data:`REFERENCE_ALPHABET` is thirty bits.

   Grouped rather than run together because six characters in one block is the
   length at which people start losing their place mid-retype. The groups are
   cosmetic to the system — :py:meth:`DmsCertificate._normalize_reference`
   strips them before anything is matched.

.. py:data:: SEAL_MARKINGS
   :type: dict[str, str]

   The fixed watermark wording per :py:attr:`DmsCertificate.seal_marking`
   value.

   .. code-block:: python

      SEAL_MARKINGS = {
          'certified': 'CERTIFIED ORIGINAL',
          'embassy': 'FOR EMBASSY SUBMISSION',
          'copy': 'COPY — NOT FOR BOARDING',
          'void': 'VOID',
      }

   Deliberately untranslated: the marking is printed into the PDF at seal time
   and read later by whoever is holding the paper, who is not the user whose
   language Odoo knows. ``custom`` has no entry here — it is the escape hatch
   that lets an issuer type their own, and
   :py:meth:`DmsCertificate._check_seal_text` makes sure they do.

.. _dms_certificate-LIVE_STATES:

.. py:data:: LIVE_STATES
   :type: tuple[str, str, str]
   :value: ("certified", "delivered", "revoked")

   The states in which a document is a real, issued thing the portal will speak
   about at all. Read by :py:meth:`DmsCertificate._match` as a search domain
   and by :py:meth:`DmsCertificate._unlink_except_issued` as a delete guard.

   ``draft`` is absent on purpose: an unsealed document has no printed
   reference, so nobody can be holding one, and a draft that answered a lookup
   would be answering about a page that does not exist yet.

   ``revoked`` **is** present, which is the less obvious half. A revoked
   reference must still resolve, because the whole point is to tell the agent
   holding that paper to turn it away — see :ref:`verification-refusals`.

.. _dms_certificate-PUBLIC_PAGE_DPI:

.. py:data:: PUBLIC_PAGE_DPI
   :type: int
   :value: 200

   What :py:meth:`DmsCertificate._public_page_image` rasterises the public page
   at.

   Measured, not guessed. The stamp's QR is 18 mm square and a version-4/5 code
   needs roughly three pixels per module to decode; at 110 dpi — PyMuPDF's
   default, and ``render_page``'s own — that came out at 2.0–2.2 px/module and
   was unscannable. 200 dpi gives 3.6–4.1, at about 460 KB for a dense A4 page,
   which a lookup pays once. There is a regression test for the legibility
   (``test_the_page_image_is_rendered_fine_enough_to_read``).

Fields
------

Identification
^^^^^^^^^^^^^^

.. _dms_certificate-reference:

.. py:attribute:: DmsCertificate.reference
   :type: fields.Char

   ``required=True, copy=False, index=True, readonly=True,
   default=lambda self: self._generate_reference()``

   What is printed on the document beside the QR code, and the only thing an
   agent types from memory of the page. High-entropy on purpose: a guessable
   reference would leave the second check as the only secret, and the second
   check is four characters.

   ``readonly=True`` is load-bearing rather than cosmetic. Paper circulates for
   months and cannot be recalled, so a reference is immutable once issued —
   :py:meth:`DmsCertificate.certify` re-stamps under the same one, and
   :py:meth:`DmsCertificate.copy` refuses outright rather than inventing a
   second record carrying the same printed string.

.. _dms_certificate-reference_key:

.. py:attribute:: DmsCertificate.reference_key
   :type: fields.Char

   ``compute="_compute_reference_key", store=True, index=True, copy=False``

   The reference with every separator stripped and the case folded —
   ``ICS-2026-DKK-4KQ7-9B`` becomes ``ICS2026DKK4KQ79B``. This is what a lookup
   matches on, so spacing, dashes and capitals never decide the outcome.

   .. admonition:: Why the UNIQUE constraint is on this and not on ``reference``
      :class: important

      Uniqueness has to hold in the space where matching happens. A constraint
      on ``reference`` would happily accept ``ICS-2026-DKK-4KQ7-9B`` and
      ``ICS 2026 DKK 4KQ7 9B`` as two different rows, and then
      :py:meth:`DmsCertificate._match` — which searches ``reference_key`` with
      ``limit=1`` — would silently pick one of them and answer about the wrong
      document. Constraining the normalised form makes that collision
      impossible to create in the first place.

      The ``index=True`` is for the same method: the public lookup is the one
      query in this module whose latency an anonymous caller controls.

   Computed by ``_compute_reference_key()`` — ``@api.depends("reference")``, and
   nothing else, because normalisation is a pure function of the string.

Lifecycle
^^^^^^^^^

.. py:attribute:: DmsCertificate.state
   :type: fields.Selection

   ``[draft, certified, delivered, revoked], default="draft", required=True,
   copy=False, index=True, tracking=True``

   The operator's view of where the document is. ``delivered`` is not set by a
   button in the normal flow — it follows the message, see
   :py:meth:`DmsCertificate.message_post`. ``index=True`` because
   :py:meth:`DmsCertificate._match` filters on it on every public lookup.

.. py:attribute:: DmsCertificate.public_state
   :type: fields.Selection

   ``[valid, expired, revoked, unpublished], compute="_compute_public_state"``

   What the public page reports, which is not the same vocabulary as
   ``state``: an embassy does not care whether a document was emailed, it cares
   whether the paper in front of them is good. ``draft`` and anything else
   outside :py:data:`LIVE_STATES` collapses to ``unpublished``.

   Computed by ``_compute_public_state()`` — ``@api.depends("state",
   "valid_until")``. **Deliberately not stored**: it is a function of today's
   date as well as of the record, so a stored value would freeze the verdict at
   whenever it was last recomputed and an expired document would keep reading
   as valid until something touched it.

Who it names
^^^^^^^^^^^^

.. py:attribute:: DmsCertificate.holder_ids
   :type: fields.One2many

   → ``dms.certificate.holder``, inverse ``certificate_id``, string
   ``Listed people``.

   Every person the page names. **Any** of them opens the document — see
   :doc:`dms_certificate_holder` and :ref:`concepts-second-factor`. A
   certificate with none cannot be certified at all
   (:py:meth:`DmsCertificate.certify`), because nobody would be able to open it.

.. py:attribute:: DmsCertificate.holder_count
   :type: fields.Integer

   ``compute="_compute_holder_count"`` — ``@api.depends("holder_ids")``.
   Not stored; it is a label, not a filter.

.. _dms_certificate-holders_locked:

.. py:attribute:: DmsCertificate.holders_locked
   :type: fields.Boolean

   ``string="Listed people fixed", default=False, copy=False, readonly=True``

   Set by the producing module when it read the listed people off the document
   itself. The list is then the *document's*, not the operator's, and the form
   stops offering :guilabel:`Add a line` or the delete handle — the view reads
   this flag through ``create``/``delete`` on the one2many's ``editable``
   options (:doc:`../views/dms_certificate_views`).

   Without it the portal could answer for people the page does not name, or
   refuse a person it does. Note that this is a **UI** lock, not an ORM one:
   nothing stops a module writing ``holder_ids`` in Python, which is exactly
   what the producing module has to be able to do.

How it opens
^^^^^^^^^^^^

.. py:attribute:: DmsCertificate.second_factor
   :type: fields.Selection

   ``[ppt4, pptfull, dob], required=True, tracking=True,
   default=lambda self: self._default_param("second_factor", "ppt4")``

   What is asked for alongside the reference. **It cannot be switched off** —
   there is no ``none`` member and the field is required, so the reference alone
   never opens a document.

   Switching modes on an issued certificate needs no re-entry of the crew:
   :doc:`dms_certificate_holder` keeps one hash per mode, precisely so this
   field can change afterwards.

.. py:attribute:: DmsCertificate.disclosure
   :type: fields.Selection

   ``[confirm, full], required=True, tracking=True,
   default=lambda self: self._default_param("disclosure", "confirm")``

   How much of the page a successful lookup gets. ``confirm`` confirms the match
   and blanks every other listed person; ``full`` serves the page as issued.
   This is the field :py:meth:`DmsCertificate._public_bytes` and
   :py:meth:`DmsCertificate._get_public_values` both branch on — see
   :ref:`concepts-disclosure`.

Validity
^^^^^^^^

.. py:attribute:: DmsCertificate.movement_date
   :type: fields.Date

   The date the document is *about* — the port call, the flight, the crew
   change. Validity is counted from here rather than from the issue date,
   because a letter written three weeks ahead of a movement is not three weeks
   closer to being stale.

.. py:attribute:: DmsCertificate.validity_days
   :type: fields.Selection

   ``[("30", …), ("90", …), ("0", "Until revoked")], required=True,
   default=lambda self: self._default_param("validity_days", "90")``

   A Selection rather than an Integer: these are the three answers a consular
   desk actually gives, and an open numeric field invites 45 and 60 to appear
   with nobody able to say why. ``"0"`` means no expiry at all.

.. py:attribute:: DmsCertificate.valid_until
   :type: fields.Date

   ``compute="_compute_valid_until", store=True``

   Past this date the portal reports the document as authentic but out of date,
   which is far more useful to an embassy than silence. Stored because
   ``public_state`` is not, and something has to be searchable.

   Computed by ``_compute_valid_until()`` — ``@api.depends("issued_on",
   "validity_days")``. Resolves to ``False`` when either input is missing, and
   ``False`` reads downstream as *valid until revoked*.

   .. admonition:: Counted from issuance, not from the movement
      :class: important

      This counted from :py:attr:`~DmsCertificate.movement_date` until
      19.0.6.0.0. The document is what expires, and it starts existing when it
      is sealed: a letter produced three weeks before the call arrived with
      three weeks of its life already spent, and one produced after a delay
      could be born expired.

      Two consequences. A **draft has no expiry at all**, which is right — the
      portal does not speak about drafts. And certificates issued before the
      change **keep the date they were stored with**, because rewriting them
      would change what the portal says about paper already in circulation;
      the new rule reaches an old entry only when its issuance or its window is
      touched.

The seal
^^^^^^^^

.. py:attribute:: DmsCertificate.seal_marking
   :type: fields.Selection

   ``[certified, confidential, embassy, copy, void, custom], required=True,
   default="certified", tracking=True``

   Which of :py:data:`SEAL_MARKINGS` the diagonal watermark carries, or
   ``custom`` to type your own. Tracked, because what a document claims about
   itself is the sort of change somebody later asks about.

.. py:attribute:: DmsCertificate.seal_text
   :type: fields.Char

   ``compute="_compute_seal_text", store=True, readonly=False``

   The words actually stamped. A **stored writable compute**: it follows
   :py:attr:`~DmsCertificate.seal_marking` until somebody types over it, and
   then keeps what they typed. The pattern is what lets one field be both the
   derived label and the free-text override, instead of a derived field plus an
   override field plus a rule for which wins.

   Computed by ``_compute_seal_text()`` — ``@api.depends("seal_marking")``. The
   ``custom`` branch re-assigns ``record.seal_text or ''``, which is how an
   existing custom string survives a recompute instead of being blanked.

.. py:attribute:: DmsCertificate.stamp_position
   :type: fields.Selection

   ``[br, bl, tr, tl], required=True``, defaulting from
   ``dms_certify_portal.seal_qr_corner``

   Which corner carries the QR code, the reference and the printed fingerprint.
   Bottom right by default, beside where a signature usually sits.

   A field rather than only a system parameter because the choice is one an
   operator makes while looking at the page: a producing module writes through
   whatever was picked on its own screen, and the parameter remains the house
   style every new entry starts from. A **top** corner reserves its strip at the
   head of the page rather than the foot when the page has to make room, so the
   setting means the same thing in all four positions.

.. py:attribute:: DmsCertificate.marked_pages
   :type: fields.Char

   A 1-based inclusive page range — ``"2-3"`` — or empty for every page.

   Empty is the normal case and the behaviour that predates the field. A range
   exists for the one situation that needs it: **a file holding several
   documents but carrying a single certificate.** ``operations_certify`` files a
   manifeste together with its movement's covering letter as one PDF whose
   certificate is the letter's, so marking the whole file would print the
   letter's watermark across a manifeste nobody certified.

   Parsed by :py:meth:`DmsCertificate._marked_page_indices`, which logs and
   falls back to *every page* for an unreadable or impossible value rather than
   raising — a seal must not fail over a hint about where to put a watermark.

   Only the watermark is ranged. The guilloche and the microtext go on every
   page regardless: they are features of the file, and claim nothing about which
   document inside it is the certified one.

Fingerprints
^^^^^^^^^^^^

.. _dms_certificate-source_hash:

.. py:attribute:: DmsCertificate.source_hash
   :type: fields.Char

   ``string="Document fingerprint", readonly=True, copy=False``

   SHA-256 of the document **as produced, before the seal was applied**. This
   is the value printed inside the stamp and shown on the public page.

   .. admonition:: A file cannot carry its own hash
      :class: important

      Stamping the page changes its bytes, so a fingerprint printed *on* the
      sealed file can never be the fingerprint *of* the sealed file. The hash
      is therefore taken of the source, in
      :py:meth:`DmsCertificate._apply_seal`, immediately before sealing, and
      passed into the spec.

      What that buys is stability. Re-stamping re-reads the same source, so the
      printed fingerprint does not move — which is exactly the claim
      :py:meth:`DmsCertificate.certify` posts to the thread when it re-stamps
      (*"copies already sent still verify"*), and why
      :py:meth:`DmsCertificate._public_bytes` seals the per-person redacted
      copy with ``self.source_hash`` rather than with the hash of the redacted
      bytes. Tests:
      ``test_printed_fingerprint_is_of_the_document_before_sealing``,
      ``test_revoking_keeps_the_printed_fingerprint``.

.. py:attribute:: DmsCertificate.sealed_hash
   :type: fields.Char

   ``string="Sealed file fingerprint", readonly=True, copy=False``

   SHA-256 of the sealed file the portal serves. The operator's side of the
   pair: it identifies the artifact, and it changes on every re-stamp.

Artifacts
^^^^^^^^^

.. py:attribute:: DmsCertificate.source_attachment_id
   :type: fields.Many2one

   → ``ir.attachment``, ``copy=False, ondelete="set null"``, with

   .. code-block:: python

      domain=[('res_field', '=', False),
              ('res_model', '!=', 'dms.certificate')]

   The document to seal, in the standalone case. The domain exists because
   without it the picker fills with attachments nobody means to pick:
   ``res_field`` is set on the internal attachments Odoo keeps behind every
   binary field — including the one holding a ``dms.file``'s own content — and
   ``res_model = dms.certificate`` is this module's own sealed copies, offering
   a sealed page back as a source to seal again. Test:
   ``test_the_source_picker_ignores_the_copies_we_generate``.

   A producing module normally leaves this empty and overrides
   :py:meth:`DmsCertificate._certify_source` instead.

.. py:attribute:: DmsCertificate.sealed_attachment_id
   :type: fields.Many2one

   → ``ir.attachment``, ``copy=False, ondelete="set null", readonly=True``

   The sealed copy, written by :py:meth:`DmsCertificate._store_artifact` and
   owned by this record. Its presence is what
   :py:meth:`DmsCertificate.action_send_to_embassy` and
   :py:meth:`DmsCertificate.action_download_sealed` both gate on.

.. _dms_certificate-preview_pdf:

.. py:attribute:: DmsCertificate.preview_pdf
   :type: fields.Binary

   ``string="Stamped output", compute="_compute_preview_pdf",
   attachment=False, readonly=True``

   The sealed document itself, shown in the form's right-hand panel through the
   ``pdf_viewer`` widget — **not** a picture of it.

   .. admonition:: The opposite choice to the public page, on purpose
      :class: important

      Here the reader is the operator deciding whether the marking sits where
      they want it, so they need a viewer: pdf.js renders vectors, with its own
      zoom and paging, and the stamp stays sharp at any magnification. A raster
      cannot do that.

      On the public page the reader is an anonymous caller, and the point is
      that they get *no* viewer of their own and no file they can re-use — so
      that side is rasterised at :py:data:`PUBLIC_PAGE_DPI`. Same document, two
      opposite answers, because the two readers are not the same person.

   ``attachment=False`` keeps a value that is recomputed on every read out of
   the filestore. Test:
   ``test_preview_is_the_sealed_pdf_not_a_picture_of_it``.

What the portal says about it
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:attribute:: DmsCertificate.type_id
   :type: fields.Many2one

   → ``dms.certificate.type``, ``required=True, index=True,
   ondelete="restrict"``

   **No default.** This module ships no document types of its own: what a
   document *is* comes from whoever produces it, and a generic fallback would
   only fill the registry — and the public page — with *"Other"*. The
   19.0.5.0.0 migration deletes exactly those generic types where they survive
   (:doc:`../migrations`). See :doc:`dms_certificate_type`.

.. py:attribute:: DmsCertificate.type_code
   :type: fields.Char

   ``related="type_id.code", store=True``

   Stored so a producing module can search and group on its own stable key
   without joining, and so the key a document was issued under stays queryable.

.. py:attribute:: DmsCertificate.facts_json
   :type: fields.Text

   ``string="Public facts", default="[]"``

   A JSON list of ``{label, value}`` printed under *Voyage* on the verification
   page. JSON rather than a child model because the vocabulary of a port call —
   vessel, berth, ETA — belongs to the producing module, and a child model here
   would mean this module having opinions about ships.

   ``label`` may be a plain string or a mapping of language to string; see
   :py:meth:`DmsCertificate._resolve_fact_label`. Parsed defensively — a
   malformed value yields no facts rather than a 500 on a public page.

Issuing and ownership
^^^^^^^^^^^^^^^^^^^^^

.. py:attribute:: DmsCertificate.issuer_id
   :type: fields.Many2one

   → ``res.users``, ``copy=False, readonly=True, default=lambda self:
   self.env.user``

   Named on the public page, and the user
   :py:meth:`DmsCertificate._flag_for_attention` puts an activity on. Set at
   create *and* re-asserted by :py:meth:`DmsCertificate.certify` on the first
   seal, so the issuer is whoever actually sealed it.

.. py:attribute:: DmsCertificate.issuer_label
   :type: fields.Char

   ``compute="_compute_issuer_label"`` — ``"George Croiac (uid 7)"``.

   The issuer as the **back office** prints them, account id included, so two
   people with the same name can be told apart when a document is queried months
   later.

   .. important::

      Deliberately absent from
      :py:meth:`DmsCertificate._get_public_values`. An embassy is told who
      issued a document, not what their account id is, and the whitelist is the
      only thing keeping that true — adding this field to that dict is the whole
      leak. Pinned by ``test_the_embassy_page_never_names_the_issuer_s_uid`` in
      ``operations_certify``.

   A compute rather than an override of ``res.users.display_name``: that string
   is read in a hundred unrelated places, and the public page reads
   ``issuer_id.name`` through the whitelist, so overriding it would either leak
   the uid outward or change screens that have nothing to do with certification.

.. py:attribute:: DmsCertificate.issued_on
   :type: fields.Datetime

   ``copy=False, readonly=True``. Written on the first seal only — which is also
   what starts the validity clock, see
   :py:attr:`~DmsCertificate.valid_until`.

.. py:attribute:: DmsCertificate.company_id
   :type: fields.Many2one

   → ``res.company``, ``required=True, index=True, default=lambda self:
   self.env.company``

   Whose name goes into the seal block. The record rule in
   :doc:`../security/ir_rule` is scoped on *this* field rather than on
   ``create_uid``, because every certificate is written under ``sudo`` and a
   rule reading the creator would file the whole registry under OdooBot.

   Note that the *public page*'s company is a separate decision — see
   ``certify_portal_company_id`` on :doc:`res_config_settings`.

.. py:attribute:: DmsCertificate.notify_on_lookup
   :type: fields.Boolean

   ``default=lambda self: self._default_param("notify_on_lookup", "1") == "1"``

   Post every verification back to the desk, not only the ones that need
   someone to act. The ``== '1'`` is the whole reason the parameter is stored as
   ``1`` rather than ``True``: ``ir.config_parameter`` values are strings, and
   ``bool("False")`` is ``True``.

Revocation
^^^^^^^^^^

.. py:attribute:: DmsCertificate.revoke_reason
   :type: fields.Char

   ``copy=False``

   Printed on the public refusal notice, which is why
   :doc:`../wizards/dms_certificate_revoke` insists on it. Exposed through
   :py:meth:`DmsCertificate._get_public_values` **only** when
   ``public_state == 'revoked'`` — a reason typed and then superseded must not
   leak from some other state.

.. py:attribute:: DmsCertificate.revoked_on
   :type: fields.Datetime

   ``copy=False, readonly=True``

.. py:attribute:: DmsCertificate.revoked_uid
   :type: fields.Many2one

   → ``res.users``, ``copy=False, readonly=True``

Link back and audit
^^^^^^^^^^^^^^^^^^^

.. py:attribute:: DmsCertificate.res_model
   :type: fields.Char

   ``string="Source model", index=True, copy=False``

.. py:attribute:: DmsCertificate.res_id
   :type: fields.Many2oneReference

   ``model_field="res_model", index=True, copy=False``

   The record this entry stands for, as a loose reference rather than a
   Many2one — this module must not know the producing module's models exist.
   Written by :py:meth:`DmsCertificate.issue` from the ``source`` recordset.

.. py:attribute:: DmsCertificate.attempt_ids
   :type: fields.One2many

   → ``dms.certificate.attempt``, inverse ``document_id``. Only the attempts
   that *matched* a document land here; a lookup against an unknown reference
   has nothing to attach to. See :doc:`dms_certificate_attempt`.

.. py:attribute:: DmsCertificate.verify_count
   :type: fields.Integer

   ``string="Successful lookups", readonly=True, copy=False``

   A plain stored counter, not a compute over ``attempt_ids`` — the attempt rows
   are vacuumed by :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate_attempt.DmsCertificateAttempt._gc_attempts`
   after the retention window, and the number of times a document was checked
   should outlive the log of who checked it. Incremented by
   :py:meth:`DmsCertificate._register_verification` and shown on the public
   page.

.. py:attribute:: DmsCertificate.last_verified_on
   :type: fields.Datetime

   ``readonly=True, copy=False``

.. py:attribute:: DmsCertificate.verify_url
   :type: fields.Char

   ``compute="_compute_verify_url"``

   ``{public base}/d/{reference}`` — what the QR code encodes and what is
   printed beside it. Note the path: ``/d/…``, not ``/_check/d/…``. The
   ``/_check`` namespace is an internal prefix the request rewrite in
   :doc:`ir_http` adds on the check host, and it must never be emitted.

   Computed with **no** ``@api.depends``. Its moving input is the
   ``dms_certify_portal.public_base_url`` system parameter, which is not a field
   on this record and cannot be expressed as a dependency; its other input,
   :py:attr:`~DmsCertificate.reference`, is ``readonly=True`` and never changes
   after creation, so there is nothing to react to. It is recomputed on load
   instead.

Computes
--------

.. py:method:: DmsCertificate._default_param(name, fallback)
   :classmethod:

   ``@api.model``. Reads ``dms_certify_portal.<name>`` from
   ``ir.config_parameter`` under ``sudo``, with a hard-coded fallback.

   Used as the ``default=`` of every field whose starting value is an
   administrator's choice, which is why those defaults are lambdas rather than
   literals: a literal is captured at import time, a lambda asks the database at
   create time. The full parameter list is on
   :doc:`../data/ir_config_parameter`.

.. py:method:: DmsCertificate._compute_reference_key()
.. py:method:: DmsCertificate._compute_holder_count()
.. py:method:: DmsCertificate._compute_valid_until()
.. py:method:: DmsCertificate._compute_seal_text()
.. py:method:: DmsCertificate._compute_public_state()
.. py:method:: DmsCertificate._compute_verify_url()

   Documented with their fields above.

.. py:method:: DmsCertificate._compute_preview_pdf()

   ``@api.depends("seal_marking", "seal_text", "source_attachment_id", "state",
   "stamp_position", "marked_pages")`` — everything that changes what a stamp
   would *look* like, plus ``state`` so certifying refreshes the panel.

   Deliberately re-seals rather than reading the stored copy back: the point of
   the panel is to show what the marking *currently selected* would produce,
   including before anything has been certified at all
   (``test_preview_renders_before_anything_is_certified``).

   Swallows everything, twice — once around
   :py:meth:`DmsCertificate._certify_source`, once around the seal itself. A
   preview never breaks the form. An unreadable source (a ``.docx`` dropped in
   the attachment field, a truncated PDF) must leave the certificate form
   openable, because that form is where somebody fixes it; the failure goes to
   the log with a traceback and the field stays ``False``, which the view turns
   into a placeholder. Test:
   ``test_preview_survives_a_document_it_cannot_read``.

   The seal *house style* parameters are read inside
   :py:meth:`DmsCertificate._seal_spec` and are not in the dependency list, so a
   change in :menuselection:`Settings --> General Settings` is picked up the
   next time the record is read rather than reactively.

Reference generation
--------------------

.. py:method:: DmsCertificate._normalize_reference(value)
   :classmethod:

   ``@api.model``. Upper-cases and strips everything that is not ``A-Z0-9``.
   The single definition of "the same reference", used by the stored
   :py:attr:`~DmsCertificate.reference_key` and by
   :py:meth:`DmsCertificate._match` on the submitted side, so the two can never
   disagree about what a match is.

.. _dms_certificate-generate_reference:

.. py:method:: DmsCertificate._generate_reference(place_code=None)
   :classmethod:

   ``@api.model``. ``PREFIX-YYYY-PPP-XXXX-XX``, e.g. ``ICS-2026-DKK-4KQ7-9B``:
   the configured prefix, the year, three characters of the port's UN/LOCODE,
   then thirty random bits from :py:data:`REFERENCE_ALPHABET` grouped per
   :py:data:`REFERENCE_GROUPS`.

   .. admonition:: There is no counter, and no ``ir.sequence``
      :class: important

      A sequential component would leak volume: anyone holding two documents
      could read off how many were issued between them, which for a consular
      operation is commercially interesting and occasionally politically
      interesting. Worse, it makes the space *walkable* — an attacker who knows
      ``…-0041`` exists tries ``…-0042``, and the second check becomes the only
      secret standing between them and a document.

      Random throughout, with the prefix/year/place part carrying no
      information an observer does not already have from the page they are
      holding. :doc:`../data/ir_config_parameter` records the same decision as
      the reason there is no sequence record. Tests:
      ``test_reference_carries_no_counter``,
      ``test_reference_never_uses_the_ambiguous_letters``,
      ``test_reference_has_the_printed_shape``.

   ``secrets.choice`` rather than ``random.choice`` — this is a credential.

   *place_code* is sanitised and right-padded with ``X`` to exactly three
   characters, so a missing or short code still produces a reference of the
   printed shape. Defaults to ``FRA``.

   An override point: see :ref:`issuing-override-points`. Keep at least thirty
   bits of entropy in whatever you return, and keep the alphabet transcribable.

Issuing and sealing
-------------------

.. _dms_certificate-issue:

.. py:method:: DmsCertificate.issue(vals, holders=None, source=None, redaction_secrets=None)
   :classmethod:

   ``@api.model``. **The integration entry point.** Creates a certificate,
   records where everyone sits on the page, and seals it, in one call.

   :param dict vals: certificate values.
   :param list holders: dicts of ``dms.certificate.holder`` values, each
      normally carrying ``passport_number`` so it can be hashed.
   :param source: the recordset this entry stands for. Its ``_name`` and ``id``
      are written to :py:attr:`~DmsCertificate.res_model` /
      :py:attr:`~DmsCertificate.res_id` with ``setdefault``, so an explicit
      value in *vals* still wins.
   :param dict redaction_secrets: ``{index: [strings]}`` keyed by position in
      *holders* — extra strings printed on the page for that person on top of
      what the holder record itself carries. Translated to
      ``{holder_id: [...]}`` here, because the caller cannot know the ids of
      records it is asking to be created.
   :returns: the created certificate.

   The ordering is the contract: create, then
   :py:meth:`DmsCertificate.stash_redaction`, then
   :py:meth:`DmsCertificate.certify`. Measuring before sealing is what makes
   the measurements be of the *source*, which is what every later lookup
   re-derives (see :ref:`sealing-redaction`).

   .. note::

      ``issue()`` **seals**. For the usual case — register the document now,
      choose the marking after looking at the stamped page — create the record
      directly and call :py:meth:`DmsCertificate.stash_redaction` yourself. See
      :doc:`../../handbook/issuing`.

.. py:method:: DmsCertificate.action_certify()

   Seal, or re-seal, every record in ``self``. The header button.

   The reference never changes: a re-stamp is a new marking on the same issued
   document, not a new document (``test_re_stamping_keeps_the_reference``).

.. py:method:: DmsCertificate.certify()

   One record. Guards, seals, then either promotes ``draft`` to ``certified``
   and announces the issue, or posts a re-stamp note.

   :raises UserError: when the record is ``revoked`` — issue a new document
      rather than re-sealing a withdrawn one, so the trail stays honest.
   :raises UserError: when there are no :py:attr:`~DmsCertificate.holder_ids`,
      because nobody could open it.

   The ``first_time`` flag is read **before** :py:meth:`_apply_seal`, so the
   first seal writes :py:attr:`~DmsCertificate.issued_on` and
   :py:attr:`~DmsCertificate.issuer_id` and every later one leaves them alone.

.. py:method:: DmsCertificate._apply_seal()

   Stamp the source and store the copy. No state changes, no guards — those
   belong to :py:meth:`DmsCertificate.certify`, and keeping them out of here is
   what lets the preview reuse the same spec-building path.

   Hashes the source *before* sealing, into
   :py:attr:`~DmsCertificate.source_hash`, then seals, then stores and hashes
   the result into :py:attr:`~DmsCertificate.sealed_hash`.

   :raises UserError: when :py:meth:`DmsCertificate._certify_source` yields no
      bytes.

.. _dms_certificate-stash_redaction:

.. py:method:: DmsCertificate.stash_redaction(secrets=None)

   Record, per listed person, the rectangles on the source document where their
   details appear — via ``seal.locate()`` — together with the fingerprint of
   the document they were measured against.

   :param dict secrets: ``{holder_id: [extra strings]}`` printed for that person
      on top of :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate_holder.DmsCertificateHolder._redaction_needles`.
   :returns: ``False`` when there is no source to measure, otherwise ``True``.

   .. admonition:: Why measure now instead of searching later
      :class: important

      A lookup could search the page for the strings to blank. It should not.
      A crew member's surname, rank or date of birth is a short string that also
      occurs in the letter *body* — ``MASTER``, a date in a sentence, a family
      name that is also a vessel name — and a search-and-blank at request time
      either destroys the sentence or, tuned to avoid that, misses the line it
      was aimed at.

      Measuring at registration time is unambiguous: these coordinates are
      where *this* person's row is on *this* document. The passport numbers make
      the point sharpest — they are printed on the page and (for the extra
      secrets a producing module passes in) stored nowhere, so where they sit
      can only be established while they are still in hand.

      The measurement is tied to ``boxes_source_hash``, so it can be *detected*
      as stale rather than trusted blindly; what happens then is
      :py:meth:`DmsCertificate._public_bytes`'s problem.

Disclosure
----------

.. _dms_certificate-public_bytes:

.. py:method:: DmsCertificate._public_bytes(holder=None)

   The sealed document **this lookup** may look at, as bytes.

   Under ``full`` disclosure that is the stored sealed copy, read with
   ``sudo``. Under ``confirm`` it is built here, per person: the source with
   everyone *else's* lines removed, then sealed with
   :py:attr:`~DmsCertificate.source_hash` so the per-person copy carries the
   same printed fingerprint as the issued page.

   Built rather than stored, because storing it means one saved file per person
   per document, each of which has to be invalidated on every re-stamp.

   Three steps, in order:

   .. code-block:: text

      1. boxes        every other holder's measured rectangles, if the
                      measurement matches this document's hash
      2. fallback     any holder whose measurement is stale or absent is
                      redacted by value instead — seal.redact(needles)
      3. leak check   tokenise the result, ask every other holder what of
                      theirs survived; if anything did, return b''

   Step 2 logs at ``INFO`` and continues. Falling back is safe *because the
   passport numbers are stored* — see :doc:`dms_certificate_holder` — and it
   beats refusing to show a page to an agent standing at a counter waiting for
   it. Test: ``test_stale_positions_fall_back_to_searching``.

   .. admonition:: Step 3 fails closed, and that is the point
      :class: important

      The boxes were measured against this document, but a measurement is not a
      guarantee. So the *result* is checked against what is stored — including
      the keyed passport hashes, which is the only way to look for a number
      nobody kept — and if any of it survived, the method logs at ``ERROR`` and
      returns ``b''``.

      Every caller treats ``b''`` as "show nothing". An empty page is a
      nuisance; a page with somebody else's passport on it is a breach. Test:
      ``test_a_page_that_still_leaks_is_not_served``.

   :param holder: the person who opened the document; they are the one row
      *not* redacted. ``None`` means everybody is redacted, which is what a
      caller with no match should get
      (``test_a_lookup_with_no_person_hides_everybody``).
   :returns: PDF bytes, or ``b''`` when the result cannot be shown to be safe.

.. py:method:: DmsCertificate._seal_spec(source_hash=None)

   Build the ``seal.SealSpec`` for this record: the per-document choices
   (reference, URL, company, marking) plus the house style read from
   ``ir.config_parameter``.

   *source_hash* is a parameter rather than a read of
   :py:attr:`~DmsCertificate.source_hash` so the preview can stamp a document
   that has never been certified and therefore has no stored hash yet.

   Two of the spec's values are per-document rather than house style:
   ``qr_corner`` comes from :py:attr:`~DmsCertificate.stamp_position`, and
   ``watermark_pages`` from :py:meth:`DmsCertificate._marked_page_indices`.

.. py:method:: DmsCertificate._marked_page_indices()

   :py:attr:`~DmsCertificate.marked_pages` as 0-based page indices, or ``None``
   for every page.

   :returns: ``frozenset[int]`` or ``None``

   Parsed rather than kept as two integer columns because "all of it" has to
   stay expressible as *nothing at all*: a file holding one document should need
   no value here, and every caller written before the field existed keeps
   working untouched.

   An unreadable or impossible value is logged at ``WARNING`` and treated as
   every page. A hint about where to put a watermark is not worth failing a seal
   over.

.. py:method:: DmsCertificate._public_page_count()

   Page count of the sealed copy, or ``0``. Catches everything: a broken file
   must not 500 a public page.

.. py:method:: DmsCertificate._public_page_image(page_number, dpi=PUBLIC_PAGE_DPI, holder=None)

   One page of this lookup's permitted copy, as PNG bytes. Returns ``b''`` on a
   failure or on a refused :py:meth:`_public_bytes`.

   Rendered per request rather than cached: lookups are rare, the session asking
   has already passed the second check, and a cache would have to be invalidated
   on every re-stamp and every revocation. Note the explicit ``dpi`` default —
   ``seal.render_page`` itself defaults to 110, which is not enough to decode
   the stamp's QR (:py:data:`PUBLIC_PAGE_DPI`).

Storage seams
-------------

.. _dms_certificate-certify_source:

.. py:method:: DmsCertificate._certify_source()

   ``(filename, bytes)`` of the document to seal.

   The default reads :py:attr:`~DmsCertificate.source_attachment_id` under
   ``sudo``, which is what lets this module stand alone with no producing
   module installed. **The main override point**: a bridge module points it at
   its own storage — the operations bridge returns the ``dms.file`` the
   generation wizard produced — and that file is never modified. Returns
   ``(None, None)`` when there is nothing.

   Called from :py:meth:`_apply_seal`, :py:meth:`stash_redaction`,
   :py:meth:`_public_bytes` and :py:meth:`_compute_preview_pdf`, so an override
   has to be cheap and side-effect free: the preview calls it on every form
   read. See :ref:`issuing-override-points`.

.. py:method:: DmsCertificate._store_artifact(existing, kind, filename, content)

   Write *content* as an ``ir.attachment`` owned by this certificate, reusing
   *existing* when there is one so a re-stamp updates in place instead of
   accumulating copies.

   Deliberately **not** filed back into the DMS. The folder shows the document
   as it was produced; the sealed copy is the portal's artifact, not the
   operator's document, and a DMS folder that fills with near-identical sealed
   variants is a folder nobody can read.

   The name is sanitised to ``[A-Za-z0-9._-]``, truncated at 60 characters, has
   its extension dropped and gets ``-<kind>.pdf`` appended.

Telling the desk
----------------

.. py:method:: DmsCertificate._post_service(body)

   A note from the certificate service itself rather than from a person:
   ``message_type='notification'``, subtype ``mail.mt_note``. Every automatic
   message in this module goes through here.

.. py:method:: DmsCertificate._notify_certified()

   The issue announcement: reference, the first 16 characters of the
   fingerprint, the validity, what opening it needs, and what the portal will
   disclose.

   It restates the rules in words because the fields encoding them are
   selections an operator may never have looked at, and the moment they care is
   the moment somebody asks why an embassy cannot open a document. Test:
   ``test_certifying_posts_the_reference_and_the_rules``.

.. py:method:: DmsCertificate._notify_verification(outcome, minutes=0)

   Post a lookup back to the desk.

   ``locked`` and ``mismatch`` are *needs attention* and are posted **even when**
   :py:attr:`~DmsCertificate.notify_on_lookup` is off, and additionally land on
   somebody's activity list. A successful check by an embassy is routine and
   goes quiet. Tests:
   ``test_routine_lookups_stay_quiet_when_notifications_are_off``,
   ``test_a_lockout_reaches_the_desk_even_with_notifications_off``.

   Every body says *"An external user"*. The address is kept on the attempt row
   and never written into the thread — see
   :doc:`dms_certificate_attempt` for that asymmetry, and
   ``test_the_requester_is_never_named_or_addressed``.

   Posted under ``sudo``, because the caller is the public user.

.. py:method:: DmsCertificate._flag_for_attention(summary)

   Schedule a ``mail.mail_activity_data_warning`` activity on
   :py:attr:`~DmsCertificate.issuer_id`, falling back to ``create_uid``, so a
   lockout lands on a plate rather than only in a log.

   Catches ``ValueError``: the warning activity type is not guaranteed to exist
   in every database, and the note is posted either way. Summary truncated to
   250 characters.

Actions
-------

.. py:method:: DmsCertificate.action_download_sealed()

   ``ir.actions.act_url`` to ``/web/content/<id>?download=true``.

   :raises UserError: when nothing has been sealed yet.

.. py:method:: DmsCertificate.action_send_to_embassy()

   Open ``mail.compose.message`` with the sealed copy attached and the subject
   prefilled, carrying ``dms_certify_delivery`` in the context.

   :raises UserError: when nothing has been sealed yet.

.. py:method:: DmsCertificate.action_mark_delivered()

   Promote ``certified`` records to ``delivered``. The manual path, for a
   document handed over outside Odoo.

.. _dms_certificate-action_revoke:

.. py:method:: DmsCertificate.action_revoke(reason=None)

   Withdraw the document. **Irreversible**, and a pure state change.

   *reason* falls back to the ``revoke_reason`` context key, then to *"No reason
   recorded."*. It is posted to the thread and printed on the public refusal
   notice, which is why :doc:`../wizards/dms_certificate_revoke` exists to
   insist on a real one.

   .. admonition:: Revocation does not re-stamp
      :class: important

      The obvious move is to re-seal with a ``VOID`` watermark. It would be
      pointless: the portal already refuses to show the page or offer the
      download once the state is ``revoked``
      (:doc:`../templates`), so there is no public copy left for a watermark to
      protect, and the paper already in somebody's hand cannot be changed
      either way. What changes is what a lookup *says* now. Tests:
      ``test_revoking_does_not_touch_the_sealed_bytes``,
      ``test_revoking_keeps_the_printed_fingerprint``.

.. py:method:: DmsCertificate.action_open_portal()

   Open :py:attr:`~DmsCertificate.verify_url` in a new tab — the prefilled
   public form, exactly as scanning the QR code would reach it. Note this lands
   on the check host, so it only works where that host resolves; see
   :ref:`deployment-check-host`.

Matching
--------

.. _dms_certificate-match:

.. py:method:: DmsCertificate._match(reference, factor_value)
   :classmethod:

   ``@api.model``. **Called by the public controller only.** Returns
   ``(certificate, holder)``, or two empty recordsets.

   Searches ``reference_key`` restricted to :py:data:`LIVE_STATES` with
   ``limit=1``, then hashes the submitted factor once and walks the holders
   comparing against each one's stored hash for the certificate's own
   :py:attr:`~DmsCertificate.second_factor`. Any listed person opens it
   (``test_any_listed_person_opens_the_document``).

   .. admonition:: A miss costs the same as a wrong passport
      :class: important

      Two things make that true.

      ``hmac.compare_digest`` for the comparison, so a nearly-right hash does
      not take measurably longer to reject than a wholly wrong one.

      And when **no certificate is found at all**, the method computes a
      throwaway HMAC over ``secrets.token_hex(16)`` before returning:

      .. code-block:: python

         if not certificate:
             Holder._submitted_factor_hash('pptfull', secrets.token_hex(16))
             return empty

      Without it, an unknown reference would return after one indexed SELECT
      while a known one paid for an HMAC, and the difference turns the public
      form into an oracle for enumerating valid references. The ``'pptfull'``
      is arbitrary — the cost is one HMAC whichever mode is named.

      This pairs with the controller giving one error message for every
      failure (:ref:`verification-refusals`). Timing is the side channel left
      once the wording is identical. Tests:
      ``test_an_unknown_reference_opens_nothing``,
      ``test_a_passport_from_another_document_does_not_open_it``,
      ``test_separators_and_case_do_not_decide_the_outcome``.

   Runs under ``sudo`` throughout: the public user has deliberately no ACL on
   this model, and the controller is the only door
   (:doc:`../security/ir_rule`).

.. py:method:: DmsCertificate._register_verification()

   Bump :py:attr:`~DmsCertificate.verify_count` and stamp
   :py:attr:`~DmsCertificate.last_verified_on`, under ``sudo``.

   There is no ``ensure_one()``, but reading ``self.verify_count`` makes it a
   single-record call in practice.

The public whitelist
--------------------

.. _dms_certificate-get_public_values:

.. py:method:: DmsCertificate._get_public_values(holder=None)

   :returns: ``dict`` of plain Python values — strings, booleans, dates,
      integers, and lists of dicts of those.

   .. admonition:: The security boundary of this module
      :class: important

      The public templates receive **this dict and nothing else**. Not a
      record, not a recordset, not a browse-able id.

      The reason is reachability. Hand a QWeb template a record and every
      relation on it becomes a one-dot walk: ``doc.issuer_id.partner_id.email``,
      ``doc.company_id.vat``, ``doc.message_ids`` — the whole thread, including
      whatever an operator typed into it. Nothing stops that walk, because QWeb
      is not a sandbox; the only defence is that there is nothing to walk. A
      plain dict has no relations.

      This is also why it is a *whitelist* rather than a blacklist of fields to
      drop: a field added to this model next year is invisible to the portal
      until somebody deliberately adds it here, which is the right default.

      Tests: ``test_public_values_are_plain_data``,
      ``test_public_values_redact_the_crew_in_confirm_mode``,
      ``test_public_values_list_the_crew_in_full_mode``.

   Two values are conditional, not merely formatted:

   * ``revoke_reason`` is ``False`` unless ``public_state == 'revoked'``.
   * ``crew`` is ``[]`` under ``confirm`` disclosure, and the full list of
     surname / first name / date of birth / rank under ``full``. The
     ``matched`` key carries only the one person who opened the document, and
     never their passport.

   ``facts`` are parsed from :py:attr:`~DmsCertificate.facts_json`, skipping
   anything that is not a dict, with each label resolved through
   :py:meth:`DmsCertificate._resolve_fact_label`.

   An override point — call ``super()`` and update the dict. Keep returning
   plain data; see :ref:`issuing-override-points`.

.. py:method:: DmsCertificate._resolve_fact_label(label)

   A fact label may be a plain string or a ``{lang: string}`` mapping. Resolves
   against ``self.env.lang``, then its bare language code, then ``en``, then any
   value at all.

   The portal is read in French by people the producing module knows about and
   this one does not, so the vocabulary of a port call stays in the producing
   module — it just has to be able to give that vocabulary in more than one
   language. The chain never raises and never returns ``None``, because this
   runs while rendering a public page. Test: ``test_facts_travel_as_given``.

Overrides
---------

.. py:method:: DmsCertificate.message_post(**kwargs)

   After ``super()``: when the context carries ``dms_certify_delivery`` **and**
   the state is ``certified``, write ``delivered``.

   Sending is what makes a certified document a delivered one, so the state
   follows the message rather than a separate button somebody has to remember
   to press. Both halves of the condition matter — a note to ourselves is not a
   delivery, and a document already delivered is not re-delivered. Tests:
   ``test_sending_is_what_makes_it_delivered``,
   ``test_an_ordinary_note_is_not_a_delivery``.

.. py:method:: DmsCertificate.copy(default=None)

   :raises UserError: always.

   There is no such thing as a duplicate certificate. The reference is printed
   on paper in circulation and ``copy=False`` on
   :py:attr:`~DmsCertificate.reference` would hand the clone a fresh one — but
   the clone would also inherit the holders, the fingerprints and the sealed
   attachment of a different document, and ``UNIQUE(reference_key)`` would not
   notice. Refusing is cheaper to reason about than making duplication correct.
   Issue a new document instead.

Guards
------

.. note::

   There was a ``_check_dates()`` constraint here refusing a document whose
   ``valid_until`` preceded its ``movement_date``. It went with 19.0.6.0.0's
   move to counting validity from issuance: under the old vocabulary that could
   only mean a mistyped date, and under this one it is an ordinary situation —
   a letter sealed in March for a call in September, valid ninety days, expires
   before the vessel arrives. That is a real thing for an operator to see, not
   something to refuse at save time, and the portal already reports it as
   *authentic but out of date*.

.. py:method:: DmsCertificate._check_seal_text()

   ``@api.constrains("seal_marking", "seal_text")``

   :raises ValidationError: when the marking is ``custom`` and
      :py:attr:`~DmsCertificate.seal_text` is blank or whitespace. ``custom``
      with no text would seal a page with no marking at all while the record
      claimed it had one.

.. py:method:: DmsCertificate._unlink_except_issued()

   ``@api.ondelete(at_uninstall=False)``

   :raises UserError: when any record is in :py:data:`LIVE_STATES`.

   Deleting an issued entry makes a genuine document read as forged to the next
   embassy that checks it, and erases the trail that would explain why. Revoke
   instead — that answers the lookup with a reason.
   ``at_uninstall=False`` so uninstalling the module is still possible. Test:
   ``test_an_issued_document_cannot_be_deleted``.

.. todo::

   The README's *Extension points* table lists ``_hide_expired()`` as an
   override point — *"Decide whether an expired document reads as expired or as
   not found"*. **No such method exists anywhere in this addon.** The
   ``dms_certify_portal.hide_expired`` parameter and the
   ``certify_hide_expired`` settings field exist and are stored, but nothing
   reads either (see :doc:`res_config_settings`). Either implement the hook or
   drop the row from the README and the setting with it — which is it?

.. todo::

   The README's integration example calls
   ``issue(..., redaction_needles=self.traveller_ids.mapped('passport_number'))``
   and ``entry.stash_redaction(passport_numbers)``. Neither matches the code:
   the keyword is ``redaction_secrets`` and takes ``{index: [strings]}`` keyed
   by position in *holders*, and
   :py:meth:`DmsCertificate.stash_redaction` takes ``{holder_id: [strings]}``.
   A flat list passed to either is silently wrong — ``secrets.get(holder.id)``
   on a list raises, and an unexpected keyword on ``issue()`` is a
   ``TypeError``. The README needs correcting.

See also
--------

* :doc:`../../handbook/issuing` — the integration flow end to end, and
  :ref:`issuing-override-points` for the four seams
* :doc:`../../handbook/sealing` and :ref:`sealing-redaction` — what the stamp
  is and how the per-person copy is built
* :doc:`../../handbook/verification` — what an agent sees, and
  :ref:`verification-refusals`
* :doc:`dms_certificate_holder` — the hashes, the pepper and the boxes
* :doc:`dms_certificate_attempt` — the two rate limits that stand in front of
  :py:meth:`DmsCertificate._match`
* :doc:`dms_certificate_type` — why the type is a record
* :doc:`../tools/seal` — ``seal``, ``locate``, ``redact_boxes``, ``redact``,
  ``text_tokens``, ``render_page``
* :doc:`../controllers/verify` — the only door to this model from outside
* :doc:`../views/dms_certificate_views` — the form, the preview panel and the
  locked holder list
* :doc:`../security/ir_rule` — why there is no public ACL
* :doc:`../../development/testing` — ``test_certificate.py`` covers the
  reference shape, the redaction loop, the matching, the preview and the
  revocation
