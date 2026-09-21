import { onWillRender } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { CertificateChatter } from "./certificate_chatter";

/**
 * Use the composer-less chatter on the certificate form, and only there.
 *
 * The obvious way to do this is to swap ``this.mailComponents.Chatter`` in a
 * ``setup()`` patch, the way outlook_chatter_theme and sh_helpdesk_relation do.
 * It would not work from here: patches apply in asset order, asset order
 * follows module load order, and this module loads *before*
 * outlook_chatter_theme (measured: #414 against #446 in web.assets_backend).
 * Our setup would therefore run first and the theme would overwrite the choice.
 * Winning that race would mean depending on the theme — but this module is
 * generic and lives in another repository, so it must not.
 *
 * So the choice is re-asserted at render time instead. ``onWillRender`` runs
 * after every ``setup()``, whoever patched it, and right before the compiled
 * template reads ``__comp__.mailComponents.Chatter``. ``mailComponents`` is a
 * plain property, not reactive state, so assigning to it here triggers no
 * further render.
 *
 * A renderer instance belongs to one form view and therefore to one model, so
 * there is nothing to restore when the record changes: only certificates ever
 * reach the assignment.
 */
patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        onWillRender(() => {
            if (
                this.mailComponents &&
                this.mailComponents.Chatter !== CertificateChatter &&
                this.props.record?.resModel === "dms.certificate"
            ) {
                this.mailComponents = { ...this.mailComponents, Chatter: CertificateChatter };
            }
        });
    },
});
