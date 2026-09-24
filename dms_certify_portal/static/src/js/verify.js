/* Public verification portal — the little that has to happen in the browser.
 *
 * Deliberately a plain script with no framework: this file is served to
 * anonymous visitors on a page whose whole argument is that it carries as
 * little as possible. Everything here degrades to nothing if it fails — the
 * form posts, the server formats, and the page still works with scripting off.
 */
(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var form = document.querySelector(".dc-portal form.dc-lookup-form");
        if (form) {
            maskReference(form);
            wireCaptcha(form);
        }
        var print = document.getElementById("dc_print");
        if (print) {
            print.addEventListener("click", function () {
                window.print();
            });
        }
    });

    /* Group the reference as it is printed, so what the agent types looks like
     * what they are copying from. The group sizes come from the server: the
     * prefix is configurable, and a hard-coded mask would fight it. */
    function maskReference(form) {
        var input = form.querySelector("#dc_reference");
        if (!input) {
            return;
        }
        var groups = (form.dataset.groups || "3,4,3,4,2")
            .split(",")
            .map(function (size) {
                return parseInt(size, 10);
            })
            .filter(function (size) {
                return size > 0;
            });

        function format(raw) {
            var value = String(raw).toUpperCase().replace(/[^A-Z0-9]/g, "");
            var out = "";
            var at = 0;
            for (var i = 0; i < groups.length; i++) {
                if (at >= value.length) {
                    break;
                }
                if (out) {
                    out += "-";
                }
                out += value.slice(at, at + groups[i]);
                at += groups[i];
            }
            return out;
        }

        input.addEventListener("input", function () {
            var atEnd = input.selectionStart === input.value.length;
            input.value = format(input.value);
            if (atEnd) {
                input.setSelectionRange(input.value.length, input.value.length);
            }
        });
        if (input.value) {
            input.value = format(input.value);
        }
    }

    /* Soft dependency: without a site key the server never asks for a token,
     * and this does nothing. */
    function wireCaptcha(form) {
        var key = form.dataset.sitekey;
        var field = document.getElementById("dc_recaptcha_token");
        if (!key || !field) {
            return;
        }
        form.addEventListener("submit", function (ev) {
            if (field.value || typeof grecaptcha === "undefined") {
                return;
            }
            ev.preventDefault();
            grecaptcha.ready(function () {
                grecaptcha
                    .execute(key, {action: "dms_certify"})
                    .then(function (token) {
                        field.value = token;
                        form.submit();
                    });
            });
        });
    }
})();
