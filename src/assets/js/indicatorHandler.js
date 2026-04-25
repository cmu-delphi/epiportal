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

    pophiveLocations = [
        { id: "us", geo_type: "nation", text: "U.S. National" },
        { id: "1", geo_type: "hhs", text: "HHS Region 1" },
        { id: "2", geo_type: "hhs", text: "HHS Region 2" },
        { id: "3", geo_type: "hhs", text: "HHS Region 3" },
        { id: "4", geo_type: "hhs", text: "HHS Region 4" },
        { id: "5", geo_type: "hhs", text: "HHS Region 5" },
        { id: "6", geo_type: "hhs", text: "HHS Region 6" },
        { id: "7", geo_type: "hhs", text: "HHS Region 7" },
        { id: "8", geo_type: "hhs", text: "HHS Region 8" },
        { id: "9", geo_type: "hhs", text: "HHS Region 9" },
        { id: "10", geo_type: "hhs", text: "HHS Region 10" },
        { id: "ak", geo_type: "state", text: "AK" },
        { id: "al", geo_type: "state", text: "AL" },
        { id: "ar", geo_type: "state", text: "AR" },
        { id: "az", geo_type: "state", text: "AZ" },
        { id: "ca", geo_type: "state", text: "CA" },
        { id: "co", geo_type: "state", text: "CO" },
        { id: "ct", geo_type: "state", text: "CT" },
        { id: "dc", geo_type: "state", text: "DC" },
        { id: "de", geo_type: "state", text: "DE" },
        { id: "fl", geo_type: "state", text: "FL" },
        { id: "ga", geo_type: "state", text: "GA" },
        { id: "hi", geo_type: "state", text: "HI" },
        { id: "ia", geo_type: "state", text: "IA" },
        { id: "id", geo_type: "state", text: "ID" },
        { id: "il", geo_type: "state", text: "IL" },
        { id: "in", geo_type: "state", text: "IN" },
        { id: "ks", geo_type: "state", text: "KS" },
        { id: "ky", geo_type: "state", text: "KY" },
        { id: "la", geo_type: "state", text: "LA" },
        { id: "ma", geo_type: "state", text: "MA" },
        { id: "md", geo_type: "state", text: "MD" },
        { id: "me", geo_type: "state", text: "ME" },
        { id: "mi", geo_type: "state", text: "MI" },
        { id: "mn", geo_type: "state", text: "MN" },
        { id: "mo", geo_type: "state", text: "MO" },
        { id: "ms", geo_type: "state", text: "MS" },
        { id: "mt", geo_type: "state", text: "MT" },
        { id: "nc", geo_type: "state", text: "NC" },
        { id: "nd", geo_type: "state", text: "ND" },
        { id: "ne", geo_type: "state", text: "NE" },
        { id: "nh", geo_type: "state", text: "NH" },
        { id: "nj", geo_type: "state", text: "NJ" },
        { id: "nm", geo_type: "state", text: "NM" },
        { id: "nv", geo_type: "state", text: "NV" },
        { id: "ny", geo_type: "state", text: "NY" },
        { id: "oh", geo_type: "state", text: "OH" },
        { id: "ok", geo_type: "state", text: "OK" },
        { id: "or", geo_type: "state", text: "OR" },
        { id: "pa", geo_type: "state", text: "PA" },
        { id: "ri", geo_type: "state", text: "RI" },
        { id: "sc", geo_type: "state", text: "SC" },
        { id: "sd", geo_type: "state", text: "SD" },
        { id: "tn", geo_type: "state", text: "TN" },
        { id: "tx", geo_type: "state", text: "TX" },
        { id: "ut", geo_type: "state", text: "UT" },
        { id: "va", geo_type: "state", text: "VA" },
        { id: "vt", geo_type: "state", text: "VT" },
        { id: "wa", geo_type: "state", text: "WA" },
        { id: "wi", geo_type: "state", text: "WI" },
        { id: "wv", geo_type: "state", text: "WV" },
        { id: "wy", geo_type: "state", text: "WY" },
    ]

    nwssPcrTargets = [
        'fluav',
        'fluav a h5',
        'hmpxv',
        'hmpxv clade i',
        'hmpxv clade ii',
        'mev_wt',
        'nvo',
        'rsv',
        'sars-cov-2',
      ];
    nwssSources = ['CDC_Biobot', 'CDC_Verily', 'State_Territory', 'WastewaterSCAN'];

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

        var pophiveGeoValues = $("#pophiveLocations").select2("data")
        if (pophiveGeoValues !== undefined && pophiveGeoValues !== null) {
            pophiveGeoValues = Object.values(
                pophiveGeoValues
                    .flat()
                    .map(({ id }) => id
                    ));
            payload.pophiveGeoValues = pophiveGeoValues;
        }
        var pophiveAgeGroupData = $("#pophiveAgeGroup").select2("data");
        if (pophiveAgeGroupData && pophiveAgeGroupData.length > 0) {
            payload.pophiveAgeGroup = pophiveAgeGroupData[0].id;
        }
        return payload;

    }

    showfluviewLocations() {
        var fluviewLocationselect = `
        <hr>
        <div class="row margin-top-1rem" id="fluviewDiv">
            <div class="col-2">
                <label for="fluviewLocations" class="col-form-label">ILINet Location(s):</label>
            </div>
            <div class="col-10">
                <select id="fluviewLocations" name="fluviewLocations" class="form-select" multiple="multiple"></select>
            </div>
        </div><hr>`;
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

    showPophiveLocations() {
        var pophiveLocationselect = `
        <hr>
        <div class="row margin-top-1rem" id="pophiveDiv">
            <div class="col-2">
                <label for="pophiveLocations" class="col-form-label">Cosmos Location(s):</label>
            </div>
            <div class="col-10">
                <select id="pophiveLocations" name="pophiveLocations" class="form-select" multiple="multiple"></select>
            </div>

            <div class="col-2 margin-top-1rem">
                <label for="pophiveAgeGroup" class="col-form-label">Age Group:</label>
            </div>
            <div class="col-10 margin-top-1rem">
                <select id="pophiveAgeGroup" name="pophiveAgeGroup" class="form-select"></select>
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(pophiveLocationselect);
            $("#pophiveLocations").select2({
                placeholder: "Select Cosmos Location(s)",
                data: this.pophiveLocations,
                allowClear: true,
                width: "100%",
            });
            $.get("get_pophive_age_groups/", function (response) {
                var ageGroups = response.age_groups.map(function (ag) {
                    return { id: ag, text: ag };
                });
                $("#pophiveAgeGroup").select2({
                    placeholder: "Select Age Group",
                    data: ageGroups,
                    allowClear: true,
                    width: "100%",
                });
            });
        }
    }

    showNwssFields() {
        var nwssFields = `
        <hr>
        <div class="row margin-top-1rem" id="nwssDiv">
            <div class="col-2">
                <label for="nwssPcrTarget" class="col-form-label">PCR Target:</label>
            </div>
            <div class="col-10">
                <select id="nwssPcrTarget" name="nwssPcrTarget" class="form-select"></select>
            </div>

            <div class="col-2 margin-top-1rem">
                <label for="nwssSource" class="col-form-label">NWSS Source:</label>
            </div>
            <div class="col-10 margin-top-1rem">
                <select id="nwssSource" name="nwssSource" class="form-select"></select>
            </div>

            <div class="col-2 margin-top-1rem">
                <label for="nwssGeographicValue" class="col-form-label">Geographic Value:</label>
            </div>
            <div class="col-10 margin-top-1rem">
                <input type="text" id="nwssGeographicValue" name="nwssGeographicValue" class="form-control" placeholder="Enter geographic value">
            </div>
        </div><hr>`;
        if ($("#otherEndpointLocations").length) {
            $("#otherEndpointLocations").append(nwssFields);
            var pcrTargets = this.nwssPcrTargets.map(function (t) {
                return { id: t, text: t };
            });
            $("#nwssPcrTarget").select2({
                placeholder: "Select PCR Target",
                data: pcrTargets,
                allowClear: true,
                width: "100%",
            });
            var sources = this.nwssSources.map(function (s) {
                return { id: s, text: s };
            });
            $("#nwssSource").select2({
                placeholder: "Select NWSS Source",
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
        const fluviewLocations = $("#fluviewLocations").select2("data");
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
        const pophiveLocations = $("#pophiveLocations").select2("data");
        const pophiveAgeGroup = $("#pophiveAgeGroup").select2("data");
        const nwssPcrTarget = $("#nwssPcrTarget").select2("data");
        const nwssSource = $("#nwssSource").select2("data");
        const nwssGeographicValue = $("#nwssGeographicValue").val();
        const submitData = {
            indicators: this.indicators,
            covidCastGeographicValues: covidCastGeographicValues,
            fluviewLocations: fluviewLocations,
            nidssFluLocations: nidssFluLocations,
            nidssDengueLocations: nidssDengueLocations,
            flusurvLocations: flusurvLocations,
            pophiveLocations: pophiveLocations,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssPcrTarget: nwssPcrTarget,
            nwssSource: nwssSource,
            nwssGeographicValue: nwssGeographicValue,
            nwssFillMethod: "source",
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
            dataLayerPush(payload);
            window.open(data["epivis_url"], '_blank').focus();
        });
    }

    exportData() {
        const fluviewLocations = $("#fluviewLocations").select2("data");
        const nidssFluLocations = $("#nidssFluLocations").select2("data");
        const nidssDengueLocations = $("#nidssDengueLocations").select2("data");
        const flusurvLocations = $("#flusurvLocations").select2("data");
        const pophiveLocations = $("#pophiveLocations").select2("data");
        const pophiveAgeGroup = $("#pophiveAgeGroup").select2("data");
        const nwssGeographicValue = $("#nwssGeographicValue").val();
        const nwssPcrTarget = $("#nwssPcrTarget").select2("data");
        const nwssSource = $("#nwssSource").select2("data");
        const nwssFillMethod = $("#nwssFillMethod").select2("data");
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
            pophiveLocations: pophiveLocations,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssGeographicValue: nwssGeographicValue,
            nwssPcrTarget: nwssPcrTarget,
            nwssSource: nwssSource,
            nwssFillMethod: nwssFillMethod,
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
        const pophiveLocations = $("#pophiveLocations").select2("data");
        const pophiveAgeGroup = $("#pophiveAgeGroup").select2("data");
        const nwssPcrTarget = $("#nwssPcrTarget").select2("data");
        const nwssSource = $("#nwssSource").select2("data");
        const nwssGeographicValue = $("#nwssGeographicValue").val();
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
            pophiveLocations: pophiveLocations,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssPcrTarget: nwssPcrTarget,
            nwssSource: nwssSource,
            nwssGeographicValue: nwssGeographicValue,
            nwssFillMethod: "source",
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
        const pophiveLocations = $("#pophiveLocations").select2("data");
        const pophiveAgeGroup = $("#pophiveAgeGroup").select2("data");
        const nwssPcrTarget = $("#nwssPcrTarget").select2("data");
        const nwssSource = $("#nwssSource").select2("data");
        const nwssGeographicValue = $("#nwssGeographicValue").val();
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
            pophiveLocations: pophiveLocations,
            pophiveAgeGroup: pophiveAgeGroup,
            nwssPcrTarget: nwssPcrTarget,
            nwssSource: nwssSource,
            nwssGeographicValue: nwssGeographicValue,
            nwssFillMethod: "source",
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
