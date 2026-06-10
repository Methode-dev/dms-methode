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

export class FileExplorerKanbanRenderer extends FileKanbanRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.explorerState = useState({folders: []});
        this._lastDir = undefined;
        onWillStart(() => this._reloadFolders());
        // The location lives on the (custom) search model; reload the subfolders
        // whenever it changes (the search model fires "update" on navigation).
        useBus(this.env.searchModel, "update", () => this._reloadFolders());
    }

    get currentDirectoryId() {
        return this.env.searchModel.explorerDirectoryId || false;
    }

    /**
     * @override
     * Never show the "Add a new File" placeholder: the explorer is read-only,
     * and a folder may legitimately contain only subfolders (no direct files).
     */
    get showNoContentHelper() {
        return false;
    }

    async _reloadFolders() {
        const dir = this.currentDirectoryId;
        if (dir === this._lastDir) {
            return;
        }
        this._lastDir = dir;
        // Direct subfolders of the current location (root directories when no
        // folder is selected). Record rules already restrict this to folders
        // the user may read.
        this.explorerState.folders = await this.orm.searchRead(
            "dms.directory",
            [["parent_id", "=", dir]],
            ["name", "icon_url"],
            {order: "name"}
        );
    }

    /** Descend into a folder: make it the current location. */
    openFolder(folder) {
        this.env.searchModel.selectDirectory(folder.id);
    }

    onFolderContextMenu() {
        // Folders are not downloadable: only suppress the browser context menu.
    }
}

FileExplorerKanbanRenderer.template = "dms.FileExplorerKanbanRenderer";
FileExplorerKanbanRenderer.components = {
    ...FileKanbanRenderer.components,
    KanbanRecord: FileExplorerKanbanRecord,
    FileNameLabel,
};
