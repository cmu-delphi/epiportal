// Row selection for the Indicator Sets table.
//
// Selected indicator set IDs live in the URL (?selected=1,2,3&only_selected=1) so that a
// selected view can be bookmarked or shared, and so that selections survive the full page
// reload that every filter change triggers.  The filter form submits via GET, so the same
// values are mirrored into hidden inputs on that form.

var SELECTED_PARAM = "selected";
var ONLY_SELECTED_PARAM = "only_selected";

function parseSelectedIds(rawValue) {
    if (!rawValue) {
        return [];
    }
    var ids = [];
    rawValue.split(",").forEach(function (part) {
        var id = part.trim();
        if (/^\d+$/.test(id) && ids.indexOf(id) === -1) {
            ids.push(id);
        }
    });
    return ids;
}

// Selected IDs are kept as strings, in the order the user picked them.
var selectedIndicatorSets = parseSelectedIds(
    new URLSearchParams(window.location.search).get(SELECTED_PARAM)
);
var showOnlySelected =
    ["1", "true", "on"].indexOf(
        new URLSearchParams(window.location.search).get(ONLY_SELECTED_PARAM)
    ) !== -1 && selectedIndicatorSets.length > 0;

function isIndicatorSetSelected(indicatorSetId) {
    return selectedIndicatorSets.indexOf(String(indicatorSetId)) !== -1;
}

function setIndicatorSetSelected(indicatorSetId, selected) {
    var wasShowingOnlySelected = showOnlySelected;
    var id = String(indicatorSetId);
    var index = selectedIndicatorSets.indexOf(id);
    if (selected && index === -1) {
        selectedIndicatorSets.push(id);
    } else if (!selected && index !== -1) {
        selectedIndicatorSets.splice(index, 1);
    }
    // A "selected only" view with nothing selected would show every row, which reads as a
    // broken filter - drop back to the unfiltered view instead.
    if (selectedIndicatorSets.length === 0) {
        showOnlySelected = false;
    }
    // Only the selected-only view depends on the row set, so skip the redraw otherwise.
    persistSelection(wasShowingOnlySelected || showOnlySelected);
}

function clearIndicatorSetSelection() {
    var wasShowingOnlySelected = showOnlySelected;
    selectedIndicatorSets = [];
    showOnlySelected = false;
    persistSelection(wasShowingOnlySelected);
}

function setShowOnlySelected(onlySelected) {
    var wasShowingOnlySelected = showOnlySelected;
    showOnlySelected = onlySelected && selectedIndicatorSets.length > 0;
    persistSelection(true);
    // Rows this view hides are detached from the tbody, so the delegated click that
    // expandSelectedRows() relies on never reaches them.  Re-run it once they are back.
    if (
        wasShowingOnlySelected &&
        !showOnlySelected &&
        typeof expandSelectedRows === "function"
    ) {
        expandSelectedRows();
    }
}

// Write the current selection to the URL, the filter form, the checkboxes and the toolbar.
function persistSelection(redraw) {
    syncSelectionToUrl();
    syncSelectionToFilterForm();
    syncSelectionToClearFiltersLink();
    syncCheckboxesToSelection();
    updateSelectionToolbar();
    if (redraw && typeof table !== "undefined") {
        table.draw(false);
    }
    updateSelectionStatsNote();
}

// The stats sentence above the table comes from get_table_stats_info/, which only knows the
// server-side filters, so it keeps counting rows this view is hiding.  Annotate it rather
// than leave it contradicting the table underneath.
function updateSelectionStatsNote() {
    var info = document.getElementById("indicatorSetsInfo");
    if (!info) {
        return;
    }
    var note = document.getElementById("selectionStatsNote");
    if (!showOnlySelected) {
        if (note) {
            note.remove();
        }
        return;
    }
    if (!note) {
        note = document.createElement("div");
        note.id = "selectionStatsNote";
        note.className = "selection-stats-note";
        info.parentNode.insertBefore(note, info.nextSibling);
    }
    var selected = selectedIndicatorSets.length;
    var shown =
        typeof table !== "undefined"
            ? table.rows({ search: "applied" }).count()
            : selected;
    var sets = typeof pluralize === "function" ? pluralize(selected, "set") : "sets";
    if (shown === selected) {
        note.textContent = `Showing only your ${selected} selected indicator ${sets}.`;
    } else {
        note.textContent = `Showing ${shown} of your ${selected} selected indicator ${sets}; the rest are excluded by your specified filters.`;
    }
}

