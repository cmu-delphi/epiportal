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
        this.nonCovidcastIndicatorSets = [];
    }

    fluviewIndicatorsMapping = {
        wili: "%wILI",
        ili: "%ILI",
    };

    flusurvLocations = [
        { id: "network_all", text: "Entire Network" },
        { id: "network_eip", text: "EIP Netowrk" },
        { id: "network_ihsp", text: "IHSP Network" },
        { id: "CA", text: "CA" },
        { id: "CO", text: "CO" },
        { id: "CT", text: "CT" },
        { id: "GA", text: "GA" },
        { id: "IA", text: "IA" },
        { id: "ID", text: "ID" },
        { id: "MD", text: "MD" },
        { id: "MI", text: "MI" },
        { id: "MN", text: "MN" },
        { id: "NM", text: "NM" },
        { id: "NY_albany", text: "NY (Albany)" },
        { id: "NY_rochester", text: "NY (Rochester)" },
        { id: "OH", text: "OH" },
        { id: "OK", text: "OK" },
        { id: "OR", text: "OR" },
        { id: "RI", text: "RI" },
        { id: "SD", text: "SD" },
        { id: "TN", text: "TN" },
        { id: "UT", text: "UT" },
    ];

    nidssFluLocations = [
        { id: 'nationwide', text: 'Taiwan National' },
        { id: 'central', text: 'Central' },
        { id: 'eastern', text: 'Eastern' },
        { id: 'kaoping', text: 'Kaoping' },
        { id: 'northern', text: 'Northern' },
        { id: 'southern', text: 'Southern' },
        { id: 'taipei', text: 'Taipei' },
    ];

    nidssDengueLocations = [
        { id: 'nationwide', text: 'Taiwan National' },
        { id: 'central', text: 'Central' },
        { id: 'eastern', text: 'Eastern' },
        { id: 'kaoping', text: 'Kaoping' },
        { id: 'northern', text: 'Northern' },
        { id: 'southern', text: 'Southern' },
        { id: 'taipei', text: 'Taipei' },
        { id: 'changhua_county', text: 'Changhua County' },
        { id: 'chiayi_city', text: 'Chiayi City' },
        { id: 'chiayi_county', text: 'Chiayi County' },
        { id: 'hsinchu_city', text: 'Hsinchu City' },
        { id: 'hsinchu_county', text: 'Hsinchu County' },
        { id: 'hualien_county', text: 'Hualien County' },
        { id: 'kaohsiung_city', text: 'Kaohsiung City' },
        { id: 'keelung_city', text: 'Keelung City' },
        { id: 'kinmen_county', text: 'Kinmen County' },
        { id: 'lienchiang_county', text: 'Lienchiang County' },
        { id: 'miaoli_county', text: 'Miaoli County' },
        { id: 'nantou_county', text: 'Nantou County' },
        { id: 'new_taipei_city', text: 'New taipei City' },
        { id: 'penghu_county', text: 'Penghu County' },
        { id: 'pingtung_county', text: 'Pingtung County' },
        { id: 'taichung_city', text: 'Taichung City' },
        { id: 'tainan_city', text: 'Tainan City' },
        { id: 'taipei_city', text: 'Taipei City' },
        { id: 'taitung_county', text: 'Taitung County' },
        { id: 'taoyuan_city', text: 'Taoyuan City' },
        { id: 'yilan_county', text: 'Yilan County' },
        { id: 'yunlin_county', text: 'Yunlin County' },
    ];

    nwssSources = ['CDC_Biobot', 'CDC_Verily', 'State_Territory', 'WastewaterSCAN'];

    // Covidcast, fluview, pophive (Cosmos) and nwss take their locations from
    // the main Location(s) dropdown.
    usesMainLocations() {
        return this.indicators.some((indicator) =>
            ["covidcast", "fluview", "pophive", "nwss"].includes(indicator["_endpoint"])
        );
    }

    getCovidcastIndicators() {
        var covidcastIndicators = [];
        this.indicators.forEach((indicator) => {
            if (indicator["_endpoint"] === "covidcast") {
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
        var nidssFluGeoValues = $("#nidssFluLocations").select2("data")
        if (nidssFluGeoValues !== undefined && nidssFluGeoValues !== null) {
            nidssFluGeoValues = Object.values(
                nidssFluGeoValues
                    .flat()
                    .map(({ id }) => id
                    ));
            payload.nidssFluGeoValues = nidssFluGeoValues;
        }
        var nidssDengueGeoValues = $("#nidssDengueLocations").select2("data")
        if (nidssDengueGeoValues !== undefined && nidssDengueGeoValues !== null) {
            nidssDengueGeoValues = Object.values(
                nidssDengueGeoValues
                    .flat()
                    .map(({ id }) => id
                    ));
            payload.nidssDengueGeoValues = nidssDengueGeoValues;
        }
        var flusurvGeoValues = $("#flusurvLocations").select2("data")
        if (flusurvGeoValues !== undefined && flusurvGeoValues !== null) {
            flusurvGeoValues = Object.values(
                flusurvGeoValues
                    .flat()
                    .map(({ id }) => id
                    ));
            payload.flusurvGeoValues = flusurvGeoValues;
        }

        var pophiveAgeGroupData = getSelectedPophiveAgeGroup();
        if (pophiveAgeGroupData.length > 0) {
            payload.pophiveAgeGroup = pophiveAgeGroupData[0].id;
        }
        return payload;

    }

    showNIDSSFluLocations() {
        var nidssFluLocationselect = `
        <hr>
        <div class="row margin-top-1rem" id="nidssFluDiv">
            <div class="col-2">
                <label for="nidssFluLocations" class="col-form-label">Taiwanese ILI Location(s):</label>
            </div>
            <div class="col-10">
                <select id="nidssFluLocations" name="nidssFluLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(nidssFluLocationselect);
            $("#nidssFluLocations").select2({
                placeholder: "Select Taiwanese ILI Location(s)",
                data: this.nidssFluLocations,
                allowClear: true,
                width: "100%",
            });
        }
    }

    showNIDSSDengueLocations() {
        var nidssDengueLocationselect = `
        <hr>
        <div class="row margin-top-1rem" id="nidssDengueDiv">
            <div class="col-2">
                <label for="nidssDengueLocations" class="col-form-label">Taiwanese Dengue Cases Location(s):</label>
            </div>
            <div class="col-10">
                <select id="nidssDengueLocations" name="nidssDengueLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(nidssDengueLocationselect);
            $("#nidssDengueLocations").select2({
                placeholder: "Select Taiwanese Dengue Cases Location(s)",
                data: this.nidssDengueLocations,
                allowClear: true,
                width: "100%",
            });
        }
    }

    showFlusurvLocations() {
        var flusurvLocationselect = `
        <hr>
        <div class="row margin-top-1rem" id="flusurvDiv">
            <div class="col-2">
                <label for="flusurvLocations" class="col-form-label">FluSurv Location(s):</label>
            </div>
            <div class="col-10">
                <select id="flusurvLocations" name="flusurvLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(flusurvLocationselect);
            $("#flusurvLocations").select2({
                placeholder: "Select FluSurv Location(s)",
                data: this.flusurvLocations,
                allowClear: true,
                width: "100%",
            });
        }
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
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
        const pophiveAgeGroup = getSelectedPophiveAgeGroup();
        const nwssSource = $("#nwssSource").select2("data");
        const submitData = {
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
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
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
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
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
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
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
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
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
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
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
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
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
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
