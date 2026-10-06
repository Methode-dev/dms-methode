Sealing
=======

The stamp is drawn onto a finished PDF. Nothing is re-rendered, no report
template is involved, and the source file is never written to — so a document
this addon knows nothing about seals exactly like one your own report engine
produced.

.. contents::
   :local:
   :depth: 2

What the stamp puts on the page
-------------------------------

.. code-block:: text

   ┌──────────────────────────────────────────────┐
   │ ╔══════════════════════════════════════════╗ │ ← guilloche frame
   │ ║                                          ║ │   (every page)
   │ ║    L E T T E R   O F   I N V I T A T…    ║ │
   │ ║         CERTIFIED ORIGINAL               ║ │ ← watermark, tiled
   │ ║   CERTIFIED ORIGINAL        CERTIFIED    ║ │   (every page)
   │ ║                                          ║ │
   │ ║   Master ......... MARTIN .............   ║ │
   │ ║                                          ║ │
   │ ║                  ┌────┐ TO BE CHECKED…   ║ │ ← seal block
   │ ║                  │ QR │ check.erp.exa…   ║ │   (last page only)
   │ ║                  └────┘ ICS-2026-DKK-…   ║ │
   │ ║                         SHA-256 a1b2c3…  ║ │
   │ ╚══════════════════════════════════════════╝ │
   │  ICS-2026-DKK-4KQ7-9B · a1b2c3… · MÉTHODE ·  │ ← microtext, 1 pt
   └──────────────────────────────────────────────┘   (every page)

Four layers. The guilloche and the microtext go on every page, the seal block on
the last one, and the watermark on every page unless the entry names a range —
see :ref:`sealing-marked-pages`.

The guilloche frame
^^^^^^^^^^^^^^^^^^^

Two rules inset from the trim with an engraved line running between them, kept
inside 5 mm so it never reaches the text area of a report whose own top margin
is only 5 mm. It is there because it **moirés on a photocopy** — a copy of a
copy looks visibly wrong next to the original, which is a cheap check an agent
can make without a computer.

Toggled by :guilabel:`Guilloche border`.

The watermark
^^^^^^^^^^^^^

The marking, diagonally across the page. Six choices, five of which have fixed
wording:

.. list-table::
   :header-rows: 1
   :widths: 30 36 34

   * - :guilabel:`Marking`
     - Printed
     - What it is for
   * - Certified original
     - ``CERTIFIED ORIGINAL``
     - The default, and the honest answer for most documents
   * - Confidential
     - ``CONFIDENTIAL``
     - How the paper is to be handled rather than what it is for. What
       ``operations_certify`` marks a Letter of Invitation with
   * - For embassy submission
     - ``FOR EMBASSY SUBMISSION``
     - A copy produced specifically to be filed at a consulate
   * - Copy — not for boarding
     - ``COPY — NOT FOR BOARDING``
     - So a crewing office's working copy cannot be presented at a gangway
   * - Void / cancelled
     - ``VOID``
     - For a document superseded before it ever left
   * - Custom text
     - whatever you type
     - A constraint refuses a blank one — ``custom`` with no text would seal a
       page with no marking while the record claimed it had one

.. admonition:: The markings are deliberately not translated
   :class: important

   They are printed into the PDF at seal time and read months later by whoever
   is holding the paper — an agent in a third country, who is not the Odoo user
   whose language the server knew when it stamped. Translating the marking would
   mean the wording depended on who happened to press the button.

