Architecture
============

|addon| is two flows that share a database and almost nothing else.

The **issuing path** runs in the back office, authenticated, under the operator's
own access rights, and writes. The **lookup path** runs on a different hostname,
anonymously, under ``sudo``, and — apart from an attempt row and a counter —
reads. Between them sits a boundary that the rest of this page is mostly about.

Everything that looks like an odd decision in this addon follows from one rule:
**the public side is given as little as possible**. Not a record but a dict; not
an ACL but a controller; not the ERP's hostname but its own; not a stamping
library with an ``env`` but one with no ORM in it at all. Each of those is a
narrowing, and each is cheap to undo by accident, which is why they are written
down here and re-stated as invariants in :doc:`contributing`.

.. contents::
   :local:
   :depth: 2

The issuing path
----------------

A producing module holds the bytes. This addon never generates a document and
never modifies one.

.. code-block:: text

   producing module                      dms_certify_portal
   ────────────────                      ──────────────────
   a report, or a scan
   dropped in a folder
         │
         │  dms.certificate.issue(vals, holders=[…], source=rec,
         │                        redaction_secrets={index: [strings]})
         ▼
      create() ───────────────────────►  dms.certificate            state=draft
         │                               dms.certificate.holder × n
         │                                 create() → _recompute_credentials()
         │                                   three HMAC digests under the pepper
         │                                   (full passport, last 4, DOB)
         ▼
      stash_redaction(secrets)
         │   _certify_source()      ──►  (filename, bytes)   ◄── override point
         │   seal.fingerprint(bytes)
         │   seal.locate(needles)   ──►  [{p: page, r: [x0,y0,x1,y1]}, …]
         └───────────────────────────►  holder.redaction_boxes
                                         holder.boxes_source_hash
         │
         ▼
      certify()
         │   refuse if revoked, refuse if nobody is listed
         │
         │   _apply_seal()
         │     _certify_source()         ──► source bytes
         │     seal.fingerprint(source)  ──► source_hash   ← printed on the page
         │     _seal_spec(source_hash)   ◄── house style, ir.config_parameter
         │     seal.seal(bytes, spec)    ──► stamped bytes
         │     _store_artifact()         ──► sealed_attachment_id, sealed_hash
         │
         └─► state=certified, issued_on, issuer_id, a note on the thread
                                         naming the reference and the rules

Three things about that order are load-bearing.

**The source is read, never written.** Sealing opens the source bytes, builds a
new document page by page, and stores the result as an attachment owned by the
certificate. The producing module's file comes out of the process byte-identical,
which is what makes a re-stamp cost a stamp pass rather than a re-render, and
what lets a scanned attestation nobody here produced be sealed the same way.

**Measuring comes before sealing.** ``stash_redaction`` records where each
person's details sit on the *source*, because that is the document every later
lookup re-derives its redacted copy from. Measure after sealing and the
coordinates describe a document the lookup path never sees.

**The fingerprint printed on the page is of the source, not of the sealed file.**
A file cannot carry its own hash: stamping changes the bytes. Hashing the source
also makes the printed value stable across re-stamps, which is the claim
``certify()`` posts to the thread when it re-seals. See :ref:`sealing-redaction`.

The trust boundary
------------------

.. admonition:: What is allowed to cross, and in which direction
   :class: important

   Nothing on the lookup side holds a reference to a business record. The
   boundary is not a module edge or a network edge — both flows are the same
   Odoo process — it is a *data shape* edge, enforced in four separate places
   so that breaking one of them still leaves three.

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Narrowing
     - What it refuses
     - Where it lives
   * - **A dict, not a record**
     - ``_get_public_values()`` returns strings, booleans, dates, integers and
       lists of those. A template handed a record could walk
       ``doc.issuer_id.partner_id.email`` or ``doc.message_ids``; a dict has no
       relations to walk
     - ``models/dms_certificate.py``,
       :doc:`../reference/models/dms_certificate`
   * - **A controller, not an ACL**
     - No ``ir.model.access`` row and no record rule grants
       ``base.group_public`` or ``base.group_portal`` anything. Every ORM call
       on the public path is ``sudo()``, and authorisation is the session token,
       the expiry and the two rate limits
     - ``security/ir_rule.xml``, and the comment in it
   * - **A host of its own**
     - ``ir.http._match`` rewrites ``/`` to ``/_check`` on a ``check.`` host and
       404s ``/_check…`` anywhere else; ``_serve_fallback`` returns ``None``
       there so no website fallback can answer
     - ``models/ir_http.py``, ``dms_certify_host``
   * - **Bytes, not an ORM**
     - ``tools/seal.py`` takes bytes and a value object and returns bytes. It
       cannot read a field, so a bug in it cannot leak one
     - :doc:`../reference/tools/seal`

The lookup path
---------------

No account, no ``res.users`` row, no invitation.

