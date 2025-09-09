function dataLayerPush(payload) {
    if (window.dataLayer) {
        window.dataLayer.push(function () {
            this.reset();
        });
        window.dataLayer.push(payload);
    }
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

    fluSurvRegions = [
        { value: "network_all", label: "Entire Network" },
        { value: "network_eip", label: "EIP Netowrk" },
        { value: "network_ihsp", label: "IHSP Network" },
        { value: "CA", label: "CA" },
        { value: "CO", label: "CO" },
        { value: "CT", label: "CT" },
        { value: "GA", label: "GA" },
        { value: "IA", label: "IA" },
        { value: "ID", label: "ID" },
        { value: "MD", label: "MD" },
        { value: "MI", label: "MI" },
        { value: "MN", label: "MN" },
        { value: "NM", label: "NM" },
        { value: "NY_albany", label: "NY (Albany)" },
        { value: "NY_rochester", label: "NY (Rochester)" },
        { value: "OH", label: "OH" },
        { value: "OK", label: "OK" },
        { value: "OR", label: "OR" },
        { value: "RI", label: "RI" },
        { value: "SD", label: "SD" },
        { value: "TN", label: "TN" },
        { value: "UT", label: "UT" },
    ];

    fluviewRegions = [
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

    showFluviewRegions() {
        var fluviewRegionSelect = `
        <div class="row margin-top-1rem" id="fluviewDiv">
            <div class="col-2">
                <label for="fluviewRegions" class="col-form-label">ILINet Location(s):</label>
            </div>
            <div class="col-10">
                <select id="fluviewRegions" name="fluviewRegions" class="form-select" multiple="multiple"></select>
            </div>
        </div>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(fluviewRegionSelect);
            $("#fluviewRegions").select2({
                placeholder: "Select ILINet Location(s)",
                data: this.fluviewRegions,
                allowClear: true,
                width: "100%",
            });
        }
    }

    showNIDSSFluLocations() {
        var nidssFluRegionSelect = `
        <div class="row margin-top-1rem" id="nidssFluDiv">
            <div class="col-2">
                <label for="nidssFluRegions" class="col-form-label">Taiwanese ILI Location(s):</label>
            </div>
            <div class="col-10">
                <select id="nidssFluRegions" name="nidssFluRegions" class="form-select" multiple="multiple"></select>
            </div>
        </div>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(nidssFluRegionSelect);
            $("#nidssFluRegions").select2({
                placeholder: "Select Taiwanese ILI Location(s)",
                data: this.nidssFluLocations,
                allowClear: true,
                width: "100%",
            });
        }
    }

    plotData() {
        const covidCastGeographicValues =
            $("#geographic_value").select2("data");
        const fluviewRegions = $("#fluviewRegions").select2("data");
        const submitData = {
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewRegions: fluviewRegions,
            apiKey: document.getElementById("apiKey").value,
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
        }).done(function (data) {
            const payload = {
                event: "submitSelectedIndicators",
                formMode: "epivis",
                indicators: JSON.stringify(submitData["indicators"]),
                covidcastGeoValues: JSON.stringify(submitData["covidCastGeographicValues"]),
                fluviewGeoValues: JSON.stringify(submitData["fluviewRegions"]),
                
                epivisUrl: data["epivis_url"],
                apiKey: submitData["apiKey"] ? submitData["apiKey"] : "Not provided",
            }
            dataLayerPush(payload);
            window.open(data["epivis_url"], '_blank').focus();
        });
    }

    exportData() {
        var fluviewRegions = $("#fluviewRegions").select2("data");

        var covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewRegions: fluviewRegions,
            apiKey: document.getElementById("apiKey").value,
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
        }).done(function (data) {
            const payload = {
                event: "submitSelectedIndicators",
                formMode: "export",
                formStartDate: submitData["start_date"],
                formEndDate: submitData["end_date"],
                indicators: JSON.stringify(submitData["indicators"]),
                covidcastGeoValues: JSON.stringify(submitData["covidCastGeographicValues"]),
                fluviewGeoValues: JSON.stringify(submitData["fluviewRegions"]),
                apiKey: submitData["apiKey"] ? submitData["apiKey"] : "Not provided",
            }
            dataLayerPush(payload);
            $('#modeSubmitResult').html(data["data_export_block"]);
        });
    }

    previewData() {
        $('#loader').show();
        var fluviewRegions = $("#fluviewRegions").select2("data");

        var covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );
        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewRegions: fluviewRegions,
            apiKey: document.getElementById("apiKey").value,
        }
        const csrftoken = Cookies.get("csrftoken");
        $.ajax({
            url: "preview_data/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        }).done(function (data) {
            const payload = {
                event: "submitSelectedIndicators",
                formMode: "preview",
                formStartDate: submitData["start_date"],
                formEndDate: submitData["end_date"],
                indicators: JSON.stringify(submitData["indicators"]),
                covidcastGeoValues: JSON.stringify(submitData["covidCastGeographicValues"]),
                fluviewGeoValues: JSON.stringify(submitData["fluviewRegions"]),
                apiKey: submitData["apiKey"] ? submitData["apiKey"] : "Not provided",
            }
            dataLayerPush(payload);
            $('#loader').hide();
            $('#modeSubmitResult').html(JSON.stringify(data, null, 2));
        });
    }

    createQueryCode() {

        var fluviewRegions = $("#fluviewRegions").select2("data");

        var covidCastGeographicValues = Object.groupBy(
            $("#geographic_value").select2("data"),
            ({ geoType }) => [geoType]
        );

        const submitData = {
            start_date: document.getElementById("start_date").value,
            end_date: document.getElementById("end_date").value,
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewRegions: fluviewRegions,
            apiKey: document.getElementById("apiKey").value,
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
        }).done(function (data) {
            const payload = {
                event: "submitSelectedIndicators",
                formMode: "queryCode",
                formStartDate: submitData["start_date"],
                formEndDate: submitData["end_date"],
                indicators: JSON.stringify(submitData["indicators"]),
                covidcastGeoValues: JSON.stringify(submitData["covidCastGeographicValues"]),
                fluviewGeoValues: JSON.stringify(submitData["fluviewRegions"]),
                apiKey: submitData["apiKey"] ? submitData["apiKey"] : "Not provided",
            }
            dataLayerPush(payload);
            createQueryCodePython += data["python_code_blocks"].join("<br>");
            createQueryCodeR += data["r_code_blocks"].join("<br>");
            $('#modeSubmitResult').html(createQueryCodePython+"<br>"+createQueryCodeR);
        });

    }
}
