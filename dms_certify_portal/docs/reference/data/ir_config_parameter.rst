ir_config_parameter
===================

Source: :ghsrc:`data/ir_config_parameter.xml`

Twenty-two ``ir.config_parameter`` records, every key prefixed
``dms_certify_portal.``, loaded ``noupdate="1"``. They are the shipped answers
to everything an administrator may want to change without touching code, and
each one is also a field on :doc:`../models/res_config_settings` so that it can
be changed from :menuselection:`Settings --> General Settings --> Document
certification`.

.. note::

   ``noupdate="1"`` is the point of this file. An upgrade re-reads the data but
   leaves existing records alone, so a window somebody shortened to five minutes
   or a seal colour somebody matched to a letterhead survives every later
   version of the module. It also means the reverse: changing a value *here*
   does not reach a database that already has the key.

Throttling and retention
------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 10 28 34

   * - Key
     - Default
     - Read by
     - What it decides
   * - ``max_failures``
     - ``10``
     - ``attempt.is_throttled()``
     - Failed lookups one IP address may make before it is refused outright
   * - ``window_minutes``
     - ``15``
     - ``attempt.is_throttled()``, the refusal page
     - The sliding window those failures are counted in, and the number the
       refusal page quotes back
   * - ``max_reference_failures``
     - ``5``
     - ``attempt.reference_lock_left()``, ``reference_attempts_left()``
     - Failed lookups one *reference* may absorb, counted across every address
   * - ``reference_lock_minutes``
     - ``30``
     - ``attempt.reference_lock_left()``
     - How long a tripped reference stays locked, timed from the failure that
       tripped it
   * - ``session_minutes``
     - ``15``
     - the controller's result session
     - How long a successful result stays readable before the agent has to look
       it up again
   * - ``retention_days``
     - ``90``
     - ``attempt._gc_attempts()``
     - How long attempt rows survive the daily purge
       (:doc:`ir_cron`)

The two failure limits are **not** two settings for one thing, and the pair is
the most consequential entry on this page. ``max_failures`` stops one client
hammering the whole registry; ``max_reference_failures`` is what actually
protects a document, because with the second check set to four characters of a
passport there are only a few thousand possibilities and a guesser changes
address freely. See :doc:`../models/dms_certificate_attempt`.

``retention_days`` is a data-protection decision wearing a technical costume.
Ninety days is long enough to investigate an incident and short enough to
defend, but it is the sort of number that belongs in a processing record rather
than in a default — see :doc:`../../handbook/security-and-privacy`.

What the portal does
--------------------

.. list-table::
   :header-rows: 1
   :widths: 28 10 28 34

   * - Key
     - Default
     - Read by
     - What it decides
   * - ``hide_expired``
     - ``False``
     - **nothing**
     - Nominally whether an expired document reads as expired or as *no match*
   * - ``allow_download``
     - ``True``
     - the controller's download route and the result page
     - Whether a successful lookup is offered the sealed PDF as well as the page
       images

.. warning::

   ``hide_expired`` **is shipped, settable, and read by nothing at all.** There
   is no ``_hide_expired()`` method and no reader of the parameter anywhere in
   the addon, so an expired document always reports as authentic but out of
   date. The README advertises an override point that does not exist — see the
   ``.. todo::`` on :doc:`../models/dms_certificate` and the field on
   :doc:`../models/res_config_settings`.

   It is also the one value in this file whose shipped spelling is visibly
   wrong in the UI: ``get_values()`` coerces with ``bool(value)``, and
   ``bool('False')`` is ``True``, so a fresh install shows :guilabel:`Hide
   expired documents` ticked.

Defaults for a new certificate
------------------------------

These are read through
:py:meth:`DmsCertificate._default_param() <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._default_param>`
as the ``default=`` of a field, which is why those defaults are lambdas: a
literal would be captured at import time, a lambda asks the database at create
time. Changing one here changes what the *next* document is created with and
never touches an issued one.

.. list-table::
   :header-rows: 1
   :widths: 28 12 60

   * - Key
     - Default
     - What it decides
   * - ``second_factor``
     - ``ppt4``
     - What a lookup is asked for alongside the reference — last four
       characters of a passport, the full number, or a date of birth
   * - ``disclosure``
     - ``confirm``
     - Whether a successful lookup sees the page as issued or with every other
       listed person blanked
   * - ``validity_days``
     - ``90``
     - Days after the movement date that a document stays valid; ``0`` means
       until revoked
   * - ``reference_prefix``
     - ``ICS``
     - The leading block of a generated reference, and the input mask and
       sample the public form shows
   * - ``notify_on_lookup``
     - ``1``
     - Whether a routine successful lookup is posted back to the desk, or only
       the ones needing attention

``reference_prefix`` is read in two places that must agree: the model, when
generating a reference, and the controller, when telling the public page how
wide the first group of the input mask is. Change it and both follow; there is
no second copy to update.

House style of the seal
-----------------------

Per-document choices — the marking and its wording — live on the certificate.
Everything below is set once, for the whole operation, and read inside
:py:meth:`DmsCertificate._seal_spec() <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._seal_spec>`.

