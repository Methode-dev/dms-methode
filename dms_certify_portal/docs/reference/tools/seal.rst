seal
====

.. py:currentmodule:: dms_certify_portal.tools.seal

Source: :ghsrc:`tools/seal.py`

The stamping and redaction engine: bytes in, bytes out, **no ORM anywhere**.
Nothing in this module imports ``odoo``, reads a parameter or knows what a
certificate is. The caller resolves every choice into a
:py:class:`SealSpec` and owns the storage on both sides.

That purity is not tidiness. It is what makes the stamp testable on a PDF built
in a fixture (``build_pdf`` in ``tests/test_certificate.py``), what lets
:py:meth:`DmsCertificate._compute_preview_pdf
<odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._compute_preview_pdf>`
stamp a document that has never been saved, and what makes the redaction
toolchain usable by a producing module that has its own idea of what needs
blanking.

.. note::

   The module is documented here as ``dms_certify_portal.tools.seal`` rather
   than ``odoo.addons.dms_certify_portal.tools.seal``, because that is the name
   autodoc imports it under in the docs build. Both spellings resolve to the
   same file for the source links. At runtime it is reached as
   ``from ..tools import seal as sealing``.

.. contents::
   :local:
   :depth: 2

What the stamp puts on a page
-----------------------------

Four layers, and only one of them is on the last page:

.. code-block:: text

   +----------------------------------------------+
   | +------------------------------------------+ |  <- guilloche: two rules at
   | |                                          | |     8 pt and 12 pt from the
   | |   CERTIFIED  ORIGINAL   CERTIFIED  ORI   | |     trim, engraved wave in
   | |        the document, unchanged           | |     the 4 pt channel
   | |   CERTIFIED  ORIGINAL   CERTIFIED  ORI   | |     between them
   | |                                          | |
   | |   ORIGINAL   CERTIFIED  ORIGINAL   CER   | |  <- watermark: tiled or one
   | |                                          | |     band, rotated about the
   | |                     +----+ TO BE CHECK   | |     page centre, every page
   | |                     | QR | check.exampl  | |
   | |                     +----+ ICS-2026-DKK  | |  <- seal block: last page
   | |                            SHA-256 3f2a  | |     only, 18 mm QR + 62 mm
   | +------------------------------------------+ |     of text
   |  ICS-2026-DKK-4KQ7-9B . 3f2a. . METHODE .    |  <- microtext at 1 pt, 9 pt
   +----------------------------------------------+     up from the foot

* the **watermark** and the **guilloche** and the **microtext** go on *every*
  page;
* the **seal block** is printed once, on the **last** page, which is where a
  reader looks for a signature.

The seal block's own contents are deliberate and in this order: a highlighted
``TO BE CHECKED BY THE EMBASSY:`` line, the verify URL **without its scheme**
(the QR carries the full URL; the printed line is there to be retyped, not
clicked), the reference at 10.5 pt, and the first twelve characters of the
source fingerprint. The highlight is the only coloured fill in the block, on
the one line an agent is meant to act on.

What the fingerprint printed there *is* — the hash of the document **before**
sealing — is the single most load-bearing fact about this module's output. It
is argued in :py:func:`fingerprint` below and in
:ref:```source_hash`` <dms_certificate-source_hash>`.

Geometry
--------

PDF user space: 1 pt = 1/72 in, origin **top-left** in PyMuPDF. Every value is
a module-level constant with no docstring, so autodoc does not pick them up;
here they are with their millimetre equivalents.

