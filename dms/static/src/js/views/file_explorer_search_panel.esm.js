// /** ********************************************************************************
//     File Explorer search panel: replaces the standard category search panel
//     with the dms_list folder/file tree (the same widget used on the Documents
//     tab and the Task view). Selecting a folder filters the file kanban to that
//     folder and its descendants; clicking a file previews it (handled by the
//     tree itself).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Component} from "@odoo/owl";
import {View} from "@web/views/view";

export class FileExplorerSearchPanel extends Component {
    static template = "dms.FileExplorerSearchPanel";
    static components = {View};
    static props = {};

    /**
     * Props for the embedded dms_list tree (dms.storage). The control panel and
     * the view's own search panel are hidden so only the tree shows; "explorer"
     * makes the tree read-only (no upload / management context menu / drop).
     */
    get dmsTreeViewProps() {
        return {
            type: "dms_list",
            resModel: "dms.storage",
            domain: [],
            display: {controlPanel: false, searchPanel: false},
            explorer: true,
            onTreeDirectorySelected: (directoryId) =>
                this.env.searchModel.selectDirectory(directoryId),
            // Stable reference so the tree can subscribe to grid navigation and
            // highlight/expand the current folder (keeping both panels in sync).
            explorerSearchModel: this.env.searchModel,
        };
    }
}
