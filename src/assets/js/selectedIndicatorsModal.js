const indicatorHandler = new IndicatorHandler();
let checkedIndicatorMembers = [];

function updateSelectedIndicators(
    dataSource,
    indicatorDisplayName,
    indicatorSet,
    indicator
) {
    var selectedIndicatorsList = document.getElementById(
        "selectedIndicatorsList"
    );

    var tr = document.createElement("tr");
    tr.setAttribute("id", `${dataSource}_${indicator}`);
    var indicatorSetName = document.createElement("td");
    indicatorSetName.textContent = indicatorSet;
    tr.appendChild(indicatorSetName);
    var indicatorName = document.createElement("td");
    indicatorName.textContent = indicatorDisplayName;
    tr.appendChild(indicatorName);
    selectedIndicatorsList.appendChild(tr);
}

function addSelectedIndicator(element) {
    if (element.checked) {
        checkedIndicatorMembers.push({
            _endpoint: element.dataset.endpoint,
            data_source: element.dataset.datasource,
            indicator: element.dataset.indicator,
            time_type: element.dataset.timeType,
            indicator_set: element.dataset.indicatorSet,
            display_name: element.dataset.indicatorDisplayname,
            indicator_set_short_name: element.dataset.indicatorSetShortName,
        });
        updateSelectedIndicators(
            element.dataset.datasource,
            element.dataset.indicatorDisplayname,
            element.dataset.indicatorSet,
            element.dataset.indicator
        );
        if (!MAIN_LOCATION_ENDPOINTS.includes(element.dataset.endpoint) && !indicatorHandler.nonCovidcastIndicatorSets.includes(element.dataset.indicatorSet)) {
            indicatorHandler.nonCovidcastIndicatorSets.push(
                element.dataset.indicatorSet
            );
        }
    } else {
        checkedIndicatorMembers = checkedIndicatorMembers.filter(
            (indicator) => indicator.indicator !== element.dataset.indicator
        );
        document
            .getElementById(
                `${element.dataset.datasource}_${element.dataset.indicator}`
            )
            .remove();
        const indicatorSet = element.dataset.indicatorSet;
        const stillExist = checkedIndicatorMembers.some(
            (indicator) => indicator.indicator_set === indicatorSet
        );
        if (!stillExist && indicatorHandler.nonCovidcastIndicatorSets.includes(indicatorSet)) {
            indicatorHandler.nonCovidcastIndicatorSets = indicatorHandler.nonCovidcastIndicatorSets.filter(
                (set) => set !== indicatorSet
            );
        }
    }

    indicatorHandler.indicators = checkedIndicatorMembers;

    if (checkedIndicatorMembers.length > 0) {
        $("#showSelectedIndicatorsButton").show();
    } else {
        $("#showSelectedIndicatorsButton").hide();
    }
}

function hideAlert(alertId) {
    const alert = document.getElementById(alertId);
    if (alert) {
        alert.remove();
    }
}

const alertPlaceholder = document.getElementById("warning-alert");

const appendAlert = (message, type) => {
    const wrapper = document.createElement("div");
    const alertId = `alert-${Date.now()}`;
    wrapper.innerHTML = [
        `<div id="${alertId}" class="alert alert-${type} alert-dismissible" data-mdb-alert-init role="alert">`,
        `   <div>${message}</div>`,
        '   <button type="button" class="btn-close" data-mdb-dismiss="alert" aria-label="Close"></button>',
        "</div>",
    ].join("");

    alertPlaceholder.append(wrapper);
    wrapper
        .getElementsByClassName("btn-close")[0]
        .addEventListener("click", () => hideAlert(alertId));
    return wrapper;
};

var currentMode = "epivis";

/* fill_method is a key column on every Epidata v5 source, so one control
 * covers the whole submission rather than one per source. The lists come from
 * the server so they stay in step with MIGRATED_DATASOURCES. */
const V5_DATA_SOURCES = typeof v5DataSources !== "undefined" ? v5DataSources : [];
const V5_ENDPOINTS = typeof v5Endpoints !== "undefined" ? v5Endpoints : [];

