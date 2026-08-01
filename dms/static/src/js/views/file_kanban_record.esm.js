// /** ********************************************************************************
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {KanbanRecord} from "@web/views/kanban/kanban_record";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {FileModel} from "@web/core/file_viewer/file_model";

const videoReadableTypes = ["x-matroska", "mp4", "webm"];
const audioReadableTypes = ["mp3", "ogg", "wav", "aac", "mpa", "flac", "m4a"];

export class DmsFileModel extends FileModel {
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
     * Build the file-viewer model for any dms.file record of this view.
     * Extracted so subclasses can build one for records other than their own
     * (e.g. the File Explorer kanban, which feeds the viewer the whole grid so
     * its prev/next arrows can navigate).
     */
    buildViewerFile(record) {
        const fileExt = record.data.name.split(".").pop();
        let mimetype = record.data.mimetype;

        if (videoReadableTypes.includes(fileExt)) {
            mimetype = `video/${fileExt}`;
        } else if (audioReadableTypes.includes(fileExt)) {
            mimetype = "audio/mpeg";
        }

        return Object.assign(new DmsFileModel(), {
            id: record.data.id,
            name: record.data.name,
            mimetype: mimetype,
        });
    }

    /**
     * Open this record's file in the in-page file viewer (when the type is
     * previewable). Extracted so subclasses (e.g. the File Explorer kanban)
     * can reuse it.
     */
    openPreview() {
        this.fileViewer.open(this.buildViewerFile(this.props.record));
    }

    /**
     * @override
     *
     * Override to open the preview upon clicking the image, if compatible.
     */
    onGlobalClick(ev) {
        if (ev.target.closest(".o_kanban_dms_file_preview")) {
            this.openPreview();
            return;
        }
        return super.onGlobalClick(ev);
    }
}
