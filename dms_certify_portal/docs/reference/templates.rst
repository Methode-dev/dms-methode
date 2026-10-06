verify_templates
================

Source: :ghsrc:`templates/verify_templates.xml`

Seven QWeb templates, no inheritance, nothing extended. This is the whole public
face of the addon: everything an embassy clerk ever sees is rendered from this
one file by the routes in :doc:`controllers/verify`.

It is also the module's only genuinely hostile surface. Every other page in this
reference describes something behind a login. These templates are served to
anonymous visitors, which is why the decisions recorded further down are mostly
about what the markup is **not** allowed to reach.

.. contents::
   :local:
   :depth: 2

Structure
---------

.. code-block:: text

   portal_layout  ── t-call web.frontend_layout   (the `web` module, not `website`)
   │     no_header / no_footer
   │     head: robots · referrer · viewport metas, then Google Fonts
   │     div.dc-portal
   │       ├── div.tri                  tricolour hairline
   │       ├── header.p-head            crest · company['name'] · "● TLS" ·
   │       │                            language switcher (t-if len(languages) > 1)
   │       ├── <t t-out="0"/>           ←  the calling page's body goes here
   │       └── footer.p-foot            address · operations desk · data notice
   │
   ├── verify_hero      the headline, the explainer, and the two inputs
   │                    form action="/" method="post", csrf_token
   ├── verify_info      "What this check is worth" + "On the paper you are holding"
   └── verify_seal      inline SVG wax seal, company name on a textPath

   verify_form ────── portal_layout
   │                  ├── verify_hero
   │                  ├── div#result    refusal card, keyed off error_code
   │                  │                 (renders empty when there is no error)
   │                  └── verify_info
   │
   verify_result ──── portal_layout
   │                  ├── verify_hero
   │                  ├── div#result
   │                  │     ├── .v-flash   notice == 'mismatch_reported'
   │                  │     ├── .v-top     headline by doc['public_state'],
   │                  │     │               + verify_seal when neither revoked
   │                  │     │                 nor expired
   │                  │     ├── .v-band    dates · verification no. · notified
   │                  │     ├── .v-cols    left: who is listed
   │                  │     │              right: the page images
   │                  │     ├── .v-foot    reference · issuer · source_hash
   │                  │     └── .v-acts    print · download · "does not match"
   │                  └── verify_info
   │
   verify_throttled ─ portal_layout
                      ├── div#result.dc-standalone
                      │     locked_reference ? "Reference locked"
                      │                      : "Checks from here are paused"
                      └── verify_info       ←  no hero. See below.

Record ids
----------

.. list-table::
   :header-rows: 1
   :widths: 22 26 52

   * - External id
     - ``name``
     - Role
   * - ``portal_layout``
     - Verification portal: layout
     - The chrome. Called by the three pages, never rendered on its own
   * - ``verify_hero``
     - Verification portal: hero
     - The lookup form. On the form page *and* the result page, so "check
       another document" is never more than a scroll away
   * - ``verify_info``
     - Verification portal: explainer
     - What the check is worth, and the markings to look for on paper. Below
       every page, including the refusals
   * - ``verify_seal``
     - Verification portal: seal
     - The wax seal stamped on an authentic verdict. Called from
       ``verify_result`` only
   * - ``verify_form``
     - Check a document
     - The page both ``GET /`` routes render, and the page every refusal
       redirects back to
   * - ``verify_result``
     - Verification result
     - The verdict. Rendered only behind a session token
   * - ``verify_throttled``
     - Verification: too many attempts
     - Both rate limits land here, distinguished by ``locked_reference``

What each template is given
---------------------------

The templates receive a flat dict assembled by the controller. Nothing resolves
itself from ``request.env`` — there is no recordset in scope to resolve from.

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Key
     - Built by
     - Read by
   * - ``company``
     - ``_company_values()``
     - ``portal_layout``, ``verify_seal``, ``verify_form``,
       ``verify_throttled`` — a seven-key dict of name and address, never the
       ``res.company`` record
   * - ``languages``
     - ``_language_values()``
     - ``portal_layout``. A list of ``{code, short, active, url}``
   * - ``reference_groups``, ``reference_sample``
     - ``_chrome()``
     - ``verify_hero`` — the input mask and the placeholder
   * - ``recaptcha_site_key``
     - ``_form_values()``
     - ``verify_hero``. Empty string when ``google_recaptcha`` is absent or
       unconfigured, and every captcha branch is written to vanish on an empty
       string
   * - ``error_code``, ``reference``, ``attempts_left``
     - ``_form_values()``
     - ``verify_form``. All three come off the session and are popped on read
   * - ``doc``
     - ``DmsCertificate._get_public_values(holder)``
     - ``verify_result``. See :ref:`templates-trust-boundary`
   * - ``token``
     - the route's own path segment
     - ``verify_result`` — pasted into the page-image, download and mismatch
       URLs
   * - ``notice``, ``allow_download``, ``expires_in``
     - the ``verify_result`` route
     - ``verify_result``
   * - ``window_minutes``, ``locked_reference``
     - the ``verify_submit`` route
     - ``verify_throttled``

