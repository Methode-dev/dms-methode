Testing
=======

The suite uses Odoo's own test framework (``odoo.tests.common``), not a separate
runner. Three modules live under ``dms_certify_portal/tests/`` and are discovered
automatically when the module is installed or updated with tests enabled.

What they assert is deliberately not the shape of the code. They assert the
promises the public page makes to an embassy agent: that a reference on its own
opens nothing, that the fingerprint printed on the paper is the fingerprint of
the paper, that a redacted copy carries nobody else's identity, and that guessing
at one reference stops working.

.. contents::
   :local:
   :depth: 2

Running the suite
-----------------

.. code-block:: bash

   odoo-bin -c odoo.conf -d <database> \
       -u dms_certify_portal --test-enable \
       --test-tags /dms_certify_portal --stop-after-init

To narrow to one class or one test:

.. code-block:: bash

   --test-tags /dms_certify_portal:TestVerifyPortal
   --test-tags /dms_certify_portal:TestVerifyPortal.test_the_form_is_public_and_asks_for_both_details

Every class in the suite is tagged ``@tagged("post_install", "-at_install")``. It
runs once the whole database is installed, not in the middle of this module's own
installation — which matters here because two classes compile asset bundles and
one reads a view's arch through ``get_view``, none of which is meaningful
mid-install.

There is no shared ``tests/common.py``. Each class builds its own fixture in
``setUpClass``: a ``dms.certificate.type``, a one-page PDF from ``build_pdf()``,
and an ``ir.attachment`` holding it. ``CREW`` and ``build_pdf`` are the two
things imported across modules, and they are importable from outside the addon
too (:doc:`extending`).

.. important::

   **A green run requires excluding one module.**
   ``tests/test_known_defects.py`` asserts behaviour the addon does not yet
   have, so every test in it fails on purpose — see
   :ref:`testing-known-defects`. The command above reports **seven failures**
   for that reason.

   .. code-block:: bash

      # the suite as it is expected to pass today
      --test-tags '/dms_certify_portal,-known_defects'

      # only the recorded defects
      --test-tags /dms_certify_portal:TestKnownDefects

   Excluded that way the suite is **120 tests, 0 failures**.

.. _testing-known-defects:

The defects that are recorded as failing tests
----------------------------------------------

``tests/test_known_defects.py`` is deliberately red. Each test asserts what the
module is *supposed* to do about a defect that is still present, so that the
defect cannot be quietly forgotten — a failing test is harder to lose than a
note in a changelog. Every one names its source line and a candidate fix in its
docstring.

When a defect is fixed its test should start passing **unchanged**. If making it
green means editing the assertion, the fix is not a fix.

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - Test
     - What is wrong
   * - ``test_the_seal_keeps_its_guilloche_border_after_a_settings_save``
       ``test_the_seal_keeps_its_microtext_footer_after_a_settings_save``
       ``test_lookup_notifications_stay_on_after_a_settings_save``
       ``test_a_shipped_boolean_parameter_reads_the_same_before_and_after_a_save``
     - ``seal_guilloche``, ``seal_microtext`` and ``notify_on_lookup`` ship as
       ``"1"`` in :doc:`../reference/data/ir_config_parameter` but are read as
       ``== '1'``. ``res.config.settings`` writes a Boolean parameter as
       ``"True"``, so **the first Settings save silently switches all three
       off** — removing two anti-forgery features from every document sealed
       afterwards. ``allow_download`` is immune because it goes through
       ``_bool_param()``, which accepts both spellings; that is the shape the
       three readers want.
   * - ``test_an_unrecognised_disclosure_mode_does_not_serve_the_whole_document``
     - ``_public_bytes`` branches on ``if self.disclosure != 'confirm'`` and
       returns the unredacted copy, so redaction is the exception rather than
       the rule. A mode added through ``selection_add`` inherits a breach it
       never wrote. The test proves it: the second holder's passport appears on
       the page served to the first. Branching on ``== 'full'`` would make an
       unknown mode redact. Contrast ``second_factor``, which fails closed.
   * - ``test_hide_expired_hides_an_expired_document``
       ``test_the_documented_hide_expired_override_point_exists``
     - ``hide_expired`` ships as a parameter and has a Settings field and
       widget, and ``_hide_expired()`` is documented in ``README.md`` and the
       manifest as an override point. **Nothing reads any of it** and the method
       does not exist, so an expired document always announces itself as
       expired — which still confirms to a stranger that the reference is real.