.. list-table::
   :header-rows: 1
   :widths: 24 14 14 48

   * - Constant
     - Value
     - In mm
     - What it decides
   * - ``MM``
     - ``72/25.4``
     - —
     - Points per millimetre, ``2.8346…``. Every dimension below that is
       expressed in millimetres is written as ``n * MM``.
   * - ``SEAL_BAND_H``
     - 68.03 pt
     - 24 mm
     - Height reserved when a page has to make room for the block. Sized so the
       shrink it forces on A4 stays around **8 %** — any deeper and the letter
       starts to read as a reduced photocopy of itself.
   * - ``SEAL_QR_SIDE``
     - 51.02 pt
     - 18 mm
     - The printed QR square. Also what sets
       :ref:`PUBLIC_PAGE_DPI <dms_certificate-PUBLIC_PAGE_DPI>` on the model
       side: 18 mm has to raster to enough pixels per module to decode.
   * - ``SEAL_QR_GAP``
     - 8.50 pt
     - 3 mm
     - Between the QR and the text column.
   * - ``SEAL_TEXT_W``
     - 175.75 pt
     - 62 mm
     - The text column. Total block width is therefore **83 mm**.
   * - ``SEAL_CLEARANCE``
     - 5.0 pt
     - —
     - Points, **not** millimetres. Clearance kept around the block when
       deciding whether the corner is free.
   * - ``FRAME_OUTER``
     - 8.0 pt
     - —
     - Outer guilloche rule, inset from the trim.
   * - ``FRAME_INNER``
     - 12.0 pt
     - —
     - Inner rule. Kept inside 5 mm so the frame never reaches the text area of
       a report whose own top margin is only 5 mm — which is what the LoI's
       paperformat sets.
   * - ``MICROTEXT_SIZE``
     - 1.0 pt
     - —
     - Legible under a loupe, a grey smear once photocopied.
   * - ``MICROTEXT_FROM_BOTTOM``
     - 9.0 pt
     - —
     - Baseline of the microtext line, measured up from the page foot.
   * - ``REDACTION_FILL``
     - ``(0, 0, 0)``
     - —
     - **Black, not grey.** A redaction should read as a deliberate act at a
       glance; grey invites the reader to wonder whether the page simply printed
       badly. Test: ``test_redactions_are_black``.

Corners
-------

``SEAL_CORNERS`` is ``('br', 'bl', 'tr', 'tl')`` — the permitted values of
:py:attr:`SealSpec.qr_corner`, chosen per document through
:py:attr:`DmsCertificate.stamp_position
<odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.stamp_position>`
and defaulting from the house style in Settings. ``SEAL_CORNERS_TOP`` and
``SEAL_CORNERS_LEFT`` are the two membership tests the geometry asks, so no
function has to spell out which letters mean what.

Two places read them. :py:func:`_seal_rect` puts the block at the head of the
page instead of the foot for a top corner, and ``_band_geometry`` takes the
reserved strip off the head instead of the foot — which is what makes
:guilabel:`Make room for the stamp` mean the same thing in all four positions
rather than quietly only working at the bottom.

Which pages carry the watermark
-------------------------------

:py:attr:`SealSpec.watermark_pages` is ``None`` for every page — the default,
and what every caller got before it existed — or a set of 0-based indices.

It exists for a file holding several documents under one certificate: a
manifeste filed together with its movement's covering letter must not come out
watermarked as though it were the letter. The caller owns the arithmetic;
:py:meth:`DmsCertificate._marked_page_indices
<odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._marked_page_indices>`
is what turns a stored ``"2-3"`` into that set.

Only the watermark is ranged. The guilloche and the microtext go on every page,
and the seal block on the last one, regardless.

Band modes
----------

``BAND_MODES`` is ``('auto', 'scale', 'overlay')`` — the permitted values of
:py:attr:`SealSpec.band`, exposed in the UI as
:guilabel:`Make room for the stamp` (:doc:`../models/res_config_settings`).

The constraint behind them, stated once: **a post-process cannot reflow a
page.** The documents being sealed leave no room for a stamp block — the LoI's
paperformat keeps a 5 mm top and 10 mm bottom margin and the crew table grows
into whatever is left — so something has to give.

.. list-table::
   :header-rows: 1
   :widths: 16 42 42

   * - Mode
     - What it does
     - What it costs
   * - ``auto``
     - Asks :py:func:`_corner_is_free` where the content actually ends on the
       last page. Clear corner: stamp at full size. Occupied: fall back to
       ``scale`` **for that document only**.
     - One extra text/drawing/image scan of the last page. A two-crew letter
       keeps its exact scale; a twenty-three-crew one gives up 8 %.
   * - ``scale``
     - Always shrink the page content into the area above the reserved band.
     - A few per cent of scale on every document, including the ones that did
       not need it. Nothing can ever be covered, and the page stays exactly A4.
   * - ``overlay``
     - Draw the block straight onto the corner as it is.
     - Whatever the document already printed in that corner is underneath it.
       Nothing is scaled.

``auto`` is the default because it is the only one of the three whose cost is
paid by the documents that caused it.

Module reference
----------------

.. automodule:: dms_certify_portal.tools.seal
   :members: fingerprint, rgb, qr_png, SealSpec, _draw_guilloche, _draw_watermark, _draw_microtext, _seal_rect, _corner_is_free, _draw_seal_block, _needs_band, seal, render_page, page_count, locate, redact_boxes, redact, text_tokens

Decisions worth naming
----------------------

Why ``seal()`` rebuilds the document instead of editing it
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:py:func:`seal` opens a **second, empty** document and, page by page, creates a
page of the source's dimensions and calls ``page.show_pdf_page(target, source,
index)``. It never draws on the input.

