import { Chatter } from "@mail/chatter/web_portal/chatter";

/**
 * The stock Odoo chatter with the composer taken out.
 *
 * A certificate's thread is a record, not a conversation: it carries the
 * lookups, the access requests and their verdicts, the state changes and the
 * planned activities. Nobody writes into it by hand, so the "Send message" and
 * "Log note" buttons — and the composer they open — are removed. Everything
 * else (activities, followers, attachments, search, the thread itself) is the
 * standard chatter, unchanged.
 *
 * Deliberately extends the *stock* Chatter rather than whatever chatter is
 * installed on other forms: see form_renderer_patch.js.
 */
export class CertificateChatter extends Chatter {
    static template = "dms_certify_portal.CertificateChatter";
}
