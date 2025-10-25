/**
 * Alternative Dashboard JavaScript
 * Simple dashboard with efficient rendering and modal functionality
 */

class AlterDashboard {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadInitialData();
    }

    loadInitialData() {
        // All data is already loaded in the template
        this.renderTable(window.djangoIndicators || []);
    }


    setupEventListeners() {
        // No event listeners needed for filtering - handled by Django
    }


    renderTable(indicators) {
        const tbody = document.getElementById('indicatorsTableBody');
        if (!tbody) return;

        if (indicators.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-muted py-4">
                        No indicators found matching your criteria.
                    </td>
                </tr>
            `;
            return;
        }

        // Use DocumentFragment for better performance
        const fragment = document.createDocumentFragment();
        
        indicators.forEach(indicator => {
            const row = document.createElement('tr');
            row.className = 'fade-in';
            row.innerHTML = `
                <td><strong>${this.escapeHtml(indicator.name)}</strong></td>
                <td>${this.renderPathogens(indicator.pathogens)}</td>
                <td>${this.escapeHtml(indicator.description || '')}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="dashboard.viewIndicator(${indicator.id})">
                        View Details
                    </button>
                </td>
            `;
            fragment.appendChild(row);
        });
        
        tbody.innerHTML = '';
        tbody.appendChild(fragment);
    }

    renderPathogens(pathogens) {
        if (!pathogens || pathogens.length === 0) {
            return '<span class="text-muted">None</span>';
        }
        
        return pathogens.map(pathogen => 
            `<span class="badge bg-secondary me-2 mb-1">${this.escapeHtml(pathogen)}</span>`
        ).join('');
    }


    viewIndicator(indicatorId) {
        // Find indicator in the original data
        const allIndicators = window.djangoIndicators || [];
        const indicator = allIndicators.find(i => i.id === indicatorId);
        
        if (!indicator) {
            console.error('Indicator not found:', indicatorId);
            return;
        }

        // Create detailed view modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered modal-lg modal-fullscreen-sm-down">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title text-truncate pe-3">${this.escapeHtml(indicator.name)}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row g-3">
                            <div class="col-12 col-lg-6">
                                <div class="card h-100">
                                    <div class="card-header">
                                        <h6 class="card-title mb-0">Basic Information</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="mb-3">
                                            <strong class="d-block text-muted small">Data Source</strong>
                                            <span class="badge bg-primary">${this.escapeHtml(indicator.source ? indicator.source.name : 'Unknown')}</span>
                                        </div>
                                        <div class="mb-3">
                                            <strong class="d-block text-muted small">Geographic Scope</strong>
                                            <span>${this.escapeHtml(indicator.geographic_scope ? indicator.geographic_scope.name : 'Unknown')}</span>
                                        </div>
                                        <div class="mb-3">
                                            <strong class="d-block text-muted small">Pathogens</strong>
                                            <div class="mt-1">${this.renderPathogens(indicator.pathogens)}</div>
                                        </div>
                                        <div class="mb-0">
                                            <strong class="d-block text-muted small">Last Updated</strong>
                                            <span class="badge bg-success">${this.escapeHtml(indicator.temporal_scope_end || 'Active')}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-12 col-lg-6">
                                <div class="card h-100">
                                    <div class="card-header">
                                        <h6 class="card-title mb-0">Description</h6>
                                    </div>
                                    <div class="card-body">
                                        <p class="mb-0 text-break">${this.escapeHtml(indicator.description || 'No description available')}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global functions for template compatibility
function viewIndicator(indicatorId) {
    dashboard.viewIndicator(indicatorId);
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new AlterDashboard();
});

// Export for use in other scripts
window.AlterDashboard = AlterDashboard;