The ``known_defects`` tag exists so a pipeline can exclude them *explicitly*
rather than by not noticing them. Do not add a test there to park work you
simply have not finished; it is for defects whose fix is a behaviour decision
somebody has to make.

.. _testing-check-host:

Every portal request fakes the check host
-----------------------------------------

.. important::

   **This is the single most important thing to know before writing a new portal
   test.** ``TestVerifyPortal`` overrides ``url_open`` to set a ``Host`` header
   on *every* request:

   .. code-block:: python

      CHECK_HOST = 'check.localhost'

      def url_open(self, url, *args, headers=None, **kwargs):
          headers = dict(headers or {})
          headers.setdefault('Host', CHECK_HOST)
          return super().url_open(url, *args, headers=headers, **kwargs)

   Without that header **none of the seven routes exist**. The paths are
   declared under ``/_check`` and ``ir.http._match`` only rewrites ``/`` to
   ``/_check`` when the request arrived on a ``check.`` host. A test that calls
   ``self.url_open('/')`` directly, or a new test class that forgets the
   override, does not get a refusal or a redirect — it gets the back office, or
   a 404, and then fails on an assertion about page content that has nothing to
   do with what it was testing.

Three consequences worth internalising:

* **Write portal tests against the bare paths.** ``/``, ``/d/<reference>``,
  ``/r/<token>``. Never ``/_check/…`` — typing the prefix on the check host
  produces ``/_check/_check`` and 404s, which is itself a test
  (``test_the_internal_namespace_is_not_addressable_on_the_check_host``).
* **The header survives the POST-Redirect-GET**, because ``requests`` keeps it
  across the redirect. That is what lets ``_submit()`` return a response whose
  body is already the result page.
* **Nothing has to resolve the name.** The request still goes to
  ``127.0.0.1``; ``check.localhost`` is only ever read out of the header. And
  tests run **without** ``proxy_mode``, so Odoo reads ``Host`` as sent — which
  is also why no test can exercise ``_client_ip`` behaving correctly behind a
  real proxy (see `Known gaps`_).

If you are adding a class that drives the portal, subclass ``TestVerifyPortal``
or copy that ``url_open`` override. Copying it is honest; forgetting it is a
confusing afternoon.

What each module covers
-----------------------

Organised by the section comments in the files, which is how the files are
organised.

