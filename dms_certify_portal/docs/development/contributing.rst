Contributing
============

Conventions this codebase enforces, and the five invariants it will not survive
you breaking casually. Read :doc:`architecture` first for *why* things are shaped
the way they are; this page is what to do about it.

If what you want is a separate module that builds on this one, do not edit these
files at all — see :doc:`extending`, which covers the same ground from the
outside.

.. contents::
   :local:
   :depth: 2

Layout
------

.. code-block:: text

   models/dms_certificate.py          the registry: issue, certify, seal, match,
                                      redact, and the public whitelist
   models/dms_certificate_holder.py   one person, three keyed hashes, the boxes
   models/dms_certificate_attempt.py  the throttle counter and the audit trail,
                                      in one table
   models/dms_certificate_type.py     what a document is, as records
   models/res_config_settings.py      throttling / portal / defaults / house style
   models/ir_http.py                  29 lines: the check-host rewrite
   controllers/main.py                seven public routes, all sudo
   tools/seal.py                      bytes in, bytes out, no ORM
   hooks.py                           the pepper, and the portal's languages
   templates/verify_templates.xml     the public page, and every refusal's wording
   views/                             the issuing screen, the attempt log, settings
   wizards/                           revocation, which only exists to insist on
                                      a reason
   static/src/js/verify.js            framework-free, public side
   static/src/js/certificate_*.js     the read-only chatter, backend side
   static/src/scss/                   certificate_form (preview geometry),
                                      verify (the whole public stylesheet)
   static/tests/tours/                three browser tours
   security/                          two groups, the matrix, one record rule
   data/                              22 parameters at noupdate="1", one cron
   migrations/                        three post-migrate steps
   i18n/                              the French catalogue
   tests/                             four modules, one deliberately failing

One file is deliberately **free of any Odoo import**, and must stay that way:

``tools/seal.py``
   Bytes and a ``SealSpec`` in, bytes out. The caller owns storage. This is what
   makes the stamping testable on a PDF built in the test file, reusable from
   anywhere, and — most importantly — unable to leak a field it was never
   handed. The riskiest code in the addon is the code that decides what comes
   off a page before a stranger sees it, and it has no ``env``.

.. _contributing-invariants:

The five invariants
-------------------

These are not style preferences. Each of them is holding up a specific attack,
and each is a plausible-looking three-line change away from being gone.

No public ACL
^^^^^^^^^^^^^

.. admonition:: The controller is the only door
   :class: important

   No ``ir.model.access`` row and no ``ir.rule`` grants ``base.group_public`` or
   ``base.group_portal`` **anything** on ``dms.certificate`` or its satellites.
   The comment saying so is at the top of ``security/ir_rule.xml``, above the one
   rule the file does contain.

   **If you break it:** an ACL does not only open what you were trying to open.
   It opens ``/web/dataset/call_kw`` — the ORM RPC endpoint — to an anonymous
   caller, who can then read the model directly, with no session token, no
   expiry, no second check and **neither rate limit**. The per-address limit and
   the per-reference lock both live in the controller; an RPC caller never
   reaches them.

   The symptom that tempts you is always the same: something on the public path
   raises ``AccessError``. The fix is a ``sudo()`` in the controller or the
   model, never a line in the matrix.

``_get_public_values`` returns plain data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Strings, booleans, dates, integers, and lists of dicts of those. The public
templates receive that dict and nothing else — not a record, not a recordset, not
an id a template is expected to browse.

**If you break it:** QWeb is not a sandbox, and
``doc.issuer_id.partner_id.email`` is one dot longer than ``doc.reference``.
Hand a template a record and the whole relation graph is reachable from a page an
anonymous caller is looking at, including ``message_ids`` — the thread, with
whatever an operator typed into it. Nothing in the framework distinguishes the
safe dot from the unsafe one.

Build it as a **whitelist**, key by key. Never as "copy the record's fields and
drop the sensitive ones": a field added next year has to be invisible to the
portal until somebody deliberately adds a line.

Three regression tests sit on this —
``test_public_values_are_plain_data``,
``test_public_values_redact_the_crew_in_confirm_mode``,
``test_public_values_list_the_crew_in_full_mode``. The first one is the
structural one; keep it passing.

