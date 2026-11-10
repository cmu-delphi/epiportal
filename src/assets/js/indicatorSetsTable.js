// Starting height for the scroll body; fitTableToContainer() replaces it as
// soon as the table is drawn.
function calculate_table_height() {
    var h = Math.max(
        document.documentElement.clientHeight,
        window.innerHeight || 0
    );
    var percent = 60;
    if (h > 1000) {
        percent = 70;
    }
    return (percent * h) / 100;
}

// Below this the table body would be too short to use; let the container
// scroll instead.
var MIN_TABLE_BODY_HEIGHT = 200;

/* Size the table's scroll body to whatever its container has left, so the
 * body is the only thing that scrolls. A fixed share of the window cannot do
 * that: the stats line, the selection toolbar and the header above the body
 * change height as they load and wrap, and any overflow scrolls the container
 * as well, giving two vertical scrollbars. */
function fitTableToContainer() {
    var wrapper = document.getElementById("indicatorSetsTable_wrapper");
    var container = wrapper?.closest(".table-container");
    var scrollBody = wrapper?.querySelector(".dt-scroll-body");
    if (!container || !scrollBody) {
        return;
    }
    var containerRect = container.getBoundingClientRect();
    var bodyRect = scrollBody.getBoundingClientRect();
    var containerStyle = getComputedStyle(container);
    // Everything stacked above and below the body inside the container,
    // measured as if the container were not scrolled.
    var above = bodyRect.top - containerRect.top + container.scrollTop
        - parseFloat(containerStyle.borderTopWidth);
    var below = wrapper.getBoundingClientRect().bottom - bodyRect.bottom
        + parseFloat(getComputedStyle(wrapper).marginBottom)
        + parseFloat(containerStyle.paddingBottom);
    var height = Math.max(
        Math.floor(container.clientHeight - above - below),
        MIN_TABLE_BODY_HEIGHT
    );
    if (scrollBody.style.maxHeight !== `${height}px`) {
        scrollBody.style.maxHeight = `${height}px`;
    }
}

