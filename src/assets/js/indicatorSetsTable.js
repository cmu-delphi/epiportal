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
    serverSide: true,
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
        { data: "name" },  // Name
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
        { data: "geographic_scope" },  // Geographic Coverage
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
        { data: "demographic_scope" }, // Population
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
        { data: "preprocessing_description" }, // Pre-processing
        { data: "censoring" }, // Censoring
        { data: "missingness" }, // Missingness
        { data: "delphi_hosted" }, // Hosted by Delphi?
        { data: "dua_required" }, // DUA required?
        { data: "license" }, // Data Use Terms
        {
            data: "documentation_link",
            render: function (data, type, row) {
                if (data) {
                    return `<a href="${data}" target="_blank">${data}</a>`;
                } else {
                    return '';
                }
            }
        }, // Documentation
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
                            `Showing <b>${response.num_of_indicators}</b> indicator sets (arranged in <b>${response.num_of_indicator_sets}</b> ${pluralize(response.num_of_indicator_sets, "set")}).`;
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

function format(indicatorSetId, relatedIndicators, indicatorSetDescription) {
    if (!relatedIndicators) {
        return '<div class="d-flex justify-content-start my-3" style="padding-left: 20px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }

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
        var data = `<p style="width: 40%;">${indicatorSetDescription}</p>`;
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
            const enabledEndpoints = ["covidcast", "fluview", "nidss_flu", "nidss_dengue", "flusurv"];
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
                `<td>${indicator.display_name}</td>` +
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
        data = "<p>No available indicators yet.</p>";
    }
    return data;
}


