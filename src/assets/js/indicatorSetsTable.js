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

var table = new DataTable("#indicatorSetsTable", {  
    ajax: {
        url: `${window.location.pathname}${window.location.search.replace(/[?&]format=[^&]*/, "")}${window.location.search ? "&" : "?"}format=json`,
        dataSrc: "data"
    },
    columns: [
        {
            className: 'dt-control',
            orderable: false,
            data: null,
            defaultContent: ''
        },  // dt-control column
        { 
            data: null,
            render: function (data, type, row) {
                if (row.geographic_scope != 'United States' && !row.name.includes(row.geographic_scope)) {
                    return `${row.name} ${row.geographic_scope}`
                } else {
                    return row.name
                }
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
        { data: "temporal_scope_start" },  // Temporal Scope Start
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
        { data: "reporting_cadence" },  // Reporting Cadence
        { data: "reporting_lag" },  // Reporting Lag
        { data: "revision_cadence" }, // Revision Cadence
        { data: "demographic_granularity" }, // Population Stratifiers
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
        { data: "delphi_hosted" }, // Hosted by Delphi?
    ],
    fixedHeader: true,
    paging: false,
    scrollCollapse: true,
    scrollX: true,
    scrollY: calculate_table_height() + 75,
    fixedColumns: {
        left: 2,
    },
    ordering: false,
    mark: true,
    language: {
        emptyTable: "No indicators match your specified filters.  Try relaxing some filters, or clear all filters and try again.",
    },
    layout: {
        topStart: function () {
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
            return indicatorSetsInfo;
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

function escapeAttr(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function initIndicatorPopovers(childContainer) {
    if (!childContainer || typeof mdb === "undefined") {
        return;
    }
    $(childContainer).find("[data-mdb-popover-init]").each(function () {
        const existing = mdb.Popover.getInstance(this);
        if (existing) {
            existing.dispose();
        }
        new mdb.Popover(this, {
            container: "body",
            trigger: "hover",
            delay: { show: 0, hide: 100 },
        });
    });
}

function buildIndicatorSetMetadata(rowData) {
    var fields = [
        { label: "Population", value: rowData.demographic_scope },
        { label: "Pre-processing", value: rowData.preprocessing_description },
        { label: "Censoring", value: rowData.censoring },
        { label: "Missingness", value: rowData.missingness },
        { label: "DUA required?", value: rowData.dua_required },
        { label: "Data Use Terms", value: rowData.license },
        {
            label: "Documentation",
            value: rowData.documentation_link
                ? `<a href="${rowData.documentation_link}" target="_blank">View documentation</a>`
                : "",
        },
    ].filter((field) => field.value);

    if (fields.length === 0) {
        return "";
    }

    var rows = fields
        .map((field) => `<div style="font-weight:600;">${field.label}</div><div>${field.value}</div>`)
        .join("");

    return `<div style="display:grid;grid-template-columns:120px 1fr;gap:4px 12px;margin-bottom:12px;">${rows}</div>`;
}

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
        var data = `<p style="width: 40%;">${rowData.description}</p>` + buildIndicatorSetMetadata(rowData);
        var tableMarkup =
            '<table class="table" cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">' +
            "<thead>" +
            "<th></th>" +
            "<th>Indicator Name</th>" +
            "<th>Indicator API Name</th>" +
            "<th>Indicator Description</th>" +
            "<th></th>" +
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
            const enabledEndpoints = ["covidcast", "fluview", "nidss_flu", "nidss_dengue", "flusurv", "pophive", "nwss"];
            disabled = enabledEndpoints.includes(indicator.endpoint) ? "" : "disabled";
            sourceType = indicator.source_type;
            var restricted = indicator.restricted != "No";
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
                `<td><input ${disabled} title="${checkboxTitle}" type="checkbox" name="selectedIndicator" onclick="addSelectedIndicator(this)" data-indicator-displayname='${indicator.display_name}' data-endpoint="${indicator.endpoint}" data-datasource="${indicator.source}" data-indicator="${indicator.name}" data-time-type="${indicator.time_type}" data-indicator-set="${indicator.indicator_set_name}" data-indicator-set-short-name="${indicator.indicator_set_short_name}" data-member-short-name="${indicator.member_short_name}" ${checked}></td>` +
                `<td><span tabindex="0" data-mdb-container="body" data-mdb-popover-init data-mdb-trigger="hover" data-mdb-placement="right" data-mdb-content="${escapeAttr(indicator.description)}">${indicator.display_name}</span></td>` +
                `<td>${indicator.member_name}</td>` +
                `<td>${indicator.member_description}</td>` +
                '<td style="width: 60%"></td>' +
                "</tr>";
        });
        tableMarkup += "</tbody></table>";
        if (disabled === "disabled" || restricted) {
            if (sourceType === "non_delphi" && sourceType != "us_state") {
                data +=
                    `<div class="alert alert-warning" data-mdb-alert-init role="alert">` +
                    `   <div>This indicator set is not available via Delphi.  It is included here for general discoverability only, and may or may not be available from the Original Data Provider.</div>` +
                    "</div>";
            } else if (sourceType === "us_state") {
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
        data = buildIndicatorSetMetadata(rowData) + "<p>No available indicators yet.</p>";
    }
    return data;
}


