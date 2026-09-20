// /** ********************************************************************************
//     File Explorer right-click context menu.
//     Uses the SAME menu interface as the left tree, i.e. jsTree's vakata context
//     menu ($.vakata.context), so the grid and the tree behave/look identical:
//       - Rename   (files and folders, when the user may write)
//       - Preview  (files)
//       - Download (files)
//       - Delete   (files and folders, when the user may unlink)
//     Also renders the grid's blank-area menu (Create folder, plus whatever a
//     host module adds), built by the renderer and handed to showMenu().
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Component, onMounted, useRef, useState} from "@odoo/owl";
import {loadBundle, loadCSS, loadJS} from "@web/core/assets";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
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
 * Ask before deleting, and answer whether the user went through with it.
 *
 * Asks only — the caller deletes, because the two surfaces of the File Explorer
 * put themselves straight differently afterwards: the grid reloads its records,
 * the tree re-reads the parent node. Sharing the question is what keeps them
 * from drifting apart.
 *
 * A folder deserves a sharper warning than a file: dms.directory.unlink
 * cascades through every sub-folder and file, so the confirmation names what
 * would go with it.
 *
 * @param {Object} services {dialog, orm}
 * @param {Object} target {model, id, name}
 * @returns {Promise<Boolean>} true when the user confirmed
 */
export async function confirmDmsDelete({dialog, orm}, target) {
    const name = target.name || "";
    let body = _t('"%(name)s" will be permanently deleted.', {name});
    if (target.model === "dms.directory") {
        let files = null;
        let folders = null;
        try {
            const [counts] = await orm.read(
                "dms.directory",
                [target.id],
                ["count_total_files", "count_total_directories"]
            );
            files = counts.count_total_files;
            folders = counts.count_total_directories;
        } catch {
            // The counts are a courtesy; never let failing to read them stand
            // between the user and a folder they asked to delete. Warn without
            // the numbers instead.
            files = null;
        }
        if (files === null) {
            body = _t(
                'The folder "%(name)s" will be permanently deleted, together ' +
                    "with everything it contains.",
                {name}
            );
        } else if (files || folders) {
            body = _t(
                'The folder "%(name)s" will be permanently deleted, together ' +
                    "with everything it contains: %(files)s file(s) and " +
                    "%(folders)s sub-folder(s).",
                {name, files, folders}
            );
        } else {
            body = _t('The empty folder "%(name)s" will be permanently deleted.', {
                name,
            });
        }
    }
    return new Promise((resolve) => {
        dialog.add(
            ConfirmationDialog,
            {
                title: _t("Delete"),
                body: body + " " + _t("This cannot be undone."),
                confirmLabel: _t("Delete"),
                confirmClass: "btn-danger",
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            },
            // Closing with Escape or the cross runs neither callback; the first
            // resolve wins, so this only catches the dismissed case.
            {onClose: () => resolve(false)}
        );
    });
}

/**
 * Hook returning `{openContextMenu, showMenu}`.
 *
 * - `openContextMenu(ev, config)` builds and shows the menu of a single
 *   file/folder. config: {model, id, name, canRename, canDelete, isFile,
 *   onRefresh, onPreview, onDownload}
 * - `showMenu(ev, items)` shows a ready-made vakata item dict. Use it for menus
 *   that are not about one record, e.g. the grid's blank-area menu.
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

    const remove = async (config) => {
        const confirmed = await confirmDmsDelete({dialog, orm}, config);
        if (!confirmed) {
            return;
        }
        await orm.unlink(config.model, [config.id]);
        if (config.onRefresh) {
            await config.onRefresh();
        }
    };

    /**
     * Render `items` (jsTree's vakata format, same as the tree's
     * loadContextMenu* helpers) at the pointer.
     *
     * Runs synchronously up to the first await, so preventDefault() still
     * counts and the event data is captured before the event is recycled.
     */
    const showMenu = async (ev, items) => {
        // Always suppress the browser menu, even when the menu comes out empty.
        ev.preventDefault();
        ev.stopPropagation();
        const x = ev.pageX;
        const y = ev.pageY;
        const target = ev.currentTarget || ev.target;
        if (!Object.keys(items).length) {
            return;
        }
        const $ = await ensureVakata();
        if ($ && $.vakata && $.vakata.context) {
            $.vakata.context.show($(target), {x, y}, items);
        }
    };

    const openContextMenu = async (ev, config) => {
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
        if (config.canDelete) {
            items.delete = {
                // Set apart so it is not clicked on the way to Download.
                separator_before: true,
                label: _t("Delete"),
                icon: "fa fa-trash-o",
                action: () => remove(config),
            };
        }
        await showMenu(ev, items);
    };

    return {openContextMenu, showMenu};
}
