Assets
======

Source: the ``assets`` block in :ghsrc:`__manifest__.py`

Three bundles, two stylesheets, a tour file and a French catalogue. There is no
build step — Odoo compiles the bundles itself, and the SCSS is compiled by
Odoo's own Sass, which matters more than it sounds (see
:ref:`assets-sass-min`).

.. contents::
   :local:
   :depth: 2

Bundle contents
---------------

.. code-block:: python

   "assets": {
       "web.assets_backend": [
           "dms_certify_portal/static/src/scss/certificate_form.scss",
           "dms_certify_portal/static/src/js/certificate_chatter.js",
           "dms_certify_portal/static/src/js/certificate_chatter.xml",
           "dms_certify_portal/static/src/js/form_renderer_patch.js",
       ],
       "web.assets_frontend": [
           "dms_certify_portal/static/src/scss/verify.scss",
           "dms_certify_portal/static/src/js/verify.js",
       ],
       "web.assets_tests": [
           "dms_certify_portal/static/tests/tours/certificate_chatter_tour.js",
       ],
   },

.. list-table::
   :header-rows: 1
   :widths: 20 34 46

   * - Bundle
     - File
     - What it is for
   * - ``web.assets_backend``
     - ``scss/certificate_form.scss``
     - The issuing screen's geometry: where the stamped page sits, and giving
       the PDF viewer's iframe a height
   * -
     - ``js/certificate_chatter.js``
     - The composer-less chatter component — :doc:`static/certificate_chatter`
   * -
     - ``js/certificate_chatter.xml``
     - Its primary-inherit template
   * -
     - ``js/form_renderer_patch.js``
     - Puts that component on the certificate form, and only there —
       :doc:`static/form_renderer_patch`
   * - ``web.assets_frontend``
     - ``scss/verify.scss``
     - The entire public stylesheet
   * -
     - ``js/verify.js``
     - The public page's framework-free script — :doc:`static/verify`
   * - ``web.assets_tests``
     - ``tests/tours/certificate_chatter_tour.js``
     - Three browser tours over the certificate form

The two halves share nothing. Nothing in the backend bundle is served to an
anonymous visitor, and nothing in the frontend bundle reaches the back office —
``verify.scss`` is scoped so that it could not even if it were loaded there.

Two things about the declaration itself
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**The OWL template is listed as an asset, from the JS directory.**
``certificate_chatter.xml`` is a QWeb template for a JavaScript component, so it
is loaded through the bundle rather than through the manifest's ``data`` list —
an entry in ``data`` would try to load it into ``ir.ui.view`` and fail. It sits
in ``static/src/js/`` beside the class that names it rather than in a separate
``static/src/xml/``, which is unconventional but keeps the two files that cannot
be understood apart from each other adjacent. The Python test reaches it by that
path, so moving it is a two-file change.

**Order within the bundle is load order, and load order is patch order.** The
backend list puts ``certificate_chatter.js`` before ``form_renderer_patch.js``
because the latter imports the former. The cross-module ordering — this bundle
against another addon's — is the subject of
:ref:`the patch's own decision <form_renderer_patch-race>`, and the reason that
file does not rely on order at all.

.. note::

   One static file the addon ships is deliberately **not** in any bundle:
   :ghsrc:`static/src/img/chart_backdrop.svg`, the 21 kB line-chart backdrop
   behind the public page's hero. It is pulled in by a ``url()`` in
   ``verify.scss`` and served straight off ``/dms_certify_portal/static/``,
   which needs no declaration. Nothing else in the module references it.

certificate_form.scss
---------------------

Source: :ghsrc:`static/src/scss/certificate_form.scss`

Forty-eight lines, two selectors, and it is geometry rather than styling. Both
halves serve the same claim: **there is one right-hand slot on the certificate
form, and the stamped page gets it.** The arch side of that argument is on
:doc:`views/dms_certificate_views`; this is the stylesheet side.

``.o_certify_preview_aside``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   .o_certify_preview_aside {
       padding: 1rem;
       .o_form_view.o_xxl_form_view & {
           flex: 0 0 40%;
           overflow: auto;
       }
   }

The panel is a sibling of the sheet's background, not a column inside it. At XXL
the form view is already a flex row — ``FormController`` adds
``o_xxl_form_view`` on screen size alone — so ``flex: 0 0 40%`` claims two
fifths and leaves the sheet's own ``flex: 2 1`` the other three.

``0 0`` rather than ``1 1`` is the decision: the panel neither grows into the
space the fields need nor shrinks to whatever is left over. Below XXL there is no
flex row, the rule does not apply, and the panel follows underneath at full
width — the same behaviour an aside chatter has, and what the superseded
``col-lg-5`` produced.

