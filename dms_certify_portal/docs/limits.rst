Known limits
============

What this addon deliberately does not do, and where the edges are. Behaviour
that is confusing but *correct* is in :doc:`handbook/troubleshooting`; this page
is for the things that are genuinely limitations.

.. contents::
   :local:
   :depth: 1

.. _limits-no-website:

No ``website`` dependency
-------------------------

The manifest depends on ``base_setup``, ``web``, ``mail`` and
``dms_certify_host``, and **not** on ``website``. The portal is a plain public
controller rendering ``web.frontend_layout``, which ships with ``web``.

That is a decision, not an omission: depending on ``website`` installs the site
builder, themes, snippets, the inline editor and the first-run configurator for
what is two inputs and a verdict, and every one of those is additional public
surface area. What it costs:

**Odoo serves no** ``robots.txt``. That route belongs to ``website``. The
pages themselves send an ``X-Robots-Tag: noindex, nofollow, noarchive`` header
and a ``robots`` meta, which is what actually stops a compliant crawler; the
file is served by nginx instead (:ref:`deployment-nginx`). A deployment that
forgets the nginx block loses the file and keeps the header.

**No** ``/fr/`` **language prefixes.** Language URLs come from
``http_routing``, which comes from ``website``. So the switcher rides a ``lang``
query parameter — ``/?lang=fr`` — and then sticks to the session for the rest
of the visit. Two consequences: a French result page cannot be bookmarked or
shared *as French*, and a shared embassy workstation keeps whatever language the
previous agent chose until the session ends.

**No website configurator** on install, and no theme. The portal's appearance
is :doc:`reference/assets` — one SCSS file and one small JS file — and is
changed by editing them, not from an editor.

``hide_expired`` is shipped and never read
------------------------------------------

``dms_certify_portal.hide_expired`` exists as a system parameter (default
``False``), as a Boolean on the Settings page (:guilabel:`Hide expired
documents`), and in both translation files. **Nothing in the codebase reads
it.**

The practical effect is that an expired document *always* reads as "authentic
but out of date" on the public page, whatever the box says. That happens to be
the better default — telling an agent that a genuine document has expired is
more useful than telling them it does not exist — but the setting is a lie, and
ticking it does nothing.

The README compounds this by advertising a ``_hide_expired()`` override point.
That method does not exist either. The real override points are the three in
:ref:`issuing-override-points`.

Recorded as two failing tests —
``test_hide_expired_hides_an_expired_document`` and
``test_the_documented_hide_expired_override_point_exists``. See
:ref:`testing-known-defects`.

.. todo::

   Decide which way to resolve ``hide_expired``: implement it in
   ``_compute_public_state`` / the controller, or delete the parameter, the
   Settings field and the two ``.po`` entries. Leaving a settings box that does
   nothing is the worst of the three. The README's ``_hide_expired()`` row has
   to go either way.

.. _limits-boolean-settings-save:

A Settings save disarms two features of the seal
------------------------------------------------

``seal_guilloche``, ``seal_microtext`` and ``notify_on_lookup`` are shipped as
``"1"`` in :doc:`reference/data/ir_config_parameter` and read strictly:

.. code-block:: python

   guilloche=param('seal_guilloche', '1') == '1',     # models/dms_certificate.py:535
   microtext=param('seal_microtext', '1') == '1',     # :536

``res.config.settings`` writes a Boolean ``config_parameter`` as ``"True"``, so
**the first time anybody saves the Settings page all three switch themselves
off.** Nothing is logged, nothing in the UI changes, and the boxes stay ticked.

Two of the three are anti-forgery features of a document that goes to an
embassy: every page sealed afterwards loses its guilloche border and its
microtext footer. The third stops the issuing desk hearing about lookups.

``allow_download`` is immune, and shows the shape the other three want — it is
read through ``_bool_param()`` in :doc:`reference/controllers/verify`, which
accepts ``('True', 'true', '1')``.

