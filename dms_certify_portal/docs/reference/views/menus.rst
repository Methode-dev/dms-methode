menus
=====

Source: :ghsrc:`views/menus.xml`

Six ``menuitem`` records. Loaded after every view file in the manifest's
``data`` list — every action they reference has to exist first — and followed
only by :doc:`../templates`, which declares no actions at all.

Structure
---------

.. code-block:: text

   Consular                                  group_certify_user     seq 95
     ├── Verification entries                 → action_dms_certificate      10
     ├── Reporting                                                          80
     │     └── Verification attempts          → action_dms_certificate_attempt 10
     └── Configuration                        group_certify_manager         90
           └── Document types                 → action_dms_certificate_type 10

.. list-table::
   :header-rows: 1
   :widths: 30 24 46

   * - External id
     - Groups
     - Action
   * - ``menu_certify_root``
     - ``group_certify_user``
     - none — the app root
   * - ``menu_dms_certificates``
     - inherited
     - :ref:`action_dms_certificate`
   * - ``menu_certify_reporting``
     - inherited
     - none — a container
   * - ``menu_certify_attempts``
     - inherited
     - ``action_dms_certificate_attempt``
   * - ``menu_certify_configuration``
     - ``dms_certify_portal.group_certify_manager``
     - none — a container
   * - ``menu_certify_types``
     - inherited
     - ``action_dms_certificate_type``

Decisions worth naming
----------------------

**A top-level application, not an overlay.** The manifest sets
``application: True`` and the root carries a ``web_icon``, so
:guilabel:`Consular` appears in the apps menu beside Sales and Project. That is
the opposite of the usual choice for a module that extends somebody else's
records, and it is right here: this addon owns its own models, and a consular
desk comes to this app to look a document up or to find out whether an embassy
has checked one. There is no host application to hang off.

Sequence 95 puts it late in the apps list — it is a specialist back-office tool,
not the thing anybody opens first.

**The root is gated on the Agent group, Configuration on the Registrar group.**
An operator who can only read the registry still needs the app: answering
*"what did we issue for this port call, and has anyone verified it?"* is their
job. What they have no reason to see is the taxonomy, so
:guilabel:`Configuration` — and only that branch — narrows to
:ref:`group_certify_manager <dms_certify_portal_groups-group_certify_manager>`.
Configuration menus are for people who configure.

Everything else inherits the root's group rather than repeating it, which is
what keeps the matrix above short.

**The attempt log sits under** :guilabel:`Reporting`, **not**
:guilabel:`Configuration`. It would be easy to file it with the technical
screens, and it would be wrong. The log is read to answer an operational
question — *is somebody guessing at one of our documents?* — and its action
opens grouped by IP address with the failures filtered in, because that is the
shape the answer comes in (:doc:`dms_certificate_attempt_views`). Nothing on it
is a setting; nobody configures it.

That also places it inside the Agent group rather than the Registrar one. An
operator noticing a lockout is the point, and
:ref:`group_certify_user <dms_certify_portal_groups-group_certify_user>` has
read-only access to the model, so they can look and cannot prune.

**Reporting at 80, Configuration at 90.** Odoo's own convention is
Configuration last in an app's menu bar, and following it means a user does not
have to re-learn where it is per app.

**The groups are written unqualified.** ``groups="group_certify_user"``, not
``groups="dms_certify_portal.group_certify_user"`` — the shorthand resolves
within the loading module. Fine here; a module *extending* this menu has to use
the full external id.

.. note::

   The menu says :guilabel:`Verification entries` and the action it opens is
   named *Certified documents*, so that is what the breadcrumb and the list's
   title show once you are inside. Both readings are defensible — the registry
   entry is not the document (:doc:`../models/dms_certificate`) — but they are
   two names for one screen, and the breadcrumb wins.

No URL paths
------------

None of the three actions declares a ``path``, so each is reached as
``/odoo/action-<numeric id>``. That id is assigned per database, which means a
link to :guilabel:`Verification entries` cannot be pasted into a runbook or a
chat message and still work somewhere else.

Adding ``path`` to the three ``ir.actions.act_window`` records in
:doc:`dms_certificate_views`, :doc:`dms_certificate_attempt_views` and
:doc:`dms_certificate_type_views` would fix that and costs nothing — it is
simply not done yet.

Not on a menu
-------------

Two actions are deliberately unreachable from here:

* :doc:`dms_certificate_revoke_views` — ``action_dms_certificate_revoke`` is
  bound by external id from the certificate form's header button. Revoking is
  something you do *to a document you are looking at*, and a menu entry would
  mean a dialog that first asks which document, with the wrong one a mis-click
  away.
* The settings — :menuselection:`Settings --> General Settings --> Document
  certification`, which is Odoo's convention for anything writing
  ``ir.config_parameter``. See :doc:`res_config_settings_views` and
  :doc:`../data/ir_config_parameter`.

The public verification page is not on a menu either, and could not be: it is a
front-end route on a different host entirely, with no session and no back-office
layout. :py:meth:`action_open_portal() <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.action_open_portal>`
on the certificate form is the way in from the back office — see
:ref:`deployment-check-host` for what has to resolve for it to work.

See also
--------

* :doc:`../security/dms_certify_portal_groups` — what the two groups grant
* :doc:`dms_certificate_views` — :ref:`action_dms_certificate`, the one entry
  under the root
* :doc:`dms_certificate_attempt_views` — the grouping and filter the Reporting
  entry opens with
* :doc:`dms_certificate_type_views` — the only Configuration screen
* :doc:`res_config_settings_views` — the other half of configuration, under
  Settings
* :doc:`../../handbook/administration` — what to set up, in the order the menus
  suggest
