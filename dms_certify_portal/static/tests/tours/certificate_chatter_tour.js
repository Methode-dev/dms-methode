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

/* Where the stamped page sits.
 *
 * It is a sibling of the sheet's background, not a column inside the sheet, so
 * at XXL the form view's own flex row puts it to the right and neither side is
 * capped by the sheet's max width. Below XXL the form is a column and it
 * follows underneath. Both are geometry — the arch and the stylesheet each look
 * right on their own, and only the rendered box says which side of the sheet
 * the panel ended up on. */
function boxes(anchor) {
    const formEl = anchor.closest(".o_form_view");
    return {
        form: formEl.getBoundingClientRect(),
        sheet: formEl.querySelector(".o_form_sheet_bg").getBoundingClientRect(),
        panel: anchor.getBoundingClientRect(),
    };
}

registry.category("web_tour.tours").add("dms_certify_portal_preview_aside_tour", {
    test: true,
    steps: () => [
        {
            content: "on a wide screen the page sits beside the sheet",
            trigger: ".o_form_view .o_certify_preview_aside",
            run() {
                const {form, sheet, panel} = boxes(this.anchor);
                if (panel.left < sheet.right - 1) {
                    throw new Error(
                        `The page should start where the sheet ends: sheet ` +
                        `ends at ${Math.round(sheet.right)}, panel starts at ` +
                        `${Math.round(panel.left)}.`
                    );
                }
                const share = panel.width / form.width;
                if (Math.abs(share - 2 / 5) > 0.01) {
                    throw new Error(
                        `The page should hold two fifths of the form: form is ` +
                        `${Math.round(form.width)}px, panel is ` +
                        `${Math.round(panel.width)}px (${(share * 100).toFixed(1)}%).`
                    );
                }
            },
        },
    ],
});

registry.category("web_tour.tours").add("dms_certify_portal_preview_below_tour", {
    test: true,
    steps: () => [
        {
            content: "on a narrower screen it stacks underneath instead",
            trigger: ".o_form_view .o_certify_preview_aside",
            run() {
                const {sheet, panel} = boxes(this.anchor);
                if (panel.top < sheet.bottom - 1) {
                    throw new Error(
                        `Squeezed beside the sheet on a ${window.innerWidth}px ` +
                        `screen instead of stacking under it.`
                    );
                }
            },
        },
    ],
});
