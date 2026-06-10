// /** ********************************************************************************
//     File Explorer kanban record.
//     OS-file-explorer interactions: double-click a file to preview it,
//     right-click to download it. Single click does nothing.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {download} from "@web/core/network/download";
import {FileKanbanRecord} from "./file_kanban_record.esm";
import {useEffect} from "@odoo/owl";

export class FileExplorerKanbanRecord extends FileKanbanRecord {
    setup() {
        super.setup();
        // Bind the OS-explorer interactions on the card root element:
        //   - double-click -> preview (in-page viewer)
        //   - right-click  -> download (suppresses the browser context menu)
        useEffect(
            (el) => {
                if (!el) {
                    return;
                }
                const onDblClick = () => this.openPreview();
                const onContextMenu = (ev) => {
                    ev.preventDefault();
                    this.downloadFile();
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
