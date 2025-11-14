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

    fluviewLocations = [
        { id: "nat", text: "U.S. National" },
        { id: "hhs1", text: "HHS Region 1" },
        { id: "hhs2", text: "HHS Region 2" },
        { id: "hhs3", text: "HHS Region 3" },
        { id: "hhs4", text: "HHS Region 4" },
        { id: "hhs5", text: "HHS Region 5" },
        { id: "hhs6", text: "HHS Region 6" },
        { id: "hhs7", text: "HHS Region 7" },
        { id: "hhs8", text: "HHS Region 8" },
        { id: "hhs9", text: "HHS Region 9" },
        { id: "hhs10", text: "HHS Region 10" },
        { id: "cen1", text: "Census Region 1" },
        { id: "cen2", text: "Census Region 2" },
        { id: "cen3", text: "Census Region 3" },
        { id: "cen4", text: "Census Region 4" },
        { id: "cen5", text: "Census Region 5" },
        { id: "cen6", text: "Census Region 6" },
        { id: "cen7", text: "Census Region 7" },
        { id: "cen8", text: "Census Region 8" },
        { id: "cen9", text: "Census Region 9" },
        { id: "AK", text: "AK" },
        { id: "AL", text: "AL" },
        { id: "AR", text: "AR" },
        { id: "AZ", text: "AZ" },
        { id: "CA", text: "CA" },
        { id: "CO", text: "CO" },
        { id: "CT", text: "CT" },
        { id: "DC", text: "DC" },
        { id: "DE", text: "DE" },
        { id: "FL", text: "FL" },
        { id: "GA", text: "GA" },
        { id: "HI", text: "HI" },
        { id: "IA", text: "IA" },
        { id: "ID", text: "ID" },
        { id: "IL", text: "IL" },
        { id: "IN", text: "IN" },
        { id: "KS", text: "KS" },
        { id: "KY", text: "KY" },
        { id: "LA", text: "LA" },
        { id: "MA", text: "MA" },
        { id: "MD", text: "MD" },
        { id: "ME", text: "ME" },
        { id: "MI", text: "MI" },
        { id: "MN", text: "MN" },
        { id: "MO", text: "MO" },
        { id: "MS", text: "MS" },
        { id: "MT", text: "MT" },
        { id: "NC", text: "NC" },
        { id: "ND", text: "ND" },
        { id: "NE", text: "NE" },
        { id: "NH", text: "NH" },
        { id: "NJ", text: "NJ" },
        { id: "NM", text: "NM" },
        { id: "NV", text: "NV" },
        { id: "NY", text: "NY" },
        { id: "OH", text: "OH" },
        { id: "OK", text: "OK" },
        { id: "OR", text: "OR" },
        { id: "PA", text: "PA" },
        { id: "RI", text: "RI" },
        { id: "SC", text: "SC" },
        { id: "SD", text: "SD" },
        { id: "TN", text: "TN" },
        { id: "TX", text: "TX" },
        { id: "UT", text: "UT" },
        { id: "VA", text: "VA" },
        { id: "VT", text: "VT" },
        { id: "WA", text: "WA" },
        { id: "WI", text: "WI" },
        { id: "WV", text: "WV" },
        { id: "WY", text: "WY" },
        { id: "ny_minus_jfk", text: "NY (minus NYC)" },
        { id: "as", text: "American Samoa" },
        { id: "mp", text: "Mariana Islands" },
        { id: "gu", text: "Guam" },
        { id: "pr", text: "Puerto Rico" },
        { id: "vi", text: "Virgin Islands" },
        { id: "ord", text: "Chicago" },
        { id: "lax", text: "Los Angeles" },
        { id: "jfk", text: "New York City" },
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

    checkForCovidcastIndicators() {
        return this.indicators.some((indicator) => {
            return indicator["_endpoint"] === "covidcast";
        });
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

    getFromToDate(startDate, endDate, timeType) {
        if (timeType === "week") {
            $.ajax({
                url: "get_epiweek/",
                type: "POST",
                async: false,
                data: {
                    csrfmiddlewaretoken: csrf_token,
                    start_date: startDate,
                    end_date: endDate,
                },
                success: function (result) {
                    startDate = result.start_date;
                    endDate = result.end_date;
                },
            });
        }
        return [startDate, endDate];
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
        var fluviewGeoValues = $("#fluviewLocations").select2("data")
        if (fluviewGeoValues !== undefined && fluviewGeoValues !== null) {
            fluviewGeoValues = Object.values(
                fluviewGeoValues
                    .flat()
                    .map(({ id }) => id
            ));
            payload.fluviewGeoValues = fluviewGeoValues;
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

        return payload;

    }

    showfluviewLocations() {
        var fluviewLocationselect = `
        <div class="row margin-top-1rem" id="fluviewDiv">
            <div class="col-2">
                <label for="fluviewLocations" class="col-form-label">ILINet Location(s):</label>
            </div>
            <div class="col-10">
                <select id="fluviewLocations" name="fluviewLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(fluviewLocationselect);
            $("#fluviewLocations").select2({
                placeholder: "Select ILINet Location(s)",
                data: this.fluviewLocations,
                allowClear: true,
                width: "100%",
            });
        }
    }

    showNIDSSFluLocations() {
        var nidssFluLocationselect = `
        <div class="row margin-top-1rem" id="nidssFluDiv">
            <div class="col-2">
                <label for="nidssFluLocations" class="col-form-label">Taiwanese ILI Location(s):</label>
            </div>
            <div class="col-10">
                <select id="nidssFluLocations" name="nidssFluLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div>`;
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
        <div class="row margin-top-1rem" id="nidssDengueDiv">
            <div class="col-2">
                <label for="nidssDengueLocations" class="col-form-label">Taiwanese Dengue Cases Location(s):</label>
            </div>
            <div class="col-10">
                <select id="nidssDengueLocations" name="nidssDengueLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div>`;
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
        <div class="row margin-top-1rem" id="flusurvDiv">
            <div class="col-2">
                <label for="flusurvLocations" class="col-form-label">FluSurv Location(s):</label>
            </div>
            <div class="col-10">
                <select id="flusurvLocations" name="flusurvLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div>`;
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

    plotData() {
        const covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const fluviewLocations = $("#fluviewLocations").select2("data");
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
        const submitData = {
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewLocations: fluviewLocations,
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
        };
        const csrftoken = Cookies.get("csrftoken");
        $.ajax({
            url: "epivis/",
            type: "POST",
            async: false,
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        }).done((data) => {
            const payload = this.prepareDataLayerPayload("epivis");
            console.log(payload);
            dataLayerPush(payload);
            window.open(data["epivis_url"], '_blank').focus();
        });
    }

    exportData() {
        const fluviewLocations = $("#fluviewLocations").select2("data");
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");

        var covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewLocations: fluviewLocations,
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
        }
        const csrftoken = Cookies.get("csrftoken");
        $.ajax({
            url: "export/",
            type: "POST",
            async: false,
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        }).done((data) => {
            const payload = this.prepareDataLayerPayload("export");
            dataLayerPush(payload);
            $('#modeSubmitResult').html(data["data_export_block"]);
        });
    }

    previewData() {
        $('#loader').show();
        const fluviewLocations = $("#fluviewLocations").select2("data");
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");

        const covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewLocations: fluviewLocations,
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
            apiKey: document.getElementById("apiKey").value ? document.getElementById("apiKey").value : "",
            clientId: clientId ? clientId : "Not available",
        }
        const csrftoken = Cookies.get("csrftoken");
        $.ajax({
            url: "preview_data/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        }).done((data) => {
            const payload = this.prepareDataLayerPayload("previewData");
            dataLayerPush(payload);
            $('#loader').hide();
            $('#modeSubmitResult').html(JSON.stringify(data, null, 2));
        });
    }

    createQueryCode() {
        const fluviewLocations = $("#fluviewLocations").select2("data");
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");

        const covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );

        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewLocations: fluviewLocations,
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
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