``tests/test_certificate.py``
   Sealing and verification at the model level. No HTTP, no browser.

   ``TestCertificate``
      *The reference* — the printed shape ``PREFIX-YYYY-PPP-XXXX-XX``; that
      ``I``, ``L``, ``O`` and ``U`` never appear; that there is **no counter**
      (two references generated back to back share no incrementing part); that a
      place code lands where it is printed.

      *Sealing* — certifying stamps a copy and leaves the source byte-identical;
      the watermark and guilloche survive a source PDF that paints its own
      opaque white background (WeasyPrint does this, wkhtmltopdf happened not
      to, and anything drawn *under* that fill is invisible); the printed
      fingerprint is of the document **before** sealing; the reference is
      actually present as text on the sealed page; a re-stamp keeps the
      reference; a revoked document refuses to be re-sealed; a document with
      nobody listed refuses to be certified at all.

      *Redaction* — confirm-only shows the person checked and hides the rest;
      each person gets their **own** view of the page; nothing but the crew
      lines is removed; the page image renders fine enough to decode the
      stamp's QR; the redaction fill is black rather than grey; a lookup with no
      matched person hides everybody; stale positions fall back to searching by
      value; a document with no positions recorded at all is still safe; and a
      page that still leaks after redaction is **not served**.

      *Matching* — the reference alone opens nothing; any listed person opens
      it; separators and case do not decide the outcome; a passport from another
      document does not open it; an unknown reference opens nothing; a draft is
      not verifiable; a revoked document still verifies and says so; switching
      the second factor needs no re-entry of the crew; the date-of-birth mode;
      the passport number reads back for an operator; matching still goes
      through the hashes after the number is corrected; an *Agent* cannot read
      the passport column; the hashes are keyed to this instance rather than
      being a bare SHA-256.

      *Throttling* — guessing at one reference locks it **across addresses**;
      successful lookups do not count against it.

      *What the public page receives* — the crew is redacted under confirm,
      listed under full, and the returned dict is plain data.

      *Validity* — validity counts from the movement date; *until revoked*
      leaves no expiry; an out-of-date document reads as expired rather than
      missing; an issued document cannot be deleted; ``verify_url`` uses the
      public base URL parameter.

   ``TestCertificateDesk``
      The issuing screen and what the desk is told.

      *Preview* — the panel is the sealed **PDF**, not a picture of it; it
      renders before anything has been certified; it follows the marking; it
      survives a document it cannot read rather than breaking the form.

      *What the desk is told* — certifying posts the reference and the rules in
      words; a re-stamp says the copies already sent still verify; a lookup is
      reported as *"An external user"*; routine lookups stay quiet when
      notifications are off while a lockout reaches the desk anyway; a reported
      mismatch lands on somebody's activity list; the requester is never named
      or addressed.

      *Revocation* — revoking does not touch the sealed bytes and keeps the
      printed fingerprint; it posts the reason the embassy will read; the wizard
      carries that reason through.

      *Delivery* — sending is what makes a certified document delivered; an
      ordinary note is not; nothing can be sent or downloaded before it is
      sealed; the composer opens with the sealed copy attached.

      *The screen itself* — the chatter sits under the form rather than beside
      it; the source attachment picker ignores the copies this module generates.

      *Document types* — the public page shows the type's name; a type in use
      cannot be deleted; codes are unique; the Settings page opens showing the
      current ``auto_stamp`` choice, and both ticking and unticking survive the
      save. That last pair is the regression test for a real bug: a *computed*
      ``certify_auto_stamp_type_ids`` was recomputed straight back to ticked
      between the client saving and ``set_values`` reading, so an untick never
      stuck.

   ``TestAssets``
      Both SCSS bundles have to survive Sass. Nothing else in the suite compiles
      assets, so nothing else would notice — and the failure is ugly: Odoo does
      not raise on a bad stylesheet, it logs a warning and returns a bundle
      whose *content is the error message*, taking every other rule in the
      bundle down with it. The tests therefore assert on
      ``assertNoLogs(..., 'WARNING')`` rather than on the returned CSS. The
      docstring records the declaration that caused it: ``height: min(78vh,
      900px)``, which Sass evaluates itself and rejects as incompatible units.

   ``TestListedPeopleLock``
      ``holders_locked`` is a **UI** lock and lives entirely in the view arch —
      a pair of domains the web client evaluates against the record. Delete them
      and nothing breaks, nothing logs, and the list quietly becomes editable
      again. So the tests read the arch: the ``create``/``delete`` option
      domains are present on ``holder_ids``, and ``holders_locked`` is itself on
      the form, because a domain over a field the arch never mentions evaluates
      against nothing.

   ``TestChatterTemplate``
      ``CertificateChatter`` inherits ``mail.Chatter`` in primary mode and cuts
      the composer out of it — and that inheritance is applied **in the
      browser**. The server ships both templates untouched and never evaluates
      the xpaths, so an expression matching nothing fails at runtime with a
      blank chatter and no Python suite would notice. These tests run the same
      xpaths through Odoo's own ``apply_inheritance_specs``, then assert that
      *Send message*, *Log note*, ``<Composer`` and ``RecipientsInput`` are gone
      and that the thread, the followers, the activity list and the file
      uploader are not.