``_public_bytes`` fails closed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After redacting, the method tokenises the result and asks every *other* holder
what of theirs survived — names and first names by exact match, passport numbers
through the keyed hash, which is the only way to look for a number nobody kept.
If anything survived it logs at ``ERROR`` and returns ``b''``.

Every caller treats ``b''`` as "show nothing": the result page renders with no
document images, the download 404s.

**If you break it** — by returning the un-rechecked bytes, by making the leak
check a warning, by catching the ``ERROR`` branch "so the agent sees something" —
the failure mode becomes a page carrying somebody else's passport number. An
empty page is a nuisance. That is the trade, and it is not a close call.

The corollary is that the ``b''`` path must stay *silent to the user and loud in
the log*. If you touch this, make sure the ERROR line still names what survived
(``_survives`` reports a leaked passport as the literal ``'<passport>'``, so the
number itself never reaches a log line — keep that).

One refusal for every failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``no_match`` covers both "no such reference" and "that reference exists but the
second check is wrong". ``verify_form_prefilled`` looks nothing up at all, so the
QR landing page is equally silent. The wording lives in **one** place,
``verify_form``, keyed off ``error_code``.

**If you break it:** a form that distinguishes the two lets anyone walk the
reference space with an arbitrary passport value and keep the hits. That is an
enumeration oracle, handed out for free in the name of a helpful error message —
and once the references are known, the second check is four characters.

The exception, which is deliberate and should stay: the refusal *does* say how
many tries are left on that reference. An agent who mistyped needs it, and
somebody guessing can count their own failures anyway.

There are two tests whose whole job is this. Both diff the full rendered page
with the CSRF token and the reference blanked out
(``test_an_unknown_reference_looks_exactly_like_a_wrong_passport``,
``test_the_qr_route_says_nothing_about_whether_it_exists``). If you add a field
to the form page that varies with whether a reference exists, they will fail —
and they are right to.

Constant-time matching
^^^^^^^^^^^^^^^^^^^^^^

Two separate things make a miss cost the same as a hit:

* ``hmac.compare_digest`` for every comparison, so a nearly-right hash does not
  take measurably longer to reject than a wholly wrong one. That applies to the
  holder hashes in ``_match`` **and** to the session token in
  ``_session_document``.
* a **throwaway HMAC** when no certificate is found at all:

  .. code-block:: python

     if not certificate:
         Holder._submitted_factor_hash('pptfull', secrets.token_hex(16))
         return empty

**If you break it** — by returning early from ``_match``, by using ``==`` on a
digest, by adding a cheap pre-check before the hash — the identical wording of
the refusals stops mattering. An unknown reference would return after one indexed
SELECT while a known one paid for an HMAC, and the difference is readable over
the network. Timing is the side channel that is left once the copy is the same.

The ``'pptfull'`` in that snippet is arbitrary: the cost is one HMAC whichever
mode is named. Do not "tidy" it into something that looks more meaningful and
costs less.

Conventions
-----------

Wording goes in the template, not in Python
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``_fail()`` takes a *code*, not a sentence, and the sentence lives in
``verify_form``. That is not only about having one place for the copy.

Odoo's translation exporter does not walk Python source in this layout:
``i18n/fr.po`` contains **no** ``code:addons/dms_certify_portal`` entries at all.
A string built with ``_()`` in ``controllers/main.py`` would therefore be
invisible to the export and would sit in English on a French page for ever — and
nothing would tell you, because the page still renders.

So: user-facing copy on the public path goes in a template. ``UserError`` and
``ValidationError`` text in the models is a different case — that is read by an
operator in the back office, where Odoo's own extraction of model source does
apply.

Parameter values are strings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``ir.config_parameter`` stores text, and ``bool("False")`` is ``True``. Hence
``_default_param("notify_on_lookup", "1") == "1"`` rather than a cast, and hence
the controller's ``_bool_param`` accepting ``'True'``, ``'true'`` and ``'1'`` —
an administrator reaches for whichever spelling they know.

Every integer read goes through ``_param``, which falls back to the shipped
default on anything unparseable. A parameter somebody deleted, or filled with a
word, must behave as though it were untouched rather than 500 a public page.

Defaults are lambdas, on purpose
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``default=lambda self: self._default_param("second_factor", "ppt4")``, not a
literal. A literal is captured at import time; a lambda asks the database at
create time, which is the only way an administrator's choice in
:menuselection:`Settings --> General Settings` can reach a new record.

