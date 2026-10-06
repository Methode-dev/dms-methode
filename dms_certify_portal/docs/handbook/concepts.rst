Concepts
========

Four things this addon keeps rigorously apart. Almost everything that confuses
people about |addon| is one of the four having been collapsed into another.

#. The **document** and the **entry about the document**.
#. The **reference**, which is public, and the **second factor**, which is not.
#. The **lifecycle state** an operator sees and the **public state** an embassy
   is told.
#. **Disclosure** — how much of the page a successful lookup earns.

.. contents::
   :local:
   :depth: 1

Two halves of one job
---------------------

|addon| does two things, and they meet in exactly one place.

**Sealing** is a post-process on finished bytes. A producing module hands over a
PDF it has already rendered; the seal draws a watermark, a guilloche frame, a
microtext footer and a stamp block onto a *copy*. The source file is never
written to. See :doc:`sealing`.

**Verification** is a public page on a host of its own, with no account behind
it. Two inputs, a verdict, and the page itself. See :doc:`verification`.

The join is ``dms.certificate``: the seal reads the reference off it, prints it,
and the public lookup reads it back.

.. code-block:: text

   your module renders a PDF
         │
         │  dms.certificate.issue()   ── or create() + stash_redaction()
         ▼
   ┌─────────────────────────┐
   │ the entry               │   reference, holders, second factor,
   │ (dms.certificate)       │   disclosure, validity, fingerprints
   └─────────────────────────┘
         │                 │
         │ seals a copy    │ answers a lookup
         ▼                 ▼
   sealed PDF ───────►  the public page
   (reference printed    (reference + second factor
    beside the QR)        typed at a counter)

Because sealing never re-renders, a document |addon| knows nothing about — a
scanned attestation dropped into an attachment — seals exactly like one your
report engine produced. And because the entry is separate from the document,
re-stamping, revoking and expiring are all things that happen to the *entry*.

The document, and the entry about the document
----------------------------------------------

This is the distinction the rest of the addon rests on, so it is worth stating
flatly.

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * -
     - The document
     - The entry
   * - What it is
     - A PDF, in a DMS folder or an attachment, produced by somebody else
     - One ``dms.certificate`` row
   * - Who owns it
     - The producing module
     - |addon|
   * - Reached through
     - ``_certify_source()``
     - the registry, and the public controller
   * - Modified by this addon
     - **Never**
     - Constantly — states, counters, artifacts
   * - What it holds
     - Everything the letter says
     - Only what the public page may show

The entry is a *thin, verifiable projection*. That is a security argument, not
tidiness: the public templates are handed a plain dict built by
``_get_public_values()``, and there is nothing on an entry worth walking to even
if a template were handed the record by mistake. See
:doc:`../reference/models/dms_certificate`.

Three consequences people meet in practice:

* **Deleting an entry makes a genuine document read as forged.** The next
  embassy to check it is told the reference does not exist. An ``@api.ondelete``
  guard refuses to delete anything in a live state; revoke instead, which
  answers the lookup with a reason.
* **Revoking does not touch a byte of the document.** No ``VOID`` re-stamp.
  The portal simply stops serving the page and starts printing the refusal.
* **A re-stamp costs no re-render.** The source is read again, so the printed
  fingerprint does not move and copies already sent still verify.

The reference
-------------

What is printed in bold beside the QR code, and the only thing an agent types
from memory of the page.

.. code-block:: text

   ICS - 2026 - DKK - 4KQ7 - 9B
    │      │      │     └──┬──┘
    │      │      │        └── 30 random bits, in groups of 4 and 2
    │      │      └─────────── three characters of the port's UN/LOCODE,
    │      │                   right-padded with X
    │      └────────────────── the year it was issued
    └───────────────────────── the configured prefix (default ``ICS``)

**There is no counter and no** ``ir.sequence``. A sequential component would
tell anyone holding two documents how many were issued in between, and — worse
— would make the space *walkable*: an attacker who knows ``…-0041`` exists tries
``…-0042``, and the second factor becomes the only thing standing between them
and a real document. The random part is generated with ``secrets.choice``,
because it is a credential.

