Administration
==============

Everything you configure once, in roughly the order you configure it. The
things that have to be right *before a document goes on paper* are in
:doc:`deployment` instead; this page is the rest.

.. contents::
   :local:
   :depth: 2

Where the settings live
-----------------------

:menuselection:`Settings --> General Settings`, in three blocks:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Block
     - What it holds
   * - :guilabel:`Document verification portal`
     - Both rate limits, the result lifetime, log retention, what the public
       page offers, and who it presents itself as
   * - :guilabel:`Certified documents: defaults`
     - What a **new** entry starts from, and which document types register
       themselves
   * - :guilabel:`Certified documents: the seal`
     - The house style of the stamp

Almost everything in them is backed by an ``ir.config_parameter``, shipped with
``noupdate="1"``. That matters: **a module upgrade will never overwrite a value
you changed.** The full list with its defaults is
:doc:`../reference/data/ir_config_parameter`.

The one exception is :guilabel:`Stamp on generation`, which is not a parameter
at all — see `Document types`_.

The two rate limits
-------------------

There are two, they count different things, and confusing them is the commonest
source of *"why is the portal refusing everybody?"*

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * -
     - Per address
     - Per reference
   * - Settings
     - :guilabel:`Failed attempts allowed per address` (10),
       :guilabel:`Rate limit window (minutes)` (15)
     - :guilabel:`Failed attempts allowed per reference` (5),
       :guilabel:`Reference lockout (minutes)` (30)
   * - Counts
     - Failures from one IP address, across every document
     - Failures against one reference, **from every address**
   * - Protects
     - The registry, from one client hammering it
     - **A document.** This is the one that matters
   * - What it counts
     - ``no_match`` and ``captcha`` rows only — being throttled does not
       deepen the hole
     - ``no_match`` and ``locked`` rows, but the clock runs from the failure
       that *tripped* the lock, so hammering does not push the release back
   * - The agent sees
     - *Checks from here are paused*
     - *Reference locked*, and that the desk has been told
   * - Reaches the desk
     - No
     - **Yes** — a note on the certificate and a warning activity on the
       issuer, even with per-document notifications off

.. admonition:: Why the per-reference limit is counted across addresses
   :class: important

   Because under the default second factor there are only a few thousand
   possibilities (:ref:`concepts-second-factor`), and no amount of hashing
   changes that. Repeated failures against *one* reference mean somebody is
   working on one specific document — and such a person will change address.
   An agent who mistyped will not.

   A per-address-only limit would be theatre against exactly the attack the
   second factor is weakest to.

Both are application-level. Put a second limit in front of Odoo as well, so a
flood never reaches Python and the limit survives a bug in this code —
:ref:`deployment-nginx`.

.. warning::

   **The per-address limit depends on** ``--proxy-mode``. Without it every
   request appears to come from your reverse proxy and the limit becomes one
   *global* limit: ten failures from anyone in the world pauses the form for
   everybody. Nothing fails loudly. See :doc:`deployment`.

.. note::

   The address-throttle page says checks resume *"in about N minutes"* where N
   is the whole window, not the time actually remaining — so it overstates the
   wait for somebody who failed early in the window. The reference-lock page
   does report real minutes left.

What the public page offers
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Setting
     - Notes
   * - :guilabel:`Result lifetime (minutes)` (15)
     - How long a result stays readable after a successful lookup. **Keep it
       short** — embassy workstations are shared, and the result page names a
       person and shows their document. The page tells the agent it closes on
       its own.
   * - :guilabel:`Allow downloading the sealed document` (on)
     - Turning it off closes the route, not just the button. Under ``confirm``
       disclosure the download is the redacted copy, not the document as
       issued.
   * - :guilabel:`Portal company`
     - Whose name, address, email and phone the page carries. Empty means
       whatever company a public request happens to resolve to, which is
       nobody's decision. Only seven strings ever reach the template — the
       company *record* stays out of it deliberately.
   * - :guilabel:`Public verification URL`
     - **Goes on paper.** See :doc:`deployment`.
   * - :guilabel:`Hide expired documents`
     - **Does nothing.** See below.

.. warning::

   :guilabel:`Hide expired documents` exists as a parameter, as a Settings box
   and in both translation files, and **nothing in the codebase reads it**. An
   expired document always reads as *authentic but out of date*, whatever the
   box says.

   That happens to be the better behaviour — telling an agent a genuine document
   has expired is more useful than telling them it does not exist — but the
   setting is a lie and ticking it changes nothing. It is tracked in
   :doc:`../limits`.

