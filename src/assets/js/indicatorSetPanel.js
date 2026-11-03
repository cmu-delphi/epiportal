/* Side panel listing one indicator set's metadata, opened by clicking the
 * set's name in the indicator sets table. The table only shows a few columns,
 * so this is where people see everything they need to decide whether a set
 * is worth using. It is filled from the table's own row data; the related
 * indicators stay in the table's expanded row.
 *
 * The panel is a non-modal <dialog> so the table stays usable while it is
 * open: clicking another set's name swaps the panel's contents. Esc, the
 * close button, or a click anywhere outside the panel closes it.
 *
 * All values come from the metadata sheet, so they are inserted as text,
 * never as HTML. */
(function () {
    var panel = document.getElementById("indicatorSetPanel");
    if (!panel || typeof table === "undefined") {
        return;
    }
    var body = panel.querySelector(".indicator-set-panel-body");
    var footer = panel.querySelector(".indicator-set-panel-footer");
    var providerEl = panel.querySelector(".indicator-set-panel-provider");
    var titleEl = panel.querySelector(".indicator-set-panel-title");
    var tagsEl = panel.querySelector(".indicator-set-panel-tags");
    var shownSetId = null;
    var returnFocusTo = null;

    var URL_PATTERN = /(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)\]])/;

    function clean(value) {
        return value === null || value === undefined ? "" : String(value).trim();
    }

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text) {
            node.textContent = text;
        }
        return node;
    }

    function externalLink(href, text) {
        var link = el("a", "", text || href);
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener";
        return link;
    }

    // Text with any http(s) addresses in it turned into links.
    function linkified(text) {
        var fragment = document.createDocumentFragment();
        text.split(URL_PATTERN).forEach(function (part, index) {
            if (!part) {
                return;
            }
            // split() with a capture group puts the matches at odd indices.
            fragment.appendChild(
                index % 2 === 1 ? externalLink(part) : document.createTextNode(part)
            );
        });
        return fragment;
    }

    function pills(names) {
        var wrap = el("div", "indicator-set-panel-pills");
        names.forEach(function (name) {
            wrap.appendChild(el("span", "badge badge-pill-outline", name));
        });
        return wrap;
    }

    function displayNames(items) {
        return (items || []).map(function (item) {
            return clean(item.display_name);
        }).filter(Boolean);
    }

    // A labelled value, or null when there is nothing to show.
    function field(label, content, wide) {
        if (!content || (typeof content === "string" && !clean(content))) {
            return null;
        }
        var item = el("div", "indicator-set-panel-field" + (wide ? " wide" : ""));
        item.appendChild(el("div", "indicator-set-panel-label", label));
        var value = el("div", "indicator-set-panel-value");
        value.appendChild(typeof content === "string" ? document.createTextNode(clean(content)) : content);
        item.appendChild(value);
        return item;
    }

    function pillsField(label, names, wide) {
        return names.length ? field(label, pills(names), wide) : null;
    }

    // A block of fields, left out entirely when every field in it is empty.
    function section(className, fields) {
        var present = fields.filter(Boolean);
        if (!present.length) {
            return null;
        }
        var block = el("div", className);
        present.forEach(function (node) {
            block.appendChild(node);
        });
        return block;
    }

    function temporalScope(row) {
        var start = clean(row.temporal_scope_start);
        var end = clean(row.temporal_scope_end);
        return start || end ? (start || "—") + " → " + (end || "—") : "";
    }

    function maintainer(row) {
        var name = clean(row.maintainer_name);
        var email = clean(row.maintainer_email);
        if (!name && !email) {
            return null;
        }
        var fragment = document.createDocumentFragment();
        if (name) {
            fragment.appendChild(document.createTextNode(name));
        }
        if (email) {
            if (name) {
                fragment.appendChild(document.createTextNode(" · "));
            }
            var mail = el("a", "", email);
            mail.href = "mailto:" + email;
            fragment.appendChild(mail);
        }
        return fragment;
    }

    function render(row) {
        providerEl.textContent = clean(row.original_data_provider);
        providerEl.hidden = !providerEl.textContent;
        titleEl.textContent = indicatorSetLabel(row);

        tagsEl.replaceChildren();
        displayNames(row.pathogens).forEach(function (name) {
            tagsEl.appendChild(el("span", "badge badge-pill-outline", name));
        });
        if (clean(row.temporal_scope_end) === "Ongoing") {
            tagsEl.appendChild(el("span", "indicator-set-panel-tag ongoing", "Ongoing"));
        }
        if (row.delphi_hosted === "Yes") {
            tagsEl.appendChild(el("span", "indicator-set-panel-tag hosted", "Hosted by Delphi"));
        }

        var granularities = clean(row.temporal_granularity)
            .split(",")
            .map(clean)
            .filter(Boolean);
        var location = clean(row.dataset_location);
        var origin = clean(row.origin_datasource);

        var notes = section("indicator-set-panel-notes-body", [
            field("Pre-processing", row.preprocessing_description, true),
            field("Censoring", row.censoring, true),
            field("Missingness", row.missingness, true),
        ]);
        var notesBlock = null;
        if (notes) {
            notesBlock = el("details", "indicator-set-panel-notes");
            notesBlock.open = true;
            notesBlock.appendChild(el("summary", "", "Data quality notes"));
            notesBlock.appendChild(notes);
        }

        body.replaceChildren(
            ...[
                clean(row.description) ? el("p", "indicator-set-panel-description", clean(row.description)) : null,
                section("indicator-set-panel-grid", [
                    field("Temporal scope", temporalScope(row)),
                    pillsField("Temporal granularity", granularities),
                    pillsField("Geographic levels", displayNames(row.geographic_levels), true),
                    field("Geographic coverage", row.geographic_scope),
                    pillsField("Surveillance categories", displayNames(row.severity_pyramid_rungs)),
                    field("Data type", row.data_type, true),
                    field("Reporting cadence", row.reporting_cadence),
                    field("Reporting lag (nominal)", row.reporting_lag),
                    field("Revision cadence", row.revision_cadence, true),
                    field("Population", row.demographic_scope),
                    field("Population stratifiers", row.demographic_granularity),
                    field("DUA required?", row.dua_required),
                    field("Data use terms", row.license),
                    field("Origin data source", origin ? linkified(origin) : null, true),
                ]),
                section("indicator-set-panel-grid", [
                    field("Dataset location", location ? linkified(location) : null, true),
                    field("Maintainer", maintainer(row), true),
                ]),
                notesBlock,
            ].filter(Boolean)
        );
        body.scrollTop = 0;

        footer.replaceChildren();
        var docs = clean(row.documentation_link);
        if (/^https?:\/\//i.test(docs)) {
            var button = externalLink(docs, "Documentation ↗");
            button.className = "btn btn-primary";
            footer.appendChild(button);
        }
        footer.hidden = !footer.children.length;
    }

    function openPanel(row, trigger) {
        render(row);
        shownSetId = row.DT_RowId;
        returnFocusTo = trigger || null;
        if (!panel.open) {
            panel.show();
        }
        panel.querySelector(".indicator-set-panel-close").focus();
    }

    function closePanel() {
        if (!panel.open) {
            return;
        }
        panel.close();
        shownSetId = null;
        if (returnFocusTo && document.contains(returnFocusTo)) {
            returnFocusTo.focus();
        }
        returnFocusTo = null;
    }

    $("#indicatorSetsTable tbody").on("click", ".indicator-set-name-link", function (event) {
        event.preventDefault();
        var row = table.row($(this).closest("tr")).data();
        if (!row) {
            return;
        }
        if (panel.open && shownSetId === row.DT_RowId) {
            closePanel();
        } else {
            openPanel(row, this);
        }
    });

    panel.querySelector(".indicator-set-panel-close").addEventListener("click", closePanel);

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && panel.open) {
            closePanel();
        }
    });

    // Close on a click outside the panel, except on another set's name, which
    // swaps the contents instead, and on popovers the page shows above it.
    document.addEventListener("click", function (event) {
        if (!panel.open || panel.contains(event.target)) {
            return;
        }
        if (event.target.closest(".indicator-set-name-link, .popover")) {
            return;
        }
        closePanel();
    });
})();
