// /** ********************************************************************************
//     File Explorer kanban record.
//     OS-file-explorer interactions: double-click a file to preview it,
//     right-click to open a context menu (Rename / Preview / Download).
//     Single click does nothing.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {download} from "@web/core/network/download";
import {FileKanbanRecord} from "./file_kanban_record.esm";
import {useEffect} from "@odoo/owl";
import {useFileExplorerContextMenu} from "./file_explorer_context_menu.esm";

export class FileExplorerKanbanRecord extends FileKanbanRecord {
    setup() {
        super.setup();
        this.openContextMenu = useFileExplorerContextMenu();
        // Bind the OS-explorer interactions on the card root element:
        //   - double-click -> preview (in-page viewer)
        //   - right-click  -> context menu (Rename / Preview / Download)
        useEffect(
            (el) => {
                if (!el) {
                    return;
                }
                const onDblClick = () => this.openPreview();
                const onContextMenu = (ev) => {
                    const data = this.props.record.data;
                    this.openContextMenu(ev, {
                        model: "dms.file",
                        id: data.id,
                        name: data.name,
                        canRename: data.permission_write,
                        isFile: true,
                        onPreview: () => this.openPreview(),
                        onDownload: () => this.downloadFile(),
                        onRefresh: () => this.props.record.model.load(),
                    });
                };
                el.addEventListener("dblclick", onDblClick);
                el.addEventListener("contextmenu", onContextMenu);
                return () => {
                    el.removeEventListener("dblclick", onDblClick);
                    el.removeEventListener("contextmenu", onContextMenu);
                };
            },
            () => [this.rootRef.el]
        );
    }

    /**
     * @override
     *
     * Single click is inert in the File Explorer — preview is on double-click
     * and download is on right-click (wired in setup), like an OS file explorer.
     */
    onGlobalClick() {}

    /**
     * @override
     *
     * Feed the viewer every file currently listed in the grid (in display
     * order) instead of just this one, so its prev/next arrows navigate the
     * folder — matching the dms_list tree's preview navigation.
     */
    openPreview() {
        const current = this.buildViewerFile(this.props.record);
        if (!current.isViewable) {
            return;
        }
        const files = this.previewNavigationRecords().map((record) =>
            record.resId === this.props.record.resId
                ? // The viewer locates the start index by identity, so the
                  // current file must be this very object.
                  current
                : this.buildViewerFile(record)
        );
        this.fileViewer.open(current, files.length ? files : [current]);
    }

    /**
     * The records the preview arrows navigate: what the grid currently shows.
     * Only the ungrouped case applies to the File Explorer today, but grouped
     * lists are flattened rather than silently reduced to a single file.
     */
    previewNavigationRecords() {
        const root = this.props.record.model && this.props.record.model.root;
        if (!root) {
            return [this.props.record];
        }
        if (root.groups) {
            return root.groups.flatMap(
                (group) => (group.list && group.list.records) || []
            );
        }
        return root.records || [this.props.record];
    }

    downloadFile() {
        const record = this.props.record;
        download({
            url: "/web/content",
            data: {
                id: record.data.id,
                download: true,
                field: "content",
                model: "dms.file",
                filename_field: "name",
                filename: record.data.name,
            },
        });
    }
}
