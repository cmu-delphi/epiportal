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
    fixedHeader: true,
    paging: false,
    scrollCollapse: true,
    scrollX: true,
    scrollY: calculate_table_height() + 75,
    info: false,
    fixedColumns: {
        left: 2,
    },
    ordering: false,
    mark: true,

    language: {
        emptyTable: "No indicators match your specified filters.  Try relaxing some filters, or clear all filters and try again.",
        // buttons: {
        //     colvis: "Toggle Columns",
        // },
    },
    search: {
        smart: true,
        highlight: true,
    },
    sDom: 'ltipr',
    rowCallback: function(row, data, index) {
        if (index % 2 === 0) {
            $(row).addClass('odd-row');
        }
    }
});

// new DataTable.Buttons(table, {
//     buttons: [
//         {
//             extend: "colvis",
//             columns: "th:nth-child(n+3)",
//             prefixButtons: ["colvisRestore"],
//         },
//     ],
// });

// table.buttons(0, null).container().appendTo("#colvis");

// $("#tableSearch").keyup(function () {
//     table.search(this.value).draw();
// });

function format(indicatorSetId, relatedIndicators, indicatorSetDescription) {
    var indicators = relatedIndicators.filter(
        (indicator) => indicator.indicator_set === indicatorSetId
    );
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


