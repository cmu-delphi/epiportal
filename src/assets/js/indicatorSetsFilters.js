// Add an event listener to each 'bulk-select' element
let bulkSelectDivs = document.querySelectorAll('.bulk-select');
bulkSelectDivs.forEach(div => {
    div.addEventListener('click', function (event) {
        let form = this.nextElementSibling;
        let checkboxes = form.querySelectorAll('input[type="checkbox"]');

        if (event.target.checked === true) {
            checkboxes.forEach((checkbox) => {
                checkbox.checked = true;
            })
        } else if (event.target.checked === false) {
            checkboxes.forEach((checkbox) => {
                checkbox.checked = false
            });
        }
    });
});

function checkBulkSelect() {
    bulkSelectDivs.forEach((div) => {
        let form = div.nextElementSibling;
        let checkboxes = form.querySelectorAll("input[type='checkbox']");
        let allChecked = Array.from(checkboxes).every(cb => cb.checked);
        if (allChecked) {
            div.querySelector('#select-all').checked = true;
        }
    });
}

checkBulkSelect();

function showLoader() {
    document.getElementById('loaderOverlay').style.display = 'flex';
    document.querySelector('.table-container').classList.add('faded');
}

$("#filterIndicatorSetsForm").find("input[type='checkbox']").on("change", function (e) {
    // Show loader and fade table
    showLoader();
    this.form.submit();
});

$("#location_search").on({
    "change": function (e) {
        // Show loader and fade table
        showLoader();
        this.form.submit();
    }
});