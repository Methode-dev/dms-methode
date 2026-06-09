// /** ********************************************************************************
//     File Explorer kanban renderer: same as the file kanban renderer but uses
//     the FileExplorerKanbanRecord (click-anywhere-to-preview).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {FileExplorerKanbanRecord} from "./file_explorer_kanban_record.esm";
import {FileKanbanRenderer} from "./file_kanban_renderer.esm";

export class FileExplorerKanbanRenderer extends FileKanbanRenderer {
    // Read-only explorer: neutralise the inherited drag-and-drop upload so a
    // basic user cannot add files by dropping them. We still prevent the
    // browser's default (opening the dropped file) but never show the drop
    // zone or trigger an upload.
    highlight(ev) {
        ev.stopPropagation();
        ev.preventDefault();
    }
    unhighlight(ev) {
        ev.stopPropagation();
        ev.preventDefault();
    }
    onDrop(ev) {
        ev.preventDefault();
    }
}

// Reuse the file kanban template (drop zone, layout, ...).
FileExplorerKanbanRenderer.template = "dms.KanbanRenderer";
FileExplorerKanbanRenderer.components = {
    ...FileKanbanRenderer.components,
    KanbanRecord: FileExplorerKanbanRecord,
};