The house style around it — opacity (9%), angle (-32°), size (24), ink
(``#10314F``) and whether it tiles or forms one diagonal band — is set once in
Settings and applies to every document. See :doc:`administration`.

.. _sealing-marked-pages:

Which pages carry it
""""""""""""""""""""

Every page, unless the entry's :guilabel:`Marked pages` names a range —
``2-3``, 1-based and inclusive. Empty means all of them, which is what a file
holding one document wants and what every caller got before the field existed.

A range matters when **one file holds several documents and only one of them is
certified**. ``operations_certify`` files a manifeste together with its
movement's covering letter as a single PDF carrying a single certificate, and
that certificate is the letter's: marking the whole file would print
``CONFIDENTIAL`` across a manifeste nobody certified and which has no entry of
its own. So it sets the range to the letter's pages, and the producing module is
the only thing that can — the boundaries are known while the parts are being
concatenated and nowhere afterwards.

The guilloche and the microtext are deliberately **not** ranged. They are
anti-forgery features of the file, and they make no claim about which document
inside it is the certified one.

The microtext footer
^^^^^^^^^^^^^^^^^^^^

A single 1 pt line along the foot of every page, repeating
``reference · first 24 characters of the fingerprint · company name`` until the
width is filled. To the eye it is a grey rule; under a loupe it is readable; on
a photocopy it is a smear. Toggled by :guilabel:`Microtext line in the footer`.

The seal block
^^^^^^^^^^^^^^

**Last page only** — which is where a reader looks for a signature. It carries
four things, in this order:

#. An 18 mm QR code encoding the document's ``verify_url``.
#. The line ``TO BE CHECKED BY THE EMBASSY:`` on a yellow highlight. It is the
   only highlighted thing on the page, because it is the only line the agent is
   meant to act on.
#. The verification URL **without its scheme**, at 5.8 pt in a monospaced face.
   That line is there to be *retyped*, not clicked — the QR already carries the
   clickable form.
#. The reference at 10.5 pt, and under it ``SHA-256`` plus the first twelve
   characters of the document's fingerprint.

The corner is :guilabel:`Stamp position` — one of the four, bottom right by
default, next to where a signature usually sits. It is set as a house style in
Settings and can be overridden **per document** on the entry, which is where a
producing module writes the choice an operator made on its own screen.

A top corner reserves its strip at the head of the page rather than the foot
when the page has to make room (see `Making room for the stamp`_), so the
setting means the same thing whichever corner is chosen.

The printed fingerprint is the fingerprint of the *unsealed* document
---------------------------------------------------------------------

.. admonition:: A file cannot carry its own hash
   :class: important

   Stamping the page changes its bytes, so a fingerprint printed *on* the sealed
   file can never be the fingerprint *of* the sealed file. The hash is therefore
   taken of the source, immediately before sealing, and passed into the stamp.

   This is the only arrangement that is actually checkable. Somebody holding the
   original — your DMS, the producing module's folder — can hash it and compare
   against what is printed. Nobody can usefully verify a hash of the file they
   are looking at, because they would have to strip the stamp first.

Two things fall out of it, and both matter operationally:

* **Re-stamping does not move the printed fingerprint.** The same source is read
  again, so copies already sent keep verifying — which is exactly what the
  chatter note says when you re-stamp.
* **Revoking does not move it either.** Revocation is a pure state change.

The entry also keeps ``sealed_hash``, the SHA-256 of the sealed artifact. That
one *does* change on every re-stamp. It is the operator's handle on "which file
is this", and it is shown on the public page beside the other; it is not what
the stamp prints.

Making room for the stamp
-------------------------

Sealing cannot reflow a page. When the seal block's corner is already occupied
by the document's own content there are only two honest options: cover it, or
shrink the page's content into a slightly smaller box and stamp into the strip
that frees. :guilabel:`Make room for the stamp` chooses between them.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Mode
     - Behaviour
   * - :guilabel:`Only when the corner is taken` (``auto``, the default)
     - Looks at where the content actually ends on the last page. If the corner
       is clear, stamp at full size; if something is already there, shrink *that
       document only*.
   * - :guilabel:`Always` (``scale``)
     - Always reserve the band. Every document comes out identically laid out,
       and nothing can ever be covered.
   * - :guilabel:`Never — stamp over the page` (``overlay``)
     - Nothing is scaled. Whatever was in that corner is under the stamp.

The reserved band is 24 mm, sized so the shrink it forces on an A4 page stays
around 8% — any deeper and the letter starts to read as a reduced photocopy of
itself. So a two-crew letter keeps its exact scale and a twenty-three-crew one
gives up 8%.

The collision test ignores full-page drawings deliberately: a background panel
or a border frame covers the corner by definition, and counting those would push
every document into the scaled branch.

.. note::

   The document is rebuilt page by page rather than edited in place. Each source
   page is placed into a fresh page as a form XObject, so **vectors stay vectors
   and the text stays selectable and searchable**. That is what lets the
   redaction pass below actually remove glyphs rather than paint over a picture.

Re-stamping, and what it costs
------------------------------

:guilabel:`Re-stamp document` on an already-certified entry.

* The reference **never changes**. A re-stamp is a new marking on the same
  issued document, not a new document.
* The printed fingerprint does not change either, so the QR code, the printed
  URL and the line an embassy would retype are all unchanged.
* The sealed attachment is updated **in place** rather than accumulating copies.
* A note goes to the chatter saying the reference and the fingerprint are
  unchanged, *"so copies already sent still verify"*.
* :guilabel:`Issued by` and :guilabel:`Issued on` are written on the **first**
  seal only. A re-stamp by somebody else does not rewrite history.

A **revoked** document cannot be re-sealed. The attempt raises an error telling
you to issue a new document instead. The reasoning is that the trail has to stay
honest: a withdrawn reference that suddenly carries a fresh marking is a
reference whose meaning changed after it left the building.

.. tip::

   The form's right-hand panel shows the stamped output **before** you certify
   anything, re-sealed on every read from whatever marking is currently
   selected. Use it to judge where the block lands. It is the real PDF in a
   viewer, not a picture of one, so you can zoom into the microtext. An
   unreadable source leaves the panel empty rather than breaking the form.

.. _sealing-redaction:

Redaction, and why it is measured in advance
--------------------------------------------

Under ``confirm`` disclosure (:ref:`concepts-disclosure`) the page an embassy
sees hides everyone except the person whose second factor opened it. This is the
most intricate thing in the addon and the part most worth understanding before
relying on it.

Positions are measured when the document is registered
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``stash_redaction()`` searches the **source** document for every string each
listed person's row carries — surname, first name, rank, passport number, and
the date of birth in two printed formats — and stores the rectangles it found,
per holder, together with the fingerprint of the document they were measured
against.

.. admonition:: Why not just search the page at lookup time?
   :class: important

   Because the strings are short and they recur. A surname that is also a vessel
   name, a rank like ``MASTER``, a date that appears in a sentence — a
   search-and-blank at request time either destroys the sentence it hit by
   accident or, tuned to avoid that, misses the line it was aimed at.

   Coordinates are unambiguous: these are the places *this* person's row was
   found on *this* document. The passport numbers make the point sharpest — any
   extra values a producing module passes in are printed on the page and stored
   nowhere, so where they sit can only be established while they are still in
   hand.

Which is why the ordering in ``issue()`` is a contract: create, measure, **then**
seal. Measuring before sealing is what makes the measurements be of the source,
which is what every later lookup re-derives.

The per-lookup rebuild
^^^^^^^^^^^^^^^^^^^^^^

A lookup under ``confirm`` disclosure does not read a stored file. It builds one:

.. code-block:: text

   1. read the source again, hash it
   2. for every *other* holder:
         boxes match this hash?  ──► use the boxes
         stale, or never measured ──► remember them for step 3
   3. redact by coordinates, then redact the remembered ones by value
   4. tokenise the result and ask every other holder what of theirs survived
         anything survived?  ──► return nothing at all
   5. seal the redacted copy, with the *original* document's fingerprint

Built rather than stored, because storing it means one saved file per person per
document, every one of which would have to be invalidated on each re-stamp.

Step 3 is a **real** redaction, not a black rectangle drawn on top: the glyphs
are dropped from the content stream. Images and line art are left alone on
purpose — a crew table's own rules touch the rectangles, and removing them would
take the grid apart around the blanked cells.

Step 5 re-seals with the source document's fingerprint rather than the hash of
the redacted bytes, so the per-person copy prints the same fingerprint as the
issued page. Otherwise every agent would see a different number under the QR
code and none of them would match the original.

The fallback, and what it is weaker at
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the document changed underneath the measurements, the stored fingerprint no
longer matches and the boxes are discarded for that holder. The portal then
searches the page for their stored values instead — which works only *because
the passport numbers are stored*, and which beats refusing to show a page to an
agent standing at a counter.

It is weaker in one specific way: searching matches a string wherever it
appears, so a surname that is also a word in the letter body gets blanked too,
and an extra value that was never stored cannot be searched for at all.

The fallback logs at ``INFO``:

.. code-block:: text

   dms_certify_portal: ICS-2026-DKK-4KQ7-9B has no current positions for
   Jan Kowalski; redacting by value instead

A document whose source keeps changing after registration produces that line on
**every single lookup**, and nobody is watching for it. Either re-register, or
call ``stash_redaction()`` again after the change.

Failing closed
^^^^^^^^^^^^^^

.. admonition:: An empty page is a nuisance; somebody else's passport is a breach
   :class: important

   Step 4 does not trust the redaction. It tokenises every word the result still
   contains and asks each other holder what of theirs is in there — names and
   first names compared directly, passport numbers by **hashing each surviving
   word** and comparing against the stored hash, which is the only way to look
   for a number nobody kept.

   If anything survives, the method logs at ``ERROR`` naming what leaked and
   returns no bytes at all. Every caller treats that as "show nothing": the
   result page renders with no document images, and the download returns a 404.

So a redaction bug degrades to *silently blank for everybody* rather than to an
error. The agent still sees the verdict, the reference and the fingerprint —
enough to establish the document is genuine — but no page. The only trace is one
``ERROR`` line in the server log. How to confirm that is what happened is in
:doc:`troubleshooting`.

Under ``full`` disclosure none of this runs: the stored sealed copy is served as
issued, and the leak check has nothing to check.

See also
--------

* :doc:`concepts` — :ref:`concepts-disclosure`, and why ``confirm`` is the
  default
* :doc:`issuing` — ``issue()``, and registering without sealing
* :doc:`administration` — the house-style settings, one by one
* :doc:`../reference/tools/seal` — the geometry, the constants and every
  function in the stamping toolchain
* :doc:`../reference/models/dms_certificate` —
  :ref:```source_hash`` <dms_certificate-source_hash>`, :ref:```stash_redaction()`` <dms_certificate-stash_redaction>`
  and :ref:```_public_bytes()`` <dms_certificate-public_bytes>`
* :doc:`../limits` — sealing cannot reflow a page, and the two ways redaction
  degrades