The alphabet is Crockford base32 — the usual thirty-two characters **without**
``I``, ``L``, ``O`` and ``U``. That is about transcription, not cryptography: an
agent is retyping this off a page that has frequently been scanned or faxed on
the way, and in that condition ``1``/``I`` and ``0``/``O`` are the same glyph.
Dropping the ambiguous letters means there is no wrong answer to guess at.

.. important::

   The public page states in as many words that those four letters are never
   used, so an agent who is unsure of a shape knows what it cannot be. The
   refusal page and the lockout page both repeat it. **Change the alphabet and
   you have to change three sentences of copy** — see
   :doc:`../reference/templates`.

Matching happens on ``reference_key``, the reference with every separator
stripped and the case folded. So spacing, dashes and capitals never decide the
outcome, and the ``UNIQUE`` constraint sits on the normalised form rather than
on the printed one — otherwise two rows differing only in punctuation could both
exist and a lookup would silently answer about one of them.

The grouping is cosmetic. It exists because six characters in one block is the
length at which people lose their place mid-retype, and the browser mask and the
server's own re-grouping both derive it from the configured prefix rather than
hard-coding it.

.. _concepts-second-factor:

The second factor
-----------------

**The reference alone never opens a document.** There is no ``none`` option and
the field is required, so this cannot be switched off — only chosen between.

The issuer picks one of three modes per document:

.. list-table::
   :header-rows: 1
   :widths: 16 30 54

   * - Mode
     - What the agent types
     - Notes
   * - ``ppt4``
     - The **last four characters** of a listed passport
     - The default. What an agent can read off the passport in their hand
       without transcribing the whole number.
   * - ``pptfull``
     - The whole passport number
     - Stronger, and more to mistype. Worth it for a document with one holder
       and a long shelf life.
   * - ``dob``
     - A listed **date of birth**, as ``DDMMYYYY``
     - For documents that carry no passport number at all. Much weaker — a
       date of birth is frequently printed elsewhere on the same paper.

**Any** listed person opens the document. A letter of invitation names a whole
crew, and the agent at the counter has one seafarer in front of them; insisting
on a particular row would mean the agent guessing which line the system
expects.

How it is stored
^^^^^^^^^^^^^^^^

Each holder keeps **three** keyed hashes — one per mode — recomputed whenever
the passport number or the date of birth is written. Three rather than one so
the issuer can move a document from "last 4" to "full passport" afterwards
**without the crew being entered again**.

Every hash is an HMAC-SHA256 under one instance-wide pepper,
``dms_certify_portal.passport_key``, generated at install. The pepper is the
whole reason hashing is worth doing here: the factor values are short — four
characters, or a date — so an unkeyed digest of one falls to a wordlist
instantly. With a key that is not in the table, it does not.

.. warning::

   Lose the pepper and **no document opens**. Every stored hash becomes
   unverifiable and the lookup form refuses every correct passport with the same
   message it gives a wrong one. Back it up with the filestore — see
   :doc:`deployment`.

Matching never touches the stored passport number. ``_match()`` hashes what was
submitted once, then compares with ``hmac.compare_digest`` so a nearly-right
value does not take measurably longer to reject than a wholly wrong one.

Four characters is a small space
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Under the default mode there are only a few thousand possibilities, and no
amount of hashing changes that. What protects a document is the **per-reference
lock**: five failures against one reference, counted across *every* address,
and the reference is shut for thirty minutes. The per-address limit is a
separate, coarser net. Both are in :doc:`administration`.

.. _concepts-disclosure:

Disclosure
----------

A successful lookup always gets the verdict. What else it gets is the
``disclosure`` field, chosen per document.

.. list-table::
   :header-rows: 1
   :widths: 26 37 37

   * -
     - ``confirm`` (the default)
     - ``full``
   * - The verdict
     - Authentic / expired / revoked
     - Authentic / expired / revoked
   * - The person checked
     - Named, with their rank, as *"1 of the 23 listed"*
     - Named the same way
   * - Everyone else listed
     - **Not shown.** A count, and nothing more
     - Surname, first name, date of birth and rank, in a table
   * - The page images
     - Rebuilt per lookup with every other person's lines **removed from the
       content stream**
     - The sealed page exactly as issued
   * - Passport numbers
     - Never
     - Never
   * - Voyage facts, fingerprint, issuer
     - Shown
     - Shown

