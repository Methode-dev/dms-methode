// /** ********************************************************************************
//     File Explorer search model.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Domain} from "@web/core/domain";
import {SearchModel} from "@web/search/search_model";

export class FileExplorerSearchModel extends SearchModel {
    /**
     * Make `directoryId` the current location. The file list then shows that
     * folder's DIRECT files (OS-style); its direct subfolders are shown as tiles
     * by the renderer. Pass a falsy id for the root (no loose files there).
     */
    selectDirectory(directoryId) {
        this.explorerDirectoryId = directoryId || false;
        this._notify();
    }

    /**
     * @override
     *
     * Restrict the file list to the current location's DIRECT files
     * (directory_id = current). At the root (no selection) directory_id = false
     * matches no files, since every file lives in a directory.
     */
    _getDomain(params = {}) {
        const base = super._getDomain({...params, raw: true});
        const domain = Domain.and([
            base,
            new Domain([["directory_id", "=", this.explorerDirectoryId || false]]),
        ]);
        return params.raw ? domain : domain.toList(this.domainEvalContext);
    }
}
