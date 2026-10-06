dms.certificate.attempt
=======================

.. py:currentmodule:: odoo.addons.dms_certify_portal.models.dms_certificate_attempt

Source: :ghsrc:`models/dms_certificate_attempt.py`

.. py:class:: DmsCertificateAttempt

   Bases: ``odoo.models.Model`` directly — no ``_inherit``, and no chatter: a
   log row is not a conversation.

   :Odoo model: ``dms.certificate.attempt`` — ``self.env["dms.certificate.attempt"]``
   :Description: Document Verification Attempt
   :Order: ``create_date desc, id desc``
   :Rec name: ``reference_tried``
   :Constraints: none declared

   Every hit on the public form, successful or not. The row is both the audit
   trail and the throttle counter — there is no separate counter table, because
   a counter that could disagree with the log would be the one thing nobody
   could reconstruct afterwards.

   .. admonition:: Two limits, not one
      :class: important

      The module counts failures twice, against two different keys, and the
      second one is the one that matters.

      **Per address** (:py:meth:`~DmsCertificateAttempt.is_throttled`) stops one
      client hammering the whole registry. It protects the *server*.

      **Per reference** (:py:meth:`~DmsCertificateAttempt.reference_lock_left`)
      protects the *document*, and it is counted across **every address**. With
      the second check set to the last four characters of a passport there are
      only a few thousand possibilities, so a handful of tries against one
      reference has to be enough to shut it — and letting the caller continue
      from a second address would make the limit theatre. Somebody guessing at
      one specific document changes address; an agent who mistyped does not.
      That asymmetry is the entire justification.

      Neither limit is a substitute for one in front of Odoo. The docstring on
      :py:meth:`~DmsCertificateAttempt.is_throttled` says so: put ``limit_req``
      or Cloudflare ahead of it so a flood never reaches Python, and so the
      limit survives a bug in this method. See :ref:`deployment-nginx`.

   **No form of the submitted secret is stored, not even a hash.** A
   per-attempt hash would let anyone with table access correlate attempts
   across documents — the same wrong passport tried against six references is
   information the log has no business holding.

.. contents::
   :local:
   :depth: 2

Fields
------

What was tried
^^^^^^^^^^^^^^

.. _dms_certificate_attempt-reference_tried:

.. py:attribute:: DmsCertificateAttempt.reference_tried
   :type: fields.Char

   ``string="Reference tried", index=True, readonly=True``

   The **normalised** reference, not what the agent typed: the controller runs
   :py:meth:`DmsCertificate._normalize_reference
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._normalize_reference>`
   before anything else, and both
   :py:meth:`~DmsCertificateAttempt.log` and the per-reference counters see the
   stripped, upper-cased form. That is what makes the lock countable at all —
   five tries at ``ics2026dkk4kq79b`` and ``ICS-2026-DKK-4KQ7-9B`` are five
   tries at one document.

   Truncated to 64 characters on write, because the value arrives from a public
   form and nothing upstream bounds it.

   ``index=True`` is load-bearing rather than tidy: every POST to the public
   form counts rows on this column before anything is matched, and a refused
   one counts them again to say how many tries are left.

.. py:attribute:: DmsCertificateAttempt.ip_address
   :type: fields.Char

   ``string="IP address", index=True, readonly=True``

   Truncated to 45 characters — an IPv6 address with a zone index, which is the
   longest thing ``remote_addr`` can produce.

   .. warning::

      This column is only meaningful if Odoo runs with ``--proxy-mode`` and the
      proxy sets ``X-Forwarded-For``. Without it every request reads as coming
      from the proxy, the per-address limit becomes **one global limit**, and
      the first ten failures of the day throttle every embassy at once. See
      :ref:`deployment-nginx`.

.. py:attribute:: DmsCertificateAttempt.user_agent
   :type: fields.Char

   ``readonly=True``, truncated to 256 characters. Hidden by default on the
   list (``optional="hide"``).