// covidcast plus the v5-only sources that share its code paths, from the
// server so they stay in step with V5_ONLY_DATASOURCES.
const COVIDCAST_ENDPOINTS =
    typeof covidcastEndpoints !== "undefined" ? covidcastEndpoints : ["covidcast"];

// Endpoints whose locations come from the main Location(s) dropdown rather
// than a dropdown of their own.
const MAIN_LOCATION_ENDPOINTS = [...COVIDCAST_ENDPOINTS, "fluview", "pophive", "nwss"];

// Preselected in the main Location(s) dropdown when nothing else is.
const DEFAULT_LOCATION_ID = "nation:US";

function isV5Indicator(indicator) {
    return (
        V5_ENDPOINTS.includes(indicator._endpoint) ||
        V5_DATA_SOURCES.includes(indicator.data_source)
    );
}

function getFillMethod() {
    return $("#fillMethod").val() || "";
}

/* Plotting never offers the control. EpiVis picks v4 vs v5 itself and its
 * covidcast and epiweek loaders take no fill_method argument, so a value
 * chosen for those would be dropped in silence; only its nwss loader accepts
 * one. Rather than show a setting that applies to some series and not others,
 * Plot always uses each source's own fill method. Export, Preview and Create
 * query code build their own v5 requests, so they honour the choice.
 * See https://github.com/cmu-delphi/www-epivis for the missing param. */
function hideFillMethod() {
    // Reset as well as hide: the control keeps its value across mode changes,
    // so a hidden one would otherwise still be read into the payload. Trigger
    // change so covidcast coverage is rechecked for the reset value.
    if ($("#fillMethod").val() !== "") {
        $("#fillMethod").val("").trigger("change");
    }
    $("#fillMethodDiv").hide();
}

function updateFillMethodVisibility() {
    if (currentMode === "epivis") {
        hideFillMethod();
        return;
    }
    if (!checkedIndicatorMembers.some(isV5Indicator)) {
        hideFillMethod();
        return;
    }
    $("#fillMethodDiv").show();
    $("#fillMethodHelp").text("How gaps in the reported series are filled.");
}

function handleModeChange(mode) {
    $('#modeSubmitResult').html('');

    var choose_dates = document.getElementsByName('choose_date');
    var data_format_div = document.getElementsByName('data_format_div');

    currentMode = mode;

    if (mode === 'epivis') {
        choose_dates.forEach((el) => {
            el.style.display = 'none';
        })
    } else {
        choose_dates.forEach((el) => {
            el.style.display = 'flex';
        })
    }

    if (mode === 'export' || mode === 'preview') {
        data_format_div.forEach((el) => {
            el.style.display = 'flex';
        })
    } else {
        data_format_div.forEach((el) => {
            el.style.display = 'none';
        })
    }
    $('#modeSubmitResult').html('');

    updateFillMethodVisibility();

    document.getElementsByName("modes").forEach((el) => {
        if (currentMode === el.value) {
            el.checked = true;
        }
    });
}

document.getElementsByName('modes').forEach((el) => {
    el.addEventListener('change', (event) => {
        currentMode = event.target.value;
        handleModeChange(currentMode);
    });
});

function showNotCoveredGeoWarningMessage(notCoveredIndicators, geoValue) {
    var warningMessage = "";
    notCoveredIndicators.forEach((indicator) => {
        if (currentMode === "epivis") {
            warningMessage += `Indicator "${indicator.display_name}" is not available for Location "${geoValue.text}" <br>`;
        } else {
            var startDate = document.getElementById("start_date").value;
            var endDate = document.getElementById("end_date").value;
            warningMessage += `Indicator "${indicator.display_name}" is not available for Location "${geoValue.text}" for the time period from "${startDate}" to "${endDate}" <br>`;
        }
    });
    return appendAlert(warningMessage, "warning");
}

/* Bumped whenever the fill method changes, so a coverage check still in
 * flight for the old one is ignored rather than raising a stale warning. */
let coverageCheckGeneration = 0;