``show_pdf_page`` embeds the source page as a **form XObject**, which has two
consequences the module depends on:

* vectors stay vectors and text stays selectable and searchable — so
  :py:func:`text_tokens` can still read a sealed page, which is what the
  post-redaction leak check needs
  (:py:meth:`DmsCertificate._public_bytes
  <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._public_bytes>`,
  step 3);
* the embedded page can be placed into a *smaller* rectangle, which is the
  whole mechanism behind ``scale`` and ``auto`` band modes. Shrinking content
  is a change of target rectangle, not a re-layout.

Editing in place could not do the second at all, and would accumulate layers on
a re-stamp. As it stands, a re-stamp re-reads the clean source — so the seal is
always applied to unstamped bytes and never on top of an older seal. Tests:
``test_certifying_seals_the_document_and_leaves_the_source_alone``,
``test_re_stamping_keeps_the_reference``.

The output is written with ``tobytes(deflate=True, garbage=3)``: the tiled
watermark can be tens of thousands of glyph placements, and garbage collection
level 3 is what keeps the sealed file from being several times the size of the
source.

Everything is painted **on top**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Both :py:func:`_draw_guilloche` (``shape.commit(overlay=True)``) and
:py:func:`_draw_watermark` (``overlay=True``) paint over the embedded page
rather than under it.

The reason is in the source comment and it is empirical: a renderer is free to
paint an opaque background of its own. WeasyPrint does; wkhtmltobdf's output
happened not to. Anything painted *under* that background is invisible no
matter how it got there, so a seal drawn underneath would simply not exist on
half the documents. At 9 % opacity the watermark reads as a wash rather than as
something obscuring the text. There is a regression test for exactly this —
``test_the_watermark_and_guilloche_survive_an_opaque_background``.

The redaction toolchain
^^^^^^^^^^^^^^^^^^^^^^^

Four functions, used in a fixed order by the model layer. See
:ref:`sealing-redaction` for the operational view.

.. code-block:: text

   at registration                      at every lookup
   ───────────────                      ───────────────
   locate(source, needles)   ──stored──▶ redact_boxes(source, boxes)
     [{'p': page, 'r': rect}]                     │
                                                  ▼
                              redact(source, needles)   ← fallback when the
                                                          stored boxes are
                                                          stale or absent
                                                  │
                                                  ▼
                                        seal(redacted, spec)
                                                  │
                                                  ▼
                              text_tokens(result) ──▶ leak check, fail closed

Three things about that pipeline are decisions rather than mechanics.

**Redaction happens on the source, before sealing.** The boxes
:py:func:`locate` measured are in the *source's* coordinates, and ``scale`` or
``auto`` band mode moves the content inside the page — so a box measured on the
source is only valid against the source. Blanking first and sealing the result
is what keeps the two operations from having to know about each other, and it
is why :ref:`boxes_source_hash <dms_certificate_holder-boxes_source_hash>`
stores the hash of the *source* and not of the sealed copy.

**It is a real redaction.** ``page.apply_redactions(images=0, graphics=0,
text=0)`` drops the glyphs from the content stream; the text is not covered, it
is gone. The three zeros read backwards at a glance and are worth spelling out,
because PyMuPDF's redaction constants are not symmetrical: ``text=0`` is
*remove the text*, while ``images=0`` and ``graphics=0`` are *leave these
alone*. Leaving line art alone is itself deliberate — a crew table's own rules
touch the rectangles, and removing them would take the grid apart around the
blanked cells.

**Measuring once beats searching every time.** :py:func:`locate` is run against
a known document while the values are still in hand; the alternative, searching
the page at request time for the strings to blank, either destroys the sentence
a surname also appears in or, tuned to avoid that, misses the crew line it was
aimed at. The full argument is on
:ref:`stash_redaction() <dms_certificate-stash_redaction>`.

:py:func:`redact` is the one-step convenience — ``redact_boxes(pdf,
locate(pdf, needles))`` — and it is the **fallback** path, not the normal one.
It is what runs when a measurement cannot be trusted.

Note what :py:func:`locate` does *not* guarantee: it returns a box for every
occurrence of every needle, anywhere in the document, including occurrences in
the letter body. It is only safe because the needles it is given are a
specific person's details and the result is checked afterwards.

``render_page``'s default DPI is a trap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:py:func:`render_page` defaults to ``dpi=110``, which is **not enough to decode
the stamp's QR code**. An 18 mm square at 110 dpi gives about 2 px per module;
a version-4/5 code needs roughly three.

