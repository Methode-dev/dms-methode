/** @odoo-module **/
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class DmsPdfMergeDialog extends Component {
    static template = "dms_pdf_merge.PdfMergeDialog";
    static components = { Dialog };
    static props = {
        "*": true,
        model: { type: String, optional: true },
        resId: { type: Number, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");
        this.ui = useService("ui");
        this.state = useState({
            pageOrder: [],
            selectedPages: new Set(),
            isLoading: true,
            isMerging: false,
            error: null,
            recordName: "",
            filename: "",
        });

        this.fileInputRef = useRef("fileInput");

        onWillStart(async () => {
            this.ui.block();
            try {
                await this.loadData();
            } finally {
                this.ui.unblock();
            }
        });
    }

    get model() {
        return this.props.model || this.props.action?.props?.model;
    }

    get resId() {
        return this.props.resId || this.props.action?.props?.resId;
    }

    closeDialog() {
        if (this.props.close) {
            this.props.close();
        } else {
            this.action.doAction({ type: "ir.actions.act_window_close" });
        }
    }

    onCheckboxClick(ev, index) {
        ev.preventDefault();
        ev.stopPropagation();
        this.togglePageSelection(index);
    }

    togglePageSelection(index) {
        const newSelection = new Set(this.state.selectedPages);
        if (newSelection.has(index)) {
            newSelection.delete(index);
        } else {
            newSelection.add(index);
        }
        this.state.selectedPages = newSelection;
    }

    selectAll() {
        this.state.selectedPages = new Set(
            Array.from({ length: this.state.pageOrder.length }, (_, i) => i)
        );
    }

    deselectAll() {
        this.state.selectedPages = new Set();
    }

    triggerFileInput() {
        this.fileInputRef.el.click();
    }

    handleDragStart = (e, index) => {
        e.dataTransfer.setData("text/plain", index.toString());
        e.dataTransfer.effectAllowed = "move";
    };

    handleDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
    };

    handleDrop = (e, targetIndex) => {
        e.preventDefault();
        const sourceIndex = parseInt(e.dataTransfer.getData("text/plain"));
        if (isNaN(sourceIndex) || sourceIndex === targetIndex) return;

        const newPageOrder = [...this.state.pageOrder];
        const [movedItem] = newPageOrder.splice(sourceIndex, 1);
        newPageOrder.splice(targetIndex, 0, movedItem);
        this.state.pageOrder = newPageOrder;

        // Update selected pages indices
        const newSelection = new Set();
        this.state.selectedPages.forEach((idx) => {
            if (idx === sourceIndex) {
                newSelection.add(targetIndex);
            } else if (sourceIndex < targetIndex) {
                if (idx > sourceIndex && idx <= targetIndex) {
                    newSelection.add(idx - 1);
                } else {
                    newSelection.add(idx);
                }
            } else {
                if (idx >= targetIndex && idx < sourceIndex) {
                    newSelection.add(idx + 1);
                } else {
                    newSelection.add(idx);
                }
            }
        });

        this.state.selectedPages = newSelection;
    };

    async loadData() {
        try {
            const result = await rpc("/dms_pdf_merge/load_data", {
                model: this.model,
                res_id: this.resId,
            });

            if (result.error) {
                this.state.error = result.error;
            } else {
                this.state.pageOrder = result.pages || [];
                this.state.recordName = result.record_name || "";
                this.state.filename = result.default_filename || "merged.pdf";

                if (result.report_error) {
                    this.notification.add(
                        `Could not generate report: ${result.report_error}`,
                        { type: "warning" }
                    );
                }

                // Select all pages by default
                this.state.selectedPages = new Set(
                    Array.from({ length: this.state.pageOrder.length }, (_, i) => i)
                );
            }
        } catch (error) {
            this.state.error = "Failed to load PDF data";
            console.error("Error:", error);
        } finally {
            this.state.isLoading = false;
        }
    }

    async onFileUpload(e) {
        const files = e.target.files;
        if (files.length === 0) return;

        const file = files[0];
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            this.notification.add("Please upload only PDF files", { type: "warning" });
            this.fileInputRef.el.value = "";
            return;
        }

        this.ui.block();
        const reader = new FileReader();
        reader.onload = async (ev) => {
            try {
                const result = await rpc("/dms_pdf_merge/process_uploaded_file", {
                    file_content: ev.target.result.split(",")[1],
                    start_page: this.state.pageOrder.length + 1,
                });

                if (result.error) {
                    this.notification.add(result.error, { type: "danger" });
                    return;
                }

                const currentLength = this.state.pageOrder.length;
                const newPages = result.pages.map((page) => ({
                    type: "uploaded",
                    id: page.id,
                    name: file.name,
                    page_number: page.page_number,
                    preview_url: page.preview_url,
                    content: page.content,
                }));

                this.state.pageOrder = [...this.state.pageOrder, ...newPages];

                // Select new pages
                const newSelection = new Set(this.state.selectedPages);
                for (let i = 0; i < newPages.length; i++) {
                    newSelection.add(currentLength + i);
                }
                this.state.selectedPages = newSelection;

                this.fileInputRef.el.value = "";
            } catch (error) {
                this.notification.add("Failed to process PDF file: " + error.message, {
                    type: "danger",
                });
                console.error("File upload error:", error);
            } finally {
                this.ui.unblock();
            }
        };
        reader.onerror = () => {
            this.notification.add("Error reading file", { type: "danger" });
            this.ui.unblock();
        };
        reader.readAsDataURL(file);
    }

    async mergeAndSave() {
        if (this.state.selectedPages.size === 0) {
            this.notification.add("Please select at least one page to merge", {
                type: "warning",
            });
            return;
        }

        this.state.isMerging = true;
        this.ui.block();

        try {
            const selectedPages = [];
            this.state.pageOrder.forEach((page, index) => {
                if (this.state.selectedPages.has(index)) {
                    selectedPages.push({
                        type: page.type,
                        id: page.id,
                        page_number: page.page_number,
                        content: page.content,
                    });
                }
            });

            const result = await rpc("/dms_pdf_merge/save", {
                model: this.model,
                res_id: this.resId,
                pages: selectedPages,
                filename: this.state.filename,
            });

            if (result.success) {
                this.notification.add(
                    `PDF saved as "${result.filename}" in ${result.directory_name}`,
                    { type: "success" }
                );
                this.closeDialog();
            } else {
                this.notification.add(result.error || "Merge failed", { type: "danger" });
            }
        } catch (error) {
            this.notification.add("Error during merge: " + error.message, {
                type: "danger",
            });
            console.error("Merge error:", error);
        } finally {
            this.state.isMerging = false;
            this.ui.unblock();
        }
    }

    deletePage(index) {
        const newPageOrder = [...this.state.pageOrder];
        newPageOrder.splice(index, 1);
        this.state.pageOrder = newPageOrder;

        // Update selection
        const newSelection = new Set();
        this.state.selectedPages.forEach((idx) => {
            if (idx < index) {
                newSelection.add(idx);
            } else if (idx > index) {
                newSelection.add(idx - 1);
            }
            // idx === index is removed
        });
        this.state.selectedPages = newSelection;
    }

    getPageBadge(page) {
        if (page.type === "report") return "Report";
        if (page.type === "attachment") return "Attachment";
        if (page.type === "dms") return "Document";
        if (page.type === "uploaded") return "Uploaded";
        return "";
    }

    getPageBadgeClass(page) {
        if (page.type === "report") return "bg-primary";
        if (page.type === "attachment") return "bg-success";
        if (page.type === "dms") return "bg-warning";
        if (page.type === "uploaded") return "bg-info";
        return "bg-secondary";
    }
}

registry.category("actions").add("dms_pdf_merge_dialog", DmsPdfMergeDialog);