Recorded as four failing tests, including
``test_a_shipped_boolean_parameter_reads_the_same_before_and_after_a_save``,
which states the invariant on its own. See :ref:`testing-known-defects`.

.. _limits-disclosure-fails-open:

The disclosure branch fails open
--------------------------------

``_public_bytes`` decides whether to redact like this:

.. code-block:: python

   if self.disclosure != 'confirm':      # models/dms_certificate.py:471
       return <the unredacted sealed copy>

Redaction is therefore the exception rather than the rule. Only the exact
string ``confirm`` triggers it, so a module adding a third mode through
``selection_add`` — a per-embassy variant, say — would serve the whole document
with every holder's name, date of birth and passport visible, without having
written a line of disclosure logic.

``second_factor`` is the counter-example and the right pattern: an unrecognised
value there fails *closed*, because the matching code asks for one specific
hash.

Recorded as
``test_an_unrecognised_disclosure_mode_does_not_serve_the_whole_document``,
which demonstrates the breach rather than describing it — the second holder's
passport appears on the page served to the first. See
:ref:`testing-known-defects`.

.. todo::

   Branch on ``== 'full'`` instead, so an unknown mode redacts. The change is
   one line; the reason it has not been made is that it needs confirming that
   no deployment relies on a non-``confirm``, non-``full`` value already.

Only a producing module can register a document
-----------------------------------------------

There is no upload screen, and no "certify this file" wizard in this addon. A
``dms.certificate`` is created by code — ``issue()``, or a plain ``create()`` —
from a module that depends on this one. See :doc:`handbook/issuing`.

The reason is that the people listed on a document have to come from somewhere:
a certificate with no holder cannot be certified at all (``certify()`` refuses
it), because nobody could open it. An entry screen would have to ask for the
crew by hand, and a hand-typed crew that disagrees with the page is worse than
no entry screen.

``dms.certificate`` does carry a ``source_attachment_id`` default for
``_certify_source()``, so a scanned attestation dropped into an attachment
*can* be sealed from the back office. What it cannot do is name its own crew.

reCAPTCHA is opt-in, and silent when absent
-------------------------------------------

``google_recaptcha`` is not in ``depends``. The controller looks for
``ir.http._verify_recaptcha_token`` at request time and, if the method is not
there, returns ``True`` and moves on. Install the module and set the keys and
enforcement begins with no code change — but an instance that never installed
it has no captcha and says nothing about it.

Two further edges worth knowing. The hook returns ``True`` when no site key is
configured, so an *installed but unconfigured* ``google_recaptcha`` is
indistinguishable from an absent one. And the verifier's signature has moved
between Odoo versions; the controller tries two call shapes and swallows
anything else as a failure, which fails closed but also means a signature
change in a future Odoo shows up as "every lookup fails the captcha" rather
than as a traceback.

The attempt log grows until the cron prunes it
----------------------------------------------

``dms.certificate.attempt`` is written on every hit of the public form —
matches, refusals, throttles, lockouts, captcha failures and mismatch reports.
It is both the throttle counter and the audit trail, so nothing can be dropped
from it at write time.

One daily cron, ``_gc_attempts``, deletes rows older than
``dms_certify_portal.retention_days``. If the cron is disabled or the server
runs with ``max_cron_threads = 0``, the table grows without bound and nothing
warns you.

**Ninety days is a default, not a legal opinion.** It is long enough to
investigate an incident and short enough to defend, and that is the whole
argument behind it. The retention period is a data-protection decision; agree
it with whoever signs off the processing record. See
:doc:`handbook/security-and-privacy`.

A database dump contains passport numbers
-----------------------------------------

``dms.certificate.holder.passport_number`` is stored in plain text, restricted
at the field level to *Certification: Registrar*.

Field groups are an ORM control. They do not apply to ``pg_dump``, to a
replica, or to anybody with a psql prompt. A dump of this database is
identity-document data and has to be handled as such.

