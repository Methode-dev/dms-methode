# DMS Certificate Portal

Seals consular documents, and gives embassies a public, account-free page on
which to check them. Odoo 19.

**Sealing** stamps an already-produced PDF: a diagonal marking, a guilloche
border, a microtext footer, and a block carrying the QR code, the reference and
the document's fingerprint. It is a post-process, so no report template is ever
touched, a re-stamp costs no re-render, and a document nobody here generated —
a scanned attestation dropped in a folder — can be sealed the same way.

**Verification** is `/verify`. An agent types the reference printed beside the
QR code plus the second check the issuer chose — the last four characters of a
listed passport, the whole number, or a listed date of birth — and gets the
document's status and the page itself. No `res.users` record, no portal
invitation, no shared password.

## No website builder

This module does **not** depend on `website`. The portal is a plain public
controller rendering `web.frontend_layout`, which ships with `web`.

That is deliberate. Depending on `website` installs the site builder, themes,
snippets, the inline editor and the first-run website configurator — none of
which a two-field verification form needs, and all of which are additional
public surface area. It also means no configurator wizard on install.

Consequences worth knowing:

- **robots.txt** is a website feature, so Odoo serves none. This repo's nginx
  config serves one (see *Deployment*). The pages also send `X-Robots-Tag` and
  a `robots` meta, which is what actually stops compliant crawlers.
- **No `/fr/verify` language prefixes.** Without `http_routing` there are no
  language URLs, so the switcher rides a `lang` query parameter and then sticks
  to the session. The module ships French (`i18n/fr.po`) and activates the
  languages it has copy for on install — otherwise a fresh database has only
  English active and the switcher has nothing to switch to.
- **reCAPTCHA is opt-in.** Install `google_recaptcha` separately and set the
  keys; the controller detects the hook and starts enforcing it with no code
  change. Leave it uninstalled and the captcha step is skipped.

## What this module is and is not

It owns **sealing** and **verification** for any document: the stamp, the
registry of verifiable entries, the public controller, the rate limiting and
the audit trail.

It does **not** produce documents, and knows nothing about what they are for.
Ships, ports, crews and the vocabulary that goes with them live in whichever
module generates the documents — see `operations_certify` for the one that
does. That is what keeps the public attack surface small: a bug in a QWeb
template here cannot reach your business records, because the public templates
only ever receive a whitelisted dict.

## Installing

```bash
# Odoo must run with --proxy-mode behind your reverse proxy, otherwise every
# request looks like it comes from the proxy and the rate limit becomes global.
odoo -d yourdb -i dms_certify_portal --proxy-mode
```

Installation generates a random HMAC pepper into the system parameter
`dms_certify_portal.passport_key`. **Back it up with your filestore.** Lose it
and every stored passport hash becomes unverifiable.

Passport numbers themselves are stored, readable by a certification registrar
and not by an agent. That is a deliberate choice — the same numbers are already
inside the sealed PDF in the same DMS and on the crew contact, so the registry
is not the only copy, and an operator correcting a mistyped number has to be
able to see what is there. It does mean **a database dump contains passport
numbers**; treat the dump accordingly, and see *Data protection* below.

Then, in Settings → General Settings → *Document verification portal*, set the
rate limit, the result lifetime and the log retention.

## Wiring up your generation module

Depend on `dms_certify_portal`, declare the kinds of document you produce as
data records, and register an entry when you produce one.

```xml
<record id="certificate_type_visa_letter" model="dms.certificate.type">
    <field name="name">Visa letter</field>
    <field name="code">visa_letter</field>
    <!-- register one automatically the moment it is generated -->
    <field name="auto_stamp" eval="True"/>
</record>
```

```python
entry = self.env['dms.certificate'].issue({
    'type_id': self.env.ref('my_module.certificate_type_visa_letter').id,
    'movement_date': self.travel_date,
    'facts_json': json.dumps([
        # a label may be a string, or a mapping of language to string
        {'label': {'en': "Destination", 'fr': "Destination"},
         'value': self.destination_id.name},
    ]),
}, holders=[{
    'name': partner.name,
    'first_name': partner.first_name,
    'date_of_birth': partner.date_of_birth,
    'passport_number': partner.passport_number,   # stored, and hashed for matching
} for partner in self.traveller_ids],
   source=self,
   redaction_needles=self.traveller_ids.mapped('passport_number'))

entry.reference    # print this beside the QR code
entry.verify_url   # what the QR code encodes
```

