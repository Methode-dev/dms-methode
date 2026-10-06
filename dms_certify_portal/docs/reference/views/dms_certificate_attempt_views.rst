dms_certificate_attempt_views
=============================

**Model:** :doc:`dms.certificate.attempt <../models/dms_certificate_attempt>`

Source: :ghsrc:`views/dms_certificate_attempt_views.xml`. One list, one search,
one action — and deliberately **no form view**. A single attempt has nothing to
read that the row does not already show, and a form would invite someone to edit
an audit record.

Structure
---------

.. code-block:: text

   list "Verification attempts"   create="false"  sample="1"
     decoration-danger  outcome == 'throttled'
     decoration-muted   outcome == 'no_match'

     create_date "When" · ip_address · reference_tried
     outcome  (badge)
     document_id   optional="hide"
     user_agent    optional="hide"
     success       column_invisible="1"

   search "Verification attempts"
     fields   ip_address · reference_tried
     filters  Failed · Blocked · | · Today
     group by IP address · Outcome · Day

Record ids
----------

.. list-table::
   :header-rows: 1
   :widths: 44 20 36

   * - External id
     - Kind
     - Notes
   * - ``view_dms_certificate_attempt_list``
     - ``ir.ui.view``
     - ``create="false"``; two row decorations
   * - ``view_dms_certificate_attempt_search``
     - ``ir.ui.view``
     - Two searchable fields, three filters, three groupings
   * - ``action_dms_certificate_attempt``
     - ``ir.actions.act_window``
     - ``view_mode`` is ``list`` only

Search elements
---------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Element
     - Domain / context
   * - ``ip_address``
     - searchable field
   * - ``reference_tried``
     - searchable field — what was *typed*, not what exists
   * - :guilabel:`Failed`
     - ``[('success', '=', False)]``
   * - :guilabel:`Blocked`
     - ``[('outcome', '=', 'throttled')]``
   * - :guilabel:`Today`
     - ``[('create_date', '>=', datetime.datetime.combine(context_today(),
       datetime.time(0,0,0)))]``
   * - :guilabel:`IP address`
     - ``{'group_by': 'ip_address'}``
   * - :guilabel:`Outcome`
     - ``{'group_by': 'outcome'}``
   * - :guilabel:`Day`
     - ``{'group_by': 'create_date:day'}``

Decisions worth naming
----------------------

.. admonition:: The action opens pre-filtered, and that is the whole design
   :class: important

   .. code-block:: xml

      <field name="context">{'search_default_group_ip': 1,
                             'search_default_filter_failed': 1}</field>

   Nobody opens this log to read it chronologically. The question is always
   *is one address failing repeatedly*, so the default view answers it before
   anyone touches the search bar: failures only, grouped by address.

   The ``help`` block says what to look for — one address producing many
   failures, or successful lookups walking through sequential references — and
   notes the gap honestly: **an attacker slow enough to stay under every rate
   limit still shows up as a shape here that nothing automatically watches
   for.** The group-by is the substitute for the alert nobody has written.

**This is where the IP address is shown, and the certificate's own log is not.**
The :guilabel:`Verification log` page on :doc:`dms_certificate_views` shows
``requester_label`` — *"An external user"* — while the same row here carries
``ip_address`` as a first-class column. The asymmetry is intentional: an issuer
watching their own document needs to know that a lookup happened, not who from,
and personal data should not be on a screen whose purpose it is not. Reading
addresses is the registrar's job, through this menu.

**Rows cannot be created, and are not readonly.** ``create="false"`` closes the
only door a user could reach; the rows themselves are written by the controller
through ``sudo()``. The access matrix in :doc:`../security/ir_model_access` is
what actually prevents an agent from editing one — a view attribute is a
convenience, never a control.

**Two decorations, chosen to be read at a glance.**
``decoration-danger="outcome == 'throttled'"`` paints the rows that mean the
limiter fired; ``decoration-muted="outcome == 'no_match'"`` greys out the
ordinary noise of somebody mistyping. What is left in normal ink is what deserves
a second look. ``outcome`` then repeats the first of those as a badge, so the
colour survives being grouped or exported.

**``success`` is on the list but** ``column_invisible="1"``. It is there for the
:guilabel:`Failed` filter's domain and nothing else — a boolean column beside a
four-value ``outcome`` badge would say less than the badge already does.

**``reference_tried`` records what the agent typed.** Searchable, because the
useful question after a lockout is "what were they aiming at", and a reference
that does not exist is exactly the interesting case. It is normalised but not
resolved — see :doc:`../models/dms_certificate_attempt`.

Retention
---------

These rows hold IP addresses and are purged by a cron against
``dms_certify_portal.retention_days`` (90 by default) — see
:doc:`../data/ir_cron`. The figure is set in
:doc:`res_config_settings_views`, under a help string that says to agree it with
whoever signs off your processing record.

See also
--------

* :doc:`../models/dms_certificate_attempt` — the two rate limits, the outcome
  values, and ``requester_label``
* :doc:`dms_certificate_views` — the per-document view of the same rows
* :doc:`menus` — why this sits under :guilabel:`Reporting`
* :doc:`../data/ir_cron` — the purge
* :doc:`../../handbook/security-and-privacy` — what is kept, and for how long