.. py:attribute:: DmsCertificateAttempt.document_id
   :type: fields.Many2one

   → ``dms.certificate``, ``string="Matched document", readonly=True,
   ondelete="set null", index=True``

   Set only on a **matched** lookup, which is the half worth noting: a failure
   names no document by definition, so the overwhelming majority of rows have
   this empty and the per-reference counters work off
   :py:attr:`~DmsCertificateAttempt.reference_tried` instead.

   ``ondelete="set null"`` rather than ``cascade``: a certificate that is
   somehow deleted should not take the record of who looked for it with it.

Outcome
^^^^^^^

.. py:attribute:: DmsCertificateAttempt.success
   :type: fields.Boolean

   ``string="Matched", index=True, readonly=True``

   Written as ``outcome == 'matched'`` by :py:meth:`~DmsCertificateAttempt.log`,
   so it is derived data rather than an independent fact — but stored and
   indexed, because every one of the three counting queries filters on
   ``success = False`` and a compute could not be searched. It is
   ``column_invisible`` on the list for the same reason it exists: the badge
   already says it.

.. _dms_certificate_attempt-outcome:

.. py:attribute:: DmsCertificateAttempt.outcome
   :type: fields.Selection

   ``string="Outcome", readonly=True, index=True``

   .. list-table::
      :header-rows: 1
      :widths: 16 26 58

      * - Value
        - Label
        - Written when
      * - ``matched``
        - Matched
        - The reference and the second check both resolved.
      * - ``no_match``
        - No match
        - Anything negative: unknown reference, wrong second check, or a
          submission missing one of the two. **One value for all three**,
          matching the single error message the form gives back
          (:ref:`verification-refusals`).
      * - ``throttled``
        - Blocked by rate limit
        - The per-address budget was already spent.
      * - ``locked``
        - Blocked, reference locked
        - The per-reference lock was already in force.
      * - ``captcha``
        - Failed the captcha
        - ``google_recaptcha`` is installed and rejected the token.
      * - ``mismatch``
        - Reported as not matching the paper
        - The agent pressed the button on the result page saying the paper in
          front of them differs from what verified.

   Which values each counter looks at is the part to read carefully, because
   the two limits do not count the same things:

   .. list-table::
      :header-rows: 1
      :widths: 34 32 34

      * - Counter
        - Counts outcomes
        - Deliberately excludes
      * - :py:meth:`~DmsCertificateAttempt.is_throttled` (per address)
        - ``no_match``, ``captcha``
        - ``throttled``, ``locked`` — a caller already being refused must not
          extend their own penalty, or the window never closes
      * - :py:meth:`~DmsCertificateAttempt.reference_lock_left` (per reference)
        - ``no_match``, ``locked``
        - ``captcha`` — failing a captcha is not evidence about *this document*
      * - both
        - —
        - ``matched``, through the ``success = False`` term they share: a
          successful lookup never counts against anything
          (``test_a_successful_lookup_does_not_count_against_the_reference``).
          ``mismatch`` is excluded too, by being absent from both outcome
          lists — a report that the paper differs is a *successful* lookup
          followed by bad news, not a failed one.

   ``index=True`` because every counting query filters on it.

Who asked
^^^^^^^^^

.. _dms_certificate_attempt-requester_label:

.. py:attribute:: DmsCertificateAttempt.requester_label
   :type: fields.Char

   ``string="Requester", compute="_compute_requester_label"``

   .. admonition:: It always reads "An external user", and the row underneath keeps the address
      :class: important

      This field is a constant. ``_compute_requester_label()`` assigns
      ``_("An external user")`` to every record and reads nothing at all — not
      :py:attr:`~DmsCertificateAttempt.ip_address`, not the user agent.

      The asymmetry is the decision, and it is deliberate in both directions.
      The address is **kept**, because the rate limit cannot work without it
      and an incident cannot be investigated without it. The address is **not
      what the desk is shown**, because an IP tells an operations manager
      nothing they can act on, and resolving it to *"Consulate of France,
      Yangon"* would mean either a third-party lookup service or a
      hand-maintained list of embassy ranges. Neither is worth it yet.

      This is the field every automatic message about a lookup uses, which is
      why :py:meth:`DmsCertificate._notify_verification
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._notify_verification>`
      never names an address in a thread an operator can forward by email.
      Tests: ``test_a_lookup_is_reported_as_an_external_user``,
      ``test_the_requester_is_never_named_or_addressed``.

   Not stored, and with **no** ``@api.depends``: there are no inputs. It is
   translated at read time, which is the one reason it is a compute rather than
   a literal in the view — the label follows the reader's language.