Retention
---------

:guilabel:`Keep attempt logs for (days)`, 90 by default. One daily cron,
*Verification: purge old attempt logs*, deletes ``dms.certificate.attempt`` rows
older than that. It is the only scheduled job in the module.

The log cannot be trimmed at write time, because it **is** the throttle counter
as well as the audit trail — every hit on the form goes into it, matches and
refusals alike.

.. important::

   **Ninety days is a default, not a legal opinion.** It is long enough to
   investigate an incident and short enough to defend, and that is the whole
   argument behind it. Retention of IP addresses is a data-protection decision;
   agree it with whoever signs off your processing record. See
   :doc:`security-and-privacy`.

   If the cron is disabled, or the server runs with ``max_cron_threads = 0``,
   the table grows without bound and nothing warns you.

The document's successful-lookup counter is *not* part of this. It is a plain
stored number on the certificate, precisely so that how many times a document
was checked outlives the log of who checked it.

Defaults for a new entry
------------------------

These are the values an entry starts from. Every one of them is per-document
afterwards, and the ones that describe how a document opens are tracked in its
chatter when they change.

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Setting
     - Default
     - Notes
   * - :guilabel:`Default second check`
     - last 4 characters
     - :ref:`concepts-second-factor`. There is no *off*.
   * - :guilabel:`Default disclosure`
     - match confirmation
     - :ref:`concepts-disclosure`. ``confirm`` is almost always enough, and
       choosing ``full`` by default would publish a crew list on every lookup.
   * - :guilabel:`Default validity`
     - 90 days after movement
     - Counted from the **movement date**, not the issue date: a letter written
       three weeks ahead of a port call is not three weeks closer to being
       stale. The three choices are a Selection on purpose — an open numeric
       field invites 45 and 60 to appear with nobody able to say why.
   * - :guilabel:`Reference prefix`
     - ``ICS``
     - Goes into every reference and into the browser's input mask, which
       derives its group sizes from this rather than hard-coding three
       characters. **Changing it does not change references already issued.**
   * - :guilabel:`Notify the desk on every lookup`
     - on
     - Per-document afterwards. With it off, a routine successful check goes
       quiet and only the outcomes needing somebody to act — a lockout, a
       reported mismatch — still come through.

The seal house style
--------------------

Per document the issuer picks a :guilabel:`Marking` and looks at the result.
Everything below is set once, here, and applies to every document.

.. list-table::
   :header-rows: 1
   :widths: 32 14 54

   * - Setting
     - Default
     - Notes
   * - :guilabel:`Watermark opacity (%)`
     - 9
     - Clamped to 0–100. Low enough to read the letter through, high enough to
       survive a fax.
   * - :guilabel:`Watermark size`
     - 24
     - Clamped to a minimum of 6.
   * - :guilabel:`Watermark angle`
     - -32
     - Degrees.
   * - :guilabel:`Watermark coverage`
     - tiled
     - Tiled across the page, or one diagonal band.
   * - :guilabel:`Watermark ink`
     - ``#10314F``
     - Hex. Anything unparseable falls back to the same navy rather than
       failing the seal. Also the colour of the guilloche.
   * - :guilabel:`Guilloche border`
     - on
     - Engraved line pattern inside the trim. **It moirés on a photocopy**,
       which is a check an agent can make without a computer.
   * - :guilabel:`Microtext line in the footer`
     - on
     - Repeats the reference, the first 24 characters of the fingerprint and
       the company name at 1 pt. Legible under a loupe, a grey smear once
       scanned.
   * - :guilabel:`Stamp position`
     - bottom right
     - Next to where a signature usually sits. Or bottom left.
   * - :guilabel:`Make room for the stamp`
     - only when the corner is taken
     - Sealing cannot reflow a page. See :doc:`sealing`.

What each layer is for, and the 8% that the reserved band costs an A4 page, is
:doc:`sealing`.

.. note::

   These are read when a document is sealed, and when the form's preview panel
   is drawn. They are **not** in the preview's dependency list, so a change here
   shows up the next time an entry is read rather than reactively. Re-opening
   the form is enough.

Document types
--------------

:menuselection:`Consular --> Configuration --> Document types`. Requires
*Certification: Registrar*.