/* Asks the server, which routes each covidcast indicator to v5 or v4 the
 * same way Export does, whether geoValue has data for it. Only real values
 * count: an indicator with nothing but nulls on both APIs is not covered.
 * The answer depends on the fill method, since Export only falls back to v4
 * for "source". covered === null means the check itself failed, so no warning
 * is shown. Resolves to null when the fill method changed mid-check. */
async function checkGeoCoverage(geoValue) {
    const generation = coverageCheckGeneration;
    const notCoveredIndicators = [];
    const covidcastIndicators = checkedIndicatorMembers.filter((indicator) =>
        COVIDCAST_ENDPOINTS.includes(indicator["_endpoint"])
    );
    if (covidcastIndicators.length === 0) {
        return notCoveredIndicators;
    }

    try {
        const result = await $.ajax({
            url: "check_covidcast_geo_coverage/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": Cookies.get("csrftoken") },
            data: JSON.stringify({
                geo: geoValue,
                fill_method: getFillMethod(),
                indicators: covidcastIndicators.map((indicator) => ({
                    _endpoint: indicator["_endpoint"],
                    data_source: indicator.data_source,
                    indicator: indicator.indicator,
                    time_type: indicator.time_type,
                })),
            }),
        });

        if (generation !== coverageCheckGeneration) {
            return null;
        }

        covidcastIndicators.forEach((indicator) => {
            const entry = result["coverage"].find(
                (e) =>
                    e.data_source === indicator.data_source &&
                    e.indicator === indicator.indicator
            );
            if (!entry || entry.covered !== false) {
                // Covered now, perhaps not under the previous fill method.
                if (indicator["notCoveredGeos"]) {
                    indicator["notCoveredGeos"] = indicator["notCoveredGeos"].filter(
                        (geo) => geo !== geoValue
                    );
                }
                return;
            }
            if (!indicator["notCoveredGeos"]) {
                indicator["notCoveredGeos"] = [];
            }
            if (!indicator["notCoveredGeos"].includes(geoValue)) {
                indicator["notCoveredGeos"].push(geoValue);
            }
            notCoveredIndicators.push(indicator);
        });

        return notCoveredIndicators;
    } catch (error) {
        console.error("Error fetching geo coverage:", error);
        return notCoveredIndicators;
    }
}

function isFluviewIndicator(indicator) {
    return (
        indicator["_endpoint"] === "fluview" ||
        indicator["_endpoint"] === "fluview_clinical"
    );
}

/* Asks the server, which routes each fluview indicator to v5 or v4 the way
 * Export does, whether geoValue has data for it. Only real values count. Keeps
 * each indicator's notCoveredGeos in step with the answer, which Plot uses to
 * skip the location; covered === null means the check itself failed, so the
 * location is neither warned about nor skipped. Resolves to the uncovered
 * indicators. */
async function checkFluviewGeoCoverage(geoValue) {
    const fluviewIndicators = checkedIndicatorMembers.filter(isFluviewIndicator);
    if (fluviewIndicators.length === 0) {
        return [];
    }
    try {
        const result = await $.ajax({
            url: "check_fluview_geo_coverage/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": Cookies.get("csrftoken") },
            data: JSON.stringify({
                geo: geoValue,
                fill_method: getFillMethod(),
                indicators: fluviewIndicators.map((indicator) => ({
                    _endpoint: indicator["_endpoint"],
                    data_source: indicator.data_source,
                    indicator: indicator.indicator,
                })),
            }),
        });
        const notCovered = [];
        fluviewIndicators.forEach((indicator) => {
            const entry = result["coverage"].find(
                (e) =>
                    e.data_source === indicator.data_source &&
                    e.indicator === indicator.indicator
            );
            indicator["notCoveredGeos"] = (indicator["notCoveredGeos"] || []).filter(
                (geo) => geo !== geoValue
            );
            if (entry && entry.covered === false) {
                indicator["notCoveredGeos"].push(geoValue);
                notCovered.push(indicator);
            }
        });
        return notCovered;
    } catch (error) {
        console.error("Error fetching fluview geo coverage:", error);
        return [];
    }
}