var table = new DataTable("#indicatorSetsTable", {  
    ajax: {
        url: `${window.location.pathname}${window.location.search.replace(/[?&]format=[^&]*/, "")}${window.location.search ? "&" : "?"}format=json`,
        dataSrc: "data"
    },
    columns: [
        {
            className: 'dt-select text-center',
            orderable: false,
            data: null,
            render: function (data, type, row) {
                var indicatorSetId = row.DT_RowId;
                // Without indicatorSetsSelection.js a checkbox would be inert, so render
                // nothing rather than taking the whole table down with a ReferenceError.
                if (indicatorSetId === undefined || indicatorSetId === null ||
                    typeof isIndicatorSetSelected !== 'function') {
                    return '';
                }
                var checked = isIndicatorSetSelected(indicatorSetId) ? ' checked' : '';
                return `<input type="checkbox" class="form-check-input indicator-set-select" data-indicator-set-id="${indicatorSetId}" aria-label="Select this indicator set"${checked}>`;
            }
        },  // Select column
        {
            className: 'dt-control',
            orderable: false,
            data: null,
            defaultContent: ''
        },  // dt-control column
        {
            data: null,
            render: function (data, type, row) {
                var label = indicatorSetLabel(row);
                if (type !== "display") {
                    return label;
                }
                // Opens the indicator set's metadata panel (indicatorSetPanel.js).
                // The description shows in a popover on hover (see initNameLinkPopovers).
                var description = (row.description || "").trim();
                var popoverAttrs = description
                    ? ` data-mdb-content="${escapeAttr(description)}. \nFor more information, click on the indicator set name."`
                    : ' title="Show indicator set details"';
                return `<a href="#" role="button" class="indicator-set-name-link"${popoverAttrs}>${escapeAttr(label)}</a>`;
            }
        },  // Name
        {
            data: "pathogens",
            render: function (data, type, row) {
                if (data) {
                    return data.map(pathogen => `<span class="badge badge-pill-outline">${pathogen.display_name}</span>`).join('');
                } else {
                    return '';
                }
            }
        }, // Pathogens
        {
            data: "geographic_levels",
            render: function (data, type, row) {
                if (data) {
                    return data.map(geography => `<span class="badge badge-pill-outline">${geography.display_name}</span>`).join('');
                } else {
                    return '';
                }
            }
        }, // Geographic Levels
        { data: "temporal_scope_end" },  // Temporal Scope End
        {
            data: "temporal_granularity",
            render: function (data, type, row) {
                if (data) {
                    return `<span class="badge badge-pill-outline">${data}</span>`;
                } else {
                    return '';
                }
            }
        }, // Temporal Granularity
        {
            data: "severity_pyramid_rungs",
            render: function (data, type, row) {
                if (data) {
                    return data.map(severity_pyramid_rung => `<span class="badge badge-pill-outline">${severity_pyramid_rung.display_name}</span>`).join('');
                } else {
                    return '';
                }
            }
        }, // Surveillance Categories
        { data: "original_data_provider" }, // Original Data Provider
    ],
    fixedHeader: true,
    paging: false,
    scrollCollapse: true,
    scrollX: true,
    scrollY: calculate_table_height(),
    fixedColumns: {
        left: 3,
    },
    ordering: false,
    // DataTables' own width calculation sizes columns wider than the container,
    // which forces a horizontal scrollbar; the browser's table layout fits them.
    autoWidth: false,
    mark: true,
    language: {
        emptyTable: "No indicators match your specified filters.  Try relaxing some filters, or clear all filters and try again.",
        // The selected-only view is the only client-side filter on this table, so this is
        // shown exactly when none of the selected sets survived the server-side filters.
        zeroRecords: "None of your selected indicator sets match your specified filters.  Try relaxing some filters, or turn off \"Show only selected\".",
    },
    layout: {
        topStart: function () {
            let topStartContainer = document.createElement('div');
            let indicatorSetsInfo = document.createElement('span');
            indicatorSetsInfo.className = 'table-stats-info';
            indicatorSetsInfo.id = 'indicatorSetsInfo';
            $.ajax({
                url: "get_table_stats_info/" + window.location.search,
                method: "GET",
                success: function (response) {
                    if (response.num_of_locations > 0) {
                        indicatorSetsInfo.innerHTML =
                            `Showing <b>${response.num_of_indicators}</b> distinct ${pluralize(response.num_of_indicators, "indicator")} (arranged in <b>${response.num_of_indicator_sets}</b> ${pluralize(response.num_of_indicator_sets, "set")}), including <b>${numberWithCommas(response.num_of_locations)}</b> Delphi-hosted time series across numerous locations.`;
                    } else {
                        indicatorSetsInfo.innerHTML =
                            `Showing <b>${response.num_of_indicators}</b> ${pluralize(response.num_of_indicators, "indicator")} (arranged in <b>${response.num_of_indicator_sets}</b> ${pluralize(response.num_of_indicator_sets, "set")}).`;
                    }
                }
            });
            topStartContainer.appendChild(indicatorSetsInfo);
            if (typeof buildSelectionToolbar === 'function') {
                topStartContainer.appendChild(buildSelectionToolbar());
            }
            return topStartContainer;
        },
        topEnd: null,
        bottomStart: null,
        bottomEnd: null
    },
    createdRow: function (row, data, dataIndex) {
        if (data.description) {
            $(row).attr('data-description', data.description);
        } else {
            $(row).attr('data-description', '');
        }
        // Set row ID if present
        if (data.DT_RowId) {
            $(row).attr('data-id', data.DT_RowId);
        }
        // Add odd-row class for styling
        if (dataIndex % 2 === 0) {
            $(row).addClass('odd-row');
        }
    },
});

var lastColumnsWidth = null;

