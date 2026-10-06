res.config.settings
===================

.. py:currentmodule:: odoo.addons.dms_certify_portal.models.res_config_settings

Source: :ghsrc:`models/res_config_settings.py`

.. py:class:: ResConfigSettings

   Bases: ``odoo.models.TransientModel`` with ``_inherit = 'res.config.settings'``
   — an extension of the standard settings record, not a model of its own.

   :Odoo model: ``res.config.settings`` — ``self.env["res.config.settings"]``
   :Description: inherited from ``base``; not redeclared here
   :Order: inherited; not redeclared here
   :Constraints: none

   Twenty-six fields, and twenty-five of them are a typed front end to an
   ``ir.config_parameter`` row. The parameters themselves are the interface the
   rest of the module reads — :py:meth:`DmsCertificate._default_param
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._default_param>`,
   :py:meth:`DmsCertificateAttempt._param
   <odoo.addons.dms_certify_portal.models.dms_certificate_attempt.DmsCertificateAttempt._param>`
   and the controller's ``_param``/``_text_param``/``_bool_param`` all read
   keys, never this model — so nothing anywhere depends on a transient record
   existing. This class exists to give those keys labels, help text, types and a
   place in :menuselection:`Settings --> General Settings`.

   The groups below are the source file's own, in its order, and they are not
   cosmetic: the first is **how the public door behaves**, the second **what the
   portal does with a document**, the third **what gets registered
   automatically**, the fourth **what a new certificate starts as**, and the
   fifth **house style for the stamp**. Different people, different days. The
   view keeps the same division — :doc:`../views/res_config_settings_views`.

.. contents::
   :local:
   :depth: 2

.. note::

   This page is the field-by-field reference: every field, the parameter key it
   writes, its declared default and the decision behind it. For the layout, the
   ``<setting>`` ids and the help strings as they read on screen, see
   :doc:`../views/res_config_settings_views`. For the values a fresh database
   starts with, see :doc:`../data/ir_config_parameter`.

Throttling
----------

The two limits, and the three windows around them. What they mean and why there
are two is on :doc:`dms_certificate_attempt`; what follows is where the numbers
live.

.. py:attribute:: ResConfigSettings.certify_max_failures
   :type: fields.Integer

   ``string="Failed attempts allowed per address",
   config_parameter='dms_certify_portal.max_failures', default=10``

   Read by :py:meth:`DmsCertificateAttempt.is_throttled
   <odoo.addons.dms_certify_portal.models.dms_certificate_attempt.DmsCertificateAttempt.is_throttled>`.

.. py:attribute:: ResConfigSettings.certify_window_minutes
   :type: fields.Integer

   ``string="Rate limit window (minutes)",
   config_parameter='dms_certify_portal.window_minutes', default=15``

   The sliding window the count above is taken over.

.. py:attribute:: ResConfigSettings.certify_max_reference_failures
   :type: fields.Integer

   ``string="Failed attempts allowed per reference",
   config_parameter='dms_certify_portal.max_reference_failures', default=5``

   The field whose ``help`` does the most work on the page: *"Counted across
   every address. This is the limit that actually protects a document when the
   second check is only four characters long."*

   Five is low on purpose. The arithmetic is in the model docstring: last four
   characters of a passport is a few thousand possibilities, so the budget has
   to be single digits for the reference to mean anything.

.. py:attribute:: ResConfigSettings.certify_reference_lock_minutes
   :type: fields.Integer

   ``string="Reference lockout (minutes)",
   config_parameter='dms_certify_portal.reference_lock_minutes', default=30``

   Doubles as the window the per-reference failures are counted over and the
   length of the lock they trip — one number, because two would invite a
   configuration where the lock outlives the count that justified it.

.. py:attribute:: ResConfigSettings.certify_session_minutes
   :type: fields.Integer

   ``string="Result page lifetime (minutes)",
   config_parameter='dms_certify_portal.session_minutes', default=15``

   How long a result stays readable after a successful lookup. The help carries
   the reason to keep it short — *"embassy workstations are shared"* — and the
   consequence is concrete: the session token is what gates the page images and
   the download as well as the verdict, so this is also how long a walk-away
   browser keeps serving somebody's sealed PDF.

