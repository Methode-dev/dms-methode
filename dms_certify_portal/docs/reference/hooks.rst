hooks
=====

Install-time wiring that cannot be expressed as static XML data.

Source: :ghsrc:`hooks.py`. Registered in the manifest as
``"post_init_hook": "post_init_hook"``.

Two jobs, and they are in here for two different reasons.

Why a hook at all
-----------------

**The pepper has to be different in every deployment.** It is the HMAC key
every stored passport hash is derived under, and a value shipped in a data file
would be the same value in every database that ever installs this module — and
in the repository, and in anyone's checkout. A secret everybody has is not a
secret, so the only place it can be created is on the instance, once, at
install. That rules out XML entirely.

**The languages have to be looked up, not referenced.** Activating a language
means finding whichever ``res.lang`` variant *this* Odoo knows about — ``fr_FR``
on one database, ``fr_BE`` on another — and a data file would have to name one
by external id and fail on the database that has the other. Reading the shipped
catalogues off disk and resolving each against ``res.lang`` at install removes
that coupling.

Neither has anything to say to the other, which is why ``post_init_hook`` is
three lines and the work is in two named functions that can be called
independently. :doc:`migrations` calls the second one on its own.

.. automodule:: dms_certify_portal.hooks
   :members:
   :private-members:
   :undoc-members:

The pepper
----------

``_generate_passport_key`` writes ``secrets.token_urlsafe(48)`` — 48 bytes of
OS entropy, base64url — to the ``ir.config_parameter`` key named by
``PASSPORT_KEY_PARAM``, which is ``dms_certify_portal.passport_key``. It writes
it **only if the key is absent**, so a re-install or an upgrade never replaces a
working one.

.. important::

   **If this key is lost, every stored hash becomes unverifiable.** Not
   degraded — unverifiable. The hashes cannot be recomputed from anything else
   the portal holds, so no document opens again until every listed person is
   re-entered and re-hashed from a trusted source, and in the meantime an
   embassy checking a genuine document is told it does not match.

   It belongs in the backup procedure as its own line, beside the filestore:
   restoring a filestore against a database that has a different
   ``passport_key`` leaves you with sealed PDFs nobody can verify. See
   :doc:`../handbook/deployment` for the checklist entry, and
   :ref:`PASSPORT_KEY_PARAM <dms_certificate_holder-PASSPORT_KEY_PARAM>` for
   why a keyed hash is the only kind worth storing here.

   :py:meth:`DmsCertificateHolder._keyed_hash() <odoo.addons.dms_certify_portal.models.dms_certificate_holder.DmsCertificateHolder._keyed_hash>`
   raises a ``UserError`` naming the parameter rather than falling back to an
   unkeyed digest, so a missing key is loud at the moment somebody tries to
   write a hash under it.

Rotation is deliberately not offered anywhere: changing the key invalidates
every existing hash, so it can only be done by a migration that re-hashes from
a source that still has the plaintext.

.. note::

   ``PASSPORT_KEY_PARAM`` is declared **twice** — here and again as a
   module-level constant in ``models/dms_certificate_holder.py``, which does not
   import it from here. Two copies of one string; if one is ever edited the
   module silently writes hashes under a key nothing reads them with. See
   :ref:`PASSPORT_KEY_PARAM <dms_certificate_holder-PASSPORT_KEY_PARAM>`.

The portal languages
--------------------

``portal_language_codes()`` returns ``{'en'}`` plus one code per ``*.po`` file in
the addon's ``i18n/`` directory — today ``{'en', 'fr'}``, because the folder
holds ``fr.po`` and the ``.pot`` template, whose extension does not match.

Read off disk rather than hard-coded, which is what makes adding a language a
data change: drop ``es.po`` beside ``fr.po`` and Spanish is offered at the
counter with no code edited. The function is also **imported by the public
controller** (:doc:`controllers/verify`), which uses it to decide which
languages the switcher shows:

.. code-block:: python

   from ..hooks import portal_language_codes

