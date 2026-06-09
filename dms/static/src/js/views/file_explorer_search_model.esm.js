// /** ********************************************************************************
//     File Explorer search model.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Domain} from "@web/core/domain";
import {SearchModel} from "@web/search/search_model";

export class FileExplorerSearchModel extends SearchModel {
    /**
     * Filter the file list to the files contained in the selected directory and
     * all of its descendants. Called by the File Explorer search panel when a
     * folder is picked in the tree. Pass a falsy id to clear the filter.
     */
    selectDirectory(directoryId) {
        this.explorerDirectoryId = directoryId || false;
        this._notify();
    }

    /**
     * @override
     *
     * AND in the recursive directory filter when a folder is selected. We use
     * "child_of" (recursive) directly here rather than the search-panel
     * category mechanism, which the dms module patches to a non-recursive "=".
     */
    _getDomain(params = {}) {
        const base = super._getDomain({...params, raw: true});
        let domain = base;
        if (this.explorerDirectoryId) {
            domain = Domain.and([
                base,
                new Domain([["directory_id", "child_of", this.explorerDirectoryId]]),
            ]);
        }
        return params.raw ? domain : domain.toList(this.domainEvalContext);
    }
}
