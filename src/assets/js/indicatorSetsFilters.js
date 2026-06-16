// Add an event listener to each 'bulk-select' element
let bulkSelectDivs = document.querySelectorAll('.bulk-select');
bulkSelectDivs.forEach(div => {
    div.addEventListener('click', function (event) {
        // Handle the special case for original data provider grouped checkboxes
        if (event.target.id === 'select-all-original-data-provider') {
            let checkboxesContainer = this.nextElementSibling;
            let checkboxes = checkboxesContainer.querySelectorAll('input.original-data-provider-checkbox');
            
            if (event.target.checked === true) {
                checkboxes.forEach((checkbox) => {
                    checkbox.checked = true;
                })
            } else if (event.target.checked === false) {
                checkboxes.forEach((checkbox) => {
                    checkbox.checked = false
                });
            }
        } else {
            // Original behavior for other bulk-select checkboxes
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
        }
    });
});

function checkBulkSelect() {
    bulkSelectDivs.forEach((div) => {
        let selectAllCheckbox = div.querySelector('#select-all-original-data-provider') || div.querySelector('#select-all');
        if (selectAllCheckbox) {
            let checkboxesContainer = div.nextElementSibling;
            let checkboxes;
            
            if (selectAllCheckbox.id === 'select-all-original-data-provider') {
                checkboxes = checkboxesContainer.querySelectorAll('input.original-data-provider-checkbox');
            } else {
                checkboxes = checkboxesContainer.querySelectorAll("input[type='checkbox']");
            }
            
            let allChecked = Array.from(checkboxes).every(cb => cb.checked);
            if (allChecked && checkboxes.length > 0) {
                selectAllCheckbox.checked = true;
            } else {
                selectAllCheckbox.checked = false;
            }
        }
    });
}

checkBulkSelect();

// Initialize group checkbox states on page load
function initializeGroupCheckboxes() {
    let groupCheckboxes = document.querySelectorAll('input.original-data-provider-group-checkbox');
    groupCheckboxes.forEach((groupCheckbox) => {
        let groupId = groupCheckbox.getAttribute('data-group-id');
        let groupCheckboxesList = document.querySelectorAll(`input.original-data-provider-checkbox[data-group-id="${groupId}"]`);
        let allChecked = Array.from(groupCheckboxesList).every(cb => cb.checked);
        groupCheckbox.checked = allChecked && groupCheckboxesList.length > 0;
    });
}

// Expand/collapse group sublist based on whether any checkboxes are selected
function updateGroupSublistVisibility(groupId) {
    let groupCheckboxes = document.querySelectorAll(`input.original-data-provider-checkbox[data-group-id="${groupId}"]`);
    let anyChecked = Array.from(groupCheckboxes).some(cb => cb.checked);
    
    // Find the collapse element for this group
    let groupElement = document.querySelector(`input.original-data-provider-group-checkbox[data-group-id="${groupId}"]`);
    if (groupElement) {
        let groupContainer = groupElement.closest('.data-provider-group');
        if (groupContainer) {
            let collapseElement = groupContainer.querySelector('.data-provider-sublist.collapse');
            
            if (collapseElement) {
                let button = groupContainer.querySelector(`button[data-mdb-target="#${collapseElement.id}"]`);
                // Use Bootstrap Collapse API to show/hide
                // Check if Bootstrap Collapse is available (MDB uses Bootstrap under the hood)
                if (typeof bootstrap !== 'undefined' && bootstrap.Collapse) {
                    let collapseInstance = bootstrap.Collapse.getInstance(collapseElement);
                    if (!collapseInstance) {
                        collapseInstance = new bootstrap.Collapse(collapseElement, { toggle: false });
                    }
                    
                    if (anyChecked) {
                        collapseInstance.show();
                    } else {
                        collapseInstance.hide();
                    }
                } else {
                    // Fallback: manually toggle classes if Bootstrap API not available
                    // Keep the 'collapse' class, just toggle 'show'
                    if (anyChecked) {
                        collapseElement.classList.add('show');
                    } else {
                        collapseElement.classList.remove('show');
                    }
                    
                    // Update icon manually
                    if (button) {
                        let expandIcon = button.querySelector('.expand-icon');
                        let collapseIcon = button.querySelector('.collapse-icon');
                        if (anyChecked) {
                            if (expandIcon) expandIcon.style.display = 'none';
                            if (collapseIcon) collapseIcon.style.display = 'inline';
                        } else {
                            if (expandIcon) expandIcon.style.display = 'inline';
                            if (collapseIcon) collapseIcon.style.display = 'none';
                        }
                    }
                }
            }
        }
    }
}

// Initialize group sublist visibility on page load
function initializeGroupSublistVisibility() {
    let groupCheckboxes = document.querySelectorAll('input.original-data-provider-group-checkbox');
    groupCheckboxes.forEach((groupCheckbox) => {
        let groupId = groupCheckbox.getAttribute('data-group-id');
        updateGroupSublistVisibility(groupId);
    });
}

// Initialize on page load
initializeGroupCheckboxes();

// Handle collapse/expand icon toggle for group sublists
function setupCollapseIcons() {
    // Get all collapse elements for group sublists
    let collapseElements = document.querySelectorAll('.data-provider-sublist.collapse');
    
    collapseElements.forEach(function(collapseElement) {
        // Find the corresponding expand/collapse button (using MDB data attributes)
        let collapseId = collapseElement.id;
        let button = document.querySelector(`button[data-mdb-target="#${collapseId}"]`);
        
        if (button) {
            // Listen for Bootstrap/MDB collapse events
            collapseElement.addEventListener('show.bs.collapse', function() {
                let expandIcon = button.querySelector('.expand-icon');
                let collapseIcon = button.querySelector('.collapse-icon');
                if (expandIcon) expandIcon.style.display = 'none';
                if (collapseIcon) collapseIcon.style.display = 'inline';
            });
            
            collapseElement.addEventListener('hide.bs.collapse', function() {
                let expandIcon = button.querySelector('.expand-icon');
                let collapseIcon = button.querySelector('.collapse-icon');
                if (expandIcon) expandIcon.style.display = 'inline';
                if (collapseIcon) collapseIcon.style.display = 'none';
            });
        }
    });
}

