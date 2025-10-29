/**
 * Alternative Dashboard JavaScript
 * Enhanced dashboard with EpiVis-like features: interactive controls, normalization, and advanced chart options
 */

class AlterDashboard {
    constructor() {
        this.originalDatasets = [];
        this.normalized = false;
        this.init();
    }

    init() {
        this.initChart();
        this.initControls();
        this.initLegendInteractivity();
    }

    initChart() {
        const ctx = document.getElementById('indicatorChart');
        if (!ctx) return;

        // Sample data for the chart - similar to Delphi EpiVis
        const labels = this.generateDateLabels(30);
        const datasets = [
            {
                label: 'Claims hosp (COVID:down-adjusted)',
                data: this.generateSampleData(30, 100),
                borderColor: '#0076aa',
                backgroundColor: 'rgba(0, 118, 170, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Claims hosp (COVID:)',
                data: this.generateSampleData(30, 120),
                borderColor: '#5489a2',
                backgroundColor: 'rgba(84, 137, 162, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Claims OV (COVID-related:down-adjusted)',
                data: this.generateSampleData(30, 90),
                borderColor: '#de1dbb',
                backgroundColor: 'rgba(222, 29, 187, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Claims OV (COVID-related:)',
                data: this.generateSampleData(30, 110),
                borderColor: '#a67c83',
                backgroundColor: 'rgba(166, 124, 131, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'ILI (Influenza-like Illness)',
                data: this.generateSampleData(30, 85),
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'RSV Hospitalizations',
                data: this.generateSampleData(30, 75),
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Emergency Department Visits (COVID)',
                data: this.generateSampleData(30, 95),
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Test Positivity Rate (COVID)',
                data: this.generateSampleData(30, 65),
                borderColor: '#06b6d4',
                backgroundColor: 'rgba(6, 182, 212, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Wastewater COVID Signal',
                data: this.generateSampleData(30, 105),
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Influenza Hospitalizations',
                data: this.generateSampleData(30, 80),
                borderColor: '#f97316',
                backgroundColor: 'rgba(249, 115, 22, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'RSV Emergency Visits',
                data: this.generateSampleData(30, 70),
                borderColor: '#ec4899',
                backgroundColor: 'rgba(236, 72, 153, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Influenza Test Positivity',
                data: this.generateSampleData(30, 55),
                borderColor: '#14b8a6',
                backgroundColor: 'rgba(20, 184, 166, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'Death Certificate Data (COVID)',
                data: this.generateSampleData(30, 45),
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            },
            {
                label: 'NCHS Mortality (COVID)',
                data: this.generateSampleData(30, 50),
                borderColor: '#84cc16',
                backgroundColor: 'rgba(132, 204, 22, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            }
        ];

        // Store original datasets for normalization/de-normalization
        this.originalDatasets = datasets.map(d => ({
            ...d,
            originalData: [...d.data]
        }));

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        onClick: (e, legendItem, legend) => {
                            // Enhanced legend click - toggle dataset visibility
                            const index = legendItem.datasetIndex;
                            const chart = legend.chart;
                            const meta = chart.getDatasetMeta(index);
                            meta.hidden = meta.hidden === null ? !chart.data.datasets[index].hidden : null;
                            chart.update();
                        },
                        onHover: (e, legendItem) => {
                            if (e.native && e.native.target) {
                                e.native.target.style.cursor = 'pointer';
                            }
                        },
                        onLeave: (e, legendItem) => {
                            if (e.native && e.native.target) {
                                e.native.target.style.cursor = 'default';
                            }
                        },
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: {
                                size: 12,
                                weight: '500'
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.85)',
                        padding: 14,
                        titleFont: {
                            size: 14,
                            weight: '600'
                        },
                        bodyFont: {
                            size: 12,
                            weight: '400'
                        },
                        displayColors: true,
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        filter: function(tooltipItem) {
                            // Only show tooltips for visible datasets
                            return !tooltipItem.hidden;
                        },
                        callbacks: {
                            title: function(context) {
                                return 'Date: ' + context[0].label;
                            },
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;
                                const formattedValue = dashboard && dashboard.normalized 
                                    ? value.toFixed(1) + '%' 
                                    : value.toFixed(2);
                                return label + ': ' + formattedValue;
                            },
                            afterBody: function(context) {
                                if (dashboard && dashboard.normalized) {
                                    return 'Values normalized to 0-100% range';
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            display: false,
                            drawBorder: false
                        },
                        ticks: {
                            font: {
                                size: 11
                            },
                            color: '#64748b',
                            maxTicksLimit: 8
                        }
                    },
                    y: {
                        display: true,
                        beginAtZero: this.normalized,
                        grid: {
                            color: 'rgba(226, 232, 240, 0.8)',
                            drawBorder: false
                        },
                        ticks: {
                            font: {
                                size: 11
                            },
                            color: '#64748b',
                            callback: (value) => {
                                return value.toFixed(1);
                            }
                        },
                        title: {
                            display: true,
                            text: 'Value',
                            font: {
                                size: 12,
                                weight: '500'
                            },
                            color: '#64748b',
                            padding: {
                                top: 5,
                                bottom: 5
                            }
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                },
                animation: {
                    duration: 1000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }

    generateDateLabels(days) {
        const labels = [];
        const today = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            labels.push(`${month}/${day}`);
        }
        return labels;
    }

    generateSampleData(count, startValue = 100) {
        const data = [];
        let baseValue = startValue;
        for (let i = 0; i < count; i++) {
            // Generate realistic-looking data with trend and noise
            const trend = Math.sin(i / count * Math.PI * 2) * 10;
            const noise = (Math.random() - 0.5) * 15;
            baseValue += trend / count + noise;
            data.push(Math.max(50, Math.round(baseValue)));
        }
        return data;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Normalize all datasets to 0-100% range for better comparison
    // Data Normalization
    // Normalizes each dataset to 0–100% based on its min/max
    // Updates y-axis labels to show percentages (%)
    // Updates axis title to "Normalized Value (%)"
    // Button toggles to "Restore" when normalized
    normalizeData() {
        if (!this.chart) return;
        
        const datasets = this.chart.data.datasets;
        datasets.forEach((dataset, index) => {
            const originalData = this.originalDatasets[index].originalData;
            const min = Math.min(...originalData);
            const max = Math.max(...originalData);
            const range = max - min || 1; // Avoid division by zero
            
            dataset.data = originalData.map(value => {
                return ((value - min) / range) * 100;
            });
        });
        
        this.normalized = true;
        // Update y-axis to show percentage
        this.chart.options.scales.y.beginAtZero = true;
        this.chart.options.scales.y.ticks.callback = (value) => {
            return value.toFixed(0) + '%';
        };
        if (this.chart.options.scales.y.title) {
            this.chart.options.scales.y.title.text = 'Normalized Value (%)';
        }
        this.chart.update();
        this.updateNormalizeButton();
    }

    // Restore original data values
    restoreData() {
        if (!this.chart) return;
        
        const datasets = this.chart.data.datasets;
        datasets.forEach((dataset, index) => {
            dataset.data = [...this.originalDatasets[index].originalData];
        });
        
        this.normalized = false;
        // Restore y-axis to original
        this.chart.options.scales.y.beginAtZero = false;
        this.chart.options.scales.y.ticks.callback = (value) => {
            return value.toFixed(1);
        };
        if (this.chart.options.scales.y.title) {
            this.chart.options.scales.y.title.text = 'Value';
        }
        this.chart.update();
        this.updateNormalizeButton();
    }

    // Toggle normalization
    toggleNormalization() {
        if (this.normalized) {
            this.restoreData();
        } else {
            this.normalizeData();
        }
    }

    // Reset all datasets to visible
    showAllDatasets() {
        if (!this.chart) return;
        
        const datasets = this.chart.data.datasets;
        datasets.forEach((dataset, index) => {
            const meta = this.chart.getDatasetMeta(index);
            meta.hidden = false;
        });
        
        this.chart.update();
    }

    // Initialize chart controls
    initControls() {
        // Create controls container if it doesn't exist
        let controlsContainer = document.getElementById('chartControls');
        if (!controlsContainer) {
            const chartSection = document.querySelector('.chart-section');
            if (chartSection) {
                const cardHeader = chartSection.querySelector('.card-header');
                if (cardHeader) {
                    const controls = document.createElement('div');
                    controls.id = 'chartControls';
                    controls.className = 'chart-controls';
                    controls.innerHTML = `
                        <div class="controls-group">
                            <button id="normalizeBtn" class="btn-control" title="Normalize data to 0-100% range">
                                <span class="control-icon">📊</span>
                                <span class="control-text">Normalize</span>
                            </button>
                            <button id="showAllBtn" class="btn-control" title="Show all indicators">
                                <span class="control-icon">👁️</span>
                                <span class="control-text">Show All</span>
                            </button>
                        </div>
                    `;
                    cardHeader.appendChild(controls);
                }
            }
        }

        // Attach event listeners
        const normalizeBtn = document.getElementById('normalizeBtn');
        if (normalizeBtn) {
            normalizeBtn.addEventListener('click', () => this.toggleNormalization());
        }

        const showAllBtn = document.getElementById('showAllBtn');
        if (showAllBtn) {
            showAllBtn.addEventListener('click', () => this.showAllDatasets());
        }
    }

    // Initialize enhanced legend interactivity
    initLegendInteractivity() {
        // Legend interactivity is handled in Chart.js config
        // Additional styling can be added here if needed
    }

    // Update normalize button state
    updateNormalizeButton() {
        const btn = document.getElementById('normalizeBtn');
        if (btn) {
            if (this.normalized) {
                btn.classList.add('active');
                btn.querySelector('.control-text').textContent = 'Restore';
            } else {
                btn.classList.remove('active');
                btn.querySelector('.control-text').textContent = 'Normalize';
            }
        }
    }

    // Update legend state display
    updateLegendState() {
        // Can add custom legend state management here
    }
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new AlterDashboard();
});

// Handle pathogen change - reset geography select and submit form
function handlePathogenChange() {
    const geographySelect = document.getElementById('geographySelect');
    if (geographySelect) {
        geographySelect.value = '';
    }
    // Show loader before submitting form
    const loader = document.getElementById('pageLoader');
    if (loader) {
        loader.style.display = 'flex';
    }
    document.getElementById('filterForm').submit();
}

// Export for use in other scripts
window.AlterDashboard = AlterDashboard;