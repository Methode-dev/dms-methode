// /** ********************************************************************************
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {KanbanRecord} from "@web/views/kanban/kanban_record";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {FileModel} from "@web/core/file_viewer/file_model";

const videoReadableTypes = ["x-matroska", "mp4", "webm"];
const audioReadableTypes = ["mp3", "ogg", "wav", "aac", "mpa", "flac", "m4a"];

class DmsFileModel extends FileModel {
    get urlRoute() {
        return `/web/content`;
    }
    get urlQueryParams() {
        return {
            id: this.id,
            field: "content",
            model: "dms.file",
            filename_field: "name",
        };
    }
}

export class FileKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        this.fileViewer = useFileViewer();
    }

    /**
     * @override
     *
     * Override to open the preview upon clicking the image, if compatible.
     */
    onGlobalClick(ev) {
        if (ev.target.closest(".o_kanban_dms_file_preview")) {
            const record = this.props.record;
            const fileExt = record.data.name.split(".").pop();
            let mimetype = record.data.mimetype;

            if (videoReadableTypes.includes(fileExt)) {
                mimetype = `video/${fileExt}`;
            } else if (audioReadableTypes.includes(fileExt)) {
                mimetype = "audio/mpeg";
            }

            const file = Object.assign(new DmsFileModel(), {
                id: record.data.id,
                name: record.data.name,
                mimetype: mimetype,
            });
            this.fileViewer.open(file);
            return;
        }
        return super.onGlobalClick(ev);
    }
}