// Setup collapse icons when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        setupCollapseIcons();
        initializeGroupSublistVisibility();
    });
} else {
    // DOM is already ready
    setupCollapseIcons();
    initializeGroupSublistVisibility();
}

// Debounce function to delay execution
function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            func.apply(context, args);
        }, wait);
    };
}

// Function to handle form submission with UI feedback
function submitFilterForm(form) {
    persistCheckedIndicators();
    showLoader();
    form.submit();
}

// Create debounced submission function
const debouncedSubmit = debounce(function(form) {
    submitFilterForm(form);
}, 2000);

// Handle group checkbox clicks (e.g., "U.S. States")
document.addEventListener('change', function(event) {
    if (event.target.classList.contains('original-data-provider-group-checkbox')) {
        let groupId = event.target.getAttribute('data-group-id');
        let groupCheckboxes = document.querySelectorAll(`input.original-data-provider-checkbox[data-group-id="${groupId}"]`);
        
        // Set all group checkboxes without triggering their change events
        groupCheckboxes.forEach((checkbox) => {
            checkbox.checked = event.target.checked;
        });
        
        // Update sublist visibility based on whether any are selected
        updateGroupSublistVisibility(groupId);
        
        // Update "Select all" checkbox state
        let checkboxesContainer = event.target.closest('.original-data-provider-checkboxes');
        if (checkboxesContainer) {
            let selectAllDiv = checkboxesContainer.previousElementSibling;
            if (selectAllDiv && selectAllDiv.classList.contains('bulk-select')) {
                let selectAllCheckbox = selectAllDiv.querySelector('#select-all-original-data-provider');
                let allCheckboxes = checkboxesContainer.querySelectorAll('input.original-data-provider-checkbox');
                let allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = allChecked && allCheckboxes.length > 0;
                }
            }
        }
        
        // Trigger debounced form submission
        if (event.target.form) {
            debouncedSubmit(event.target.form);
        }
    }
});

// Update group checkbox state when individual checkboxes change
document.addEventListener('change', function(event) {
    if (event.target.classList.contains('original-data-provider-checkbox')) {
        let groupId = event.target.getAttribute('data-group-id');
        
        // Update group checkbox if this checkbox belongs to a group
        if (groupId) {
            let groupCheckbox = document.querySelector(`input.original-data-provider-group-checkbox[data-group-id="${groupId}"]`);
            if (groupCheckbox) {
                let groupCheckboxes = document.querySelectorAll(`input.original-data-provider-checkbox[data-group-id="${groupId}"]`);
                let allChecked = Array.from(groupCheckboxes).every(cb => cb.checked);
                let someChecked = Array.from(groupCheckboxes).some(cb => cb.checked);
                
                // Set group checkbox to checked if all are checked, unchecked if none are checked
                // For partial selection, we'll leave it unchecked (or you could use indeterminate state)
                groupCheckbox.checked = allChecked && groupCheckboxes.length > 0;
                
                // Update sublist visibility based on whether any are selected
                updateGroupSublistVisibility(groupId);
            }
        }
        
        // Update "Select all" checkbox
        let checkboxesContainer = event.target.closest('.original-data-provider-checkboxes');
        if (checkboxesContainer) {
            let selectAllDiv = checkboxesContainer.previousElementSibling;
            if (selectAllDiv && selectAllDiv.classList.contains('bulk-select')) {
                let selectAllCheckbox = selectAllDiv.querySelector('#select-all-original-data-provider');
                let allCheckboxes = checkboxesContainer.querySelectorAll('input.original-data-provider-checkbox');
                let allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = allChecked && allCheckboxes.length > 0;
                }
            }
        }
    }
});

function persistCheckedIndicators() {
    if (typeof checkedIndicatorMembers !== 'undefined') {
        sessionStorage.setItem('checkedIndicatorMembers', JSON.stringify(checkedIndicatorMembers));
    }
}

function showLoader() {
    document.getElementById('loaderOverlay').style.display = 'flex';
    document.querySelector('.table-container').classList.add('faded');
}

$("#filterIndicatorSetsForm").find("input[type='checkbox']").on("change", function (e) {
    // Skip if it's a group checkbox (handled by separate event listener)
    if (this.classList.contains('original-data-provider-group-checkbox')) {
        return;
    }
    
    // Trigger debounced submission
    debouncedSubmit(this.form);
});

$("#location_search").on({
    "change": function (e) {
        // Trigger debounced submission
        debouncedSubmit(this.form);
    },
    // Also debounce on keyup for better UX if needed, or just keep change
    "keyup": function(e) {
         if (e.key === 'Enter') {
            debouncedSubmit(this.form);
         }
    }
});

// Mobile filter toggle
$('#mobile-filter-toggle').on('click', function() {
    $('#filterIndicatorSetsForm').addClass('show');
    $('#mobile-filter-overlay').addClass('show');
    $('body').css('overflow', 'hidden');
});

// Close filter menu
$('#mobile-filter-close, #mobile-filter-overlay').on('click', function() {
    $('#filterIndicatorSetsForm').removeClass('show');
    $('#mobile-filter-overlay').removeClass('show');
    $('body').css('overflow', '');
});