The list is **empty** on a fresh install and stays that way until a producing
module declares something. That is the design: what a document *is* belongs to
whoever produces it, and the 19.0.5.0.0 migration deleted the four generic types
this addon used to ship (:doc:`../changelog`).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Field
     - Notes
   * - :guilabel:`Name`
     - Translatable. Rename it freely.
   * - :guilabel:`Code`
     - The stable key a producing module refers to. Unique across the
       database. **Not** renameable in practice — change it and the module that
       owns it stops finding its own type.
   * - :guilabel:`Stamp on generation`
     - When a producing module generates a document of this kind, register it
       for verification straight away, **as a draft**. Sealing stays a separate
       deliberate act.
   * - :guilabel:`Active`
     - Archive rather than delete. A type on issued documents **cannot** be
       deleted: those documents have to keep being able to say what they are,
       and the guard says so by naming the count.

:guilabel:`Stamp on generation` is also editable from
:menuselection:`Settings --> General Settings --> Certified documents: defaults`
as a list of types, which is where an administrator is more likely to look.

.. admonition:: Why that one Settings field is not a ``config_parameter``
   :class: important

   The flag lives on the type itself, so a producing module can ship a sensible
   default with its type and an administrator can change it without either side
   knowing about the other. The Settings page therefore writes it through
   ``get_values``/``set_values`` rather than through a parameter.

   It is also a plain ``Many2many``, not a computed one, for a subtle reason: a
   non-stored compute recomputes when the cache is invalidated — which happens
   between the client saving the record and ``set_values`` reading it back — so
   an **unticked box was recomputed straight back to ticked** before anything
   was written.

Access rights
-------------

Two groups, both under the :guilabel:`Document certification` privilege in the
:guilabel:`Certification` category.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Group
     - What it is for
   * - *Certification: Agent*
     - Look things up in the back office. **Read-only on everything.** Sees the
       :guilabel:`Consular` menu and the entries, but not
       :guilabel:`Configuration`.
   * - *Certification: Registrar*
     - Implies Agent. Creates, edits and revokes entries, manages document
       types, **and is the only group that can read passport numbers.**

.. important::

   ``passport_number`` and the three hashes beside it are restricted at the
   **field** level to *Certification: Registrar*. An agent with read access to
   the registry has no business reading passport numbers out of it, and the
   field simply is not there for them — not greyed out, absent.

   Deciding who gets Registrar is therefore a data-protection decision, not a
   convenience one. See :doc:`security-and-privacy`.

   Field groups are an ORM control. They do not apply to ``pg_dump``, to a
   replica, or to anybody with a ``psql`` prompt.

Two further details worth knowing:

* **The attempt log gives the Registrar read and unlink only** — no write, no
  create. Every row is written by the public controller under ``sudo``, and
  nobody should be hand-creating an audit entry. Unlink exists so the retention
  cron can do its job.
* **There is deliberately no public or portal ACL anywhere.** The controller is
  the only door. Adding one to make something work would also open
  ``/web/dataset/call_kw``, which bypasses both rate limits and the second
  factor entirely. :doc:`../reference/security/ir_rule` carries the full
  argument.

The administrator is granted *Certification: Registrar* at install, so there is
nothing to assign before you can use the module. The full matrix is
:doc:`../reference/security/ir_model_access`.

Multi-company
-------------

A certificate carries a ``company_id``, required, defaulting to the current one.
One record rule restricts *Certification: Agent* to entries belonging to a
company the user has selected.

The rule is scoped on the certificate's **own** company rather than on its
creator's, because every certificate is written under ``sudo`` — the passport
fields are group-restricted — and a rule reading ``create_uid`` would file the
whole registry under OdooBot.

.. note::

   The **portal's** company is a separate decision, and deliberately so: an
   embassy is looking at one organisation whichever of your companies issued the
   document in front of them. That is :guilabel:`Portal company` above, and it
   has no effect on which entries a back-office user can see.

See also
--------

* :doc:`deployment` — the things that must be right before a document is
  printed
* :doc:`security-and-privacy` — retention, who gets Registrar, and what to
  settle before going live
* :doc:`issuing` — the defaults above, as seen from a producing module
* :doc:`../reference/data/ir_config_parameter` — every parameter with its
  default
* :doc:`../reference/models/res_config_settings` — the Settings fields
  themselves
* :doc:`../reference/security/dms_certify_portal_groups` — the group records
* :doc:`../reference/data/ir_cron` — the purge job
* :doc:`../limits` — ``hide_expired``, and the attempt log growing unbounded
  without the cron