// DataTables caches the rendered cells, so a redraw will not re-run the checkbox renderer.
// Selection changes made outside the checkboxes themselves (clearing the selection, or a
// row hidden by the selected-only view) therefore have to update them directly.
function syncCheckboxesToSelection() {
    if (typeof table === "undefined") {
        return;
    }
    table.rows().every(function () {
        var row = this.node();
        if (!row) {
            return;
        }
        var checkbox = row.querySelector("input.indicator-set-select");
        if (checkbox) {
            checkbox.checked = isIndicatorSetSelected(
                checkbox.getAttribute("data-indicator-set-id")
            );
        }
    });
}

function syncSelectionToUrl() {
    var params = new URLSearchParams(window.location.search);
    if (selectedIndicatorSets.length > 0) {
        params.set(SELECTED_PARAM, selectedIndicatorSets.join(","));
    } else {
        params.delete(SELECTED_PARAM);
    }
    if (showOnlySelected) {
        params.set(ONLY_SELECTED_PARAM, "1");
    } else {
        params.delete(ONLY_SELECTED_PARAM);
    }
    var query = params.toString();
    window.history.replaceState(
        null,
        "",
        window.location.pathname + (query ? "?" + query : "") + window.location.hash
    );
}

// The filter form submits via GET, which rebuilds the query string from its own fields
// only, so the selection has to ride along as hidden inputs.
function syncSelectionToFilterForm() {
    var form = document.getElementById("filterIndicatorSetsForm");
    if (!form) {
        return;
    }
    setFilterFormHiddenInput(
        form,
        SELECTED_PARAM,
        selectedIndicatorSets.length > 0 ? selectedIndicatorSets.join(",") : null
    );
    setFilterFormHiddenInput(form, ONLY_SELECTED_PARAM, showOnlySelected ? "1" : null);
}

function setFilterFormHiddenInput(form, name, value) {
    var input = form.querySelector('input[type="hidden"][name="' + name + '"]');
    if (value === null) {
        if (input) {
            input.remove();
        }
        return;
    }
    if (!input) {
        input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        form.appendChild(input);
    }
    input.value = value;
}

// "Clear all filters" points at the bare indicator sets URL; keep the selection on it so
// clearing filters does not silently discard selected rows.
function syncSelectionToClearFiltersLink() {
    var link = document.getElementById("clearAllFiltersLink");
    if (!link) {
        return;
    }
    var basePath = link.getAttribute("data-base-href");
    if (!basePath) {
        basePath = link.getAttribute("href").split("?")[0];
        link.setAttribute("data-base-href", basePath);
    }
    var params = new URLSearchParams();
    if (selectedIndicatorSets.length > 0) {
        params.set(SELECTED_PARAM, selectedIndicatorSets.join(","));
        if (showOnlySelected) {
            params.set(ONLY_SELECTED_PARAM, "1");
        }
    }
    var query = params.toString();
    link.setAttribute("href", basePath + (query ? "?" + query : ""));
}

function updateSelectionToolbar() {
    var count = document.getElementById("selectedIndicatorSetsCount");
    if (count) {
        count.textContent = selectedIndicatorSets.length;
    }
    var toggle = document.getElementById("showOnlySelectedToggle");
    if (toggle) {
        toggle.checked = showOnlySelected;
        toggle.disabled = selectedIndicatorSets.length === 0;
    }
    var clearButton = document.getElementById("clearIndicatorSetSelection");
    if (clearButton) {
        clearButton.disabled = selectedIndicatorSets.length === 0;
    }
}