.. list-table::
   :header-rows: 1
   :widths: 28 12 60

   * - Key
     - Default
     - What it decides
   * - ``seal_opacity``
     - ``9``
     - Watermark opacity, per cent. Low enough that the document stays
       readable under it
   * - ``seal_angle``
     - ``-32``
     - Watermark angle, degrees
   * - ``seal_size``
     - ``24``
     - Watermark type size
   * - ``seal_mode``
     - ``tile``
     - ``tile`` across the page, or a ``single`` diagonal band
   * - ``seal_color``
     - ``#10314F``
     - Watermark ink
   * - ``seal_guilloche``
     - ``1``
     - The engraved border, which moirés on a photocopy
   * - ``seal_microtext``
     - ``1``
     - The 1 pt footer line repeating the reference
   * - ``seal_qr_corner``
     - ``br``
     - Which bottom corner the stamp block sits in — ``br`` or ``bl``
   * - ``seal_band``
     - ``auto``
     - Whether the page is shrunk to free a strip for the stamp: ``auto`` only
       when the corner is occupied, ``scale`` always, ``overlay`` never

Changing any of these affects documents sealed **from now on**. An issued
document keeps the house style it was sealed under, because the seal is in its
bytes; a re-stamp picks up the new one. The millimetre geometry these values
feed is on :doc:`../tools/seal`.

Not in this file
----------------

Three keys the code reads are deliberately absent, and one is missing by
oversight:

``dms_certify_portal.passport_key``
   The HMAC pepper. **Generated per instance** by ``post_init_hook`` as
   ``secrets.token_urlsafe(48)`` — see :doc:`../hooks` and
   :ref:`PASSPORT_KEY_PARAM <dms_certificate_holder-PASSPORT_KEY_PARAM>`. A
   secret shipped in a data file would be the same secret in every deployment and in the repository, so
   there is nothing left for it to protect. This is the one parameter that is a
   backup item rather than a setting.

``dms_certify_portal.company_id`` and ``dms_certify_portal.public_base_url``
   Written from :doc:`../models/res_config_settings` only. Neither has a
   defensible shipped default: the portal company depends on who installed the
   module, and the public base URL goes on paper that circulates for months, so
   a wrong default is worse than an empty one — an empty value falls back to the
   instance's own address, a wrong one prints an address that resolves to
   somebody else. See :ref:`deployment-check-host`.

``dms_certify_portal.default_lang``
   Read by the controller as ``self._text_param('default_lang', 'fr')`` when a
   request names no language, and **not shipped here and not on the settings
   page**. The hard-coded fallback is French, which is not obviously what every
   deployment wants and is not discoverable from the UI.

   .. todo::

      ``default_lang`` is a real parameter with no record and no settings field.
      Should it be shipped here (and with which default), exposed in Settings
      next to the other portal behaviour, or dropped in favour of the
      instance's own language? Right now the only way to set it is by hand in
      :menuselection:`Settings --> Technical --> System Parameters`.

There is also **no** ``ir.sequence`` record anywhere in this addon, and the
comment at the top of this file is where that is recorded. A counter inside a
reference would tell anyone holding two documents how many were issued in
between, and would make the space walkable from a reference somebody already
has. The reference is random throughout — see
:ref:`_generate_reference() <dms_certificate-generate_reference>`.

The boolean spelling, which is a trap
-------------------------------------

Five of these parameters back a Boolean settings field, and this file spells
their values three different ways: ``1`` for ``notify_on_lookup``,
``seal_guilloche`` and ``seal_microtext``; ``True`` for ``allow_download``;
``False`` for ``hide_expired``. The readers are not interchangeable either —
the controller's ``_bool_param()`` accepts ``'True'``, ``'true'`` and ``'1'``,
while the model compares ``== '1'`` exactly.

.. important::

   **Those three spellings are not interchangeable, and a save does not
   preserve them.** Saving :menuselection:`Settings --> General Settings`
   rewrites a ticked box as ``'True'`` and **deletes the parameter row
   entirely** for an unticked one, after which the shipped value no longer
   applies and the ``default=`` on the settings field does.

   The consequence is that :guilabel:`Guilloche border`,
   :guilabel:`Microtext line in the footer` and :guilabel:`Notify the desk on
   every lookup` invert the first time anybody saves that page, and
   :guilabel:`Allow downloading the sealed document` cannot be turned off from
   the UI at all. The full trace, the table of outcomes and the two candidate
   fixes are on :ref:`settings-boolean-round-trip`.

   For this file the request is narrower: it should ship **one** boolean
   spelling, not three.

See also
--------

* :doc:`../models/res_config_settings` — the same values as a settings page,
  grouped the same way
* :doc:`../views/res_config_settings_views` — where each one appears in
  :menuselection:`Settings --> General Settings`
* :doc:`ir_cron` — the job ``retention_days`` drives
* :doc:`../models/dms_certificate_attempt` — the two failure limits in detail
* :doc:`../hooks` — the one parameter that is generated rather than shipped
* :doc:`../tools/seal` — what the seal house style actually draws
* :doc:`../../handbook/administration` — which of these to set before issuing
  anything
