// /** ********************************************************************************
//     File Explorer: turn the main (control-panel) search bar into a live,
//     storage-wide search of files AND folders. Typing filters as you go (no
//     autocomplete dropdown / facets); the Filters & Group By options of the
//     same bar keep working alongside it. Gated to the File Explorer via the
//     custom search model's `isFileExplorer` marker, so every other view keeps
//     the standard behaviour.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {onWillUnmount} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {SearchBar} from "@web/search/search_bar/search_bar";
import {useBus} from "@web/core/utils/hooks";

patch(SearchBar.prototype, {
    setup() {
        super.setup();
        const searchModel = this.env.searchModel;
        if (searchModel && searchModel.isFileExplorer) {
            // Reset the input when the search is cleared elsewhere (e.g.
            // navigating into a folder exits search mode).
            useBus(searchModel, "update", () => {
                if (
                    this.inputRef.el &&
                    !searchModel.explorerSearchTerm &&
                    this.inputRef.el.value
                ) {
                    this.inputRef.el.value = "";
                }
            });
            onWillUnmount(() => {
                if (this._fileExplorerSearchTimer) {
                    clearTimeout(this._fileExplorerSearchTimer);
                }
            });
        }
    },

    onSearchInput(ev) {
        const searchModel = this.env.searchModel;
        if (searchModel && searchModel.isFileExplorer) {
            // Live search instead of the autocomplete/facet flow.
            this.inputDropdownState.close();
            const value = ev.target.value;
            if (this._fileExplorerSearchTimer) {
                clearTimeout(this._fileExplorerSearchTimer);
            }
            this._fileExplorerSearchTimer = setTimeout(() => {
                searchModel.setSearchTerm(value.trim());
            }, 250);
            return;
        }
        return super.onSearchInput(ev);
    },
});