// Built by the DataTable's topStart layout callback, so it sits next to the table stats.
function buildSelectionToolbar() {
    var toolbar = document.createElement("div");
    toolbar.className = "selection-toolbar";
    toolbar.innerHTML =
        '<div class="form-check mb-0">' +
        '    <input class="form-check-input" type="checkbox" id="showOnlySelectedToggle">' +
        '    <label class="form-check-label" for="showOnlySelectedToggle">' +
        '        Show only selected (<span id="selectedIndicatorSetsCount">0</span>)' +
        "    </label>" +
        "</div>" +
        '<button type="button" class="btn btn-link btn-sm selection-toolbar-action" id="clearIndicatorSetSelection">Clear selection</button>' +
        '<button type="button" class="btn btn-link btn-sm selection-toolbar-action" id="copySelectionLink">Copy link to this view</button>';

    toolbar
        .querySelector("#showOnlySelectedToggle")
        .addEventListener("change", function () {
            setShowOnlySelected(this.checked);
        });
    toolbar
        .querySelector("#clearIndicatorSetSelection")
        .addEventListener("click", function () {
            clearIndicatorSetSelection();
        });
    toolbar
        .querySelector("#copySelectionLink")
        .addEventListener("click", function () {
            copySelectionLink(this);
        });
    return toolbar;
}

function copySelectionLink(button) {
    var url = window.location.href;
    var originalLabel = button.getAttribute("data-original-label");
    if (!originalLabel) {
        originalLabel = button.textContent;
        button.setAttribute("data-original-label", originalLabel);
    }

    function reportCopied(copied) {
        button.textContent = copied ? "Link copied" : "Copy failed";
        setTimeout(function () {
            button.textContent = originalLabel;
        }, 2000);
    }

    // execCommand("copy") is only permitted while the click's user activation is live, so
    // it has to run synchronously here: navigator.clipboard is async, and by the time a
    // rejection of it came back the activation would be gone and this could no longer be
    // used as a fallback.  The clipboard API covers the browsers that refuse execCommand.
    if (copyLinkSynchronously(url)) {
        reportCopied(true);
    } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(
            function () {
                reportCopied(true);
            },
            function () {
                reportCopied(false);
            }
        );
    } else {
        reportCopied(false);
    }
}

// Works over plain http too, where navigator.clipboard is unavailable.
function copyLinkSynchronously(url) {
    var textarea = document.createElement("textarea");
    textarea.value = url;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    var copied = false;
    try {
        copied = document.execCommand("copy");
    } catch (error) {
        copied = false;
    }
    document.body.removeChild(textarea);
    return copied;
}

// Client-side filter, so toggling the selected view is instant and composes with the
// server-side filters already applied to the loaded rows.
DataTable.ext.search.push(function (settings, searchData, dataIndex, rowData) {
    // ext.search is global to every DataTable on the page, so ignore any other table.
    if (typeof table === "undefined" || settings !== table.settings()[0]) {
        return true;
    }
    if (!showOnlySelected || selectedIndicatorSets.length === 0) {
        return true;
    }
    var data = rowData || (settings.aoData[dataIndex] || {})._aData;
    if (!data || data.DT_RowId === undefined || data.DT_RowId === null) {
        return true;
    }
    return isIndicatorSetSelected(data.DT_RowId);
});

$(document).on("change", "input.indicator-set-select", function () {
    setIndicatorSetSelected(this.getAttribute("data-indicator-set-id"), this.checked);
});

// Keeps the stats note honest on the initial ajax draw and on every filter-driven redraw.
$(document).on("draw.dt", "#indicatorSetsTable", function () {
    updateSelectionStatsNote();
});

$(document).ready(function () {
    syncSelectionToFilterForm();
    syncSelectionToClearFiltersLink();
    updateSelectionToolbar();
});