async function getAvailableGeos(indicators) {
    const csrftoken = Cookies.get("csrftoken");
    const submitData = { indicators: indicators };

    try {
        const data = await $.ajax({
            url: "get_available_geos/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": csrftoken },
            data: JSON.stringify(submitData),
        });
        return data.geographic_granularities;
    } catch (error) {
        console.error("Error fetching available geos:", error);
        return null;
    }
}

/* Covidcast coverage warnings are tagged so a fill method change can swap
 * them out without touching the other alerts in the modal. */
function warnIfCovidcastGeoNotCovered(geo) {
    checkGeoCoverage(geo.id).then((notCoveredIndicators) => {
        if (notCoveredIndicators && notCoveredIndicators.length > 0) {
            showNotCoveredGeoWarningMessage(notCoveredIndicators, geo).classList.add(
                "covidcast-coverage-alert"
            );
        }
    });
}

// Fluview reads its locations from the main dropdown too; the server maps
// each pick to a fluview region and answers "not covered" when there is none.
// Bumped whenever the fluview answer may change (fill method), so a check
// still in flight for the old choice is ignored. Its warnings are tagged so
// they can be swapped out without touching the other alerts.
let fluviewCoverageCheckGeneration = 0;

function warnIfFluviewGeoNotCovered(geo) {
    const generation = fluviewCoverageCheckGeneration;
    checkFluviewGeoCoverage(geo.id).then((notCoveredIndicators) => {
        if (generation !== fluviewCoverageCheckGeneration) {
            return;
        }
        if (notCoveredIndicators.length > 0) {
            showNotCoveredGeoWarningMessage(notCoveredIndicators, geo).classList.add(
                "fluview-coverage-alert"
            );
        }
    });
}

function recheckFluviewCoverage() {
    fluviewCoverageCheckGeneration += 1;
    $("#warning-alert .fluview-coverage-alert").remove();
    if (!$("#geographic_value").hasClass("select2-hidden-accessible")) {
        return;
    }
    $("#geographic_value").select2("data").forEach(warnIfFluviewGeoNotCovered);
}

/* Asks the server, which reads /viz/ the way Export does, whether geoValue
 * has Cosmos data for each pophive indicator with the selected age group and
 * fill method. The age group list loads after the modal opens, so until one
 * is selected there is nothing to check; selecting it re-checks. Resolves to
 * the uncovered indicators; covered === null means the check itself failed,
 * so no warning is shown. */
async function checkPophiveGeoCoverage(geoValue) {
    const pophiveIndicators = checkedIndicatorMembers.filter(
        (indicator) => indicator["_endpoint"] === "pophive"
    );
    const ageGroup = getSelectedPophiveAgeGroup();
    if (pophiveIndicators.length === 0 || ageGroup.length === 0) {
        return [];
    }
    try {
        const result = await $.ajax({
            url: "check_pophive_geo_coverage/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": Cookies.get("csrftoken") },
            data: JSON.stringify({
                geo: geoValue,
                age_group: ageGroup[0].id,
                fill_method: getFillMethod(),
                indicators: pophiveIndicators.map((indicator) => ({
                    _endpoint: indicator["_endpoint"],
                    data_source: indicator.data_source,
                    indicator: indicator.indicator,
                })),
            }),
        });
        return pophiveIndicators.filter((indicator) =>
            result["coverage"].some(
                (entry) => entry.indicator === indicator.indicator && entry.covered === false
            )
        );
    } catch (error) {
        console.error("Error fetching Cosmos geo coverage:", error);
        return [];
    }
}

// Bumped whenever the Cosmos answer may change (age group or fill method), so
// a check still in flight for the old choice is ignored. Its warnings are
// tagged so they can be swapped out without touching the other alerts.
let pophiveCoverageCheckGeneration = 0;

// Cosmos (pophive) reads its locations from the main dropdown too; places it
// has no data for (counties, territories, ...) are skipped, so say so.
function warnIfPophiveGeoNotCovered(geo) {
    const generation = pophiveCoverageCheckGeneration;
    checkPophiveGeoCoverage(geo.id).then((notCoveredIndicators) => {
        if (generation !== pophiveCoverageCheckGeneration) {
            return;
        }
        if (notCoveredIndicators.length > 0) {
            showNotCoveredGeoWarningMessage(notCoveredIndicators, geo).classList.add(
                "pophive-coverage-alert"
            );
        }
    });
}

