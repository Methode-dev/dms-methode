// /** ********************************************************************************
//     File Explorer kanban renderer: in addition to the file records, it shows
//     the current location's direct subfolders as tiles (same layout as files).
//     Double-clicking a folder opens it (descends into it).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {onWillStart, useState} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {FileExplorerKanbanRecord} from "./file_explorer_kanban_record.esm";
import {FileKanbanRenderer} from "./file_kanban_renderer.esm";
import {FileNameLabel} from "./file_explorer_filename.esm";
import {useFileExplorerContextMenu} from "./file_explorer_context_menu.esm";

export class FileExplorerKanbanRenderer extends FileKanbanRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.openContextMenu = useFileExplorerContextMenu();
        this.explorerState = useState({folders: [], breadcrumb: []});
        this._lastDir = undefined;
        onWillStart(() => this._reloadLocation());
        // The location lives on the (custom) search model; reload the subfolders
        // and breadcrumb whenever it changes (the search model fires "update" on
        // navigation).
        useBus(this.env.searchModel, "update", () => this._reloadLocation());
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
        const dir = this.currentDirectoryId;
        if (dir === this._lastDir) {
            return;
        }
        this._lastDir = dir;
        // Direct subfolders of the current location (root directories when no
        // folder is selected). Record rules already restrict this to folders
        // the user may read.
        const folders = await this.orm.searchRead(
            "dms.directory",
            [["parent_id", "=", dir]],
            ["name", "icon_url", "permission_write"],
            {order: "name"}
        );
        // Breadcrumb = the current folder and all its ancestors, root -> current.
        let breadcrumb = [];
        if (dir) {
            try {
                const ancestors = await this.orm.searchRead(
                    "dms.directory",
                    [["id", "parent_of", dir]],
                    ["name", "complete_name"],
                    {}
                );
                ancestors.sort(
                    (a, b) =>
                        (a.complete_name || "").split(" / ").length -
                        (b.complete_name || "").split(" / ").length
                );
                breadcrumb = ancestors.map((a) => ({id: a.id, name: a.name}));
            } catch {
                breadcrumb = [];
            }
        }
        // Guard against an out-of-order async resolution overwriting a newer one.
        if (this._lastDir === dir) {
            this.explorerState.folders = folders;
            this.explorerState.breadcrumb = breadcrumb;
        }
    }

    /** Force a refresh of the subfolders + breadcrumb (e.g. after a rename). */
    async _refresh() {
        this._lastDir = undefined;
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
