function dataLayerPush(payload) {
    if (window.dataLayer) {
        window.dataLayer.push(function () {
            this.reset();
        });
        window.dataLayer.push(payload);
    }
}


function getGACookie() {
    // Get all cookies as a string
    const cookies = document.cookie.split(';');

    // Find the _ga cookie
    const gaCookie = cookies.find(cookie => cookie.trim().startsWith('_ga='));

    if (gaCookie) {
        // Extract the full _ga cookie value
        const gaValue = gaCookie.split('=')[1];

        // Extract the Client ID (remove the GA1.X prefix)
        const clientId = gaValue.split('.').slice(2).join('.');

        return clientId;
    }

    return null; // Return null if _ga cookie is not found
}

const clientId = getGACookie();

var DEFAULT_POPHIVE_AGE_GROUP = "all";

/* Select "all" ages, or the first age group if pophive stops offering "all".
 * Defaulting to the first one meant infants only for anyone who left the
 * menu alone. */
function selectDefaultPophiveAgeGroup() {
    var select = $("#pophiveAgeGroup");
    var hasDefault = select.find("option").filter(function () {
        return this.value === DEFAULT_POPHIVE_AGE_GROUP;
    }).length > 0;
    if (hasDefault) {
        select.val(DEFAULT_POPHIVE_AGE_GROUP);
    } else {
        select.prop("selectedIndex", 0);
    }
    select.trigger("change");
}

/* The chosen pophive age group in the shape the server reads: a one-item
 * list of {id, text}, or an empty list when the menu has no selection. */
function getSelectedPophiveAgeGroup() {
    var ageGroup = $("#pophiveAgeGroup").val();
    return ageGroup ? [{ id: ageGroup, text: ageGroup }] : [];
}

class IndicatorHandler {
    constructor() {
        this.indicators = {};
    }

    fluviewIndicatorsMapping = {
        wili: "%wILI",
        ili: "%ILI",
    };

    nwssSources = ['CDC_Biobot', 'CDC_Verily', 'State_Territory', 'WastewaterSCAN'];

    // Every source takes its locations from the main Location(s) dropdown:
    // covidcast (and the v5-only sources sharing its paths), fluview,
    // FluSurv, NIDSS, pophive (Cosmos) and nwss.
    usesMainLocations() {
        return this.indicators.some((indicator) =>
            MAIN_LOCATION_ENDPOINTS.includes(indicator["_endpoint"])
        );
    }

    getCovidcastIndicators() {
        var covidcastIndicators = [];
        this.indicators.forEach((indicator) => {
            if (COVIDCAST_ENDPOINTS.includes(indicator["_endpoint"])) {
                covidcastIndicators.push(indicator);
            }
        });
        return covidcastIndicators;
    }