``tests/test_portal.py``
   The public routes, through real HTTP (``HttpCase``). Read
   :ref:`testing-check-host` before adding to this file.

   ``TestVerifyPortal``
      *The form* — it is public and asks for both details, and says so in as
      many words; it is never indexed (``X-Robots-Tag``, ``Referrer-Policy``,
      ``Cache-Control: no-store``); a scanned QR prefills the reference and
      nothing else; the URL the **model** prints lands on the form the
      **controller** serves — the one place those two are held to each other,
      and a drift on either side prints a QR that 404s on every document issued
      since; and the QR route says nothing about whether the reference exists.

      *Refusals* — a wrong second check is refused without saying which half
      failed; an unknown reference produces a page **byte-identical** to a wrong
      passport once the CSRF token and the echoed reference are blanked; the
      reference is given back grouped as it is printed; the refusal says how many
      tries are left; guessing locks the reference and says so; a draft cannot be
      opened.

      *The verdicts* — an authentic document shows its reference and fingerprint;
      a revoked one verifies and refuses, printing the reason; an expired one
      reads as out of date rather than missing; the page is served as a PNG, not
      a PDF.

      *Disclosure* — confirm-only names the person checked and nobody else; full
      lists everyone; and the **downloaded file matches what the screen showed**,
      asserted by re-opening the PDF and checking that one passport number is in
      its text and the other is not. That test is the one that would catch a
      redaction that only applied to the images.

      *The gate* — a made-up token gets the ``expired`` refusal rather than a
      404; page images and downloads are behind the same gate; a browser's
      unsolicited ``/favicon.ico`` cannot leave an ``expired`` error waiting on
      the agent's next form (which is why results live under ``/r/``); the
      download can be switched off, and switching it off closes the **route**,
      not just the button.

      *Reporting a mismatch* — it reaches the desk as both an attempt row and an
      activity.

      *Language* — French when asked, via a query parameter since there is no
      ``http_routing``; the choice sticks for the rest of the visit; a French
      verdict is French all through; a French refusal uses the translated
      message; an unknown language falls back instead of breaking; the designed
      typefaces are requested with ``display=swap`` and a local stack behind
      them; the switcher is offered, and offers **only** the languages the portal
      is actually written in.

      *Whose portal it is* — the configured company is presented; an unset or
      deleted ``company_id`` parameter falls back instead of breaking.

   ``TestPortalHost``
      The other half of the host story, and the lock that is left when a proxy
      is misconfigured. On the plain host: the portal is not served and the whole
      ``/_check`` namespace 404s. On the check host: ``/_check`` itself is not
      addressable, the back office does not exist (``/web/login``, ``/odoo``,
      ``/web``, both database manager paths), and ``/web/assets/`` **is** served
      — the single passthrough, and the one whose failure is silent, because the
      page would still return 200 while rendering unstyled and without its input
      mask.

``tests/test_chatter_tour.py``
   See `The browser tours`_.

The browser tours
-----------------

Three tours in ``static/tests/tours/certificate_chatter_tour.js``, driven by
``TestCertificateChatterTour``. They need a headless Chrome on ``PATH``; the
image installs one. Without it Odoo raises ``SkipTest``, so a missing browser
reports as *skipped*, not failed — worth knowing, because a suite that silently
skips three tests looks exactly like a suite that passed.

``dms_certify_portal_chatter_tour``
   The issuer cannot post into a certificate thread. ``TestChatterTemplate``
   proves the xpaths locate what they claim to in the ``mail.Chatter`` source;
   it cannot prove the browser applies them, nor that the form picks
   ``CertificateChatter`` up at all. Both are client-side, and a primary-inherit
   template whose parent moved fails there, silently, with the chatter simply
   missing.

   .. admonition:: The race this tour exists to pin
      :class: important

      On a database that also has ``outlook_chatter_theme``, that module swaps
      the chatter on *every* form and its assets load **after** this addon's.
      That is why ``form_renderer_patch.js`` re-asserts the choice in
      ``onWillRender`` rather than in ``setup()``.

      The theme is not a dependency and so is absent from the test database, but
      the race can be run on demand, and was, both ways:

      .. code-block:: bash

         make test m=dms_certify_portal,outlook_chatter_theme \
             t=/dms_certify_portal:TestCertificateChatterTour

      It passes as written and fails — *"A Send message button … is on the
      certificate chatter"* — the moment the override moves back into
      ``setup()``. Nothing in the default test run covers this; the code comment
      and this paragraph are the only record of it.

``dms_certify_portal_preview_aside_tour`` / ``_below_tour``
   Where the stamped page sits. The preview panel is a sibling of the sheet's
   background rather than a column inside it, so at XXL the form view's own flex
   row puts it to the right and neither side is capped by the sheet's max width;
   below XXL the form is a column and the panel follows underneath.

   Both are geometry, and geometry is the thing a Python test cannot see: the
   arch and the stylesheet each look right on their own, and only the rendered
   box says which side of the sheet the panel ended up on. The two tests set
   ``self.browser_size`` before ``start_tour`` — ``1920x1080`` and ``1366x768``
   — because ``FormController`` adds ``o_xxl_form_view``, and with it the flex
   row, only at ``SIZES.XXL``.

Known gaps
----------

Ranked by what would hurt most if it broke silently in production, not by how
much work it would be to close. This is an audit, not a highlight reel.

**High — the two rate limits are half tested**

``dms.certificate.attempt.is_throttled`` — the **per-address** limit — is never
called by any test. Only the per-reference lock is exercised
(``test_guessing_at_one_reference_locks_it``,
``test_guessing_locks_the_reference_and_says_so``). So ``max_failures`` and
``window_minutes`` have no coverage at all, and neither does the first branch of
``verify_submit``, which is the one that renders ``verify_throttled`` with
``locked_reference=False``.