Never emit ``/_check``
^^^^^^^^^^^^^^^^^^^^^^

The declared routes are an internal namespace. ``FORM_URL`` (``/``) and
``RESULT_URL`` (``/r/%s``) are what the controller actually redirects to, and
``verify_url`` on the model builds ``{base}/d/{reference}``. A ``/_check`` that
escapes into a page, a QR code or a printed line is a URL that works nowhere —
the rewrite only adds the prefix, it never strips it, so ``/_check`` typed on the
check host becomes ``/_check/_check`` and 404s. There is a test for that
(``test_the_internal_namespace_is_not_addressable_on_the_check_host``).

Nothing is dropped from the attempt log
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Every branch of ``verify_submit`` writes a row, including the ones that never
reach the registry. The log is the **throttle counter** as well as the audit
trail, so a branch that returns without logging does not merely lose a record —
it hands a free attempt to whoever triggered it. An empty submission is logged as
``no_match`` and refused as ``incomplete``, precisely so the counter is not
fooled by it.

Pruning is the cron's job (``_gc_attempts``), and only the cron's.

The pepper never degrades
^^^^^^^^^^^^^^^^^^^^^^^^^

``_keyed_hash`` raises ``UserError`` when ``dms_certify_portal.passport_key`` is
missing. It does **not** fall back to an unkeyed digest, which would quietly
write hashes nothing can later verify, under a scheme nothing records.

If you touch the hashing, keep that shape: a missing key is a loud failure, not a
different algorithm.

Shipped parameters are ``noupdate="1"``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All twenty-two of them. An upgrade must never restore a rate limit somebody
widened or a watermark colour somebody chose. Add new ones the same way, and
remember that a parameter's *absence* can be meaningful — ``public_base_url``,
``company_id`` and ``default_lang`` are deliberately not shipped, because "unset"
means "derive it".

Running it
----------

.. code-block:: bash

   odoo-bin -c odoo.conf -d <database> -u dms_certify_portal --stop-after-init

   # tests
   odoo-bin -c odoo.conf -d <database> -u dms_certify_portal \
       --test-enable --test-tags /dms_certify_portal --stop-after-init

Use a scratch database. Pass the production database name explicitly and
deliberately, never by default.

``dms_certify_host`` has to be in ``server_wide_modules`` or the portal has no
address, and ``--proxy-mode`` has to be on behind a real proxy or the
per-address limit becomes one global limit. Neither fails loudly. See
:doc:`testing` for narrowing to one class or one test, and
:ref:`deployment-check-host` for the host itself.

Building these docs
-------------------

.. code-block:: bash

   # an existing venv that already has Sphinx
   ~/venvs/odoo3.12/bin/sphinx-build -b html -W docs docs/_build/html

   # or a clean one, with no Odoo anywhere
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r docs/requirements.txt
   sphinx-build -b html -W docs docs/_build/html

``-W`` turns warnings into errors. That is not pedantry: the failure mode it
catches is a **broken cross-reference**, and a broken cross-reference in a
reference manual is worse than a missing page, because it looks like a link. A
renamed page, a typo in a ``:doc:``, a duplicate label, a heading underline one
character short — all of them are warnings that scroll past in a successful build
and all of them ship a document that lies about itself. The tree builds clean
under ``-W``; keep it that way.

The ``.. todo::`` directives are the exception to "build clean". They are not
warnings, and ``todo_include_todos = True`` is set so they render loudly into the
page instead of hiding in the source. A hole is supposed to be visible.

.. note::

   ``conf.py`` mocks ``odoo`` **unconditionally**, even when a real Odoo is
   installed, because Odoo 19's ``MetaModel`` asserts that every
   ``models.Model`` subclass is imported under ``odoo.addons.*`` — and here the
   package is the plain ``dms_certify_portal``. Mocking it also keeps the docs
   buildable from ``docs/requirements.txt`` with no Odoo and no database, which
   is the more valuable property.

   The consequence is that Odoo models cannot be introspected, so almost every
   reference page is hand-written. ``linkcode_resolve`` still gives them
   ``[source]`` links, and ``:ghsrc:`` covers everything that is not a Python
   object. ``pymupdf``/``fitz`` and ``qrcode`` are mocked only when genuinely
   absent.

Adding things
-------------

