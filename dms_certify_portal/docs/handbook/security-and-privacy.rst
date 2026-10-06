Security and privacy
====================

An anonymous public form in front of a registry of identity-document data is an
unusual thing for an Odoo addon to be, so most of this addon's design is a
series of refusals. This page collects them with their reasoning, and then says
plainly what personal data is held and what you have to settle before going
live.

.. contents::
   :local:
   :depth: 2

The design refusals
-------------------

Each of these is something the addon deliberately does **not** do. They are
listed together because they only make sense together: several are cheap
individually and load-bearing as a set.

No public ACL
^^^^^^^^^^^^^

There is no ``ir.model.access`` line granting ``base.group_public`` or
``base.group_portal`` any right on ``dms.certificate``, or on anything else in
this addon. The public controller runs every ORM call under ``sudo()`` instead.

.. admonition:: An ACL does not open one door, it opens several
   :class: important

   If you ever find yourself adding a public ACL line to make something work,
   the fix is in the controller. An ACL on this model would also expose it
   through ``/web/dataset/call_kw`` — the ORM's own RPC endpoint — which has
   **no rate limit, no second factor and no session token** in front of it. The
   same read access the portal takes thirty lines of checks to grant would be
   available for the asking.

   The reasoning is recorded as a comment in
   :ghsrc:`security/ir_rule.xml`, where somebody about to add the line will
   see it.

The authorisation here is the second factor, the session token, the token's
expiry and the two rate limits. The access matrix has no part in it.

One refusal for every failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*"Unknown reference"* and *"that reference exists but the second check is
wrong"* are never distinguished. Both get *"Those two details do not open a
document"*, and the page says out loud that it will not tell you which failed.

Splitting them would hand anybody an enumeration oracle: walk the reference
space with an arbitrary passport value, keep the hits, and then attack a known
reference with four characters of secret in front of it.

The full catalogue, including what each refusal *does* disclose, is
:ref:`verification-refusals`.

Constant time, including when there is nothing to compare
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Identical wording is worthless if the two cases take measurably different
amounts of time, so two things are done about it.

The hash comparison uses ``hmac.compare_digest``, so a nearly-right value does
not take longer to reject than a wholly wrong one.

And when **no certificate is found at all**, the matcher computes a throwaway
HMAC over sixteen random bytes before returning:

.. code-block:: python

   if not certificate:
       Holder._submitted_factor_hash('pptfull', secrets.token_hex(16))
       return empty

Without it an unknown reference would return after one indexed ``SELECT`` while
a known one paid for an HMAC — and that difference is the oracle the identical
wording was meant to close. The mode named in that call is arbitrary; the point
is that it costs one HMAC either way.

POST-Redirect-GET
^^^^^^^^^^^^^^^^^

The second factor arrives in a ``POST`` body, is matched, and is then dropped.
It is never put into a URL, so it never reaches browser history, never leaves in
a ``Referer`` header, and never lands in an nginx access log — three places that
are routinely backed up, shipped to a log aggregator and read by people who were
never meant to see a passport number.

What goes into the URL instead is an opaque, session-bound token. It resolves
only against the session that minted it, it expires, and it is compared in
constant time. ``Referrer-Policy: no-referrer`` closes the remaining leak, which
is the *reference* rather than the passport: without it, clicking any link on
the result page would hand the result URL to the link's target.

Non-sequential references
^^^^^^^^^^^^^^^^^^^^^^^^^

No counter, no ``ir.sequence``. A sequential component would tell anyone holding
two documents how many were issued in between — commercially interesting, and
occasionally politically interesting, for a consular operation — and it would
make the space walkable, which leaves the second factor as the only secret.

Thirty random bits from ``secrets.choice``, in an alphabet chosen for
transcription rather than cryptography. See :doc:`concepts`.

Redaction that is verified rather than trusted
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Under the default disclosure mode the page an embassy sees is rebuilt per lookup
with everyone else's lines **removed from the content stream** — a real
redaction, not a black rectangle drawn over text that is still in the file and
still copy-pasteable.

