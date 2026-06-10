// /** ********************************************************************************
//     File Explorer search model.
//     Holds the "current location" (a dms.directory) and a back/forward
//     navigation history. The file list is filtered to that location's DIRECT
//     files; the renderer shows its direct subfolders as tiles and a breadcrumb.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Domain} from "@web/core/domain";
import {SearchModel} from "@web/search/search_model";

export class FileExplorerSearchModel extends SearchModel {
    // Current location (a dms.directory id, or false for the root) and the
    // browser-style navigation history.
    explorerDirectoryId = false;
    explorerHistory = [];
    explorerHistoryIndex = -1;

    /**
     * Make `directoryId` the current location (falsy = root). Records the move
     * in the navigation history unless it comes from back/forward.
     */
    selectDirectory(directoryId, {fromHistory = false} = {}) {
        const id = directoryId || false;
        if (id === this.explorerDirectoryId && !fromHistory) {
            return;
        }
        this.explorerDirectoryId = id;
        if (!fromHistory) {
            // Drop any "forward" entries, then push the new location.
            this.explorerHistory = this.explorerHistory.slice(
                0,
                this.explorerHistoryIndex + 1
            );
            this.explorerHistory.push(id);
            this.explorerHistoryIndex = this.explorerHistory.length - 1;
        }
        this._notify();
    }

    get canGoBack() {
        return this.explorerHistoryIndex > 0;
    }

    get canGoForward() {
        return this.explorerHistoryIndex < this.explorerHistory.length - 1;
    }

    goBack() {
        if (this.canGoBack) {
            this.explorerHistoryIndex--;
            this.selectDirectory(this.explorerHistory[this.explorerHistoryIndex], {
                fromHistory: true,
            });
        }
    }

    goForward() {
        if (this.canGoForward) {
            this.explorerHistoryIndex++;
            this.selectDirectory(this.explorerHistory[this.explorerHistoryIndex], {
                fromHistory: true,
            });
        }
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
