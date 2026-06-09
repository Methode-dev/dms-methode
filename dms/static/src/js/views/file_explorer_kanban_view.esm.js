// /** ********************************************************************************
//     File Explorer kanban view (js_class="file_explorer_kanban").
//     Same as the file kanban view, but clicking a file always previews it.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {FileExplorerKanbanRenderer} from "./file_explorer_kanban_renderer.esm";
import {FileExplorerSearchModel} from "./file_explorer_search_model.esm";
import {FileExplorerSearchPanel} from "./file_explorer_search_panel.esm";
import {FileKanbanView} from "./file_kanban_view.esm";
import {registry} from "@web/core/registry";

export const FileExplorerKanbanView = {
    ...FileKanbanView,
    Renderer: FileExplorerKanbanRenderer,
    // Left panel: the dms_list folder/file tree (same as Documents tab / Task
    // view) instead of the standard category search panel.
    SearchPanel: FileExplorerSearchPanel,
    // Recursive directory filtering driven by the tree selection.
    SearchModel: FileExplorerSearchModel,
};

registry.category("views").add("file_explorer_kanban", FileExplorerKanbanView);