Then the result is checked. Every surviving word is compared against what is
stored for each other holder, with passport numbers checked by hashing each
surviving word, which is the only way to look for a number nobody kept. If
anything survived, **nothing is served at all**.

An empty page is a nuisance; a page carrying somebody else's passport number is
a breach. The full mechanism, including how it degrades, is
:ref:`sealing-redaction`.

Nothing about the submitted secret is stored
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The attempt log records the reference that was tried, the address, the user
agent and the outcome. It stores **no form of the submitted second factor — not
even a hash**, because a per-attempt hash would let anyone with table access
correlate attempts across documents and work out which values were being tried
where.

Two gates in front of the bytes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The portal never links ``/web/content/<id>``. That route is readable by anyone
who knows the attachment id as soon as the attachment is public, which would
detach the file from the second check entirely — no token, no session, no rate
limit. The download streams through the controller instead, behind the same
session gate as everything else.

And the pages themselves are served as **images**, not as a PDF, because a PDF
viewer carries its own save, print and text-extraction and none of those pass
back through the gate. Comparing a screen with a sheet of paper needs no more
than a picture.

What personal data this holds
-----------------------------

Three kinds, and they have different answers, so it is worth being precise.

Passport numbers — **stored**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In ``dms.certificate.holder.passport_number``, in plain text, restricted at the
field level to *Certification: Registrar*. Alongside each sit three keyed
hashes, and **matching a lookup always goes through the hashes, never through
the stored number**.

This is the addon's most consequential privacy decision, so here is the whole
argument for it:

* The same numbers are **already** inside the sealed PDF, in the same DMS, and
  on the crew contact record. The registry is not a new copy of anything.
* An operator correcting a mistyped number has to be able to see what is
  actually there. A write-only field means a document that nobody can open and
  nobody can diagnose.
* Hashing alone would not let the redaction leak check work. That check hashes
  every word surviving on a redacted page and compares it against the stored
  hash — but the *fallback* redaction, when measured positions have gone stale,
  can only search for values it has. A registry that kept only hashes would
  have to refuse to serve any page whose measurements had drifted.

And here is the cost, stated as plainly:

.. warning::

   **A database dump contains passport numbers.** Field groups are an ORM
   control; they do not apply to ``pg_dump``, to a read replica, or to anybody
   with a ``psql`` prompt. A dump of this database is identity-document data and
   has to be handled, transported and retained as such.

   Under the GDPR a passport number is not special category data under Article
   9, but supervisory authorities treat mishandling of identity documents
   harshly, and French CNIL guidance on identity documents is stricter than the
   GDPR floor.

The ``dms_certify_portal.passport_key`` pepper is in the same dump. It is what
makes hashing short values worth doing at all — four characters or a date would
fall to a wordlist instantly under an unkeyed digest — so a dump compromises
both the numbers and the thing protecting the hashes.

Names and dates of birth
^^^^^^^^^^^^^^^^^^^^^^^^

Of everyone listed on a certified document: surname, first name, date of birth,
rank. Readable by *Certification: Agent*, and that is correct — an agent
answering a telephone call about a document has to be able to see who is on it.

They are held **for as long as the document stays verifiable**, which is longer
than the port call it was about. A document has to keep answering after it has
been used, or an embassy auditing its own file six months later is told the
letter they acted on does not exist.

Under the default disclosure mode none of this reaches the public page except
the one person who opened it, by name and rank. Under ``full`` disclosure the
whole list does, with dates of birth — which is why ``full`` is a per-document
decision an issuer makes deliberately and not a default.

IP addresses
^^^^^^^^^^^^

In ``dms.certificate.attempt``, on every hit of the public form. They are not
optional: the log **is** the per-address rate limit's counter as well as the
audit trail, so nothing can be dropped from it at write time.

Ninety days by default, pruned by a daily cron. See `What to settle before going
live`_.