The reasoning behind ``confirm`` being the default is that it is almost always
enough. An agent wants to know whether the person at their counter is on a
document this organisation really issued — confirming that one line establishes
the whole paper's authenticity, and the other twenty-two seafarers' names and
dates of birth are not the agent's business. The portal says so, and tells them
the operations desk can open full disclosure on a reasoned request.

Under ``confirm`` the redacted copy is **built on every lookup** rather than
stored, and the result is checked for leaks before it is served. That machinery
is :ref:`sealing-redaction`, and it is the part most worth reading before you
rely on it.

.. note::

   Disclosure is about *the page*, not about who may look. Both modes are
   reached by the same two inputs, through the same rate limits. Switching a
   document to ``full`` does not loosen any control except what the result page
   prints.

Two state vocabularies
----------------------

The operator's view and the embassy's view are different words on purpose.

.. list-table::
   :header-rows: 1
   :widths: 22 24 54

   * - ``state``
     - ``public_state``
     - What is going on
   * - ``draft``
     - ``unpublished``
     - Registered, not sealed. **The portal will not speak about it at all** —
       a lookup is refused as though the reference did not exist, which is true
       enough: nothing has been printed yet, so nobody can be holding one.
   * - ``certified``
     - ``valid`` / ``expired``
     - Sealed, and the moment the validity clock starts: ``valid_until`` is
       ``issued_on`` plus the window, not the movement date plus it. Expiry is
       then a function of today's date, not a stored flag.
   * - ``delivered``
     - ``valid`` / ``expired``
     - Sealed and sent. The portal treats it identically — an embassy does not
       care whether a document was emailed.
   * - ``revoked``
     - ``revoked``
     - Withdrawn. **Still resolves**, and that is the point.

Two of these are worth dwelling on.

**A revoked reference must still answer.** The whole purpose of revocation is
to tell the agent holding that paper to turn it away, with the reason printed
under the refusal. A revoked document that simply read as *unknown* would leave
the agent unable to distinguish a cancelled letter from a forged one.

**Validity runs from issuance.** The document is what expires, and it starts
existing when it is sealed — a letter produced three weeks before the call would
otherwise arrive with three weeks of its life already spent, and one produced
after a delay could be born expired. A draft therefore has no expiry at all,
which is right: the portal will not speak about a draft either way.

**``public_state`` is computed and deliberately not stored.** It depends on
today's date as well as on the record, so a stored value would freeze the
verdict at whenever it was last recomputed and an expired document would keep
reading as valid until something touched it. ``valid_until`` *is* stored,
because something has to be searchable.

The states the portal will speak about at all are ``certified``, ``delivered``
and ``revoked`` — ``LIVE_STATES`` in the source. The same tuple is the delete
guard.

.. note::

   There is a Settings box called :guilabel:`Hide expired documents` that looks
   as though it belongs in this section. **Nothing reads it.** An expired
   document always reads as expired. See :doc:`../limits`.

How they fit together
---------------------

.. code-block:: text

   dms.certificate.type ──► what the page calls the document
                            (a record, not a Selection; this
                             module ships none of its own)

   dms.certificate ──┬──► reference ─────────────► printed + in the QR
                     │                             matched on reference_key
                     ├──► second_factor ─────────► which hash is compared
                     │        │
                     │        └── holder_ids ────► three keyed hashes each,
                     │                             under one instance pepper
                     ├──► disclosure ───────────► how much the result page
                     │        │                    prints …
                     │        └──────────────────► … and whether the page
                     │                             images are rebuilt redacted
                     ├──► issued_on
                     │    + validity_days ──────► valid_until ──► public_state
                     └──► state ────────────────────────────────┘

   dms.certificate.attempt ──► every hit on the form: the audit trail
                               *and* both rate-limit counters

Where to go next
----------------

* :doc:`quickstart` — build one, end to end.
* :doc:`sealing` — what the stamp puts on the page, and the redaction.
* :doc:`verification` — the same thing from the agent's side.
* :doc:`issuing` — for the module that produces the documents.
* :doc:`../limits` — what this addon deliberately does not do.
