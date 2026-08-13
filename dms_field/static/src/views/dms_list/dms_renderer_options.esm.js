/* License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */

/**
 * Per-usage configuration for the embedded DMS tree.
 *
 * The widget is rendered through two different code paths (the full `dms_list`
 * view via DmsListController, and `mode="dms_list"` on a field via the patched
 * X2ManyField), and until now only the first one could pass renderer props — so
 * a host module had no way to tune the widget from XML. Options are resolved
 * once in the shared controller mixin and handed to the renderer as a single
 * `options` prop, which makes both paths configurable the same way.
 *
 * They are read from two places and merged, the field tag winning:
 *
 *   <dms_list options="{'files_only': True}">                     (arch root)
 *   <field name="dms_directory_ids" mode="dms_list"
 *          options="{'preview_navigation': 'folder'}"/>           (field tag)
 *
 * XML uses snake_case (Odoo convention); the renderer sees camelCase. Both
 * spellings are accepted so JS embedders can pass camelCase directly.
 */

export const PREVIEW_NAVIGATION_MODES = ["tree", "folder", "none"];

export const DMS_RENDERER_OPTION_DEFAULTS = {
    // Which files the in-page viewer's prev/next arrows cycle through:
    //   "tree"   - every file currently visible in the tree, in display order,
    //              so expanded nested folders contribute their files too
    //   "folder" - only files under the previewed file's own folder
    //   "none"   - no navigation, the previewed file on its own
    previewNavigation: "tree",
    // Expand every folder on load instead of only the first depth.
    openAllFolders: false,
    // Leave only files selectable (folders stay navigation-only).
    filesOnly: false,
};

// Both spellings map to the same renderer option.
const OPTION_NAMES = {
    preview_navigation: "previewNavigation",
    previewNavigation: "previewNavigation",
    open_all_folders: "openAllFolders",
    openAllFolders: "openAllFolders",
    files_only: "filesOnly",
    filesOnly: "filesOnly",
};

/**
 * Merge the given raw option dicts (later sources win) over the defaults,
 * keeping only known keys and coercing them to their expected type.
 *
 * @param {...Object} sources raw option dicts, e.g. the arch root's `options`
 *      attribute and the field tag's `options`
 * @returns {Object} a complete option set, safe to spread onto the renderer
 */
export function extractDmsRendererOptions(...sources) {
    const options = {...DMS_RENDERER_OPTION_DEFAULTS};
    for (const source of sources) {
        for (const [key, value] of Object.entries(source || {})) {
            const name = OPTION_NAMES[key];
            if (name !== undefined && value !== undefined) {
                options[name] = value;
            }
        }
    }
    // An unknown navigation mode would silently disable the arrows; fall back
    // to the default instead.
    if (!PREVIEW_NAVIGATION_MODES.includes(options.previewNavigation)) {
        options.previewNavigation = DMS_RENDERER_OPTION_DEFAULTS.previewNavigation;
    }
    options.openAllFolders = Boolean(options.openAllFolders);
    options.filesOnly = Boolean(options.filesOnly);
    return options;
}