/* With autoWidth off, DataTables pins every column's width and min-width
 * (on the <col>s of both the header and body tables) to what they were at
 * the first draw and never recomputes them. When the container then changes
 * width the body reflows but the separate header table does not, so the
 * column borders drift apart, or the pinned widths force a horizontal
 * scrollbar. Unpin them and let DataTables re-measure. */
function fitColumnsToContainer() {
    var wrapper = document.getElementById("indicatorSetsTable_wrapper");
    var container = wrapper?.closest(".table-container");
    if (!container || container.clientWidth === lastColumnsWidth) {
        return;
    }
    lastColumnsWidth = container.clientWidth;
    wrapper.querySelectorAll("col").forEach(function (col) {
        col.style.width = "";
        col.style.minWidth = "";
    });
    table.columns.adjust();
}

function fitToContainer() {
    fitColumnsToContainer();
    fitTableToContainer();
}

table.on("init", function () {
    lastColumnsWidth = document
        .getElementById("indicatorSetsTable_wrapper")
        ?.closest(".table-container")?.clientWidth ?? null;
    fitTableToContainer();
    // Refit whenever the space changes: the window or filter panel resizes the
    // container, and the rows around the body grow as the stats line loads and
    // the selection toolbar wraps. The body's own row is left out, since the
    // fit itself resizes it.
    if (typeof ResizeObserver === "function") {
        var observer = new ResizeObserver(fitToContainer);
        var wrapper = document.getElementById("indicatorSetsTable_wrapper");
        observer.observe(wrapper.closest(".table-container"));
        wrapper.querySelectorAll(".dt-layout-row:not(.dt-layout-table)").forEach(function (row) {
            observer.observe(row);
        });
    } else {
        window.addEventListener("resize", fitToContainer);
    }
});

// The set's name as the table shows it: sets outside the United States get
// their geographic scope appended unless the name already mentions it.
function indicatorSetLabel(row) {
    if (row.geographic_scope && row.geographic_scope != 'United States' && !row.name.includes(row.geographic_scope)) {
        return `${row.name} ${row.geographic_scope}`;
    }
    return row.name;
}

