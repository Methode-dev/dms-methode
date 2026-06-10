// /** ********************************************************************************
//     File Explorer file/folder name label.
//     Renders a name on at most two lines. When too long, it is truncated in the
//     MIDDLE so both the beginning and the end (the extension) stay visible:
//         this_is_an_example_of_a_filename_that_is_very_very_long_and_wont_fit.txt
//     ->  this_is_an_examp
//         le_of_a...nt_fit.txt
//     Used both by the file kanban records (via the dms_filename_truncate field
//     widget) and by the folder tiles rendered by the explorer renderer.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Component, useEffect, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

const ELLIPSIS = "...";

export class FileNameLabel extends Component {
    static template = "dms.FileNameLabel";
    static props = {
        name: {type: String, optional: true},
    };

    setup() {
        this.root = useRef("root");
        this.state = useState({display: this.text});
        useEffect(
            () => {
                this._update();
                if (!this.root.el || typeof ResizeObserver === "undefined") {
                    return;
                }
                // Recompute when the tile is resized (responsive widths).
                const ro = new ResizeObserver(() => this._update());
                ro.observe(this.root.el);
                return () => ro.disconnect();
            },
            () => [this.root.el, this.text]
        );
    }

    get text() {
        return this.props.name || "";
    }

    /** Width of `str` in px, using the element's actual font. */
    _measure(str) {
        if (!this._ctx) {
            this._ctx = document.createElement("canvas").getContext("2d");
        }
        const cs = getComputedStyle(this.root.el);
        this._ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
        return this._ctx.measureText(str).width;
    }

    _update() {
        const el = this.root.el;
        if (!el) {
            return;
        }
        const name = this.text;
        const line = el.clientWidth;
        if (line <= 0) {
            this.state.display = name;
            return;
        }
        // With `word-break: break-all`, a string whose total width is <= 2 line
        // widths wraps into at most 2 lines. Keep a small safety margin so a
        // sub-pixel measurement error can never push it onto a 3rd line (which
        // the clamp would cut from the END, hiding the extension).
        const budget = line * 2 - 4;
        if (this._measure(name) <= budget) {
            this.state.display = name;
            return;
        }
        // Tail = the end of the name (keeps the extension); capped to one line.
        let tail = name.slice(-Math.min(name.length - 1, 10));
        while (tail.length > 4 && this._measure(ELLIPSIS + tail) > line) {
            tail = tail.slice(1);
        }
        // Grow the head until head + "..." + tail no longer fits two lines.
        const maxHead = name.length - tail.length;
        let head = "";
        for (let i = 1; i <= maxHead; i++) {
            const candidate = name.slice(0, i);
            if (this._measure(candidate + ELLIPSIS + tail) > budget) {
                break;
            }
            head = candidate;
        }
        this.state.display = head + ELLIPSIS + tail;
    }
}

// Field widget wrapper so the kanban file records can use `widget="..."`.
export class FileNameTruncate extends Component {
    static template = "dms.FileNameTruncate";
    static components = {FileNameLabel};
    static props = {...standardFieldProps};

    get value() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("dms_filename_truncate", {
    component: FileNameTruncate,
    supportedTypes: ["char"],
});