A database with six languages installed for the back office must not offer an
embassy six buttons, five of which lead to an English page. So the hook and the
switcher read the same list from the same place, and cannot disagree about what
the portal is translated into.

.. warning::

   The code is taken as ``name[:-3]`` — everything before ``.po``. A catalogue
   named ``pt_BR.po`` therefore yields the code ``pt_BR``, and
   ``activate_portal_languages()`` then looks for ``pt_BR_PT_BR`` and for codes
   matching ``pt_BR\_%``, neither of which exists. It logs a warning and the
   language is never activated.

   **Name the catalogue with the bare language code** — ``pt.po``, not
   ``pt_BR.po`` — which is also what Odoo's own export produces for a portal
   catalogue. See :doc:`assets` for what the French catalogue actually covers.

``activate_portal_languages()`` installs what is missing
--------------------------------------------------------

For each code, in sorted order:

.. code-block:: text

   already active?   any installed lang whose code before the "_"
                     matches  ->  skip
   otherwise         try  <code>_<CODE>        e.g. fr -> fr_FR
                     then every res.lang whose code is like "<code>\_%",
                          active or not
                     first one _activate_lang() accepts, wins
                     none      ->  log a warning and carry on

The *skip* test compares on the part before the underscore, so a database that
already runs ``fr_BE`` is left alone rather than having ``fr_FR`` installed
beside it. The *fallback* list exists for the opposite case — an Odoo build that
knows ``fr_CA`` but not ``fr_FR``.

A language that cannot be installed produces a ``WARNING`` and **does not fail
the install**. Being unable to offer French at the counter is a degradation; a
module that refuses to install over it is worse.

.. admonition:: Why a fresh database needs this at all
   :class: important

   A new Odoo database has exactly one active language, English. Translations
   are not applied for inactive languages, so the French copy shipped in
   ``i18n/fr.po`` would sit in the file and never reach a page, and the public
   page's language switcher would have nothing to switch to — it lists only
   active languages whose code is in ``portal_language_codes()``.

   Activating a language is a **database-wide** change, not a portal-scoped
   one: it affects the back office too, and it is what makes Odoo load every
   installed module's French terms. That is a large side effect for a module to
   take on its own, and it is taken deliberately, because the alternative is a
   portal that is translated and does not show it. It is reversible from
   :menuselection:`Settings --> Translations --> Languages`.

Run again on upgrade
--------------------

``post_init_hook`` fires on **install only**. A database that already had this
module therefore never ran the language step, which is why
``migrations/19.0.3.0.0/post-migrate.py`` imports ``activate_portal_languages``
and calls it directly — see :doc:`migrations`.

The pepper step is not re-run, and does not need to be: the parameter either
exists already on such a database, or the module was installed before the key
existed at all, in which case
:py:meth:`_keyed_hash() <odoo.addons.dms_certify_portal.models.dms_certificate_holder.DmsCertificateHolder._keyed_hash>`
raises and tells the reader to reinstall or restore it.

.. note::

   ``hooks.py`` imports only ``odoo.modules.module.get_module_path`` and three
   modules from the standard library — no models, no ``fields``. That is why it
   is the one file in this addon besides :doc:`tools/seal` that the
   documentation build can import and ``autodoc`` can read directly; everything
   else here is hand-written. Keep it that way if you add to it.

See also
--------

* :doc:`models/dms_certificate_holder` — what the pepper is used for, and
  :ref:`PASSPORT_KEY_PARAM <dms_certificate_holder-PASSPORT_KEY_PARAM>`
* :doc:`data/ir_config_parameter` — every *other* parameter, all of which are
  shipped rather than generated
* :doc:`controllers/verify` — the other caller of
  ``portal_language_codes()``
* :doc:`migrations` — the 19.0.3.0.0 step that re-runs the language activation
* :doc:`assets` — the French catalogue and the surface it covers
* :doc:`../handbook/deployment` — backing up the pepper, as a checklist item