The descendant form (``.o_form_view.o_xxl_form_view &``) is what makes that
conditional at all: the class is on an ancestor, not on the panel, so it cannot
be a media query.

.. _assets-sass-min:

``.o_certify_preview .o_pdfview_iframe``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An iframe has no intrinsic size to grow to, so left alone the ``pdf_viewer``
widget collapses to nothing. Everything else about the preview — zoom, paging,
fit — belongs to pdf.js, and all this rule has to do is hand it a usable box:
``height: 78vh``, clamped by ``min-height: 420px`` and ``max-height: 900px``.

.. warning::

   The comment in the file records a trap worth carrying forward, because the
   failure is wildly out of proportion to the cause:

   .. code-block:: scss

      // Not min(78vh, 900px)
      height: 78vh;
      max-height: 900px;

   Sass evaluates ``min()`` itself when both arguments are literals, and it
   refuses to compare ``vh`` with ``px``. That is a **compile** error, and the
   unit of compilation is the bundle — so one unreachable line in one addon's
   stylesheet takes down the whole of ``web.assets_backend`` and with it every
   back-office page in the database. The ``height`` / ``max-height`` pair
   expresses the same intent and is evaluated by the browser instead.

``.o_certify_preview_empty`` is the dashed placeholder the form shows in place of
the viewer when there is nothing to preview, so a draft reads as *not yet
stamped* rather than as broken.

verify.scss
-----------

Source: :ghsrc:`static/src/scss/verify.scss`

511 lines, and the entire visual identity of the public page. Read with
:doc:`templates`, which is where every class name in it comes from.

Scoped under ``.dc-portal``, start to finish
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

One top-level rule nests everything else, including the ``button``, ``input`` and
``:focus-visible`` resets. ``.dc-portal`` is the wrapper
``portal_layout`` puts around the whole page.

This is not tidiness. ``web.assets_frontend`` is served on every frontend page
Odoo renders, and this module does not know what else is installed — a portal
module, a payment acquirer's return page, somebody's website. An unscoped
``h1 { font: 400 44px/1.06 … }`` would redecorate all of them. The scope is what
makes a 511-line opinionated stylesheet safe to ship in a shared bundle.

The palette and the type stack are custom properties
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Eleven colour variables and three font stacks are declared on ``.dc-portal``
itself:

.. list-table::
   :header-rows: 1
   :widths: 22 20 58

   * - Property
     - Value
     - Used for
   * - ``--bleu`` / ``--rouge``
     - ``#000091`` / ``#E1000F``
     - The tricolour hairline, the submit button, the focus ring, and a
       revoked verdict's top border
   * - ``--vert``
     - ``#18753C``
     - An authentic verdict and the wax seal
   * - ``--ambre``
     - ``#B34000``
     - Expired — distinct from revoked, because *authentic but out of date* is
       not *do not accept*
   * - ``--marine``
     - ``#10314F``
     - The hero, and an unknown verdict's top border
   * - ``--brass`` / ``--brass-l``
     - ``#9C7A3C`` / ``#D8BE86``
     - Rules, the crest, the disclosure gate box
   * - ``--display``
     - Cormorant Garamond
     - Headlines
   * - ``--prose``
     - Spectral
     - Body
   * - ``--mono``
     - IBM Plex Mono
     - References, fingerprints and dates — anything transcribed

Custom properties rather than Sass variables, so the values survive into the
compiled stylesheet and can be overridden by a later rule on ``.dc-portal``
without recompiling the bundle.

.. admonition:: A public page must render if the font request fails
   :class: important

   Each of the three families carries a **local stack behind it**:

   .. code-block:: scss

      --display: "Cormorant Garamond", Didot, "Times New Roman", Georgia, serif;
      --prose:   Spectral, Georgia, "Times New Roman", serif;
      --mono:    "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

   The three faces are loaded from Google Fonts in ``portal_layout``'s ``head``.
   A port-authority or embassy workstation on a network that blocks the CDN is
   not a hypothetical, and the fallbacks are chosen to keep the page's register
   rather than to be merely legible — Didot and Georgia in place of Cormorant and
   Spectral, not a drop to the browser default sans.

   The counter-argument is still worth stating: the request happens, and this
   mitigates its failure rather than removing it. See :doc:`templates`.

