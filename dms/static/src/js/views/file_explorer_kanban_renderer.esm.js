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
        this.openContextMenu = useFileExplorerContextMenu();
        this.explorerState = useState({folders: [], breadcrumb: []});
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
                    ["name", "icon_url", "permission_write"],
                    {order: "name", limit: 200}
                );
            } catch {
                folders = [];
            }
            if (this._lastKey === key) {
                this.explorerState.folders = folders;
                this.explorerState.breadcrumb = [];
            }
            return;
        }

        // Browse mode: direct subfolders + breadcrumb. Also (re)compute the
        // current storage so a later search can be scoped to it.
        const folders = await this.orm.searchRead(
            "dms.directory",
            [["parent_id", "=", dir]],
            ["name", "icon_url", "permission_write"],
            {order: "name"}
        );
        let breadcrumb = [];
        if (dir) {
            try {
                const ancestors = await this.orm.searchRead(
                    "dms.directory",
                    [["id", "parent_of", dir]],
                    ["name", "complete_name", "storage_id"],
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
        }
    }

    /** Force a refresh of the folders + breadcrumb (e.g. after a rename). */
    async _refresh() {
        this._lastKey = undefined;
        await this._reloadLocation();
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

    onFolderContextMenu(ev, folder) {
        // Folders are not downloadable: offer Rename only.
        this.openContextMenu(ev, {
            model: "dms.directory",
            id: folder.id,
            name: folder.name,
            canRename: folder.permission_write,
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
