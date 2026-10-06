ir_cron
=======

Source: :ghsrc:`data/ir_cron.xml`

One scheduled job, loaded ``noupdate="1"``. There is no other, and nothing else
in this addon runs on a timer.

.. list-table::
   :widths: 26 74

   * - External id
     - ``cron_gc_verify_attempts``
   * - Name
     - *Verification: purge old attempt logs*
   * - Model
     - ``dms.certificate.attempt``
   * - Code
     - ``model._gc_attempts()``
   * - Interval
     - every ``1`` ``days``
   * - Active
     - ``True``

What it does
------------

:py:meth:`_gc_attempts() <odoo.addons.dms_certify_portal.models.dms_certificate_attempt.DmsCertificateAttempt._gc_attempts>`
deletes every :doc:`../models/dms_certificate_attempt` row whose ``create_date``
is older than ``dms_certify_portal.retention_days`` — ninety days by default
(:doc:`ir_config_parameter`) — logs the count at ``INFO`` when there was
anything to drop, and returns it.

The retention window is read on every run rather than baked into the job, so
shortening it in :menuselection:`Settings --> General Settings` takes effect at
the next pass with no need to touch the cron. Daily is the right frequency for
the same reason the window is in days: nothing downstream depends on a row
disappearing promptly, and a shorter interval would only mean more passes
finding nothing.

Why the attempt log needs a job at all
--------------------------------------

Every hit on the public form writes a row — successes, misses, throttled
requests, captcha failures. The table is therefore the only one in this addon
that grows with *traffic* rather than with work done, and it holds IP addresses
and user agents, which makes unbounded growth a data-protection problem before
it is a disk one.

The rows cannot simply be dropped on read, because the same table is both the
audit trail and both throttle counters: ``is_throttled()`` and
``reference_lock_left()`` count rows inside their own windows, which are
minutes wide, while the retention window is months wide. Deleting inside the
limit windows would hand a guesser their budget back.

.. note::

   :py:attr:`verify_count <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.verify_count>`
   on the certificate is a plain stored counter rather than a count over
   ``attempt_ids`` precisely so that this job can run: how many times a document
   was checked should outlive the log of who checked it.

Fields the record deliberately does not set
-------------------------------------------

``user_id``
   Unset, so Odoo's ``default=lambda self: self.env.user`` applies and the job
   runs as whoever loaded the data file — the superuser, at install. It does
   not matter here: ``_gc_attempts()`` searches and unlinks under ``sudo()``
   internally, so the job's own rights never decide what it can remove. A data
   file that names a user would be the fragile version of this.

``nextcall``
   Unset, so it defaults to the moment of install and the first pass happens
   within the hour. Nothing is gained by delaying it.

``priority``
   Unset, so ``5`` — the Odoo default. This job is neither urgent nor
   expensive, and a priority here would only be a claim about other modules'
   jobs.

``interval_type``, by contrast, **is** set, and has to be: Odoo's own default is
``months``.

Deleting rows by hand
---------------------

The Registrar group holds ``perm_unlink`` on
``dms.certificate.attempt`` and nothing else — no write, no create
(:doc:`../security/ir_model_access`). That exists so retention can also be
enforced on demand, from :menuselection:`Consular --> Reporting -->
Verification attempts`, because a data-protection request does not wait for a
scheduled job.

See also
--------

* :doc:`../models/dms_certificate_attempt` — the model, ``_gc_attempts()``, and
  the two throttle counters that share the table
* :doc:`ir_config_parameter` — ``retention_days``
* :doc:`../security/ir_model_access` — read-and-unlink, and why create is denied
  to everybody
* :doc:`../views/menus` — where the log is reachable from
* :doc:`../../handbook/administration` — agreeing a retention period