Two keys ``_get_public_values()`` publishes are deliberately **not** read here:
``public_state_label`` (the state's own translated label — the page writes a
whole sentence per state instead, see :ref:`templates-whole-sentences`) and
``sealed_hash``. The result page prints ``source_hash`` and only
``source_hash``, labelled :guilabel:`SHA-256 fingerprint of the issued file`,
because that is the value also printed on the paper; the sealed file's hash
changes on every re-stamp and would not match anything in an embassy's file.

.. _templates-refusals:

The refusal card
----------------

``verify_form`` carries every negative outcome that is not a rate limit. The
controller sets a session key and redirects; the template picks the wording off
``error_code``.

.. list-table::
   :header-rows: 1
   :widths: 16 32 52

   * - ``error_code``
     - Headline
     - When, and what it withholds
   * - ``expired``
     - That result has expired
     - The session token no longer resolves. Set by the ``verify_result`` route
       itself, so a stale tab refuses rather than 404s
   * - ``incomplete``
     - Both details are needed
     - One of the two inputs was empty. Logged as ``no_match`` all the same —
       the attempt counter does not distinguish them
   * - ``captcha``
     - We could not confirm this came from a browser
     - Only reachable with ``google_recaptcha`` installed and configured
   * - *(anything else)*
     - Those two details do not open a document
     - The ``t-else`` branch, and the one that matters. Unknown reference and
       wrong second check are the **same** sentence: *"We will not say which of
       the two failed."*

The copy then volunteers the one thing it is happy to give away — *our
references never use I, L, O or U* — because an agent squinting at ``0`` against
``O`` is the overwhelmingly likely cause, and a guesser already knows the
alphabet from any document they have seen. The same sentence appears on
``verify_throttled``. Change the reference alphabet and both have to change with
it.

``attempts_left`` prints only when there is both an error and a reference to
count against. See :ref:`verification-refusals` for the same table told from the
agent's side.

Decisions worth naming
----------------------

.. _templates-trust-boundary:

The result page is handed a dict, never a record
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The single load-bearing decision in the file, and the comment above
``verify_result`` says so in as many words.

``doc`` is the plain dict returned by ``_get_public_values()``. A QWeb template
handed a recordset can walk it: ``doc.partner_id.email``, ``doc.message_ids``,
``doc.company_id.partner_id.bank_ids``. None of that is a hypothetical failure
mode — it is the normal way one writes an Odoo template, which is exactly why
the recordset must not be in scope. A whitelist that has to be edited to publish
a new fact is the point.

The same reasoning produced ``company`` as a dict rather than the
``res.company`` record: one dot from a company sits a partner, and one dot from
a partner sits a bank account.

.. important::

   Adding a fact to the result page is a two-file change by construction — the
   key has to be added to ``_get_public_values()`` before the template can read
   it. If you find yourself wanting to pass the recordset "just for this one
   field", that is the guard working.

.. _templates-no-website:

The layout wraps ``web.frontend_layout``, not ``website``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``web.frontend_layout`` lives in the ``web`` module, which every Odoo
installation has. Calling it gives the page Bootstrap, the base resets and the
``web.assets_frontend`` bundle — all the styling ``verify.scss`` needs to sit on
top of — and brings along no builder, no themes, no snippets, no editor and no
first-run configurator. That is what lets the manifest leave ``website`` out of
``depends`` altogether; the manifest's own comment calls the alternative "public
surface area this module does not want". See :ref:`limits-no-website`.

``no_header`` and ``no_footer`` are set even though ``web.frontend_layout`` is
already bare. They are the flags the portal and website layouts honour, and they
are here so that installing ``website`` later for unrelated reasons does not
suddenly wrap an embassy-facing page in somebody's site chrome.

