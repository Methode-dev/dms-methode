// /** ********************************************************************************
//     File Explorer right-click context menu.
//     Uses the SAME menu interface as the left tree, i.e. jsTree's vakata context
//     menu ($.vakata.context), so the grid and the tree behave/look identical:
//       - Rename   (files and folders, when the user may write)
//       - Preview  (files)
//       - Download (files)
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Component, onMounted, useRef, useState} from "@odoo/owl";
import {loadBundle, loadCSS, loadJS} from "@web/core/assets";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";

let vakataReady = null;

/**
 * Ensure jQuery + jsTree (which defines $.vakata.context) and the proton theme
 * (which styles the context menu) are loaded. The left tree loads these too, so
 * this is normally already satisfied; loading is cached/idempotent.
 */
async function ensureVakata() {
    const jq = window.jQuery;
    if (jq && jq.vakata && jq.vakata.context) {
        return jq;
    }
    if (!vakataReady) {
        vakataReady = (async () => {
            await loadBundle("web._assets_jquery");
            await loadCSS("/dms_field/static/lib/jsTree/themes/proton/style.css");
            await loadJS("/dms_field/static/lib/jsTree/jstree.js");
        })();
    }
    await vakataReady;
    return window.jQuery;
}

export class FileExplorerRenameDialog extends Component {
    static template = "dms.FileExplorerRenameDialog";
    static components = {Dialog};
    static props = {
        title: {type: String, optional: true},
        value: {type: String, optional: true},
        confirm: Function,
        close: Function,
    };

    setup() {
        this.state = useState({value: this.props.value || ""});
        this.inputRef = useRef("input");
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                this.inputRef.el.select();
            }
        });
    }

    async onConfirm() {
        const value = (this.state.value || "").trim();
        if (value) {
            await this.props.confirm(value);
        }
        this.props.close();
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onConfirm();
        }
    }
}

/**
 * Hook returning `openContextMenu(ev, config)`.
 * config: {model, id, name, canRename, isFile, onRefresh, onPreview, onDownload}
 */
export function useFileExplorerContextMenu() {
    const dialog = useService("dialog");
    const orm = useService("orm");

    const rename = (config) => {
        dialog.add(FileExplorerRenameDialog, {
            title: _t("Rename"),
            value: config.name,
            confirm: async (newName) => {
                if (newName && newName !== config.name) {
                    await orm.write(config.model, [config.id], {name: newName});
                    if (config.onRefresh) {
                        await config.onRefresh();
                    }
                }
            },
        });
    };

    const openContextMenu = async (ev, config) => {
        // Always suppress the browser menu; capture the event data before any
        // await (the event is recycled afterwards).
        ev.preventDefault();
        ev.stopPropagation();
        const x = ev.pageX;
        const y = ev.pageY;
        const target = ev.currentTarget;

        // Build the menu in jsTree's vakata format (same as the tree's
        // loadContextMenu* helpers).
        const items = {};
        if (config.canRename) {
            items.rename = {
                label: _t("Rename"),
                icon: "fa fa-pencil",
                action: () => rename(config),
            };
        }
        if (config.isFile) {
            if (config.onPreview) {
                items.preview = {
                    label: _t("Preview"),
                    icon: "fa fa-eye",
                    action: () => config.onPreview(),
                };
            }
            if (config.onDownload) {
                items.download = {
                    label: _t("Download"),
                    icon: "fa fa-download",
                    action: () => config.onDownload(),
                };
            }
        }
        if (!Object.keys(items).length) {
            return;
        }

        const $ = await ensureVakata();
        if ($ && $.vakata && $.vakata.context) {
            $.vakata.context.show($(target), {x, y}, items);
        }
    };

    return openContextMenu;
}