function recheckPophiveCoverage() {
    pophiveCoverageCheckGeneration += 1;
    $("#warning-alert .pophive-coverage-alert").remove();
    if (!$("#geographic_value").hasClass("select2-hidden-accessible")) {
        return;
    }
    $("#geographic_value").select2("data").forEach(warnIfPophiveGeoNotCovered);
}

// #pophiveAgeGroup is added to the modal only once Cosmos indicators are
// selected, and selecting its default fires a change too.
$(document).on("change", "#pophiveAgeGroup", recheckPophiveCoverage);

function getSelectedNwssSources() {
    if (!$("#nwssSource").hasClass("select2-hidden-accessible")) {
        return [];
    }
    return $("#nwssSource").select2("data").map((source) => source.id);
}

/* Asks the server, which reads /viz/ for the county's sewersheds the way
 * Export does, whether each NWSS indicator has data from each selected NWSS
 * source. Until a source is picked there is nothing to check. Resolves to one
 * entry per uncovered (indicator, source), labelled with the source;
 * covered === null means the check itself failed, so no warning is shown. */
async function checkNwssGeoCoverage(geoValue) {
    const nwssIndicators = checkedIndicatorMembers.filter(
        (indicator) => indicator["_endpoint"] === "nwss"
    );
    const nwssSources = getSelectedNwssSources();
    if (nwssIndicators.length === 0 || nwssSources.length === 0) {
        return [];
    }
    try {
        const result = await $.ajax({
            url: "check_nwss_geo_coverage/",
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": Cookies.get("csrftoken") },
            data: JSON.stringify({
                geo: geoValue,
                nwss_sources: nwssSources,
                fill_method: getFillMethod(),
                indicators: nwssIndicators.map((indicator) => ({
                    _endpoint: indicator["_endpoint"],
                    data_source: indicator.data_source,
                    indicator: indicator.indicator,
                })),
            }),
        });
        const notCovered = [];
        result["coverage"].forEach((entry) => {
            if (entry.covered !== false) {
                return;
            }
            const indicator = nwssIndicators.find(
                (i) => i.indicator === entry.indicator
            );
            if (indicator) {
                notCovered.push({
                    ...indicator,
                    display_name: `${indicator.display_name} (source: ${entry.nwss_source})`,
                });
            }
        });
        return notCovered;
    } catch (error) {
        console.error("Error fetching NWSS geo coverage:", error);
        return [];
    }
}

// NWSS reads its locations from the main dropdown too, as the sewersheds of
// the picked counties; anything else (states, counties with no sewershed) is
// skipped, so say so, per selected NWSS source.
// Bumped whenever the NWSS answer may change (source or fill method), so a
// check still in flight for the old choice is ignored.
let nwssCoverageCheckGeneration = 0;

// NWSS warnings are tagged so a source or fill method change can swap them
// out without touching the other alerts in the modal.
function warnIfNwssGeoNotCovered(geo) {
    const generation = nwssCoverageCheckGeneration;
    checkNwssGeoCoverage(geo.id).then((notCoveredIndicators) => {
        if (generation !== nwssCoverageCheckGeneration) {
            return;
        }
        if (notCoveredIndicators.length > 0) {
            showNotCoveredGeoWarningMessage(notCoveredIndicators, geo).classList.add(
                "nwss-coverage-alert"
            );
        }
    });
}

// The answer depends on the selected NWSS sources and fill method as well as
// the location, so re-check every picked location whichever is chosen last.
function recheckNwssCoverage() {
    nwssCoverageCheckGeneration += 1;
    $("#warning-alert .nwss-coverage-alert").remove();
    if (!$("#geographic_value").hasClass("select2-hidden-accessible")) {
        return;
    }
    $("#geographic_value").select2("data").forEach(warnIfNwssGeoNotCovered);
}

// #nwssSource is added to the modal only once NWSS indicators are selected.
$(document).on("change", "#nwssSource", recheckNwssCoverage);