.. py:attribute:: ResConfigSettings.certify_retention_days
   :type: fields.Integer

   ``string="Keep attempt logs for (days)",
   config_parameter='dms_certify_portal.retention_days', default=90``

   Read by :py:meth:`DmsCertificateAttempt._gc_attempts
   <odoo.addons.dms_certify_portal.models.dms_certificate_attempt.DmsCertificateAttempt._gc_attempts>`.
   A data-protection figure rather than a technical one; the attempt rows hold
   IP addresses.

   .. warning::

      Set below ``certify_reference_lock_minutes`` or ``certify_window_minutes``
      and the purge starts deleting the rows the limits are counting. Nothing
      validates the relationship.

What the portal does
--------------------

.. _res_config_settings-certify_hide_expired:

.. py:attribute:: ResConfigSettings.certify_hide_expired
   :type: fields.Boolean

   ``string="Hide expired documents",
   config_parameter='dms_certify_portal.hide_expired'`` — and **no**
   ``default=``, which is the only field here without one.

   The help describes a real trade-off: off, an expired document is reported as
   genuine but out of date; on, it reads as *"no match"*, which shrinks the
   searchable set but can make an agent reject a real holder.

   .. warning::

      **Nothing reads the parameter.** A grep for ``hide_expired`` across
      ``models/``, ``controllers/``, ``tools/``, ``wizards/`` and ``hooks.py``
      finds this declaration and nothing else. An expired document always reads
      as expired, whatever this says — see
      ``test_an_out_of_date_document_reads_as_expired_not_missing`` and
      :doc:`../../limits`.

   The missing ``default=`` is not harmless either. ``get_values`` falls back to
   ``field.default(self) if field.default else False``, so with no default the
   fallback is ``False`` — but the shipped parameter is the **string**
   ``'False'`` (:doc:`../data/ir_config_parameter`), and the boolean conversion
   in core is ``bool(value)``. ``bool('False')`` is ``True``, so on a fresh
   database this box displays **ticked** while the parameter says the opposite.
   It is invisible today only because nothing consults it.

.. py:attribute:: ResConfigSettings.certify_allow_download
   :type: fields.Boolean

   ``string="Allow downloading the sealed document",
   config_parameter='dms_certify_portal.allow_download', default=True``

   Read by the controller's ``_bool_param``, which gates both the
   :guilabel:`Download the sealed PDF` button and the ``/r/<token>/file`` route.
   It governs **this module's gated route only** — see the warning on
   :doc:`../views/res_config_settings_views` about ``/web/content``.

   See :ref:`settings-boolean-round-trip` before relying on being able to turn
   it off from the UI.

.. py:attribute:: ResConfigSettings.certify_portal_company_id
   :type: fields.Many2one

   → ``res.company``, ``string="Portal company",
   config_parameter='dms_certify_portal.company_id'``

   Whose name, address and contact details the public page carries. A
   **decision, not a fallback**: a public request resolves to whatever company
   the public user happens to default to, which is nobody's choice, and an
   embassy is looking at one organisation whichever company issued the document
   in front of them.

   A ``Many2one`` backed by a parameter stores the bare id as a string. That is
   why the controller reads it as ``int(self._text_param('company_id', '0') or
   0)`` and then calls ``.exists()``: a company deleted after the setting was
   made degrades to the request's own company instead of raising on a public
   page (``test_a_deleted_company_falls_back_instead_of_breaking``,
   ``test_an_unset_company_falls_back_instead_of_breaking``).

   Note that this is a *separate* decision from
   :py:attr:`DmsCertificate.company_id
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.company_id>`,
   which is whose name goes into the seal block and what the record rule is
   scoped on.

.. _res_config_settings-certify_public_base_url:

.. py:attribute:: ResConfigSettings.certify_public_base_url
   :type: fields.Char

   ``string="Public verification URL",
   config_parameter='dms_certify_portal.public_base_url'``

   .. admonition:: The one setting that cannot be corrected later
      :class: important

      This value is printed beside the QR code and encoded inside it, by
      :py:attr:`DmsCertificate.verify_url
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.verify_url>`,
      on paper that circulates for months. A document already in an embassy's
      file cannot be re-pointed, and the embassy will not be told the host
      moved.

      Set it before issuing anything. Everything else on this page can be
      changed on a Tuesday afternoon; this one is a decision about a domain name
      you are promising to answer on. See :ref:`deployment-check-host` and
      ``test_the_verify_url_uses_the_public_base_url``.

   Empty falls back to the instance's own address, which is the right default
   for a staging box and the wrong one for production.

What gets registered automatically
----------------------------------

.. _res_config_settings-certify_auto_stamp_type_ids:

.. py:attribute:: ResConfigSettings.certify_auto_stamp_type_ids
   :type: fields.Many2many

   → ``dms.certificate.type``, ``string="Stamp on generation"``

   **The one field on this page with no ``config_parameter``.** Filled by
   :py:meth:`~ResConfigSettings.get_values` and written back by
   :py:meth:`~ResConfigSettings.set_values`.

   .. admonition:: Why it is a plain field and not a compute
      :class: important

      The flag it edits lives on the type itself
      (:py:attr:`DmsCertificateType.auto_stamp
      <odoo.addons.dms_certify_portal.models.dms_certificate_type.DmsCertificateType.auto_stamp>`),
      so a producing module ships a sensible value with its own data record and
      an administrator changes it here, neither side knowing about the other. A
      parameter listing type codes would be a second, divergent answer to the
      same question.

      Reading that flag into a *computed* field is the obvious implementation
      and it does not work. A non-stored compute recomputes whenever the cache
      is invalidated, and that happens between the client writing the record and
      ``set_values()`` reading it back — so an unticked box was recomputed
      straight back to ticked before anything reached the database. Writing it
      through ``get_values()`` instead puts the value in the record at
      ``default_get`` time and leaves it there.

      This was a real bug, not a hypothetical, and both directions have
      regression tests that go through ``create()`` and ``execute()`` the way
      the client does — ``test_unticking_a_kind_survives_the_save``,
      ``test_ticking_a_kind_survives_the_save``,
      ``test_settings_opens_showing_the_current_choice``. The docstring on the
      unticking test says why calling ``set_values()`` directly proves nothing.

   Registering is explicitly **not** sealing: the help says *"Sealing stays a
   separate, deliberate act."* An auto-registered document is a draft, and a
   draft answers no lookup.

Defaults for a new certificate
------------------------------

Four of these five are read as the ``default=`` of a field on
``dms.certificate``, through
:py:meth:`DmsCertificate._default_param
<odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._default_param>`.
They are therefore the value a **new** record starts with and have no effect on
one already issued — changing the default second check does not change how any
existing document opens.

.. py:attribute:: ResConfigSettings.certify_second_factor
   :type: fields.Selection

   ``[('ppt4', …), ('pptfull', …), ('dob', …)], string="Default second check",
   config_parameter='dms_certify_portal.second_factor', default='ppt4'``

   The same three members as :py:attr:`DmsCertificate.second_factor
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.second_factor>`,
   and like it there is **no "none"**: the reference alone never opens a
   document and this page offers no way to make it. See
   :ref:`concepts-second-factor`.

   ``ppt4`` is the default because four characters is what an agent can read off
   a faxed page and type without a mistake.

.. py:attribute:: ResConfigSettings.certify_disclosure
   :type: fields.Selection

   ``[('confirm', …), ('full', …)], string="Default disclosure",
   config_parameter='dms_certify_portal.disclosure', default='confirm'``

   ``confirm`` by default — the page confirms the match and blanks every other
   listed person. The cautious direction is the default because the expensive
   mistake is the other one: a crew list disclosed to a stranger cannot be
   undisclosed. See :ref:`concepts-disclosure`.

.. py:attribute:: ResConfigSettings.certify_validity_days
   :type: fields.Selection

   ``[('30', …), ('90', …), ('0', "Until revoked")],
   string="Default validity",
   config_parameter='dms_certify_portal.validity_days', default='90'``

   A Selection rather than an Integer, for the same reason as the field it
   defaults — these are the three answers a consular desk actually gives, and an
   open numeric field invites 45 and 60 with nobody able to say why.

