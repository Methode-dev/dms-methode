/*
 * The certificate chatter, in a real browser.
 *
 * Everything about this chatter is decided client-side: the server ships
 * mail.Chatter and our primary-inherit template side by side and never
 * evaluates the xpaths, and the component itself is chosen at render time
 * (form_renderer_patch.js). So Python can only check the xpaths in isolation
 * — TestChatterTemplate does that — while this checks the form an issuer sees.
 */
import { registry } from "@web/core/registry";

/** Throw naming what was found, rather than failing on a bare selector. */
function assertChatter(chatter) {
    for (const [what, selector] of Object.entries({
        "A Send message button": ".o-mail-Chatter-sendMessage",
        "A Log note button": ".o-mail-Chatter-logNote",
        "A composer": ".o-mail-Composer",
    })) {
        if (chatter.querySelector(selector)) {
            throw new Error(
                `${what} (${selector}) is on the certificate chatter: the ` +
                `thread records what happened, it is not written into.`
            );
        }
    }
    // And it is still the chatter, not an empty box where one used to be.
    for (const [what, selector] of Object.entries({
        "The Activity button": ".o-mail-Chatter-activity",
        "The followers": ".o-mail-Followers",
        "The attachment button": ".o-mail-Chatter-attachFiles",
    })) {
        if (!chatter.querySelector(selector)) {
            throw new Error(`${what} (${selector}) is missing.`);
        }
    }
}

registry.category("web_tour.tours").add("dms_certify_portal_chatter_tour", {
    test: true,
    steps: () => [
        {
            content: "open the certificate from the list",
            trigger: ".o_list_view .o_data_row td:contains(ICS-)",
            run: "click",
        },
        {
            content: "the chatter mounted, and nothing can be posted into it",
            trigger: ".o_form_view .o-mail-Chatter",
            run() {
                assertChatter(this.anchor);
            },
        },
    ],
});