`issue()` creates the entry **and seals it**. To register a document without
sealing it yet — the usual case, because the marking is chosen by looking at
the stamped page — create it directly and call `stash_redaction()`:

```python
entry = self.env['dms.certificate'].sudo().create({...})
entry.stash_redaction(passport_numbers)
```

That last call matters. It measures where each listed person appears, so a
confirm-only lookup can blank everyone except the person who opened it without
searching the page again for strings that might also appear in the letter body.
If the document later changes underneath those measurements, the portal falls
back to searching for the values.

Withdrawing a document:

```python
entry.action_revoke(reason="Superseded by %s" % new_entry.reference)
```

### Extension points

| Method | Why you'd override it |
|---|---|
| `_certify_source()` | Point the seal at your own storage instead of an attachment. Return `(filename, bytes)` |
| `_generate_reference(place_code)` | Change the reference shape. Keep ≥30 bits of entropy in it |
| `_get_public_values()` | Add fields to the result page. Call `super()` and update the dict |
| `_hide_expired()` | Decide whether an expired document reads as expired or as not found |

Document types are records, not a selection, and this module ships **none** of
its own: what a document *is* belongs to whoever produces it. Add a
`dms.certificate.type` — in XML as above, or from a hook if the list already
exists somewhere in your module — and it appears in Settings, where an
administrator decides whether documents of that kind are stamped on
generation.

`_get_public_values()` is the security boundary. Return plain data from it,
never a recordset — a template that receives a record can walk to
`doc.partner_id.email` or `doc.message_ids`, and eventually someone will.

## Why the flow looks the way it does

**POST-Redirect-GET.** The passport is submitted in a POST body, matched, then
discarded. A fresh session-bound token goes in the URL instead. The passport
therefore never lands in browser history, in a `Referer` header, or in your
nginx access log.

**One error message for every failure.** "Unknown reference" and "wrong
passport" are never distinguished. Splitting them turns the form into an oracle
for enumerating valid references.

**Constant-time comparison.** `hmac.compare_digest`, and a throwaway hash is
computed when no record is found, so a missing reference and a wrong passport
cost roughly the same wall time.

**No public ACL.** There is deliberately no `ir.model.access` line for
`base.group_public` on `dms.certificate`. The controller is the only door. If
you ever add one to make something work, you have also opened
`/web/dataset/call_kw` and the website search, both of which bypass the rate
limit and the passport check entirely.

**High-entropy references, with no counter.** `ICS-2026-DKK-4KQ7-9B` — prefix,
year, the last three characters of the port's UN/LOCODE, then thirty random
bits. Deliberately not sequential: a counter would tell anyone holding two
documents how many were issued in between, and would make the space walkable,
leaving the second check as the only secret. The alphabet is Crockford base32,
which drops `I`, `L`, `O` and `U`, so an agent transcribing from a faxed page
cannot turn a one into an I. The public page says so in as many words — if you
change the alphabet, change that sentence.

**Redaction that is checked.** Under confirm-only disclosure the page an
embassy sees hides everyone except the person whose passport opened it. It is
built per lookup from positions measured when the document was registered, and
the result is then searched for what should have gone: the other holders'
names, and their passports by keyed hash. If anything survives, nothing is
served. An empty page is a nuisance; a page with somebody else's passport on it
is a breach.

## Deployment

- [ ] `--proxy-mode` on, and the proxy sets `X-Forwarded-For`. Without it every
      request looks like it came from the proxy and the per-address limit
      becomes a single global one.
- [ ] **Settings → Document verification portal → Public verification URL.**
      This goes on paper. It is printed beside the QR code and encoded inside
      it, on documents that circulate for months, and a document already in an
      embassy's file cannot be re-pointed. Set it before issuing anything.
- [ ] **Portal company** — whose name, address and contact details the public
      page carries.
- [ ] `web.base.url` correct, and `web.base.url.freeze` set to `True`
- [ ] Seal house style agreed (Settings → *Certified documents: the seal*), and
      **Stamp on generation** ticked for the document types that should
      register themselves
