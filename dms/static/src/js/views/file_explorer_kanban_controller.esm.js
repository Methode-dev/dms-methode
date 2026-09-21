// /** ********************************************************************************
//     File Explorer kanban controller.
//     Owns the control panel's left-hand button area for the explorer, and
//     offers `explorerTopbarButtons()` as the seam host modules add to — the
//     same arrangement as the renderer's `backgroundContextMenuItems()` for the
//     blank-area right-click menu.
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {KanbanController} from "@web/views/kanban/kanban_controller";
import {useService} from "@web/core/utils/hooks";

export class FileExplorerKanbanController extends KanbanController {
    setup() {
        super.setup();
        // KanbanController takes the action and dialog services but not the
        // ORM; a top bar button that opens a wizard needs it.
        this.orm = useService("orm");
    }

    /**
     * Buttons shown at the top left of the control panel, in order.
     *
     * The explorer itself adds none: it is `create="0"`, so the inherited
     * Upload button is hidden and the area is empty until a host module fills
     * it. Patch this and push a descriptor:
     *
     *   {
     *     id: "my_module_action",     // unique, used as the render key
     *     label: "Do the thing",      // translated by the caller
     *     icon: "fa fa-file-text-o",  // optional
     *     className: "btn-primary",   // optional, defaults to btn-primary
     *     title: "Why it is off",     // optional tooltip
     *     disabled: false,            // optional
     *     action: () => this.doIt(),  // called on click
     *   }
     */
    explorerTopbarButtons() {
        return [];
    }
}