The crawler defence is a meta tag and a header, because there is no ``robots.txt``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Without ``website`` installed, Odoo serves no ``robots.txt`` at all. So the two
mechanisms that actually reach a compliant crawler are both on the response:

* ``<meta name="robots" content="noindex, nofollow, noarchive, nosnippet"/>``
  in ``portal_layout``'s ``head``.
* ``X-Robots-Tag: noindex, nofollow, noarchive``, applied to every portal
  response by the controller's ``NO_STORE`` list — including the page images and
  the PDF download, which carry no HTML and therefore no meta tag.

Neither stops a crawler that ignores them. What stops that one is that there is
nothing to crawl: every result lives behind a session token and a POST.

``<meta name="referrer" content="no-referrer"/>`` is the matching pair of the
``Referrer-Policy`` header, and exists so a reference cannot ride out in a
``Referer`` when the agent clicks a page image open in a new tab.

.. _templates-whole-sentences:

Every verdict sentence is one text node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An XML comment in ``verify_result`` states the rule: each sentence is a whole
text node, and every moving value sits in the band underneath it rather than
inside the prose.

Wrapping a date in ``<b>`` mid-sentence splits one translatable string into
fragments the translator cannot reorder, and French needs to reorder them. So
the headline is *"Authentic, but out of date"* and the dates are a flat row of
``<span>``\ s in ``.v-band`` below — three states' worth of prose above, the
figures below, and no string in the file that reads as half a clause.

The one deliberate exception is ``attempts_left``, where the number genuinely
belongs in the sentence.