function escapeAttr(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

/* Indicator set descriptions in a popover on the set name. The table has no
 * paging, so popovers are created on first hover rather than for every row up
 * front, and shown and hidden by hand so the first hover already shows one.
 * MDB loads after this script (at the end of index.html), so `mdb` is only
 * looked up inside the handlers, never at bind time.
 *
 * Hiding waits a moment so small cursor slips off the link, or moving onto the
 * popover itself, don't close it. Animation is off because MDB's hide finishes
 * after the fade and then disposes the popover unconditionally, which would
 * kill a popover re-shown during that fade. */
function initNameLinkPopovers() {
    var selector = ".indicator-set-name-link[data-mdb-content]";
    var popoverClass = "indicator-set-name-popover";
    var hideDelayMs = 200;
    var activeLink = null;
    var hideTimer = null;

    function cancelHide() {
        clearTimeout(hideTimer);
        hideTimer = null;
    }
    function hideNow() {
        cancelHide();
        if (activeLink && typeof mdb !== "undefined") {
            mdb.Popover.getInstance(activeLink)?.hide();
        }
        activeLink = null;
    }
    function scheduleHide() {
        cancelHide();
        hideTimer = setTimeout(hideNow, hideDelayMs);
    }
    function show(link) {
        cancelHide();
        if (typeof mdb === "undefined" || link === activeLink) {
            return;
        }
        hideNow();
        mdb.Popover.getOrCreateInstance(link, {
            container: "body",
            placement: "bottom",
            trigger: "manual",
            animation: false,
            customClass: popoverClass,
        }).show();
        activeLink = link;
    }

    $("#indicatorSetsTable tbody")
        .on("mouseenter focusin", selector, function () {
            show(this);
        })
        .on("mouseleave focusout", selector, scheduleHide)
        .on("click", selector, hideNow);
    // Keep the popover open while the pointer is over it.
    $(document)
        .on("mouseenter", "." + popoverClass, cancelHide)
        .on("mouseleave", "." + popoverClass, scheduleHide);
    // A redraw can remove the hovered row, which would strand its popover.
    table.on("preDraw", hideNow);
}

initNameLinkPopovers();

function format(rowData, relatedIndicators) {
    if (!relatedIndicators) {
        return '<div class="d-flex justify-content-start my-3" style="padding-left: 20px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }

    var indicatorSetId = rowData.DT_RowId;
    var indicators;
    if (Array.isArray(relatedIndicators)) {
        indicators = relatedIndicators.filter(
            (indicator) => indicator.indicator_set === indicatorSetId
        );
    } else {
        indicators = relatedIndicators[indicatorSetId] || [];
    }
    var disabled, restricted, sourceType;

    if (indicators.length > 0) {
        var data = "";
        var tableMarkup =
            '<table class="table" cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">' +
            "<thead>" +
            "<th></th>" +
            "<th>Indicator Name</th>" +
            "<th>Indicator API Name</th>" +
            "<th>Indicator Description</th>" +
            "</thead>" +
            "<tbody>";
        indicators.forEach((indicator) => {
            checked = checkedIndicatorMembers.filter(
                (obj) =>
                    obj.data_source == indicator.source &&
                    obj.indicator == indicator.name
            ).length;
            var checkboxTitle = "";
            checked = checked ? "checked" : "";
            const enabledEndpoints = [
                ...(typeof covidcastEndpoints !== "undefined" ? covidcastEndpoints : ["covidcast"]),
                "fluview", "nidss_flu", "nidss_dengue", "flusurv", "pophive", "nwss",
            ];
            disabled = enabledEndpoints.includes(indicator.endpoint) ? "" : "disabled";
            sourceType = indicator.kind;
            var restricted = indicator.restricted === true;
            if (disabled === "disabled") {
                checkboxTitle =
                    "Visualization functionality for this endpoint is coming soon.";
            }
            if (restricted) {
                disabled = "disabled";
                checkboxTitle =
                    "Access to this data source is restricted. Contact delphi-support@andrew.cmu.edu for more information.";
            }
            
            tableMarkup +=
                "<tr>" +
                `<td><input ${disabled} title="${checkboxTitle}" type="checkbox" name="selectedIndicator" onclick="addSelectedIndicator(this)" data-indicator-displayname='${indicator.display_name}' data-endpoint="${indicator.endpoint}" data-datasource="${indicator.source}" data-indicator="${indicator.name}" data-time-type="${indicator.time_type}" data-indicator-set="${indicator.indicator_set_name}" data-indicator-set-short-name="${indicator.indicator_set_short_name}" ${checked}></td>` +
                `<td>${indicator.display_name}</td>` +
                `<td>${indicator.name}</td>` +
                `<td>${indicator.description}</td>` +
                "</tr>";
        });
        tableMarkup += "</tbody></table>";
        if (disabled === "disabled" || restricted) {
            if (sourceType === "non_delphi") {
                data +=
                    `<div class="alert alert-warning" data-mdb-alert-init role="alert">` +
                    `   <div>This indicator set is not available via Delphi.  It is included here for general discoverability only, and may or may not be available from the Original Data Provider.</div>` +
                    "</div>";
            } else if (sourceType === "us_states") {
                data +=
                    `<div class="alert alert-warning" data-mdb-alert-init role="alert">` +
                    `   <div>This indicator set is not hosted by Delphi and is listed here for discoverability.  It can be found on the website listed under "Documentation".</div>` +
                    "</div>";
            }
            else {
                data +=
                    `<div class="alert alert-warning" data-mdb-alert-init role="alert">` +
                    `   <div>This indicator set is available via the <a href="https://cmu-delphi.github.io/delphi-epidata/">Epidata API</a>, and directly via <a href="https://delphi.cmu.edu/epivis/">Epivis</a>, but is not yet available via this interface.</div>` +
                    "</div>";
            }
        }

        data += tableMarkup;
    } else {
        data = "<p>No available indicators yet.</p>";
    }
    return data;
}