    getFluviewIndicators() {
        var fluviewIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "fluview") {
                fluviewIndicators.push(indicator);
            }
        });
        return fluviewIndicators;
    }

    getNIDSSFluIndicators() {
        var nidssFluIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "nidss_flu") {
                nidssFluIndicators.push(indicator);
            }
        });
        return nidssFluIndicators;
    }

    getNIDSSDengueIndicators() {
        var nidssDengueIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "nidss_dengue") {
                nidssDengueIndicators.push(indicator);
            }
        });
        return nidssDengueIndicators;
    }

    getFlusurvIndicators() {
        var flusurvIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "flusurv") {
                flusurvIndicators.push(indicator);
            }
        });
        return flusurvIndicators;
    }

    getPophiveIndicators() {
        var pophiveIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "pophive") {
                pophiveIndicators.push(indicator);
            }
        });
        return pophiveIndicators;
    }

    getNwssIndicators() {
        var nwssIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "nwss") {
                nwssIndicators.push(indicator);
            }
        });
        return nwssIndicators;
    }

    sendAsyncAjaxRequest(url, data) {
        var request = $.ajax({
            url: url,
            type: "GET",
            data: data,
        });
        return request;
    }

    prepareDataLayerPayload(form_mode) {
        var payload = {
            event: "submitSelectedIndicators",
            formMode: form_mode,
            numIndicators: this.indicators.length,
            numCovidcastIndicators: this.getCovidcastIndicators().length,
            numFluviewIndicators: this.getFluviewIndicators().length,
            numNIDSSFluIndicators: this.getNIDSSFluIndicators().length,
            numNIDSSDengueIndicators: this.getNIDSSDengueIndicators().length,
            numFlusurvIndicators: this.getFlusurvIndicators().length,
            numPophiveIndicators: this.getPophiveIndicators().length,
            numNwssIndicators: this.getNwssIndicators().length,
            formStartDate: document.getElementById("start_date").value,
            formEndDate: document.getElementById("end_date").value,
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
        };
        var covidcastGeoValues = $("#geographic_value").select2("data")
        if (covidcastGeoValues !== undefined && covidcastGeoValues !== null) {
            covidcastGeoValues = Object.values(
                covidcastGeoValues
                    .flat()
                    .map(({ id }) => id
                    ));
            payload.covidcastGeoValues = covidcastGeoValues;
        }
        var pophiveAgeGroupData = getSelectedPophiveAgeGroup();
        if (pophiveAgeGroupData.length > 0) {
            payload.pophiveAgeGroup = pophiveAgeGroupData[0].id;
        }
        return payload;

    }

    // Cosmos (pophive) takes its locations from the main Location(s)
    // dropdown; only its age group needs a control of its own.
    showPophiveAgeGroup() {
        var pophiveAgeGroupSelect = `
        <hr>
        <div class="row margin-top-1rem" id="pophiveDiv">
            <div class="col-2">
                <label for="pophiveAgeGroup" class="col-form-label">Cosmos Age Group:</label>
            </div>
            <div class="col-10">
                <select id="pophiveAgeGroup" name="pophiveAgeGroup" class="form-select"></select>
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(pophiveAgeGroupSelect);
            // A handful of options, one choice: a plain select, no select2
            // search box.
            $.get("get_pophive_age_groups/", function (response) {
                var select = $("#pophiveAgeGroup").empty();
                response.age_groups.forEach(function (ageGroup) {
                    select.append(new Option(ageGroup, ageGroup));
                });
                selectDefaultPophiveAgeGroup();
            });
        }
    }


    // TODO: to return this fields -> move them to nwssFields below and uncomment corresponding code in showNwssFields function
    // <div class="col-2">
    //     <label for="nwssPcrTarget" class="col-form-label">PCR Target:</label>
    // </div>
    // <div class="col-10">
    //     <select id="nwssPcrTarget" name="nwssPcrTarget" class="form-select"></select>
    // </div>

    

    showNwssFields() {
        var nwssFields = `
        <hr>
        <div id="nwssDiv">
            <div class="row margin-top-1rem">
                <div class="col-2">
                    <label for="nwssSource" class="col-form-label">NWSS Source:</label>
                </div>
                <div class="col-10">
                    <select id="nwssSource" name="nwssSource" class="form-select" multiple="multiple"></select>
                </div>
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(nwssFields);
            // var pcrTargets = this.nwssPcrTargets.map(function (t) {
            //     return { id: t, text: t };
            // });
            // $("#nwssPcrTarget").select2({
            //     placeholder: "Select PCR Target",
            //     data: pcrTargets,
            //     allowClear: true,
            //     width: "100%",
            //     dropdownParent: $("#selectedIndicatorsModal"),
            // });
            var sources = this.nwssSources.map(function (s) {
                return { id: s, text: s };
            });
            $("#nwssSource").select2({
                placeholder: "Select NWSS Source",
                maximumSelectionLength: 5,
                minimumSelectionLength: 1,
                data: sources,
                allowClear: true,
                width: "100%",
            });
        }
    }

    plotData() {
        const covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const pophiveAgeGroup = getSelectedPophiveAgeGroup();
        const nwssSource = $("#nwssSource").select2("data");
        const submitData = {
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssSource: nwssSource,
            fillMethod: getFillMethod(),
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
        };
        const csrftoken = Cookies.get("csrftoken");
        /* Open synchronously from the user gesture so pop-up blockers allow it,
         * then navigate to the real Epivis URL when the AJAX response arrives. */
        const epivisTab = window.open("about:blank", "_blank");

        $.ajax({
            url: "epivis/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        })
            .done((data) => {
                const payload = this.prepareDataLayerPayload("epivis");
                dataLayerPush(payload);
                const url = data["epivis_url"];
                if (!url) {
                    if (epivisTab) epivisTab.close();
                    $("#modeSubmitResult").html(
                        '<div class="alert alert-warning" role="alert">Epivis URL was not returned.</div>'
                    );
                    return;
                }
                if (epivisTab && !epivisTab.closed) {
                    epivisTab.location.href = url;
                    epivisTab.focus();
                } else {
                    /* Pop-up blocker may have prevented opening the prefetch tab — offer a clickable link */
                    const $wrap = $('<div>', { class: "mt-2" });
                    $('<p>', {
                        text: "Your browser may have blocked a new tab. Open Epivis from the button below:",
                    }).appendTo($wrap);
                    $("<a>", {
                        href: url,
                        target: "_blank",
                        rel: "noopener noreferrer",
                        class: "btn btn-primary mt-2",
                        text: "Open Epivis",
                    }).appendTo($wrap);
                    $("#modeSubmitResult").empty().append($wrap);
                }
            })
            .fail(() => {
                if (epivisTab && !epivisTab.closed) epivisTab.close();
                $("#modeSubmitResult").html(
                    '<div class="alert alert-danger" role="alert">Could not prepare Epivis. Please try again.</div>'
                );
            });
    }

    exportData() {
        const pophiveAgeGroup = getSelectedPophiveAgeGroup();
        const nwssSource = $("#nwssSource").select2("data");
        let dataFormat = 'csv';
        if ($("#data_format_json").is(":checked")) {
            dataFormat = 'json';
        }
        var covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssSource: nwssSource,
            fillMethod: getFillMethod(),
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
            dataFormat: dataFormat,
        }
        const csrftoken = Cookies.get("csrftoken");
        $.ajax({
            url: "export/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        })
            .done((data) => {
                const payload = this.prepareDataLayerPayload("export");
                dataLayerPush(payload);
                $("#modeSubmitResult").html(data["data_export_block"]);
            })
            .fail(() => {
                $("#modeSubmitResult").html(
                    '<div class="alert alert-danger" role="alert">Export failed. Please try again.</div>'
                );
            });
    }

    escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    generatePreviewDataCSV(previewBlocks) {
        if (!Array.isArray(previewBlocks) || previewBlocks.length === 0) {
            return '<p>No preview data available.</p>';
        }
        const blocks = previewBlocks
            .filter((block) => block !== null && block !== undefined)
            .map((block) => {
                if (!Array.isArray(block)) {
                    const message = (block && block.message) || 'No preview data available.';
                    return `<p class="preview-no-data">${this.escapeHtml(message)}</p>`;
                }
                if (block.length === 0) {
                    return '';
                }
                const [header, ...dataRows] = block;
                const headerHtml = header
                    .map((cell) => `<th>${this.escapeHtml(cell)}</th>`)
                    .join('');
                const bodyHtml = dataRows
                    .map((row) => `<tr>${row.map((cell) => `<td>${this.escapeHtml(cell)}</td>`).join('')}</tr>`)
                    .join('');
                return `<table class="table table-bordered table-sm preview-table">
                    <thead><tr>${headerHtml}</tr></thead>
                    <tbody>${bodyHtml}</tbody>
                </table>`;
            })
            .filter((html) => html !== '');
        return blocks.length ? blocks.join('') : '<p>No preview data available.</p>';
    }

    previewData() {
        $('#loader').show();
        const pophiveAgeGroup = getSelectedPophiveAgeGroup();
        const nwssSource = $("#nwssSource").select2("data");
        const covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        let dataFormat = 'csv';
        if ($("#data_format_json").is(":checked")) {
            dataFormat = 'json';
        }
        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssSource: nwssSource,
            fillMethod: getFillMethod(),
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
            dataFormat: dataFormat,
        }
        const csrftoken = Cookies.get("csrftoken");
        $.ajax({
            url: "preview_data/",
            type: "POST",
            dataType: 'json',
            contentType: 'application/json',
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        }).done((data) => {
            const payload = this.prepareDataLayerPayload("previewData");
            dataLayerPush(payload);
            $('#loader').hide();
            if (dataFormat === 'csv') {
                $('#modeSubmitResult').html(this.generatePreviewDataCSV(data));
            } else {
                $('#modeSubmitResult').html(JSON.stringify(data, null, 2));
            }
        }).fail(() => {
            $('#loader').hide();
            $('#modeSubmitResult').html(
                '<div class="alert alert-danger" role="alert">Preview failed. Please try again.</div>'
            );
        });
    }

    createQueryCode() {
        const pophiveAgeGroup = getSelectedPophiveAgeGroup();
        const nwssSource = $("#nwssSource").select2("data");
        const covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );

        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssSource: nwssSource,
            fillMethod: getFillMethod(),
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
        }
        const csrftoken = Cookies.get("csrftoken");
        var createQueryCodePython = `<h4>PYTHON PACKAGE</h4>`
            + `<p>Install <code class="highlight-code"><a href="https://github.com/cmu-delphi/epidatpy">epidatpy</a></code> via pip: </p>`
            + `<pre class="code-block"><code>pip install -e "git+https://github.com/cmu-delphi/epidatpy.git#egg=epidatpy"</code></pre><br>`
            + `<p>Fetch data: </p>`;
        var createQueryCodeR = `<h4>R PACKAGE</h4>`
            + `<p>Install <code class="highlight-code"><a href="https://github.com/cmu-delphi/epidatr">epidatr</a></code> via CRAN: </p>`
            + `<pre class="code-block"><code>pak::pkg_install("epidatr")</code></pre><br>`
            + `<p> Fetch data: </p>`
        $.ajax({
            url: "create_query_code/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        }).done((data) => {
            const payload = this.prepareDataLayerPayload("createQueryCode");
            dataLayerPush(payload);
            createQueryCodePython += data["python_code_blocks"].join("<br>");
            createQueryCodeR += data["r_code_blocks"].join("<br>");
            $('#modeSubmitResult').html(createQueryCodePython + "<br>" + createQueryCodeR);
        });

    }
}