Sections, in source order
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Block
     - Notes
   * - ``.tri``, ``.p-head``, ``.p-lang``, ``.p-tls``
     - The masthead. A three-column CSS grid for the tricolour hairline, and the
       language switcher styled as a segmented control with ``.is-on`` for the
       active one
   * - ``.p-hero``, ``.p-form``, ``.refbox``, ``.p-go``
     - The desk. ``1fr 400px`` grid — a fixed-width form column, because the
       lookup card must not reflow as the headline changes language. The
       reference input is 19 px monospace with a doubled bottom border; the
       passport input is capped at ``150px``, which is a quiet way of saying the
       second check is short
   * - ``.p-res``, ``.verdict``
     - The verdict card. ``margin: -30px 0 0`` lifts it over the hero's lower
       edge, with a 3 px top border recoloured per state: green by default,
       ``.bad`` red, ``.warn`` amber, ``.unknown`` marine
   * - ``.v-seal`` + ``dc-stamp``
     - The seal lands with a 0.5 s stamp — scale 1.5 and ``-14deg`` down to
       ``-7deg``. Wrapped in ``@media (prefers-reduced-motion: reduce)``, which
       sets the final transform without the animation. Gated on ``.reveal``, a
       class only ``verify_result`` applies, so the seal never animates anywhere
       else
   * - ``.v-band``, ``.v-cols``, ``.led``, ``.kv``, ``.gate``
     - The verdict's body. ``.led`` is the crew table, ``.kv`` the two-column
       definition grid, ``.gate`` the brass-bordered box explaining what
       confirm-only disclosure withholds
   * - ``.docframe``
     - ``max-height: 520px`` with ``overflow: auto`` — a multi-page document
       scrolls inside the column instead of pushing the fingerprint and the
       actions off the screen. ``cursor: zoom-in`` on each page, which is the
       only hint that the image is a link
   * - ``.v-foot``, ``.v-acts``, ``.p-btn``
     - Reference, issuer and fingerprint in a three-column grid; the action row,
       with ``.spacer { margin-left: auto }`` pushing :guilabel:`The paper does
       not match` away from the other two so it cannot be hit by accident
   * - ``.p-info``, ``.steps``, ``.sec``, ``.p-foot``
     - The explainer and the page footer. ``.steps`` numbers itself with
       ``counter-reset`` / ``counter-increment`` and a ``::before`` ring, so the
       markup stays a plain ``<ol>``

Three rules exist to pay for a template decision
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Worth naming because each is invisible until you know which markup it answers:

* ``.p-res:empty { padding: 0 }`` — ``verify_form`` always renders its
  ``#result`` container so the redirect fragment resolves, even with no error to
  show. This stops the empty case costing vertical space.
* ``.dc-standalone { padding-top: 48px }`` and
  ``.dc-standalone .verdict { margin: 0 }`` — ``verify_throttled`` has no hero
  for the card to tuck under, so the negative margin has to be undone.
* ``.docframe .dc-page + .dc-page { margin-top: 14px }`` — the adjacent-sibling
  selector, rather than a margin on every page, so a single-page document has no
  stray gap.

Responsive, and print
^^^^^^^^^^^^^^^^^^^^^

Two breakpoints. At ``960px`` every two-column grid collapses to one and the
column dividers become top borders; the seal drops from 118 px to 88 px and
``.v-acts .spacer`` loses its ``auto`` margin. At ``520px`` the TLS indicator is
hidden and the masthead tightens.

The ``@media print`` block sits **outside** the ``.dc-portal`` nesting, at the
foot of the file, and is the part an agent actually keeps:

.. code-block:: scss

   @media print {
       .dc-portal {
           .p-hero, .p-info, .p-foot, .p-head, .tri, .v-acts {
               display: none !important;
           }
           .verdict { margin: 0; box-shadow: none;
                      border: 1px solid #333333; page-break-inside: avoid; }
           .docframe { max-height: none; overflow: visible; }
       }
   }

The furniture goes, the card gets a plain border a printer can render, and
``.docframe`` loses its ``max-height`` so **every** page image prints rather
than the first scrollful. ``page-break-inside: avoid`` keeps a verdict from being
split across sheets. The :guilabel:`Print this result` button that triggers it is
documented in :doc:`static/verify`.

Translations
------------

Source: :ghsrc:`i18n/fr.po`, with :ghsrc:`i18n/dms_certify_portal.pot` as the
template.

373 entries in the catalogue. **106 are translated, and every one of them belongs
to a public portal template** — all seven of them, from ``portal_layout``'s
footer to ``verify_result``'s verdicts. The back office is untranslated: the field
labels, the settings page, the certificate form, the menus, the groups and the
selection values are all empty ``msgstr`` and fall back to English.

.. list-table::
   :header-rows: 1
   :widths: 40 14 46

   * - Surface
     - French?
     - Why
   * - The seven ``verify_*`` / ``portal_layout`` templates
     - yes
     - An embassy clerk at a French counter is the one reader who has no choice
       about the language
   * - Field labels, help text, selections
     - no
     - Read by the issuing desk and by configuration staff
   * - The certificate form, the settings page, the wizard
     - no
     - Same
   * - Menus, groups, actions, constraints
     - no
     - Same

The split is purely what is in the file — untranslated entries fall back to
English, so nothing is broken by it.

A handful of entries are translated as a side effect: a string shared between a
portal template and a backend label (a state name, say) carries one ``msgid``
with both references, and translating it for the portal translates it everywhere.

.. important::

   The catalogue contains **no** ``#: code:`` reference of any kind. Every entry
   arrived through ``model_terms:ir.ui.view`` or a ``model:`` record.

   That is the evidence for a decision recorded in two places in the source —
   ``_fail()``'s docstring and an XML comment in ``verify_form``: a refusal
   sentence built in the controller would be invisible to the translation export
   and would sit in English on a French page for ever. So the controller passes a
   reason code and the wording lives in the template. See :doc:`templates`.

Adding a language
^^^^^^^^^^^^^^^^^

Two mechanisms meet here, and neither needs code:

* ``portal_language_codes()`` in :ghsrc:`hooks.py` reads the two-letter codes off
  the ``i18n`` directory rather than a hard-coded list, so dropping an ``es.po``
  beside ``fr.po`` is all it takes to offer Spanish at the counter. The
  controller imports the same function to build the switcher, so the page offers
  exactly the languages the portal is written in — not the six a database may
  have active for the back office, five of which would lead to an English page.
* ``activate_portal_languages()`` installs them, because a fresh database has
  only English active and the switcher would otherwise have nothing to switch
  to.

See :doc:`hooks`.

Re-exporting after a change:

.. code-block:: bash

   odoo-bin i18n export -c odoo.conf -d <database> -l fr_FR \
       -o /tmp/certify_fr.po dms_certify_portal

Browser tours
-------------

Source: :ghsrc:`static/tests/tours/certificate_chatter_tour.js`

One file, three tours, all over the certificate form. They are in
``web.assets_tests``, which is loaded only for a test run.

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - Tour
     - Asserts
   * - ``dms_certify_portal_chatter_tour``
     - Opens a certificate from the list (``td:contains(ICS-)``) and checks the
       chatter has no :guilabel:`Send message`, no :guilabel:`Log note` and no
       composer — **and** that the Activity button, the followers and the
       attachment button are still there, so a chatter that failed to render
       does not pass. :doc:`static/certificate_chatter`
   * - ``dms_certify_portal_preview_aside_tour``
     - At 1920×1080: the stamped page starts at or after the sheet's right edge,
       and its width is two fifths of the form's to within one percent
   * - ``dms_certify_portal_preview_below_tour``
     - At 1366×768: the panel's top is at or below the sheet's bottom — it
       stacked rather than being squeezed beside the sheet

The two layout tours share a ``boxes()`` helper that reads
``getBoundingClientRect()`` off the form, the sheet background and the panel, and
they throw with the measured pixel values rather than a bare assertion.

.. admonition:: Why geometry is tested in a browser at all
   :class: important

   The arch and the stylesheet each look right on their own. Only the rendered
   box says which side of the sheet the panel ended up on, and which branch of
   the layout you get is decided by the viewport — ``FormController`` adds
   ``o_xxl_form_view``, and with it the flex row, only at XXL. So the pair sets
   ``browser_size`` before ``start_tour`` and runs the same element twice at two
   sizes.

   The chatter tour is in a browser for a different reason: the server ships
   ``mail.Chatter`` and our primary-inherit template side by side and never
   evaluates the xpaths, and the component itself is chosen at render time. Only
   a browser can see either. :doc:`static/form_renderer_patch`

See also
--------

* :doc:`templates` — every class name in ``verify.scss``, and the ``head`` that
  loads the three typefaces
* :doc:`static/verify` — the print button, and the mask that reads
  ``data-groups``
* :doc:`static/certificate_chatter` and :doc:`static/form_renderer_patch` — the
  two backend JavaScript files and the one decision between them
* :doc:`views/dms_certificate_views` — the arch half of
  ``certificate_form.scss``'s geometry
* :doc:`hooks` — ``portal_language_codes()`` and
  ``activate_portal_languages()``
* :doc:`../development/testing` — running the three tours