The choice is deliberate and argued in :doc:`handbook/security-and-privacy`:
the same numbers are already inside the sealed PDF in the same DMS and on the
crew contact, so the registry is not the only copy, and an operator correcting
a mistyped number has to be able to see what is there. Matching never touches
the stored number — three keyed hashes alongside it do that.

Losing the pepper is unrecoverable
----------------------------------

``dms_certify_portal.passport_key`` is generated once, at install. Every
second-factor hash is an HMAC under it.

There is no key history, no secondary key, and no re-derivation path. If the
parameter is deleted or overwritten, ``_keyed_hash`` starts producing different
digests and **no document opens** — the lookup form refuses every correct
passport with the same message it gives a wrong one. The stored passport
numbers are still there, so a recovery script could re-hash from them; nothing
in the module does that for you, and a holder whose number was never stored
cannot be recovered at all.

Back the parameter up with the filestore, not instead of it.

Redaction measures at registration, and can fall back
-----------------------------------------------------

Under confirm-only disclosure the public copy is built per lookup from
*positions* recorded when the document was registered —
``redaction_boxes`` on each holder, stamped with the ``boxes_source_hash`` of
the document they were measured against.

If the document changes underneath those measurements, the hash no longer
matches and the boxes are discarded. The portal then falls back to searching
the page for the stored values. That fallback is weaker in one specific way:
searching matches a string wherever it appears, so a surname that is also a
word in the letter body gets blanked too, and a passport number that was never
stored cannot be searched for at all.

The fallback is logged at INFO (``has no current positions for …; redacting by
value instead``). A document whose source keeps changing after registration
will produce that line on every single lookup and nobody will see it.
Re-register, or call ``stash_redaction()`` again after the change.

``_public_bytes`` fails closed, and that is a nuisance by design
----------------------------------------------------------------

After redacting, ``_public_bytes`` hashes every surviving word on the page and
compares it against each other holder's stored details — names and first names
directly, passport numbers through the keyed hash, which is the only way to
look for a number nobody kept. If anything survives, it returns ``b''``.

Every caller treats ``b''`` as "show nothing": the result page renders with no
document images at all, the download 404s. The agent sees a verdict and a
reference and no page.

That is the intended trade. An empty page is a nuisance; a page carrying
somebody else's passport number is a breach. But it does mean a single
redaction bug degrades to *silently blank for everyone* rather than to an
error, and the only trace is an ERROR line in the server log naming what
survived. How to confirm it is in :doc:`handbook/troubleshooting`.

Sealing cannot reflow a page
----------------------------

The stamp is drawn onto finished bytes. When the seal block's corner is already
occupied by the document's own content, there is no way to make room except to
shrink the page's content into a slightly smaller box — about 8% on A4 — and
stamp into the strip that frees. That is what :guilabel:`Make room for the
stamp` chooses between, and ``auto`` (the default) only does it for the
documents that need it.

A document that already fills its last page edge to edge therefore comes out
very slightly reduced. The alternative modes are *always* shrink, or *never*
shrink and let the stamp cover whatever was there.

Uninstalling
------------

Dropping this addon drops every certificate, so every document in circulation
stops verifying. The guards that stop you deleting an issued entry record by
record do not apply to an uninstall. See :doc:`installation`.

Testing
-------

The suite is four modules — one of which, ``test_known_defects.py``, is
**deliberately failing**: it records the defects on this page as tests so they
cannot be forgotten. A run that is expected to be green has to exclude it with
``--test-tags '/dms_certify_portal,-known_defects'``. See
:ref:`testing-known-defects`.

The other three have an audited list of their gaps by severity in
:doc:`development/testing`. The ones worth knowing before relying on the
corresponding path:

* ``migrations/`` has no test coverage at all. The three post-migrate steps are
  exercised only by running them.
* ``tools/seal.py`` is tested through the model, never directly, so the
  geometry decisions (band mode, corner collision) are asserted as "the
  reference is on the sealed page", not as layout.
* The captcha branch is never exercised — no test installs or fakes
  ``google_recaptcha``.