.. code-block:: text

   embassy agent                      check.<host>
   ─────────────                      ────────────
   GET /                ──► ir.http._match → /_check
                              verify_form  → template verify_form

   POST /   reference + the second check, in the body
      │
      ├─ attempt.is_throttled(ip) ───────────► verify_throttled   log: throttled
      │                                        (per address, in a window)
      ├─ attempt.reference_lock_left(ref) ───► verify_throttled   log: locked
      │                                        (per reference, any address;
      │                                         the desk is told)
      ├─ _captcha_ok(token) ─────────────────► _fail('captcha')   log: captcha
      ├─ reference and passport both given ──► _fail('incomplete') log: no_match
      │
      ├─ dms.certificate._match(ref, value)
      │     sudo, reference_key, LIVE_STATES, limit=1
      │     one hmac of the submitted value, compare_digest per holder
      │     no certificate at all → one throwaway hmac, then empty
      │                   │
      │                   ├─ no match ──────► _fail('no_match')   log: no_match
      │                   │                   (the desk is told)
      │                   ▼ matched
      └─ secrets.token_urlsafe(32) into the session, with the document id,
         the holder id and an absolute expiry
            │
            └──────────────────────────────► 302  /r/<token>#result

   GET /r/<token>
      │  _session_document(token): expiry first, then compare_digest,
      │                            then the holder must belong to that document
      ▼
     _get_public_values(holder) ──► plain dict ──► template verify_result

   GET  /r/<token>/page/<n>  ──► _public_page_image() ──► PNG, or 404
   GET  /r/<token>/file      ──► _public_bytes()      ──► PDF,  or 404
   POST /r/<token>/mismatch  ──► attempt row + chatter note + an activity

Under confirm-only :ref:`disclosure <concepts-disclosure>` the last two are not
reads of a stored file. ``_public_bytes`` rebuilds the document for *this*
lookup: everyone else's measured rectangles redacted out, anyone whose
measurement is stale redacted by value instead, then the surviving words
tokenised and checked against every other holder's stored details and keyed
passport hash. Anything that survives and the method returns ``b''``, which every
caller renders as nothing at all. An empty page is a nuisance; a page carrying
somebody else's passport number is a breach. See :ref:`sealing-redaction` and
:doc:`../limits`.

The order of the checks is itself a decision, documented route by route in
:doc:`../reference/index`. The short version: both rate limits come before the
captcha, because the captcha is an outbound HTTP call and putting it first turns
a flood into one upstream request per hit.

Why the stamping module holds no ORM
------------------------------------

``tools/seal.py`` imports ``hashlib``, ``io``, ``math``, PyMuPDF and ``qrcode``.
It does not import ``odoo``. Bytes and a ``SealSpec`` go in, bytes go out, and
the caller owns storage.

That buys three things:

* **It is testable on bytes.** ``build_pdf()`` in ``tests/test_certificate.py``
  makes a one-page stand-in with crew lines on it, and the redaction assertions
  are made by re-opening the result and reading its text. No registry, no
  fixtures, no database state in the interesting part of the test.
* **It is reusable.** Any module that wants a fingerprint, a rasterised page or
  a real redaction can import it. ``redact_boxes`` calls
  ``apply_redactions(images=0, graphics=0, text=0)``, which drops the glyphs from
  the content stream rather than drawing a rectangle over them — a distinction
  that matters enough to be worth reaching for from elsewhere.
* **It cannot leak a field it was never given.** The riskiest code in the addon
  — the code that decides what is removed from a document before a stranger sees
  it — has no way to read anything the caller did not hand it.

``SealSpec`` exists for the same reason the public side gets a dict, pointed the
other way: a plain object rather than a kwargs dict, so a mistyped layer name
raises at construction instead of silently dropping the guilloche off every page.
It clamps and validates on the way in — opacity into 0–100, size to a floor of 6,
``band`` and ``qr_corner`` to their known members — so no caller can hand the
drawing code a value it has to defend against.

Why the public templates receive a dict
---------------------------------------

QWeb is not a sandbox. ``t-esc="doc.issuer_id.partner_id.email"`` is one dot
longer than ``t-esc="doc.reference"`` and nothing in the framework distinguishes
them. On a template rendered for authenticated users that is fine, because the
reader was already allowed to read those fields; on a template rendered for an
anonymous caller under ``sudo`` it is the whole attack.

So the controller never passes a recordset to ``request.render``. The result page
is ``_get_public_values(holder)``, the company block is seven strings copied out
of ``res.company``, and the chrome is the language options, the reference
grouping and a sample. There is nothing on the page object to walk to.

The shape of that method matters as much as its return type: it is a
**whitelist**, built key by key, not a copy of the record with some fields
removed. A field added to ``dms.certificate`` next year is invisible to the
portal until somebody deliberately adds a line — which is the right default for a
page an anonymous caller can reach.

Why the check host is a separate addon
--------------------------------------

Two reasons, and the second is the real one.

The mechanism has to run **before any request is routed**. ``dms_certify_host``
carries a ``post_load`` entry that patches ``odoo.http.db_filter`` so
``check.erp.example`` resolves to the same database as ``erp.example``. Odoo
picks a database from the host name, so without that patch a ``dbfilter`` keyed
on ``%h`` or ``%d`` goes looking for a database called *check*. ``post_load``
runs at server start, from ``server_wide_modules``, which is earlier than any
installed module's code — so it cannot live here.

