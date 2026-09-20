// /** ********************************************************************************
//     File Explorer kanban renderer: in addition to the file records, it shows
//     the current location's direct subfolders as tiles (same layout as files).
//     Double-clicking a folder opens it (descends into it).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";
import {FileExplorerKanbanRecord} from "./file_explorer_kanban_record.esm";
import {FileKanbanRenderer} from "./file_kanban_renderer.esm";
import {FileNameLabel} from "./file_explorer_filename.esm";
import {useFileExplorerContextMenu} from "./file_explorer_context_menu.esm";

export class FileExplorerKanbanRenderer extends FileKanbanRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.http = useService("http");
        this.notification = useService("notification");
        const contextMenu = useFileExplorerContextMenu();
        this.openContextMenu = contextMenu.openContextMenu;
        this.showContextMenu = contextMenu.showMenu;
        // canCreate: may the user create a subfolder in the current folder?
        // Read together with the breadcrumb so the blank-area "Create folder"
        // entry can be disabled instead of failing server-side.
        this.explorerState = useState({folders: [], breadcrumb: [], canCreate: false});
        this._lastKey = undefined;
        onWillStart(() => this._reloadLocation());
        // The location / search term live on the (custom) search model; reload
        // the folders and breadcrumb whenever they change (the search model fires
        // "update" on navigation and on search). The search itself is driven by
        // the main control-panel search bar (see file_explorer_search_bar.esm).
        useBus(this.env.searchModel, "update", () => this._reloadLocation());
        onWillUnmount(() => {
            if (this._dragHideTimer) {
                clearTimeout(this._dragHideTimer);
            }
        });
    }

    get isExplorerSearching() {
        return this.env.searchModel.isExplorerSearching;
    }

    // ---- Drag & drop upload to the current location -------------------------
    // The inherited file-kanban drop zone routes the drop through the kanban
    // controller's hidden upload <input>, which the explorer does not render
    // (create=0) — hence the "Cannot set properties of null" error. Override the
    // handlers to (a) show a centered overlay while dragging and (b) upload the
    // dropped files straight into the currently open folder.

    highlight(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        // Cancel a pending hide so moving over child tiles doesn't flicker.
        if (this._dragHideTimer) {
            clearTimeout(this._dragHideTimer);
            this._dragHideTimer = null;
        }
        this.dragState.showDragZone = true;
    }

    unhighlight(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        // Defer hiding: a continuing drag fires dragover again and cancels it.
        if (this._dragHideTimer) {
            clearTimeout(this._dragHideTimer);
        }
        this._dragHideTimer = setTimeout(() => {
            this.dragState.showDragZone = false;
            this._dragHideTimer = null;
        }, 150);
    }

    async onDrop(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (this._dragHideTimer) {
            clearTimeout(this._dragHideTimer);
            this._dragHideTimer = null;
        }
        this.dragState.showDragZone = false;
        await this._uploadFilesToCurrent(ev.dataTransfer && ev.dataTransfer.files);
    }

    async _uploadFilesToCurrent(files) {
        const directoryId = this.currentDirectoryId;
        if (!directoryId) {
            this.notification.add(
                _t("Open a folder first to upload files into it."),
                {type: "warning"}
            );
            return;
        }
        if (!files || !files.length) {
            return;
        }
        try {
            const params = {
                csrf_token: odoo.csrf_token,
                ufile: [...files],
                model: "dms.file",
                id: 0,
            };
            const raw = await this.http.post(
                "/web/binary/upload_attachment",
                params,
                "text"
            );
            const attachments = JSON.parse(raw);
            if (attachments.error) {
                this.notification.add(attachments.error, {type: "danger"});
                return;
            }
            const attachmentIds = attachments.map((a) => a.id).filter(Boolean);
            if (!attachmentIds.length) {
                this.notification.add(_t("An error occurred during the upload"), {
                    type: "danger",
                });
                return;
            }
            const fileDatas = await this.orm.call(
                "dms.file",
                "get_dms_files_from_attachments",
                [],
                {attachment_ids: attachmentIds}
            );
            const valsList = fileDatas.map((data) => ({
                name: data.name,
                content: data.datas,
                mimetype: data.mimetype,
                directory_id: directoryId,
            }));
            await this.orm.call("dms.file", "create", [valsList]);
            // Refresh the file list so the new files appear.
            await this.props.list.model.load();
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) ||
                    _t("An error occurred during the upload"),
                {type: "danger"}
            );
        }
    }

    get currentDirectoryId() {
        return this.env.searchModel.explorerDirectoryId || false;
    }

    get canGoBack() {
        return this.env.searchModel.canGoBack;
    }

    get canGoForward() {
        return this.env.searchModel.canGoForward;
    }

    /**
     * @override
     * Never show the "Add a new File" placeholder: the explorer is read-only,
     * and a folder may legitimately contain only subfolders (no direct files).
     */
    get showNoContentHelper() {
        return false;
    }

    async _reloadLocation() {
        const sm = this.env.searchModel;
        const dir = sm.explorerDirectoryId || false;
        const term = sm.explorerSearchTerm || "";
        const key = dir + "|" + term;
        if (key === this._lastKey) {
            return;
        }
        this._lastKey = key;

        if (term) {
            // Search mode: matching folders anywhere in the current storage,
            // flat. Record rules restrict this to folders the user may read.
            const domain = [["name", "ilike", term]];
            if (sm.explorerStorageId) {
                domain.push(["storage_id", "=", sm.explorerStorageId]);
            }
            let folders = [];
            try {
                folders = await this.orm.searchRead(
                    "dms.directory",
                    domain,
                    ["name", "icon_url", "permission_write", "permission_unlink"],
                    {order: "name", limit: 200}
                );
            } catch {
                folders = [];
            }
            if (this._lastKey === key) {
                this.explorerState.folders = folders;
                this.explorerState.breadcrumb = [];
                this.explorerState.canCreate = false;
            }
            return;
        }

        // Browse mode: direct subfolders + breadcrumb. Also (re)compute the
        // current storage so a later search can be scoped to it.
        const folders = await this.orm.searchRead(
            "dms.directory",
            [["parent_id", "=", dir]],
            ["name", "icon_url", "permission_write", "permission_unlink"],
            {order: "name"}
        );
        let breadcrumb = [];
        let canCreate = false;
        if (dir) {
            try {
                const ancestors = await this.orm.searchRead(
                    "dms.directory",
                    [["id", "parent_of", dir]],
                    ["name", "complete_name", "storage_id", "permission_create"],
                    {}
                );
                ancestors.sort(
                    (a, b) =>
                        (a.complete_name || "").split(" / ").length -
                        (b.complete_name || "").split(" / ").length
                );
                breadcrumb = ancestors.map((a) => ({id: a.id, name: a.name}));
                const current = ancestors.find((a) => a.id === dir);
                sm.explorerStorageId =
                    current && current.storage_id ? current.storage_id[0] : false;
                canCreate = Boolean(current && current.permission_create);
            } catch {
                breadcrumb = [];
            }
        } else {
            sm.explorerStorageId = false;
        }
        // Guard against an out-of-order async resolution overwriting a newer one.
        if (this._lastKey === key) {
            this.explorerState.folders = folders;
            this.explorerState.breadcrumb = breadcrumb;
            this.explorerState.canCreate = canCreate;
        }
    }

    /** Force a refresh of the folders + breadcrumb (e.g. after a rename). */
    async _refresh() {
        this._lastKey = undefined;
        await this._reloadLocation();
    }

    /**
     * Reload everything on screen: the folder tiles *and* the file records.
     *
     * The two halves of the grid come from different places — folders are read
     * here, files come through the view's own list model — so showing work done
     * elsewhere takes both. Public, because what adds files to the open folder
     * is not always this component: a host module generating documents into it
     * calls this when its dialog closes, and the files appear the way a created
     * folder does.
     */
    async reloadExplorer() {
        await Promise.all([this._refresh(), this.props.list.model.load()]);
    }

    /** Descend into a folder: make it the current location. */
    openFolder(folder) {
        this.navigateTo(folder.id);
    }

    /** Navigate to a directory id (or false for the root). */
    navigateTo(directoryId) {
        this.env.searchModel.selectDirectory(directoryId);
    }

    goBack() {
        this.env.searchModel.goBack();
    }

    goForward() {
        this.env.searchModel.goForward();
    }

    // ---- Blank-area context menu --------------------------------------------

    /**
     * Right-click anywhere in the grid that is not a tile: below the files, in
     * the gaps, or on one of the invisible ghost records the kanban pads the
     * last row with.
     *
     * Bound on the renderer root, which fills the content area (`.o_renderer`
     * is height:100% next to a search panel), so the empty space underneath the
     * tiles is covered. The per-tile handlers call stopPropagation() before
     * anything else, so a tile's own menu still wins — including when it comes
     * out empty for lack of permission, which the `closest` guard below keeps
     * from falling through to this menu.
     */
    onBackgroundContextMenu(ev) {
        // Group By replaces the explorer chrome with the standard grouped
        // kanban (see the template), where there is no current folder.
        if (this.props.list.isGrouped) {
            return;
        }
        if (
            ev.target.closest(".o_kanban_record:not(.o_kanban_ghost)") ||
            ev.target.closest(".o_file_explorer_navbar")
        ) {
            return;
        }
        this.showContextMenu(ev, this.backgroundContextMenuItems());
    }

    /**
     * The blank-area menu, in jsTree's vakata format.
     *
     * Split out from the handler so a host module can patch just the items and
     * inherit the hit-testing above — the seam `operations` uses to add its own
     * entries, the way it patches DmsListRenderer.loadContextMenu for the tree.
     */
    backgroundContextMenuItems() {
        // Search results are a flat view across folders, and at Home the tiles
        // are root directories, which belong to a storage rather than a parent
        // — neither has a folder to create into.
        const canCreate = Boolean(
            this.currentDirectoryId &&
                !this.isExplorerSearching &&
                this.explorerState.canCreate
        );
        return {
            create_folder: {
                separator_before: false,
                separator_after: false,
                icon: "fa fa-folder",
                label: _t("Create folder"),
                title: canCreate
                    ? false
                    : _t("Open a folder you can write into to create one here."),
                _disabled: () => !canCreate,
                action: () => this.createFolder(),
            },
        };
    }

    /**
     * Create a subfolder of the current folder. The name ("New Folder", then
     * "New Folder(1)", ...) is settled server-side, which is the only place
     * that sees every sibling — record rules may hide some from the user.
     */
    async createFolder() {
        const directoryId = this.currentDirectoryId;
        if (!directoryId) {
            return;
        }
        // Let an AccessError surface through the standard error dialog: the
        // menu entry is already disabled without create permission, so getting
        // here means something worth reading in full.
        await this.orm.call("dms.directory", "action_dms_create_child_directory", [
            [directoryId],
        ]);
        await this._refresh();
    }

    onFolderContextMenu(ev, folder) {
        // Folders are not downloadable or previewable: Rename and Delete only.
        this.openContextMenu(ev, {
            model: "dms.directory",
            id: folder.id,
            name: folder.name,
            canRename: folder.permission_write,
            canDelete: folder.permission_unlink,
            isFile: false,
            onRefresh: () => this._refresh(),
        });
    }
}

FileExplorerKanbanRenderer.template = "dms.FileExplorerKanbanRenderer";
FileExplorerKanbanRenderer.components = {
    ...FileKanbanRenderer.components,
    KanbanRecord: FileExplorerKanbanRecord,
    FileNameLabel,
};
