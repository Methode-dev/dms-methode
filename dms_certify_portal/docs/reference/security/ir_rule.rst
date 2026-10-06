ir_rule
=======

Source: :ghsrc:`security/ir_rule.xml`

One record rule, loaded ``noupdate="1"``. Most of this file is a comment, and
the comment is the more important half: it records what is **not** here and why
adding it would undo the module's security model.

The one rule
------------

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - External id
     - Model
     - Scope
   * - ``rule_dms_certificate_company``
     - ``dms.certificate``
     - ``[('company_id', 'in', company_ids)]``, attached to
       :ref:`group_certify_user <dms_certify_portal_groups-group_certify_user>`

*Certified documents: own company.* ``company_ids`` is the request's allowed
companies, so the registry follows the company switcher rather than the user's
default company — a shared-services desk that has two issuing companies enabled
sees both lists at once, which is what they are looking at the switcher for.

.. admonition:: Scoped on the certificate's company, not on its creator
   :class: important

   The obvious alternative is a rule over ``create_uid``, and it would file the
   entire registry under OdooBot.

   Every certificate is written under ``sudo``: a producing module calls
   :py:meth:`issue() <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.issue>`
   from its own flow, and it has to, because the passport fields on
   :doc:`../models/dms_certificate_holder` are restricted to the Registrar group
   and the module generating documents is not a user. So ``create_uid`` carries
   no information about who the document belongs to.
   :py:attr:`company_id <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.company_id>`
   does, is ``required=True``, and is the company whose name goes into the seal
   block.

Two details of the domain are worth stating because their absence is often a
bug elsewhere:

* There is **no** ``'|', ('company_id', '=', False)`` branch. The usual
  multi-company idiom includes one so that shared records stay visible, but
  ``company_id`` is required on this model — a company-less certificate cannot
  exist, so the branch would only ever widen the rule for nothing.
* The rule is **group-local**, not ``global``. It restricts members of
  :ref:`group_certify_user <dms_certify_portal_groups-group_certify_user>`,
  which by implication includes every Registrar. Nobody else has an ACL row on
  this model (:doc:`ir_model_access`), so in practice that covers every user who
  can read the model at all — but if you ever add a third group with its own
  ACL, remember that group rules do not apply to groups that are not listed,
  and that group would see every company's registry.

Nothing scopes the holders, the attempts or the types
-----------------------------------------------------

None of :doc:`../models/dms_certificate_holder`,
:doc:`../models/dms_certificate_attempt` or
:doc:`../models/dms_certificate_type` carries a ``company_id`` field, so there
is nothing for a company rule to filter on and none is defined.

For the holders that is sufficient rather than merely unavoidable: they are
reached through ``certificate_id``, and reading a one2many walks the parent's own
rules first. The types are a shared taxonomy on purpose — a document type is a
kind of document, not a company's property. The attempt log is genuinely
unscoped, and a multi-company deployment should know that: a Registrar in either
company reads every lookup against every document.

.. _ir_rule-no-public-acl:

The absence that matters: no public or portal ACL
-------------------------------------------------

.. important::

   There is deliberately **no** access rule granting ``base.group_public`` or
   ``base.group_portal`` any right on ``dms.certificate`` — not read, not
   anything — and none on the holders, the attempts or the types either.

   The public user reaches these records through
   :doc:`../controllers/verify` and nowhere else. Every read in that path is an
   explicit ``sudo()`` on a method that has already checked the rate limits and
   the second factor.

The comment in the file puts the consequence plainly, and it is worth repeating
in full because it is the trap this module is most likely to fall into during a
future debugging session:

   *If you ever find yourself adding a public ACL line to make something work,
   the fix is in the controller, not here: an ACL would also open*
   ``/web/dataset/call_kw``\ *, the ORM RPC endpoint and the website search, all
   of which bypass your rate limit and your passport check.*

The reasoning in longer form:

**An ACL is not scoped to your route.** ``ir.model.access`` is a property of the
model, not of the code path. Granting the public user read on
``dms.certificate`` grants it to every generic endpoint Odoo exposes to that
user as well — ``/web/dataset/call_kw`` most obviously, where an anonymous
caller can issue ``search_read`` with any domain they like.

**That bypasses both rate limits at once.** The per-address and per-reference
limits in :doc:`../models/dms_certificate_attempt` live in the controller's
submit handler. A ``call_kw`` read never goes near it, so the budget of five
tries per reference becomes unlimited reads of every reference.

**And it bypasses the second factor entirely.** The whole lookup design is
*reference plus one thing only the holder knows*. An ORM read answers without
either: no reference to guess, because ``search_read`` with an empty domain
returns the lot, and no passport to supply.

**A record rule cannot rescue it.** You could try narrowing the public user to
one certificate with a rule, but the rule would have to depend on what this
particular request has proved, and a record rule has no access to that. The
session-scoped permission a lookup earns is controller state; the ORM layer is
the wrong place to express it.

So the controller is the only door, and it stays the only door. See
:doc:`../../handbook/security-and-privacy` for the rest of the design refusals
that follow from this one, and :ref:`limits-no-website` for the related reason
this addon does not depend on ``website``.

.. note::

   ``noupdate="1"`` on the ``<data>`` element means a module upgrade will not
   rewrite this rule, so a deployment that has deliberately narrowed or widened
   the domain keeps its change. It also means the reverse: fixing the domain in
   this file does **not** reach a database that already has the record. Change
   it in :menuselection:`Settings --> Technical --> Record Rules`, or ship a
   migration.

See also
--------

* :doc:`dms_certify_portal_groups` — the group this rule is attached to
* :doc:`ir_model_access` — what a group can do once the rule has decided what it
  can see
* :doc:`../controllers/verify` — the only door, and the checks that stand in it
* :doc:`../models/dms_certificate` — ``company_id``, and the ``sudo`` in
  ``_match()``
* :doc:`../../handbook/security-and-privacy` — the same argument for the
  non-technical reader