And the host test has to be usable by more than one addon.
``dms_certify_host.hosts.is_check_host`` is imported by this module's
``ir.http`` override and is available to any other addon that wants to know
whether a request arrived on the portal's name. Keeping it in a 57-line addon
with no models and no data means a deployment can reason about it on its own —
and means this addon's hard dependency on it is a dependency on a host test, not
on a portal.

What that costs is a prerequisite that is easy to forget, with a failure mode
that looks like the portal simply not existing. See :ref:`deployment-check-host`.

File by file
------------

Why each piece is where it is, rather than what is in it — for that, use
:doc:`../reference/index`.

**The registry**

``models/dms_certificate.py``
   The whole public contract and most of the issuing flow: the reference
   generator, ``issue()``, ``certify()``, ``stash_redaction()``,
   ``_public_bytes()``, ``_match()`` and ``_get_public_values()``. It is the
   largest file in the addon and that is deliberate — the lookup path's
   decisions are a sequence, and splitting them across files would hide the
   sequence. :doc:`../reference/models/dms_certificate`.

``models/dms_certificate_holder.py``
   One row per person named on the document, carrying two jobs that look
   unrelated: the three keyed hashes (the access control for a lookup) and the
   measured rectangles (the map of where that person sits on the page). Both
   exist because the portal has to answer a stranger about a named individual
   without telling them about anyone else.

``models/dms_certificate_attempt.py``
   The throttle counter and the audit trail, in one table, because nothing can
   be dropped from it at write time. Two different limits live here — per
   address and per reference — and they protect different things.

``models/dms_certificate_type.py``
   What a document *is*, as records rather than a Selection, so a producing
   module ships its own kinds as data instead of overriding a method. This addon
   ships none of its own.

**The two doors**

``controllers/main.py``
   Seven public routes, all ``auth="public"``, all under ``/_check``, all
   ``sudo``. It is the only door to the registry from outside, which is why
   there is no public ACL and must never be one.

``models/ir_http.py``
   Twenty-nine lines carrying a large share of the security posture: the prefix
   rewrite on the check host, the 404 for an explicit ``/_check…`` elsewhere,
   ``_serve_fallback`` returning ``None`` so no website fallback runs, and
   ``/web/assets/`` as the single passthrough.

**The stamp**

``tools/seal.py``
   Pure functions over bytes: ``seal``, ``fingerprint``, ``render_page``,
   ``page_count``, ``locate``, ``redact_boxes``, ``redact``, ``text_tokens``,
   plus ``SealSpec`` and the millimetre constants. No ORM, by rule.
   :doc:`../reference/tools/seal`.

**The public page**

``templates/verify_templates.xml``
   Seven templates. ``portal_layout`` wraps ``web.frontend_layout`` with
   ``no_header``/``no_footer``, which is what lets the addon avoid depending on
   ``website`` at all (:ref:`limits-no-website`). All the refusal copy lives in
   ``verify_form``, keyed off ``error_code``, so there is exactly one place the
   wording can diverge.

``static/src/js/verify.js``
   Framework-free IIFE rather than OWL: it runs on a public page that must not
   pull the Odoo JS framework. The input mask groups the reference from
   **server-supplied** group sizes, so the alphabet and the grouping are not
   duplicated in JavaScript.

``static/src/scss/verify.scss``
   The entire public stylesheet, scoped under ``.dc-portal``, with local serif
   fallbacks behind the web fonts — a public page has to render when the font
   request is blocked.

**The back office**

``views/``, ``wizards/dms_certificate_revoke.py``
   The issuing screen, the preview panel, the locked holder list, the attempt
   log, and the one wizard, which exists to insist on a revocation reason and
   then delegates to ``action_revoke()`` so there is a single revocation path.

``static/src/js/certificate_chatter.js`` + ``form_renderer_patch.js``
   The pair exists to make the certificate's chatter **read-only**. The thread
   is an audit trail, and a human-written note would sit indistinguishably
   beside machine-written ones. The renderer patch re-asserts the component in
   ``onWillRender`` rather than only in ``setup`` — an asset-ordering race with
   third-party chatter themes.

**Setup and configuration**

``hooks.py``
   ``post_init_hook`` generates the HMAC pepper once, with
   ``secrets.token_urlsafe(48)``. ``portal_language_codes()`` reads the ``i18n/``
   folder and is imported by the controller too, so the language switcher and
   the install step agree by construction.

``security/``, ``data/``, ``migrations/``
   Two groups, the access matrix, the single company record rule, twenty-two
   shipped parameters at ``noupdate="1"``, one daily cron, and three
   post-migrate scripts.

See also
--------

* :doc:`extending` — building the module that produces the documents
* :doc:`contributing` — the same decisions restated as invariants, with the cost
  of breaking each
* :doc:`testing` — what is asserted, and what is not
* :doc:`../handbook/issuing` — the issuing path as a procedure rather than a
  diagram, and :ref:`issuing-override-points`
* :doc:`../reference/index` — every symbol, with source links
* :doc:`../limits` — the edges these decisions leave behind