function warnIfGeoNotCovered(geo) {
    warnIfCovidcastGeoNotCovered(geo);
    warnIfFluviewGeoNotCovered(geo);
    warnIfPophiveGeoNotCovered(geo);
    warnIfNwssGeoNotCovered(geo);
}

$("#geographic_value").on("select2:select", function (e) {
    warnIfGeoNotCovered(e.params.data);
});

$("#fillMethod").on("change", function () {
    coverageCheckGeneration += 1;
    $("#warning-alert .covidcast-coverage-alert").remove();
    recheckFluviewCoverage();
    recheckPophiveCoverage();
    recheckNwssCoverage();
    if (!$("#geographic_value").hasClass("select2-hidden-accessible")) {
        return;
    }
    $("#geographic_value").select2("data").forEach(warnIfCovidcastGeoNotCovered);
});

function showNIDSSFluLocationSelect() {
    if (indicatorHandler.getNIDSSFluIndicators().length > 0) {
        if (document.getElementsByName("nidssFluLocations").length === 0) {
            indicatorHandler.showNIDSSFluLocations();
        } else {
            // IF code goes here, we assume that otherEndpointLocationWarning & nidssRegion selector is already on the page, but is just hidden, so we should just show it.
            $("#nidssFluDiv").show();
        }
    } else {
        // If there are no non-covidcast indicators selected then hide otherEndpointLocationWarning & nidssFluLocations selector.
        $("#nidssFluLocations").val(null).trigger("change");
        $("#nidssFluDiv").hide();
    }
}

function showNIDSSDengueLocationSelect() {
    if (indicatorHandler.getNIDSSDengueIndicators().length > 0) {
        if (document.getElementsByName("nidssDengueLocations").length === 0) {
            indicatorHandler.showNIDSSDengueLocations();
        } else {
            // IF code goes here, we assume that otherEndpointLocationWarning & nidssRegion selector is already on the page, but is just hidden, so we should just show it.
            $("#nidssDengueDiv").show();
        }
    } else {
        // If there are no non-covidcast indicators selected then hide otherEndpointLocationWarning & nidssDengueLocations selector.
        $("#nidssDengueLocations").val(null).trigger("change");
        $("#nidssDengueDiv").hide();
    }
}

function showFlusurvLocationSelect() {
    if (indicatorHandler.getFlusurvIndicators().length > 0) {
        if (document.getElementsByName("flusurvLocations").length === 0) {
            indicatorHandler.showFlusurvLocations();
        } else {
            // IF code goes here, we assume that otherEndpointLocationWarning & flusurvRegion selector is already on the page, but is just hidden, so we should just show it.
            $("#flusurvDiv").show();
        }
    } else {
        // If there are no non-covidcast indicators selected then hide otherEndpointLocationWarning & flusurvLocations selector.
        $("#flusurvLocations").val(null).trigger("change");
        $("#flusurvDiv").hide();
    }
}


// Cosmos (pophive) indicators get an age group control below the main
// Location(s) dropdown; their locations come from that dropdown.
function showPophiveAgeGroupSelect() {
    if (indicatorHandler.getPophiveIndicators().length > 0) {
        if (document.getElementById("pophiveAgeGroup") === null) {
            indicatorHandler.showPophiveAgeGroup();
        } else {
            $("#pophiveDiv").show();
        }
    } else {
        selectDefaultPophiveAgeGroup();
        $("#pophiveDiv").hide();
    }
}

function showNwssFieldsSelect() {
    if (indicatorHandler.getNwssIndicators().length > 0) {
        if (document.getElementById("nwssSource") === null) {
            indicatorHandler.showNwssFields();
        } else {
            $("#nwssDiv").show();
        }
    }
    else {
        $("#nwssPcrTarget").val(null).trigger("change");
        $("#nwssSource").val(null).trigger("change");
        $("#nwssDiv").hide();
    }
}