This is the gap with the worst failure mode on the list. If the address limit
stopped counting, nothing would fail, nothing would log, and the per-reference
lock would be the only thing standing between a scripted caller and the whole
registry — one document at a time, five tries each, with no global budget.

**High — the captcha branch is never exercised**

No test installs or fakes ``google_recaptcha``. ``_captcha_ok`` therefore always
takes its "the module is absent, return ``True``" path, and nothing covers the
two call shapes it tries, the ``TypeError`` fallback between them, or the
"anything else is a failure" branch. A signature change in a future Odoo would
show up in production as *every lookup fails the captcha* — which fails closed,
but would be diagnosed from scratch. See :doc:`../limits`.

**High — ``migrations/`` has no coverage at all**

Three post-migrate steps, exercised only by running them. The 4.0.0 one maps a
retired ``document_type`` Selection column onto ``dms.certificate.type`` records
and logs orphaned codes; the 5.0.0 one deletes the generic shipped types where
unused. Both make decisions about live data on somebody else's database, from a
script nothing has ever run twice in a test.

**Medium — ``tools/seal.py`` is only tested through the model**

Never directly. The geometry decisions are asserted as *"the reference is on the
sealed page"* and *"the redaction fill is black"*, not as layout — so the three
``band`` modes (``auto``, ``scale``, ``overlay``), the corner-collision probe in
``_corner_is_free``, the 8% shrink, the microtext and the guilloche channel are
covered only in the sense that sealing did not crash. A band mode that stamped
over the crew table would pass the suite.

**Medium — ``_client_ip`` behind a proxy**

Tests run without ``proxy_mode``, by design, so the per-address limit is only
ever fed the request's real ``remote_addr``. The production configuration — where
Werkzeug has to resolve the address out of ``X-Forwarded-For`` — is never
exercised, and getting it wrong turns the per-address limit into one global
limit with no visible symptom. The deployment checklist carries the warning
(:ref:`deployment-nginx`) because the suite cannot.

**Medium — the attempt log is never pruned in a test**

``_gc_attempts`` has no coverage, and it is the cron target. Nothing asserts that
it honours ``retention_days``, that it leaves newer rows alone, or that it does
not touch the ``verify_count`` the log is supposed to outlive.

**Medium — the public base URL is only tested when it is set**

``test_the_verify_url_uses_the_public_base_url`` sets the parameter explicitly.
The **derivation** — ``erp.example`` → ``check.erp.example``, with the
``check.`` prefix not doubled when it is already there — is never asserted,
although it is what every deployment that forgets to set the parameter actually
uses, and what gets printed on paper.

**Low — ``_resolve_fact_label`` is tested only in its simple form**

``test_facts_travel_as_given`` passes a plain string label. The ``{lang:
string}`` mapping, and its fallback chain (context language, bare code, ``en``,
then any value at all), are the whole reason the method exists and have no
coverage.

**Low — ``static/src/js/verify.js`` is not exercised**

``test_the_portal_assets_are_served_on_the_check_host`` proves the bundle is
reachable and ``TestAssets`` proves the SCSS compiles. Nothing proves the
JavaScript works: the live reference mask built from server-supplied group sizes,
the captcha wiring and the print button have no tour. A broken mask leaves a
form that still submits, so the page would look fine and type badly.

**Low — a test docstring overstates where one string comes from**

``test_a_french_refusal_uses_the_translated_message`` describes the generic
refusal as coming *"from Python, not the template"* and claims to prove that the
``odoo-python`` entries in ``fr.po`` are loaded. The string is in fact a
``model_terms:ir.ui.view`` entry on ``verify_form``, and ``fr.po`` contains **no**
``code:addons/dms_certify_portal`` entries at all — which is consistent with the
rest of the design (:doc:`contributing`) but means the test proves something
narrower than it says. The assertion itself is correct and worth keeping.

.. todo::

   Is the per-address throttle gap deliberate — i.e. is ``is_throttled`` meant
   to be considered covered by the per-reference lock tests — or simply
   unwritten? It is four lines of ``Attempt.log`` from the same address plus one
   assertion, so if it is unwritten it should be the next test added.

See also
--------

* :doc:`contributing` — the five invariants, several of which have a named
  regression test
* :doc:`extending` — testing a module built on top of this one
* :doc:`architecture` — what the two flows are, which is what the suite is
  shaped around
* :doc:`../limits` — the gaps above, from the operator's side rather than the
  developer's
* :doc:`../reference/index` — the symbols each test module is about
