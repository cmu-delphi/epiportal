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
            member_short_name: element.dataset.memberShortName,
        });
        updateSelectedIndicators(
            element.dataset.datasource,
            element.dataset.indicatorDisplayname,
            element.dataset.indicatorSet,
            element.dataset.indicator
        );
    } else {
        checkedIndicatorMembers = checkedIndicatorMembers.filter(
            (indicator) => indicator.indicator !== element.dataset.indicator
        );
        document
            .getElementById(
                `${element.dataset.datasource}_${element.dataset.indicator}`
            )
            .remove();
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
};

var currentMode = "epivis";

function handleModeChange(mode) {
    $('#modeSubmitResult').html('');

    var choose_dates = document.getElementsByName('choose_date');

    if (mode === 'epivis') {
        currentMode = 'epivis';
        choose_dates.forEach((el) => {
            el.style.display = 'none';
        });
        $('#modeSubmitResult').html('');
    } else if (mode === 'export') {
        currentMode = 'export';
        choose_dates.forEach((el) => {
            el.style.display = 'flex';
        });
        $('#modeSubmitResult').html('');
    } else if (mode === 'preview') {
        currentMode = 'preview';
        choose_dates.forEach((el) => {
            el.style.display = 'flex';
        });
    } else if (mode === 'create_query_code') {
        currentMode = 'create_query_code'
        choose_dates.forEach((el) => {
            el.style.display = 'flex';
        });
    }
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
            warningMessage += `Indicator ${indicator.display_name} is not available for Location ${geoValue} <br>`;
        } else {
            var startDate = document.getElementById("start_date").value;
            var endDate = document.getElementById("end_date").value;
            warningMessage += `Indicator ${indicator.display_name} is not available for Location ${geoValue} for the time period from ${startDate} to ${endDate} <br>`;
        }
    });
    appendAlert(warningMessage, "warning");
}

async function checkGeoCoverage(geoValue) {
    const notCoveredIndicators = [];

    try {
        const result = await $.ajax({
            url: "epidata/covidcast/geo_coverage/",
            type: "GET",
            data: {
                geo: geoValue,
            },
        });

        checkedIndicatorMembers
            .filter((indicator) => indicator["_endpoint"] === "covidcast")
            .forEach((indicator) => {
                const covered = result["epidata"].some(
                    (e) =>
                        e.source === indicator.data_source &&
                        e.signal === indicator.indicator
                );
                if (!covered) {
                    notCoveredIndicators.push(indicator);
                }
            });

        return notCoveredIndicators;
    } catch (error) {
        console.error("Error fetching geo coverage:", error);
        return notCoveredIndicators;
    }
}

function getAvailableGeos(indicators) {
    var availableGeos = null;

    const csrftoken = Cookies.get("csrftoken");

    const submitData = {
        indicators: indicators
    }

    $.ajax({
        url: "get_available_geos/",
        type: "POST",
        async: false, // Synchronous request to ensure availableGeos is populated before returning
        dataType: "json",
        contentType: "application/json",
        headers: { "X-CSRFToken": csrftoken },
        data: JSON.stringify(submitData),
    }).done(function (data) {
        availableGeos = data.geographic_granularities;
    });
    return availableGeos;
}

$("#geographic_value").on("select2:select", function (e) {
    var geo = e.params.data;
    checkGeoCoverage(geo.id).then((notCoveredIndicators) => {
        if (notCoveredIndicators.length > 0) {
            showNotCoveredGeoWarningMessage(notCoveredIndicators, geo.text);
        }
    });
});


$("#showSelectedIndicatorsButton").click(function () {
    alertPlaceholder.innerHTML = "";
    const availableGeos = getAvailableGeos(checkedIndicatorMembers);
    const locationIds = $("#location_search").select2("data").map((item) => item.id);
    $("#geographic_value").select2({
        data: availableGeos,
        minimumInputLength: 0,
        maximumSelectionLength: 5,
    });
    $('#geographic_value').val(locationIds).trigger('change');
    if (!indicatorHandler.checkForCovidcastIndicators()) {
        $('#geographic_value').val(null).trigger('change');
        $("#geographic_value").prop("disabled", true);
    } else {
        $("#geographic_value").prop("disabled", false);
    }
    $('#geographic_value').select2("data").forEach(geo => {
        checkGeoCoverage(geo.id).then((notCoveredIndicators) => {
            if (notCoveredIndicators.length > 0) {
                showNotCoveredGeoWarningMessage(notCoveredIndicators, geo.text);
            }
        })
    });
    nonCovidcastIndicatorSets = [...new Set(checkedIndicatorMembers.filter(indicator => indicator["_endpoint"] != "covidcast").map((indicator) => indicator["indicator_set"]))];
    var otherEndpointLocationsWarning = `<div class="alert alert-info" data-mdb-alert-init role="alert">`
    otherEndpointLocationsWarning += `For Indicator Set(s): ${nonCovidcastIndicatorSets.join(", ")}, please use the Location menu below:`
    otherEndpointLocationsWarning += `</div>`
    if (indicatorHandler.getFluviewIndicators().length > 0) {
        $("#differentLocationNote").html(otherEndpointLocationsWarning)
        if (document.getElementsByName("fluviewRegions").length === 0) {
            indicatorHandler.showFluviewRegions();
        } else {
            // IF code goes here, we assume that otherEndpointLocationWarning & fluviewRegion selector is already on the page, but is just hidden, so we should just show it.
            $("#otherEndpointLocationsWrapper").show();
        }
    } else {
        // If there are no non-covidcast indicators selected (only fluview is supported for now) then hide otherEndpointLocationWarning & fliviewRegions selector.
        $("#fluviewRegions").val(null).trigger("change");
        $("#otherEndpointLocationsWrapper").hide();
    }
});



function submitMode(event) {
    event.preventDefault();
    var geographicValues = $('#geographic_value').select2('data');
    if (indicatorHandler.checkForCovidcastIndicators()) {
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