function showNonDelphiIndicatorSetsLocations() {
    const hasOwnLocationMenus = indicatorHandler.nonCovidcastIndicatorSets.length > 0;
    if (hasOwnLocationMenus) {
        var otherEndpointIndicatorSetsLocationMessage = `<div class="alert alert-info" data-mdb-alert-init role="alert">For indicator set(s): ${indicatorHandler.nonCovidcastIndicatorSets.join(", ")}, instead of the Location(s) menu, please use the Geographic Value menu below.</div>`
        $("#differentLocationNote").html(otherEndpointIndicatorSetsLocationMessage);
    } else {
        $("#differentLocationNote").html("");
    }
    // Each of these shows its control when its indicators are selected and
    // hides it otherwise.
    showNIDSSFluLocationSelect();
    showNIDSSDengueLocationSelect();
    showFlusurvLocationSelect();
    showPophiveAgeGroupSelect();
    showNwssFieldsSelect();
    // The Cosmos age group and the NWSS source sit in this section too, though
    // both use the main Location(s) dropdown.
    if (
        hasOwnLocationMenus ||
        indicatorHandler.getPophiveIndicators().length > 0 ||
        indicatorHandler.getNwssIndicators().length > 0
    ) {
        $("#otherEndpointLocationsWrapper").show();
    } else {
        $("#otherEndpointLocationsWrapper").hide();
    }
}



$("#showSelectedIndicatorsButton").click(async function () {
    showNonDelphiIndicatorSetsLocations();
    updateFillMethodVisibility();
    alertPlaceholder.innerHTML = "";

    const prevSelectedIds = $('#geographic_value').val() || [];


    if ($('#geographic_value').hasClass("select2-hidden-accessible")) {
        $('#geographic_value').select2('destroy').empty();
    }

    // Show loader in #geographic_value
    $('#geographic_value').hide();
    $('#geographic_value').after('<div id="geo-loader" class="lds-ellipsis"><div></div><div></div><div></div><div></div></div>');

    const availableGeos = await getAvailableGeos(checkedIndicatorMembers);
    const locationIds = $("#location_search").select2("data").map((item) => item.id);

    // Remove loader and show Select2
    $('#geo-loader').remove();
    $('#geographic_value').show();

    $("#geographic_value").select2({
        data: availableGeos,
        minimumInputLength: 0,
        maximumSelectionLength: 5,
    });

    const availableGeoIds = availableGeos.flatMap(group => group.children.map(child => child.id));
    const preservedIds = prevSelectedIds.filter(id => availableGeoIds.includes(id));

    let selectedGeos = [...locationIds, ...preservedIds];
    // Default to the nation when nothing was picked in the filter panel or on
    // an earlier open, and the selected indicators offer it.
    if (selectedGeos.length === 0 && availableGeoIds.includes(DEFAULT_LOCATION_ID)) {
        selectedGeos = [DEFAULT_LOCATION_ID];
    }
    $('#geographic_value').val(selectedGeos).trigger('change');
    if (!indicatorHandler.usesMainLocations()) {
        $('#geographic_value').val(null).trigger('change');
        $("#geographic_value").prop("disabled", true);
    } else {
        $("#geographic_value").prop("disabled", false);
    }
    $('#geographic_value').select2("data").forEach(warnIfGeoNotCovered);
});



function submitMode(event) {
    event.preventDefault();
    var geographicValues = $('#geographic_value').select2('data');
    if (indicatorHandler.usesMainLocations()) {
        if (geographicValues.length === 0) {
            appendAlert("Please select at least one geographic location", "warning")
            return;
        }
    }

    if (currentMode === 'epivis') {
        indicatorHandler.plotData();
    } else if (currentMode === 'export') {
        indicatorHandler.exportData();
    } else if (currentMode === 'preview') {
        indicatorHandler.previewData();
    } else if (currentMode === 'create_query_code') {
        indicatorHandler.createQueryCode();
    }
}


function manageApiKeys(isChecked, apiKeyValue) {
    try {
        // Store checkbox state in localStorage
        localStorage.setItem('storeApiKey', String(isChecked));

        if (isChecked) {
            // Set api-key in localStorage from input value
            localStorage.setItem('apiKey', apiKeyValue || '');
        } else {
            // Remove api-key from localStorage when unchecked
            localStorage.removeItem('apiKey');
        }
    } catch (error) {
        console.error('Storage operation failed:', error);
    }
}