All refusal copy lives in the template, and the controller passes a code
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``_fail()`` sets a reason code on the session; the sentences are in
``verify_form``. The reason given in both the controller docstring and the
template comment is translation: Odoo's exporter does not walk Python source in
this layout, so a sentence built in the controller would never reach
``i18n/*.po`` and would sit in English on a French page for ever.

The claim is checkable, and it holds — :ghsrc:`i18n/fr.po` contains no
``#: code:`` reference of any kind. Every string in the catalogue arrived through
``model_terms:ir.ui.view``. See :doc:`assets`.

The secondary benefit is the one a reader of this page will care about more:
there is exactly **one** place the four refusal wordings can diverge, and they
sit within a few lines of each other where an inconsistency is visible.

The throttled page has no lookup form
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``verify_form`` and ``verify_result`` both open with ``verify_hero``.
``verify_throttled`` does not — it goes straight to the verdict, under
``.dc-standalone``, and then to ``verify_info``.

Offering an input box to someone who has just been rate-limited invites them to
use it, and every use is another logged failure against a counter that is
already full. What the page offers instead is the operations desk's email and
phone number, which is the only action that can actually help either an agent
who mistyped or a desk that needs to know somebody is guessing.

``.dc-standalone`` exists purely to pay for the missing hero: the verdict card
is styled with ``margin: -30px 0 0`` so it tucks under the hero's lower edge, and
the standalone rule resets that to zero and adds top padding. See
:doc:`assets`.

The seal costs no request; the typefaces do
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``verify_seal`` is inline SVG — three concentric circles, a ``textPath`` carrying
``VERIFIED · <company name>``, and the same staff-and-ring glyph as the
masthead's crest. No image file, no request, nothing to 404, and it renders in
the printed copy because the browser already has it. ``.p-crest`` is inline for
the same reason.

That makes the ``head`` of ``portal_layout`` the honest exception worth naming:
it carries two ``preconnect`` hints and a stylesheet ``<link>`` to
``fonts.googleapis.com``, so a request leaves the visitor's machine before the
page paints. The mitigation is real but partial — ``verify.scss`` keeps a local
stack behind each of the three families, so a workstation on a network that
blocks the CDN gets Didot and Georgia rather than a broken page. The request
itself still happens.

A second external request appears only when a site key is configured: the
reCAPTCHA ``<script>`` inside ``verify_hero``'s ``t-if``.

.. note::

   ``.p-hero .chart`` pulls a third asset,
   ``/dms_certify_portal/static/src/img/chart_backdrop.svg``, through a
   ``url()`` in ``verify.scss``. It is served from this module, not a CDN, and it
   is the one static file the addon ships that is **not** listed in the manifest
   bundles — a ``url()`` reference needs no declaration.

.. todo::

   The masthead renders ``● TLS`` as static copy. It is not a check of anything:
   the string is in the template unconditionally and would print identically over
   plain HTTP. Is the intent to assert the deployment requirement, or should it
   be dropped or made conditional? As written it is a claim the page cannot
   substantiate.

The page is shown as images, and each one links to itself
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``verify_result`` loops ``range(1, doc['page_count'] + 1)`` and emits an
``<a>``-wrapped ``<img>`` per page, both pointing at the same
``/r/<token>/page/<n>``. The anchor is not redundant: fitted to its column the
page is right for comparing line by line, but the seal's QR code comes out around
40 pixels across, which no reader will decode. Opening the image gives it the
~140 it needs.

``target="_blank" rel="noreferrer"`` and ``loading="lazy"``. The ``t-else``
branch — no ``page_count`` — says so plainly and falls back to comparing the
reference and the fingerprint by eye, rather than rendering an empty frame.

Why images rather than the PDF is the controller's decision, not this file's; see
:doc:`controllers/verify`. The opposite choice is made on the issuing screen,
where the reader is the operator and a real viewer is what they want —
:doc:`views/dms_certificate_views`.

Every URL in the file is written without ``/_check``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The lookup form posts to ``/``; the page images, the download and the mismatch
form all hang off ``/r/<token>/``; :guilabel:`Try again` is ``href="/"``. The
routes themselves are declared under ``/_check``, and ``ir.http`` rewrites a
bare path on the check host onto the prefix.

So the paths here are correct **only on the check host** — which is the only host
the templates are ever rendered on. Emitting ``/_check/...`` from a template
would leak the internal prefix into the printed world and into an embassy's
bookmarks.

.. todo::

   The README documents the public routes under ``/verify`` and ships an nginx
   block to match. Both are wrong: the routes are ``/_check…`` and the templates
   emit bare paths. The code is right; fix the README. See
   :ref:`deployment-nginx`.

The second-factor help text describes all three modes at once
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The passport field's help says: *some documents ask for the whole number, others
for just the last 4 characters — type what the passport in hand shows. If the
document carries no passport number, type a listed date of birth instead
(DDMMYYYY).*

That covers the three second-factor modes in one static paragraph, and it has to,
because the form does not know which mode applies. It cannot: the mode is a
property of the document, the document is identified by the reference, and the
reference is in the input the agent has not submitted yet. Telling them after the
fact would be an oracle — "this reference uses full passports" confirms the
reference exists. See :ref:`concepts-second-factor`.

For the same reason the single input is labelled *"Passport of a person listed on
the paper"* rather than naming a format, and ``maxlength="12"`` is sized for the
longest of the three rather than for whichever applies.

Small things that are not accidents
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* ``novalidate="novalidate"`` on the lookup form, with ``required="required"``
  on both inputs. The attributes are kept for assistive technology; browser
  validation is turned off so that the server decides, once, what counts as
  incomplete — and so that an empty submission produces the module's own refusal
  card rather than a native tooltip.
* ``autocomplete="off"``, ``spellcheck="false"``, ``autocapitalize="characters"``
  on both inputs. A shared counter workstation must not offer the last
  seafarer's passport number to the next agent.
* ``maxlength="26"`` on the reference against a grouped length of 20 for the
  default three-character prefix — the prefix is configurable, and the input must
  not truncate a longer one.
* ``#result`` is on a ``<div>`` that renders even with no error, so the fragment
  the controller redirects to always resolves. ``.p-res:empty`` zeroes its
  padding so the empty case costs no vertical space.
* ``t-if="len(languages) > 1"`` on the switcher. One language is not a choice,
  and a single dead button is worse than none.
* The footer's data notice names the controller and states the retention promise
  on every page, including the refusals — which is where a visitor is most likely
  to be reading the small print.

See also
--------

* :doc:`controllers/verify` — the routes that render these three pages, the
  session gate, and the order the submission is checked in
* :doc:`models/dms_certificate` — ``_get_public_values()``, the whitelist that
  decides what ``verify_result`` can say
* :doc:`static/verify` — the little JavaScript this markup carries, and why it is
  not OWL
* :doc:`assets` — ``verify.scss``, and the French catalogue that covers these
  seven templates and nothing else
* :doc:`views/dms_certificate_views` — the issuing screen, which shows the same
  document with the opposite viewer decision
* :doc:`../handbook/verification` — the same pages told as a task, and
  :ref:`verification-refusals`