Computes
--------

.. py:method:: DmsCertificateAttempt._compute_requester_label()

   Documented with its field above.

Parameters
----------

.. py:method:: DmsCertificateAttempt._param(name, default)
   :classmethod:

   ``@api.model``. ``dms_certify_portal.<name>`` from ``ir.config_parameter``
   under ``sudo``, coerced to ``int``.

   Falls back to ``int(default)`` on a value that will not parse, rather than
   raising. Every caller here is on the public request path, and a
   hand-mangled parameter must degrade to the shipped limit rather than 500 a
   page — the alternative is that one bad character in Settings takes the
   portal down. The shipped values are on
   :doc:`../data/ir_config_parameter`; the UI for them is
   :doc:`res_config_settings`.

   Separate from :py:meth:`DmsCertificate._default_param
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._default_param>`
   because that one returns the string and this one is only ever asked for
   counts and minutes.

Writing the log
---------------

.. _dms_certificate_attempt-log:

.. py:method:: DmsCertificateAttempt.log(reference=None, ip_address=None, user_agent=None, outcome='no_match', document=None)
   :classmethod:

   ``@api.model``. Write one row. **Always called with ``sudo`` from the
   controller**, and the method re-asserts ``self.sudo()`` on the create
   itself.

   :returns: the created attempt.

   The double ``sudo`` is not redundancy for its own sake: the public user has
   deliberately no ACL on anything in this module (:doc:`../security/ir_rule`),
   so an unprivileged create is not merely restricted, it is impossible. Making
   the method raise its own privilege means a caller cannot forget, and it is
   why the access matrix grants the Registrar **read and unlink only** on this
   model — every row is written here, and nobody should be hand-creating one
   (:doc:`../security/ir_model_access`).

   ``outcome='no_match'`` as the default is the safe direction: a caller that
   forgets to say what happened records a failure, which counts against the
   limits, rather than a success, which would not.

   Every string is truncated on the way in — see the fields above.

Counting
--------

.. _dms_certificate_attempt-is_throttled:

.. py:method:: DmsCertificateAttempt.is_throttled(ip_address)
   :classmethod:

   ``@api.model``. ``True`` when *ip_address* has burned through its failure
   budget: ``max_failures`` (default 10) failures within ``window_minutes``
   (default 15).

   A falsy address returns ``False`` — fail **open**, deliberately. With no
   address there is nothing to count, and refusing every request because the
   proxy headers are misconfigured would take the portal down for a
   configuration mistake. The per-reference lock below does not depend on the
   address and is unaffected, so the document is still protected.

   Logs at ``WARNING`` when it trips, naming the address, the count and the
   window, so a flood is visible in the Odoo log and not only in the attempt
   list.

   A **sliding window**, not a bucket that resets on the hour: the query counts
   rows newer than ``now - window``, so the budget refills gradually as old
   failures age out.

.. _dms_certificate_attempt-reference_lock_left:

.. py:method:: DmsCertificateAttempt.reference_lock_left(reference_key)
   :classmethod:

   ``@api.model``. Minutes this reference stays locked, or ``0`` when it is
   open. ``max_reference_failures`` (default 5) failures in
   ``reference_lock_minutes`` (default 30) lock it.

   :param str reference_key: a **normalised** reference. Pass anything else and
      it counts nothing.
   :returns: ``int`` minutes, rounded up, never negative.

   .. admonition:: The clock runs from the failure that tripped the lock
      :class: important

      The method does not return the window; it loads the matching failures
      ``order='create_date asc'``, takes the *n*-th one — the one that tripped
      the lock — and measures the window from there.

      Measuring from the most recent failure instead would mean a caller who
      keeps trying keeps pushing their own release back, which sounds like a
      feature and is not. It turns a mistyping agent's five-minute wait into an
      unbounded one, it gives an attacker who has already lost nothing further
      to lose, and it makes the number the refusal page prints wrong the moment
      it is shown.

   Note that the minutes are deliberately *reported*, not hidden: the figure is
   printed on the refusal page so the agent knows whether to wait or to phone.