A field on ``dms.certificate``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Decide whether the public page needs it. If it does, it needs a line in
   ``_get_public_values`` — and that line has to be plain data. If it does not,
   it is invisible to the portal and that is the default you want.
#. Give it a ``help=`` that says *why*, not what. The label already says what.
#. If it holds anything personal, it needs
   ``groups="dms_certify_portal.group_certify_manager"`` like the passport
   columns, and a line in :doc:`../limits` if it ends up in a database dump.
#. Add it to the view, and to the matching page under ``docs/reference/``.

A public route
^^^^^^^^^^^^^^

Declare it under ``/_check``, ``auth="public"``, with explicit ``methods=``.
Then, before anything else:

* put it behind ``_session_document(token)`` if it serves anything about a
  document — that gate is what keeps the file attached to the second check;
* render through ``_render()`` so it inherits ``NO_STORE``;
* set ``readonly=True`` unless it writes, and ``csrf=True`` if it is a ``POST``;
* decide what it logs. A route that can fail repeatedly needs to count against a
  limit, or it is the hole in front of the two that already work.

Do not add a route that returns a different page for a document that exists than
for one that does not.

A refusal code
^^^^^^^^^^^^^^

Add the code in the controller and the wording in ``verify_form``'s
``error_code`` block, in the same change. A code with no template branch renders
as nothing — the agent gets a form with no explanation — and the French
catalogue needs the new string too.

Then ask the question from `One refusal for every failure`_: does the new code
tell the caller something the existing ones deliberately do not?

A seal house-style parameter
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Four places, all of them: the ``data/ir_config_parameter.xml`` record at
``noupdate="1"``, a field on ``res.config.settings`` with its
``config_parameter``, a read in ``_seal_spec()``, and a clamp in ``SealSpec``'s
constructor. The clamp is the one people skip. ``SealSpec`` validates on the way
in so the drawing code never has to defend itself, and a parameter that reaches
PyMuPDF unclamped is a settings box that can produce an unreadable page.

A migration
^^^^^^^^^^^

``migrations/<version>/post-migrate.py``, and bump the manifest. Write one when
a change cannot be expressed as data: the three that exist re-run language
activation (because ``post_init_hook`` only fires on install), map a retired
Selection column onto ``dms.certificate.type`` records, and delete generic
shipped types where they are unused.

Two rules learned from those three: log what you could not convert rather than
dropping it silently, and keep the step idempotent — somebody will run the
upgrade twice. There is no test coverage for ``migrations/`` at all
(:doc:`testing`), so the script is only ever exercised by running it.

You are maintaining somebody's API
----------------------------------

``_certify_source``, ``_generate_reference`` and ``_get_public_values`` are
documented as extension points in :doc:`extending` and in
:ref:`issuing-override-points`. Another addon is calling ``super()`` into them
right now. So:

* **Adding a keyword argument is fine**; reordering or removing one is not.
* **Changing a return shape is a breaking change.** ``_certify_source``
  returning ``(filename, bytes)`` and ``_get_public_values`` returning a flat
  dict are contracts — overriders unpack the first and update the second.
* **Renaming one is a breaking change**, the leading underscore
  notwithstanding. The underscore here means "not a UI action", not "not an
  API".

The same applies to the ``dms.certificate.type`` ``code`` as a lookup key, and to
the ``dms_certify_portal.*`` parameter names, which deployments edit by hand.

If you change any of them, say so in :doc:`../limits` or the changelog and update
:ref:`extending-stability`.

Before you commit
-----------------

* Run the tests. If you touched the public path, run them and then read
  :doc:`testing`'s known-gaps list to see whether your change lands in one of
  the holes.
* Build the docs with ``-W`` if you touched them.
* Re-read `The five invariants`_ against your diff. All five are breakable by a
  change that looks like a simplification.
* Update the reference page for anything you added or renamed — a stale
  reference page is worse than a missing one.
* If you touched an extension point, update :doc:`extending` too.
* If you added a user-facing string, check it reached ``i18n/`` — and check it
  is in a template rather than in Python, or it never will.
* Add a line to the changelog.

See also
--------

* :doc:`architecture` — the two flows and the boundary between them
* :doc:`extending` — the same decisions seen from a module that depends on this
  one
* :doc:`testing` — the suite, and what it does not cover
* :doc:`../reference/index` — every symbol, with source links
* :doc:`../limits` — the edges, including the ones that are open bugs
