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
    // Plot checks all time, the other modes the Start/End dates.
    recheckCoverageIfChanged();

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

/* Coverage checks: for each location picked in the main Location(s)
 * dropdown, ask the server whether each selected indicator has data there,
 * the way a submission would get it, and warn about the ones that do not. */

/* The dates a check is limited to. Export, Preview and Create query code use
 * the Start/End dates; Plot always shows the whole series, so null (all
 * time). undefined when the dates make no window (one missing, or start
 * after end): there is nothing sensible to check then. */
function getCoverageWindow() {
    if (currentMode === "epivis") {
        return null;
    }
    const start = document.getElementById("start_date").value;
    const end = document.getElementById("end_date").value;
    if (!start || !end || start > end) {
        return undefined;
    }
    return { start_date: start, end_date: end };
}

function showNotCoveredGeoWarningMessage(labels, geo, window) {
    const period = window
        ? ` for the time period from "${window.start_date}" to "${window.end_date}"`
        : "";
    const warningMessage = labels
        .map(
            (label) =>
                `Indicator "${label}" is not available for Location "${geo.text}"${period}`
        )
        .join(" <br>");
    return appendAlert(warningMessage, "warning");
}

function isFluviewIndicator(indicator) {
    return (
        indicator["_endpoint"] === "fluview" ||
        indicator["_endpoint"] === "fluview_clinical"
    );
}

function getSelectedNwssSources() {
    if (!$("#nwssSource").hasClass("select2-hidden-accessible")) {
        return [];
    }
    return $("#nwssSource").select2("data").map((source) => source.id);
}

/* One entry per kind of source the main dropdown serves. Each picks its
 * indicators and adds what its server check needs beyond the shared geo, fill
 * method and dates, or null when there is nothing to check yet (no NWSS
 * source, no Cosmos age group). skipsInPlot marks the ones Plot leaves an
 * uncovered location out for, via the indicator's notCoveredGeos; NWSS drops
 * empty sewersheds on the server instead. */
const COVERAGE_CHECKS = [
    {
        url: "check_covidcast_geo_coverage/",
        indicators: () =>
            checkedIndicatorMembers.filter((i) => COVIDCAST_ENDPOINTS.includes(i["_endpoint"])),
        params: () => ({}),
        skipsInPlot: true,
    },
    {
        url: "check_fluview_geo_coverage/",
        indicators: () => checkedIndicatorMembers.filter(isFluviewIndicator),
        params: () => ({}),
        skipsInPlot: true,
    },
    {
        url: "check_pophive_geo_coverage/",
        indicators: () => checkedIndicatorMembers.filter((i) => i["_endpoint"] === "pophive"),
        params: () => {
            const ageGroup = getSelectedPophiveAgeGroup();
            return ageGroup.length > 0 ? { age_group: ageGroup[0].id } : null;
        },
    },
    {
        url: "check_nwss_geo_coverage/",
        indicators: () => checkedIndicatorMembers.filter((i) => i["_endpoint"] === "nwss"),
        params: () => {
            const sources = getSelectedNwssSources();
            return sources.length > 0 ? { nwss_sources: sources } : null;
        },
        // One answer per selected NWSS source, so name it.
        label: (indicator, entry) => `${indicator.display_name} (source: ${entry.nwss_source})`,
    },
];

/* Resolves to the {indicator, label, skipsInPlot} entries ``check`` reports
 * no data for at geoId. covered === null means the server could not tell, and
 * a failed request means the same, so neither warns. */
async function runCoverageCheck(check, geoId, window) {
    const indicators = check.indicators();
    const params = indicators.length > 0 ? check.params() : null;
    if (params === null) {
        return [];
    }
    try {
        const result = await $.ajax({
            url: check.url,
            type: "POST",
            dataType: "json",
            contentType: "application/json",
            headers: { "X-CSRFToken": Cookies.get("csrftoken") },
            data: JSON.stringify({
                geo: geoId,
                fill_method: getFillMethod(),
                ...(window || {}),
                ...params,
                indicators: indicators.map((indicator) => ({
                    _endpoint: indicator["_endpoint"],
                    data_source: indicator.data_source,
                    indicator: indicator.indicator,
                    time_type: indicator.time_type,
                })),
            }),
        });
        return result["coverage"]
            .filter((entry) => entry.covered === false)
            .map((entry) => {
                const indicator = indicators.find(
                    (i) => i.data_source === entry.data_source && i.indicator === entry.indicator
                );
                return (
                    indicator && {
                        indicator,
                        label: check.label ? check.label(indicator, entry) : indicator.display_name,
                        skipsInPlot: Boolean(check.skipsInPlot),
                    }
                );
            })
            .filter(Boolean);
    } catch (error) {
        console.error(`Error checking coverage with ${check.url}:`, error);
        return [];
    }
}