.. admonition:: The desk is shown "An external user", the row keeps the address
   :class: important

   Every chatter message this addon writes about a lookup says *"An external
   user"*. The address is never written into the thread, and that asymmetry is
   deliberate on both sides.

   The thread is read by an operations manager, for whom an IP address is
   nothing they can act on — and resolving it to *"Consulate of France,
   Yangon"* would mean either a third-party lookup service or a hand-maintained
   list of embassy ranges, neither of which is worth it yet.

   The *row* keeps the address because the rate limit needs it and because an
   investigation needs it. Which means the two have different retention
   characteristics: a chatter message outlives the attempt row it describes and
   carries no personal data forward, which is the right way round.

Which is also why the certificate's successful-lookup counter is a plain stored
number rather than a count over the log: how many times a document was checked
should outlive the record of who checked it.

What to settle before going live
--------------------------------

Four decisions, none of which this addon can make for you.

**1. The lawful basis, written down.** For the registry (names, dates of birth,
passport numbers) and for the attempt log (addresses) separately — they are not
the same processing and may not have the same basis.

**2. The retention period.** Ninety days for the attempt log is a starting point
chosen because it is long enough to investigate an incident and short enough to
defend. It is not a legal opinion. The registry's own retention is a different
question again, and harder: a certificate cannot be deleted without making a
genuine document read as forged, so "retention" there means deciding when a
document stops needing to be verifiable at all.

**3. Whether a DPIA is required.** Consider it likely rather than unlikely. The
processing is at scale, it concerns identity documents, and the whole purpose is
disclosure to **embassies outside the EEA** — a cross-border transfer to third
countries, triggered by an anonymous request, with no contract between you and
the person making it.

**4. Who gets *Certification: Registrar*.** That is the group that can read
passport numbers, and it is the only access decision in this addon with a
privacy consequence rather than a convenience one. *Certification: Agent* is
read-only and cannot see them at all. :doc:`administration` has both.

Also worth putting in the operational runbook:

* the pepper is in the backup procedure, and a post-restore smoke test proves
  a known document still opens (:doc:`deployment`);
* somebody is nominated to act on a **reported mismatch** within minutes, since
  that is the one signal in the system that means a document may be forged;
* somebody looks at :menuselection:`Consular --> Reporting --> Verification
  attempts` occasionally. A reference locking raises an activity, but an
  attacker slow enough to stay under every limit — one attempt a minute, spread
  across addresses — is a *shape* in that log, and nothing currently looks for
  shapes.

.. important::

   I am not a lawyer, and none of the above is legal advice. Run it past whoever
   handles your data protection.

Known weaknesses, stated honestly
---------------------------------

Not design decisions — gaps.

* **The default second factor is four characters.** A few thousand
  possibilities. What protects a document is the per-reference lock, not the
  secret's entropy. For a single-holder document with a long shelf life, choose
  ``pptfull``.
* **A date of birth is a weak factor.** It is frequently printed elsewhere on
  the same paper the agent is holding, and on many other documents. Use ``dob``
  only for documents that genuinely carry no passport number.
* **The redaction fail-closed path is silent to the user.** A leak check that
  trips renders the result page with no document images and logs one ``ERROR``
  line. The agent sees a verdict and no page, and nothing tells them why.
* **No captcha unless you install and key one**, and no signal when you have
  not (:doc:`deployment`).
* **The attempt log is not analysed.** It is a counter and an archive; nothing
  alerts on a pattern.
* **The captcha branch has no test coverage at all** — see
  :doc:`../development/testing` for the audited list of gaps.

See also
--------

* :doc:`concepts` — :ref:`concepts-second-factor` and
  :ref:`concepts-disclosure`
* :doc:`sealing` — :ref:`sealing-redaction` in full
* :doc:`verification` — :ref:`verification-refusals`
* :doc:`deployment` — the pepper, the allowlist, reCAPTCHA
* :doc:`administration` — the two groups, and retention
* :doc:`../limits` — a dump contains passport numbers; losing the pepper is
  unrecoverable; ``_public_bytes`` fails closed
* :doc:`../reference/security/ir_rule` — the absence of a public ACL, in the
  source
* :doc:`../reference/models/dms_certificate_attempt` — both limits, and the
  requester label
