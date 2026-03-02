/* @odoo-module */

import {Component, onMounted, onPatched, useRef} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {useService} from "@web/core/utils/hooks";

/**
 * Widget that renders review_documents_html and hooks up
 * eye-icon clicks to the Odoo file viewer (same as preview_widget).
 */
export class CRReviewDocuments extends Component {
    static template = "spp_change_request_v2.CRReviewDocuments";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.fileViewer = useFileViewer();
        this.rootRef = useRef("root");

        onMounted(() => this._bindPreviewClicks());
        onPatched(() => this._bindPreviewClicks());
    }

    get htmlContent() {
        return this.props.record.data[this.props.name] || "";
    }

    _bindPreviewClicks() {
        const root = this.rootRef.el;
        if (!root) return;

        for (const el of root.querySelectorAll(".o_cr_doc_preview")) {
            el.addEventListener("click", (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                const docId = parseInt(el.dataset.docId);
                if (docId) this._openPreview(docId);
            });
        }
    }

    async _openPreview(docId) {
        const [record] = await this.orm.read("spp.dms.file", [docId], ["content", "name", "mimetype"]);
        if (!record || !record.content) return;

        const binaryData = atob(record.content);
        const arrayBuffer = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
            arrayBuffer[i] = binaryData.charCodeAt(i);
        }

        const blob = new Blob([arrayBuffer], {type: record.mimetype});
        const fileUrl = URL.createObjectURL(blob);

        if (record.mimetype === "application/pdf") {
            window.open(fileUrl, "_blank");
        } else {
            this.fileViewer.open({
                isImage: Boolean(record.mimetype.startsWith("image/")),
                isVideo: Boolean(record.mimetype.startsWith("video/")),
                isViewable: true,
                displayName: record.name,
                defaultSource: fileUrl,
                downloadUrl: fileUrl,
            });
        }
    }
}

const crReviewDocuments = {
    component: CRReviewDocuments,
    supportedTypes: ["html"],
};

registry.category("fields").add("cr_review_documents", crReviewDocuments);