function selectedGeos() {
    if (!$("#geographic_value").hasClass("select2-hidden-accessible")) {
        return [];
    }
    return $("#geographic_value").select2("data");
}

/* Bumped by every full re-check, so a check still in flight for the old
 * dates, fill method, NWSS sources or age group is ignored rather than
 * raising a stale warning or skipping a location in Plot. */
let coverageCheckGeneration = 0;

/* Checks one location against every kind of source at once, and raises one
 * warning for it, tagged with the location so removing it can take the
 * warning away. */
function warnIfGeoNotCovered(geo) {
    const window = getCoverageWindow();
    if (window === undefined) {
        return;
    }
    const generation = coverageCheckGeneration;
    Promise.all(COVERAGE_CHECKS.map((check) => runCoverageCheck(check, geo.id, window))).then(
        (results) => {
            if (
                generation !== coverageCheckGeneration ||
                !selectedGeos().some((selected) => selected.id === geo.id)
            ) {
                return;
            }
            const notCovered = results.flat();
            notCovered.forEach(({ indicator, skipsInPlot }) => {
                if (!skipsInPlot) {
                    return;
                }
                indicator["notCoveredGeos"] = indicator["notCoveredGeos"] || [];
                if (!indicator["notCoveredGeos"].includes(geo.id)) {
                    indicator["notCoveredGeos"].push(geo.id);
                }
            });
            if (notCovered.length > 0) {
                const alert = showNotCoveredGeoWarningMessage(
                    notCovered.map((entry) => entry.label),
                    geo,
                    window
                );
                alert.classList.add("coverage-alert");
                alert.dataset.geo = geo.id;
            }
        }
    );
}

/* Everything besides the location an answer depends on. A full re-check only
 * runs when this changes, so a mode switch that keeps the same dates (Export
 * to Preview, say) asks the server nothing. */
function coverageInputs() {
    const window = getCoverageWindow();
    return JSON.stringify([
        window === undefined ? "no window" : window,
        getFillMethod(),
        getSelectedNwssSources(),
        getSelectedPophiveAgeGroup().map((ageGroup) => ageGroup.id),
    ]);
}

let lastCoverageInputs = null;

/* Drops every coverage warning and every location Plot was told to skip, and
 * checks each picked location again. */
function recheckCoverage() {
    coverageCheckGeneration += 1;
    lastCoverageInputs = coverageInputs();
    $("#warning-alert .coverage-alert").remove();
    checkedIndicatorMembers.forEach((indicator) => {
        delete indicator["notCoveredGeos"];
    });
    selectedGeos().forEach(warnIfGeoNotCovered);
}

function recheckCoverageIfChanged() {
    if (coverageInputs() !== lastCoverageInputs) {
        recheckCoverage();
    }
}

$("#geographic_value").on("select2:select", function (e) {
    warnIfGeoNotCovered(e.params.data);
});

$("#geographic_value").on("select2:unselect", function (e) {
    const geoId = e.params.data.id;
    $("#warning-alert .coverage-alert")
        .filter((_, alert) => alert.dataset.geo === geoId)
        .remove();
    checkedIndicatorMembers.forEach((indicator) => {
        if (indicator["notCoveredGeos"]) {
            indicator["notCoveredGeos"] = indicator["notCoveredGeos"].filter(
                (id) => id !== geoId
            );
        }
    });
});

$("#fillMethod").on("change", recheckCoverageIfChanged);
// Both are added to the modal only once their indicators are selected.
$(document).on("change", "#nwssSource, #pophiveAgeGroup", recheckCoverageIfChanged);

// Typing a date fires change per edit; wait for the user to settle.
let coverageDatesTimer = null;
$("#start_date, #end_date").on("change", function () {
    clearTimeout(coverageDatesTimer);
    coverageDatesTimer = setTimeout(recheckCoverageIfChanged, 500);
});

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
    recheckCoverage();
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
