// /** ********************************************************************************
//     File Explorer kanban record.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {CANCEL_GLOBAL_CLICK} from "@web/views/kanban/kanban_record";
import {FileKanbanRecord} from "./file_kanban_record.esm";

export class FileExplorerKanbanRecord extends FileKanbanRecord {
    /**
     * @override
     *
     * On the File Explorer, clicking a file always opens its preview — whether
     * the click lands on the icon, the file name, or any blank area of the
     * card — instead of opening the record form (the base File page only
     * previews when the icon is clicked).
     */
    onGlobalClick(ev) {
        // Let genuine interactive controls behave normally (the manage-menu
        // dropdown and its action links/toggles). The preview icon is an <a>,
        // so it also matches CANCEL_GLOBAL_CLICK — keep it as an explicit
        // exception so it still previews.
        if (
            ev.target.closest(CANCEL_GLOBAL_CLICK) &&
            !ev.target.closest(".o_kanban_dms_file_preview")
        ) {
            return super.onGlobalClick(ev);
        }
        this.openPreview();
    }
}