- [ ] `dms_certify_portal.passport_key` in the backup procedure — lose it and
      every stored hash becomes unverifiable
- [ ] Retention period agreed with whoever signs off the processing record
- [ ] `google_recaptcha` installed and keys set (Settings → Integrations) —
      optional; the controller picks it up with no code change
- [ ] If the embassies have static egress IPs, allowlist them in nginx. That
      single block is worth more than everything else here.

### nginx

Already configured in this repository, in both `nginx/nginx.conf.template` and
`nginx/nginx.dev.conf` — the zones at the top of the file and the `/verify` and
`/robots.txt` locations in the Odoo vhost. What follows is the shape of it, for
deployments outside this repo.

Note the two limits. One lookup is not one request: the form, the POST, the
result page, one image per page of the document and often the download come to
six or more. A single limit sized for the POST throttles a counter doing its
job, and one sized for the page images does not slow a guesser down.

```nginx
# Keyed on the address only for POSTs. nginx does not account a request whose
# key is empty, so GETs never touch this zone.
map $request_method $verify_submit_key {
    POST    $binary_remote_addr;
    default "";
}

limit_req_zone $verify_submit_key  zone=verify_submit:10m  rate=20r/m;
limit_req_zone $binary_remote_addr zone=verify_traffic:10m rate=120r/m;

location /verify {
    limit_req zone=verify_submit  burst=5  nodelay;
    limit_req zone=verify_traffic burst=40 nodelay;
    limit_req_status 429;

    # If the set of embassies is known and they have static addresses:
    # allow 203.0.113.0/24;
    # deny all;

    proxy_pass http://127.0.0.1:8069;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Odoo serves no robots.txt without the website module.
location = /robots.txt {
    default_type text/plain;
    return 200 "User-agent: *\nDisallow: /verify\n";
}
```

Measured against that config: twenty rapid submissions from cold let six
through and refuse fourteen; a realistic lookup — one POST and six page
requests — passes untouched.

The application limits sit behind these and are the ones that actually protect
a document: a reference locks after five failed attempts **from any address**,
because someone guessing at one document will change address and an agent
mistyping will not.

## Data protection

This module holds three kinds of personal data, and it is worth being precise
about which, because they have different answers.

**Passport numbers are stored**, in `dms.certificate.holder`, readable by a
certification registrar and not by an agent. They are identity-document data:
under GDPR not special category data under Article 9, but sensitive enough that
supervisory authorities treat mishandling harshly, and French CNIL guidance on
identity documents is stricter than the GDPR floor. **A database dump contains
them.** Alongside each is a keyed hash, which is what a lookup is matched
against — the hash is the access control, the stored number is for the operator
who has to correct a typo.

**Names and dates of birth** of everyone listed on a certified document, for as
long as that document stays verifiable — which is longer than the port call,
because a document has to keep verifying after it has been used.

**IP addresses**, in the attempt log. The default 90-day retention is a
starting point, not a legal opinion. Note the asymmetry the desk sees: the log
shows "An external user", never an address, while the row underneath keeps the
address for the rate limit and the audit trail.

Before going live:

- Write down the lawful basis for the processing and the retention period
- Check whether a DPIA is required for the expected volume and for the
  cross-border transfers involved — embassies outside the EEA make this likely
- Decide who gets *Certification: Registrar*, since that is the group that can
  read passport numbers

I'm not a lawyer, and none of the above is legal advice — run it past whoever
handles your data protection.

## Ideas worth adding later

- Watermark the streamed PDF with the requesting IP and a timestamp, so a leaked
  copy points back to the lookup that produced it
- Alert on a pattern rather than a threshold. A reference locking already
  raises an activity, but an attacker slow enough to stay under every limit —
  one attempt a minute, spread across addresses — still shows up as a shape in
  the attempt log that nothing currently looks for.
- A per-embassy path prefix (`/verify/ma-rabat`) with a pre-shared value, which
  gives you per-embassy rate limits and per-embassy revocation
- A dedicated verification hostname, so the reference printed on a document
  does not carry the hostname of your ERP and the public name exposes four
  routes rather than all of Odoo
- Certifying uploaded documents. Today only a module that generates them can
  register one, because the crew has to come from somewhere; an entry screen
  would lift that