.. py:attribute:: ResConfigSettings.certify_reference_prefix
   :type: fields.Char

   ``string="Reference prefix",
   config_parameter='dms_certify_portal.reference_prefix', default='ICS'``

   The first segment of every reference
   (:ref:```_generate_reference()`` <dms_certificate-generate_reference>`). It moves more than the prefix:
   the controller derives the public form's input mask from its **length**
   (``[len(prefix), 4, 3, 4, 2]``), so changing it reformats both the browser
   mask and the server-side regrouping of a refused reference. See
   :doc:`../static/verify`.

   Changing it does not touch references already issued — they are
   ``readonly=True`` and printed on paper — so a database can hold two prefixes
   and both still verify.

.. py:attribute:: ResConfigSettings.certify_notify_on_lookup
   :type: fields.Boolean

   ``string="Notify the desk on every lookup",
   config_parameter='dms_certify_portal.notify_on_lookup', default=True``

   Off means only failures, lockouts and mismatch reports reach the desk;
   routine successful checks go quiet. Those three are posted **regardless** of
   this setting, which is the part worth knowing before turning it off — see
   :py:meth:`DmsCertificate._notify_verification
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._notify_verification>`.

   Read by :py:attr:`DmsCertificate.notify_on_lookup
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.notify_on_lookup>`
   as ``_default_param("notify_on_lookup", "1") == "1"`` — see
   :ref:`settings-boolean-round-trip`, which is where that comparison goes
   wrong.

The seal
--------

Per document the issuer picks a marking and looks at the result in the preview
panel; everything below is the house style, set once, here. The division is
deliberate and argued on :doc:`../views/res_config_settings_views`: a document
whose stamp looks unlike the others is a document an agent has to think about.

Every one of these is read inside :py:meth:`DmsCertificate._seal_spec
<odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._seal_spec>`
and passed to ``seal.SealSpec``, which clamps and validates whatever it is
given (:doc:`../tools/seal`) — so a nonsensical value here degrades to a sane
stamp rather than to a traceback on the form.

.. py:attribute:: ResConfigSettings.certify_seal_opacity
   :type: fields.Integer

   ``string="Watermark opacity (%)",
   config_parameter='dms_certify_portal.seal_opacity', default=9``

   Clamped to 0–100 by ``SealSpec``. **Zero suppresses the watermark
   entirely** — ``_draw_watermark`` returns early on a falsy opacity — which is
   the only way to turn the marking off, and it is not labelled as such.

.. py:attribute:: ResConfigSettings.certify_seal_angle
   :type: fields.Integer

   ``string="Watermark angle",
   config_parameter='dms_certify_portal.seal_angle', default=-32``

   Degrees. Applied as a rotation about the page centre, so the whole tiled grid
   turns as one piece.

.. py:attribute:: ResConfigSettings.certify_seal_size
   :type: fields.Integer

   ``string="Watermark size",
   config_parameter='dms_certify_portal.seal_size', default=24``

   Point size, floored at 6 by ``SealSpec``. It also drives the tile spacing, so
   it changes the density of the wash and not only the glyph size.

.. py:attribute:: ResConfigSettings.certify_seal_mode
   :type: fields.Selection

   ``[('tile', "Tiled across the page"), ('single', "One diagonal band")],
   string="Watermark coverage",
   config_parameter='dms_certify_portal.seal_mode', default='tile'``

   Anything ``SealSpec`` does not recognise falls back to ``tile``.

.. py:attribute:: ResConfigSettings.certify_seal_color
   :type: fields.Char

   ``string="Watermark ink",
   config_parameter='dms_certify_portal.seal_color', default='#10314F'``

   A hex triplet. Parsed by ``seal.rgb()``, which returns the house navy for
   anything that is not six hex digits — so a half-typed value prints the
   default rather than nothing. Also the colour of the guilloche frame, which is
   not obvious from the label: :py:meth:`DmsCertificate._seal_spec
   <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._seal_spec>`
   passes the same value to both layers.