// Initialize input and checkbox from localStorage
window.addEventListener('DOMContentLoaded', () => {
    const apiKeyInput = document.getElementById('apiKey');
    const storeApiKeyCheckbox = document.getElementById('storeApiKey');

    // Pre-populate input and checkbox from localStorage
    const storedApiKey = localStorage.getItem('apiKey');
    const storedCheckboxState = localStorage.getItem('storeApiKey');

    if (storedApiKey) {
        apiKeyInput.value = storedApiKey;
    }
    if (storedCheckboxState === 'true') {
        storeApiKeyCheckbox.checked = true;
    }

    // Handle checkbox change
    storeApiKeyCheckbox.addEventListener('change', (event) => {
        const isChecked = event.target.checked;
        const apiKeyValue = apiKeyInput.value;
        manageApiKeys(isChecked, apiKeyValue);
    });

    // Handle input change (save API key if checkbox is already checked)
    apiKeyInput.addEventListener('input', () => {
        if (storeApiKeyCheckbox.checked) {
            const apiKeyValue = apiKeyInput.value;
            manageApiKeys(true, apiKeyValue);
        }
    });
});

window.addEventListener('load', function() {
    const stored = sessionStorage.getItem('checkedIndicatorMembers');
    if (stored) {
        try {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed) && parsed.length > 0) {
                 parsed.forEach(ind => {
                     checkedIndicatorMembers.push(ind);
                     updateSelectedIndicators(
                        ind.data_source,
                        ind.display_name,
                        ind.indicator_set,
                        ind.indicator
                     );
                     
                     if (!MAIN_LOCATION_ENDPOINTS.includes(ind._endpoint) && !indicatorHandler.nonCovidcastIndicatorSets.includes(ind.indicator_set)) {
                        indicatorHandler.nonCovidcastIndicatorSets.push(ind.indicator_set);
                     }
                 });
                 
                 indicatorHandler.indicators = checkedIndicatorMembers;
                 
                 if (checkedIndicatorMembers.length > 0) {
                    $("#showSelectedIndicatorsButton").show();
                    
                    if (typeof expandSelectedRows === 'function') {
                        expandSelectedRows();
                    } else {
                         // Fallback inline implementation if function not found (though we will define it below)
                         if (typeof table !== 'undefined' && typeof relatedIndicators !== 'undefined' && relatedIndicators) {
                            const selectedSetIds = new Set();
                            
                            checkedIndicatorMembers.forEach(member => {
                                const match = relatedIndicators.find(ri => 
                                    ri.source === member.data_source && 
                                    ri.name === member.indicator
                                );
                                if (match) {
                                    selectedSetIds.add(String(match.indicator_set));
                                }
                            });
                            
                            table.rows().every(function() {
                                const tr = $(this.node());
                                const rowId = String(tr.data('id'));
                                
                                if (selectedSetIds.has(rowId)) {
                                    if (!this.child.isShown()) {
                                        tr.find('td.dt-control').trigger('click');
                                    }
                                }
                            });
                         }
                    }
                 }
            }
        } catch (e) {
            console.error("Error restoring selected indicators", e);
        }
        sessionStorage.removeItem('checkedIndicatorMembers');
    }
});

function expandSelectedRows() {
     if (typeof table !== 'undefined' && typeof relatedIndicators !== 'undefined' && relatedIndicators && Array.isArray(relatedIndicators) && typeof checkedIndicatorMembers !== 'undefined') {
        const selectedSetIds = new Set();
        
        checkedIndicatorMembers.forEach(member => {
            const match = relatedIndicators.find(ri => 
                ri.source === member.data_source && 
                ri.name === member.indicator
            );
            if (match) {
                selectedSetIds.add(String(match.indicator_set));
            }
        });
        
        table.rows().every(function() {
            const tr = $(this.node());
            const rowId = String(tr.data('id'));
            
            if (selectedSetIds.has(rowId)) {
                if (!this.child.isShown()) {
                    tr.find('td.dt-control').trigger('click');
                }
            }
        });
     }
}