Every caller in this module therefore passes an explicit DPI — see
:ref:`PUBLIC_PAGE_DPI <dms_certificate-PUBLIC_PAGE_DPI>`, which is 200 and has
a regression test behind it
(``test_the_page_image_is_rendered_fine_enough_to_read``). If you add a caller,
pass one too.

The reason it rasterises at all, rather than handing over the PDF, is the
public side of the module: a PDF in a viewer carries its own save, print and
text extraction, none of which pass back through the gate that decided the
reader was allowed to see the page. A picture has none of that, and comparing
the screen with the paper in hand needs nothing more. The opposite choice is
made for the operator's preview panel, deliberately — see
:ref:`preview_pdf <dms_certificate-preview_pdf>`.

The QR code
^^^^^^^^^^^

:py:func:`qr_png` uses error correction **M** — enough to survive a stamp, a
fold and a fax without inflating the module count to the point where the
printed square stops scanning at 20 mm — and ``version=None`` with
``make(fit=True)``, so the version grows with the URL rather than being pinned.

``box_size=10, border=1``: the PNG is scaled into a fixed 18 mm rectangle by
``insert_image(..., keep_proportion=True)``, so ``box_size`` only sets the
resolution of the raster handed over, not the printed size. ``border=1`` is one
module of quiet zone where the specification asks for four — the block is drawn
on the white of the page, so the quiet zone is there in practice, and inside a
fixed 18 mm square every module spent on border is a module not spent on data.

.. warning::

   A longer verify URL means a denser QR in the same 18 mm. The URL comes from
   :py:attr:`~SealSpec.verify_url`, which is
   :ref:`certify_public_base_url <res_config_settings-certify_public_base_url>`
   plus ``/d/<reference>``. A very long public base URL is therefore a
   scannability problem, not just a cosmetic one, and it is the one setting that
   cannot be changed after documents are in circulation.

``SealSpec`` validates rather than trusts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A plain value object, not a dict, *"so a typo raises here instead of silently
dropping a layer off the page"* — a mistyped key in a dict is a missing
watermark that nobody notices until an embassy asks why a document has no
marking.

It also clamps and coerces everything it is handed: opacity to 0–100, size to a
floor of 6, mode and corner and band to their permitted members, every string
to ``''`` rather than ``None``. That is what lets
:py:meth:`DmsCertificate._seal_spec
<odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._seal_spec>`
pass system parameters straight in: a nonsensical value in Settings degrades to
a sane stamp instead of a traceback on a form — or, worse, on a public page.

Note the one input it does **not** validate: ``watermark_color`` is stored as
given and parsed later by :py:func:`rgb`, which has its own fallback to the
house navy.

The import that has two names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   try:  # PyMuPDF renamed its import in 1.24; the stack still ships both names.
       import pymupdf
   except ImportError:  # pragma: no cover - older wheels
       import fitz as pymupdf

PyMuPDF renamed its import from ``fitz`` to ``pymupdf`` in 1.24 and kept the
old name as an alias, so either works on a current wheel and only the old one
works on an older wheel. The module binds whichever it finds to ``pymupdf`` and
uses that name throughout, so the rest of the file reads as though the rename
had always happened.

.. note::

   ``__manifest__.py`` declares ``'external_dependencies': {'python': ['fitz',
   'qrcode']}`` — the **old** name, matching how ``dms_pdf_merge`` declares it.
   That is the one Odoo checks at install, and it is satisfied by both wheels
   because the alias is still there. If PyMuPDF ever drops ``fitz`` entirely,
   the manifest is what will fail first, not this import.

   The docs build mocks ``pymupdf``, ``fitz`` and ``qrcode`` only when they are
   genuinely absent, so an Odoo virtualenv reports the real types here — see
   ``conf.py``.

See also
--------

* :doc:`../models/dms_certificate` — the only caller:
  :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._seal_spec`,
  :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._apply_seal`,
  :ref:`stash_redaction() <dms_certificate-stash_redaction>` and
  :ref:`_public_bytes() <dms_certificate-public_bytes>`
* :doc:`../models/dms_certificate_holder` — where the boxes and the needles come
  from, and :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate_holder.DmsCertificateHolder._survives`,
  the check that runs on ``text_tokens`` output
* :doc:`../models/res_config_settings` — every house-style value this module is
  handed, and its default
* :doc:`../../handbook/sealing` and :ref:`sealing-redaction` — the same
  pipeline, from the desk's point of view
* :doc:`../controllers/verify` — the public side, and why a page image rather
  than a PDF
* :doc:`../../development/architecture` — why this file holds no ORM at all
* :doc:`../../development/testing` — the stamping and redaction assertions in
  ``test_certificate.py``