.. py:attribute:: ResConfigSettings.certify_seal_guilloche
   :type: fields.Boolean

   ``string="Guilloche border",
   config_parameter='dms_certify_portal.seal_guilloche', default=True``

   *"Engraved line pattern around the page. It moirés on a photocopy."* The
   help carries the justification: it is worth printing because it **degrades on
   reproduction**.

   Read as ``param('seal_guilloche', '1') == '1'``. See
   :ref:`settings-boolean-round-trip`.

.. py:attribute:: ResConfigSettings.certify_seal_microtext
   :type: fields.Boolean

   ``string="Microtext line in the footer",
   config_parameter='dms_certify_portal.seal_microtext', default=True``

   *"Repeats the reference at 1 pt. Legible under a loupe, a grey smear once
   scanned."* Same argument, same mechanism — and the same
   ``== '1'`` comparison.

.. py:attribute:: ResConfigSettings.certify_seal_qr_corner
   :type: fields.Selection

   ``[('br', "Bottom right, next to the signature"), ('bl', "Bottom left")],
   string="Stamp position",
   config_parameter='dms_certify_portal.seal_qr_corner', default='br'``

   Bottom right by default because that is where a reader looks for a
   signature. ``SealSpec`` accepts only these two and coerces anything else to
   ``br``.

.. py:attribute:: ResConfigSettings.certify_seal_band
   :type: fields.Selection

   ``[('auto', "Only when the corner is taken"), ('scale', "Always"),
   ('overlay', "Never — stamp over the page")],
   string="Make room for the stamp",
   config_parameter='dms_certify_portal.seal_band', default='auto'``

   The one setting here with a real trade-off, and the help states it:
   *"Sealing cannot reflow a page."* The three modes and what each costs are
   documented on :doc:`../tools/seal` under ``BAND_MODES``; ``auto`` keeps most
   documents at their exact size and only shrinks the ones that would otherwise
   be overprinted.

Overrides
---------

.. py:method:: ResConfigSettings.get_values()

   ``super()``, then fill
   :py:attr:`~ResConfigSettings.certify_auto_stamp_type_ids` with every
   ``dms.certificate.type`` whose ``auto_stamp`` is set, as a ``(6, 0, ids)``
   command.

   Searched ``with_context(active_test=False)``, so an **archived** type with
   the flag still set appears ticked. That is a readable asymmetry rather than a
   bug: this page shows the flag, while
   :py:meth:`DmsCertificateType._auto_stamp_codes
   <odoo.addons.dms_certify_portal.models.dms_certificate_type.DmsCertificateType._auto_stamp_codes>`
   — which decides what actually gets stamped — searches with the default
   ``active_test`` and so skips archived types.

.. py:method:: ResConfigSettings.set_values()

   ``super()`` — which writes all twenty-five parameters — then reconciles the
   ``auto_stamp`` flag on every type:

   .. code-block:: python

      (every - chosen).filtered('auto_stamp').auto_stamp = False
      chosen.filtered(lambda kind: not kind.auto_stamp).auto_stamp = True

   Both sides are ``filtered`` first so only the types that actually change are
   written. Without that, every save would touch every type row, bumping
   ``write_date`` on records nobody edited and inviting a pointless line in
   whatever is watching them.

   Runs under ``sudo()`` and ``with_context(active_test=False)``: the person in
   General Settings is a systems administrator who need not hold
   *Certification: Registrar*, and an archived type must still be unticked
   rather than silently kept.

.. _settings-boolean-round-trip:

The boolean round trip
----------------------

Three of the five booleans on this page do not survive a save, and the cause is
one interaction between Odoo's settings machinery and this module's parameter
readers. It is worth stating precisely, because the symptom is silent.

**What core does.** ``res.config.settings.set_values`` converts ``char``,
``integer``, ``float`` and ``many2one`` values before storing them and leaves a
``boolean`` alone, so ``ir.config_parameter.set_param`` receives a Python
``bool``. That method writes ``True`` into a ``Char`` column as the string
``'True'``, and — for ``False`` — **deletes the parameter row** rather than
writing a falsy value. On the way back in, ``get_values`` reads the row with
the field's ``default=`` as the fallback and coerces with ``bool(value)``.

**What this module does.** Two readers compare against the digit:

