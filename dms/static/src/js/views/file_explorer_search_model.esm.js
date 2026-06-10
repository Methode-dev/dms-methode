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
    // Marker used by the patched control-panel SearchBar to enable the live,
    // storage-wide File Explorer search on the main search bar.
    isFileExplorer = true;
    // Current location (a dms.directory id, or false for the root) and the
    // browser-style navigation history.
    explorerDirectoryId = false;
    explorerHistory = [];
    explorerHistoryIndex = -1;
    // Live search across the current storage (set by the top search bar).
    explorerSearchTerm = "";
    explorerStorageId = false;

    /**
     * Make `directoryId` the current location (falsy = root). Records the move
     * in the navigation history unless it comes from back/forward. Navigating
     * always exits search mode.
     */
    selectDirectory(directoryId, {fromHistory = false} = {}) {
        const id = directoryId || false;
        if (
            id === this.explorerDirectoryId &&
            !this.explorerSearchTerm &&
            !fromHistory
        ) {
            return;
        }
        this.explorerDirectoryId = id;
        this.explorerSearchTerm = "";
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

    /** Live search term from the top search bar. Empty => browse mode. */
    setSearchTerm(term) {
        const value = term || "";
        if (value === this.explorerSearchTerm) {
            return;
        }
        this.explorerSearchTerm = value;
        this._notify();
    }

    get isExplorerSearching() {
        return Boolean(this.explorerSearchTerm);
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
     * Browse mode: restrict the file list to the current location's DIRECT
     * files (directory_id = current; the root matches no loose files).
     * Search mode: drop the location filter and match files by name anywhere in
     * the current storage (flat results).
     */
    _getDomain(params = {}) {
        const base = super._getDomain({...params, raw: true});
        let extra;
        if (this.explorerSearchTerm) {
            extra = new Domain([["name", "ilike", this.explorerSearchTerm]]);
            if (this.explorerStorageId) {
                extra = Domain.and([
                    extra,
                    new Domain([["storage_id", "=", this.explorerStorageId]]),
                ]);
            }
        } else {
            extra = new Domain([
                ["directory_id", "=", this.explorerDirectoryId || false],
            ]);
        }
        const domain = Domain.and([base, extra]);
        return params.raw ? domain : domain.toList(this.domainEvalContext);
    }
}