.. py:method:: DmsCertificateAttempt.is_reference_locked(reference_key)
   :classmethod:

   ``@api.model``. ``bool(reference_lock_left(...))``.

   The controller does not use it — it needs the minutes, so it calls
   :py:meth:`~DmsCertificateAttempt.reference_lock_left` directly and treats a
   non-zero result as the lock. This predicate exists for the tests
   (``test_guessing_at_one_reference_locks_it``,
   ``test_a_successful_lookup_does_not_count_against_the_reference``) and for
   an external caller that only wants the yes/no. Keeping it a one-line
   delegate means there is one definition of *locked*.

.. _dms_certificate_attempt-reference_attempts_left:

.. py:method:: DmsCertificateAttempt.reference_attempts_left(reference_key)
   :classmethod:

   ``@api.model``. How many tries remain on this reference before it locks.

   An empty *reference_key* returns the full budget rather than ``0``, so the
   first view of the form offers the whole allowance.

   .. admonition:: Telling the caller how many tries are left is a deliberate disclosure
      :class: important

      It looks like a leak and is not. An attacker can count their own failures
      anyway — they know exactly how many requests they have sent — so the
      number tells them nothing they did not have. The agent at the counter who
      mistyped one character does not know, and three goes left is the
      difference between retyping carefully and phoning the issuing desk.

      It is shown only on a refusal, and only when a reference was actually
      submitted; see ``_form_values`` in :doc:`../controllers/verify`.

Retention
---------

.. _dms_certificate_attempt-gc_attempts:

.. py:method:: DmsCertificateAttempt._gc_attempts()
   :classmethod:

   ``@api.model``. The cron target: delete every row older than
   ``retention_days`` (default 90).

   :returns: the number of rows removed.

   Scheduled daily by ``cron_gc_verify_attempts`` — see :doc:`../data/ir_cron`,
   which is the module's only scheduled job. Logs at ``INFO`` only when it
   actually removed something, so a quiet instance does not write a line a day
   saying nothing happened.

   **Retention is a data-protection decision, not a technical one.** These rows
   hold IP addresses. Ninety days is long enough to investigate an incident and
   short enough to defend, but the figure belongs to whoever signs off the
   processing record — see :doc:`../../handbook/security-and-privacy`.

   .. note::

      The purge is why :py:attr:`DmsCertificate.verify_count
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.verify_count>`
      is a plain stored counter rather than a compute over ``attempt_ids``. How
      many times a document was checked should outlive the log of who checked
      it; a count derived from these rows would silently fall to zero ninety
      days after the last lookup.

   .. warning::

      A purge is also a reset of both limits. A lock in force when the cron runs
      survives only as long as the rows backing it: ``reference_lock_minutes``
      is 30 by default and ``retention_days`` is 90, so this never matters in
      practice — but set retention to a figure shorter than either window and
      the limits stop working.

See also
--------

* :doc:`../controllers/verify` — the only caller, and the order the two limits
  are consulted in
* :doc:`dms_certificate` — :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._match`,
  which the limits stand in front of, and
  :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._notify_verification`,
  which turns an outcome into a message
* :doc:`res_config_settings` — both limits, the retention window and their
  defaults
* :doc:`../data/ir_cron` — the daily purge
* :doc:`../views/dms_certificate_attempt_views` — the list, the search and why
  there is no form
* :doc:`../../handbook/verification` and :ref:`verification-refusals` — what
  the agent is told when a limit fires, and what they are not
* :doc:`../../handbook/security-and-privacy` — IP addresses, retention and the
  "An external user" asymmetry
* :ref:`deployment-nginx` — the limit that should be in front of this one