.. code-block:: python

   # models/dms_certificate.py — _seal_spec()
   guilloche=param('seal_guilloche', '1') == '1',
   microtext=param('seal_microtext', '1') == '1',

   # models/dms_certificate.py — the notify_on_lookup default
   default=lambda self: self._default_param('notify_on_lookup', '1') == '1'

and the shipped parameters are the digit ``1``
(:doc:`../data/ir_config_parameter`), so a fresh database is correct. The
controller's ``_bool_param`` is the tolerant one — it accepts ``'True'``,
``'true'`` and ``'1'`` — which is why ``allow_download`` behaves differently
from the other three.

**What happens on the first save.** Opening :menuselection:`Settings -->
General Settings` and pressing :guilabel:`Save` writes ``'True'`` over the
shipped ``'1'`` — the values differ as strings, so core does not skip them —
and ``'True' == '1'`` is ``False``:

.. list-table::
   :header-rows: 1
   :widths: 24 20 28 28

   * - Setting
     - Shipped
     - After a save with the box **ticked**
     - After a save with the box **unticked**
   * - ``seal_guilloche``
     - ``'1'`` → on
     - ``'True'`` → **off**, box still reads ticked
     - row deleted → ``'1'`` default → **on**, box reads ticked again
   * - ``seal_microtext``
     - ``'1'`` → on
     - ``'True'`` → **off**, box still reads ticked
     - row deleted → ``'1'`` default → **on**, box reads ticked again
   * - ``notify_on_lookup``
     - ``'1'`` → on
     - ``'True'`` → **off** for every new certificate
     - row deleted → ``'1'`` default → **on**
   * - ``allow_download``
     - ``'True'`` → on
     - ``'True'`` → on
     - row deleted → ``default=True`` → **on**, box reads ticked again
   * - ``hide_expired``
     - ``'False'`` → reads **ticked** (``bool('False')``)
     - ``'True'``
     - row deleted → no ``default=`` → unticked

So: the two anti-copying features invert the first time anybody saves General
Settings and cannot be turned off from the UI at all; the lookup notification
silently stops applying to new certificates while still reading as on; and the
download switch cannot be turned off from the UI, only by writing the parameter
directly — which is exactly what ``test_the_download_can_be_switched_off``
does, so the test passes and the UI path is untested.

.. todo::

   Decide one convention for booleans in this module and apply it in both
   directions. The two candidates:

   * read tolerantly everywhere — give ``dms.certificate`` the controller's
     ``_bool_param`` logic (``in ('True', 'true', '1')``) instead of
     ``== '1'``; or
   * stop round-tripping booleans through ``config_parameter`` — keep the
     parameters as text and set them from ``set_values()`` by hand, the way
     :py:attr:`~ResConfigSettings.certify_auto_stamp_type_ids` already is.

   Either way the *untick* case needs its own answer, because ``set_param``
   deletes the row and the ``default=`` then re-asserts the opposite: a
   false-by-default parameter, or an explicit ``'0'``.

   And ``data/ir_config_parameter.xml`` should ship one spelling, not three —
   it currently has ``1``, ``True`` and ``False`` as boolean values.

   This belongs in :doc:`../../limits` once somebody confirms it against a
   live database; it is derived here from ``base``'s ``set_values`` /
   ``set_param`` and this module's readers, and there is no regression test on
   the UI path.

See also
--------

* :doc:`../views/res_config_settings_views` — the three blocks, the
  ``<setting>`` ids and the layout convention
* :doc:`../data/ir_config_parameter` — every shipped parameter and its value,
  and why ``passport_key`` is not among them
* :doc:`dms_certificate_attempt` — both rate limits, the windows and the purge
* :doc:`dms_certificate` —
  :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._default_param`
  and :py:meth:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate._seal_spec`,
  the two readers of this page
* :doc:`dms_certificate_type` — where ``auto_stamp`` actually lives
* :doc:`../tools/seal` — ``SealSpec``, which clamps every house-style value
* :doc:`../../handbook/administration` — the same settings in the order you
  would configure them
* :doc:`../../handbook/deployment` — the ones that have to be right **before**
  the first document is issued
