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
    } else {
        currentMode = 'preview';
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

async function checkGeoCoverage(geoType, geoValue) {
    const notCoveredIndicators = [];

    try {
        const result = await $.ajax({
            url: "epidata/covidcast/geo_coverage/",
            type: "GET",
            data: {
                geo: `${geoType}:${geoValue}`,
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

$("#geographic_value").on("select2:select", function (e) {
    var geo = e.params.data;
    checkGeoCoverage(geo.geoType, geo.id).then((notCoveredIndicators) => {
        if (notCoveredIndicators.length > 0) {
            showNotCoveredGeoWarningMessage(notCoveredIndicators, geo.text);
        }
    });
});


$("#showSelectedIndicatorsButton").click(function () {
    alertPlaceholder.innerHTML = "";
    if (!indicatorHandler.checkForCovidcastIndicators()) {
        $('#geographic_value').val(null).trigger('change');
        $("#geographic_value").prop("disabled", true);
    } else {
        $("#geographic_value").prop("disabled", false);
    }
    $('#geographic_value').select2("data").forEach(geo => {
        checkGeoCoverage(geo.geoType, geo.id).then((notCoveredIndicators) => {
            if (notCoveredIndicators.length > 0) {
                showNotCoveredGeoWarningMessage(notCoveredIndicators, geo.text);
            }
        })
    });
    var otherEndpointLocationsWarning = `<div class="alert alert-info" data-mdb-alert-init role="alert">` +
        `   <div>Please, note that some indicator sets may require to select location(s) that is/are different from location(s) above.<br> `
    nonCovidcastIndicatorSets = [...new Set(checkedIndicatorMembers.filter(indicator => indicator["_endpoint"] != "covidcast").map((indicator) => indicator["indicator_set"]))];
    otherEndpointLocationsWarning += `Different location is required for following Indicator Set(s): ${nonCovidcastIndicatorSets.join(", ")}`
    otherEndpointLocationsWarning += `</div></div>`
    if (indicatorHandler.getFluviewIndicators().length > 0) {
        $("#differentLocationNote").html(otherEndpointLocationsWarning)
        if (document.getElementsByName("fluviewRegions").length === 0) {
            indicatorHandler.showFluviewRegions();
        }
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
    } else {
        indicatorHandler.previewData();
    }
}