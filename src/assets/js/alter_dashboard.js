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

        // Require backend-provided chartData
        if (!window.chartData || !Array.isArray(window.chartData.labels) || !Array.isArray(window.chartData.datasets)) {
            return;
        }
        const palette = ['#2563eb','#16a34a','#dc2626','#a855f7','#f59e0b','#0ea5e9','#ef4444','#10b981'];
        const labels = Array.isArray(window.chartData.labels)
            ? window.chartData.labels.map(l => String(l))
            : [];
        const sanitizeValue = (v) => {
            if (v === null || v === undefined) return null;
            if (typeof v === 'number') return Number.isFinite(v) ? v : null;
            if (typeof v === 'string') {
                const s = v.trim().toLowerCase();
                if (s === '' || s === 'none' || s === 'null' || s === 'nan') return null;
                const num = parseFloat(s);
                return Number.isFinite(num) ? num : null;
            }
            // For booleans, objects, arrays, etc.
            return null;
        };
        const sanitizeColor = (c, fallback) => {
            if (c === null || c === undefined) return fallback;
            if (typeof c === 'string') {
                const s = c.trim().toLowerCase();
                if (s === 'none' || s === 'null' || s === '') return fallback;
            }
            return c;
        };
        const alignData = (arr, targetLen) => {
            const a = Array.isArray(arr) ? arr : [];
            if (a.length > targetLen) return a.slice(0, targetLen);
            if (a.length < targetLen) return a.concat(Array(targetLen - a.length).fill(null));
            return a;
        };
        const datasets = window.chartData.datasets.map((ds, i) => ({
            label: (ds.label === null || ds.label === undefined) ? '' : String(ds.label),
            data: alignData(Array.isArray(ds.data) ? ds.data.map(sanitizeValue) : [], labels.length),
            borderColor: sanitizeColor(ds.borderColor, palette[i % palette.length]),
            backgroundColor: sanitizeColor(ds.backgroundColor, (palette[i % palette.length] + '33')),
            borderWidth: 2,
            fill: true,
            tension: 0.2,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: false,
        }));

        // Store original datasets for normalization/de-normalization
        this.originalDatasets = datasets.map(d => ({
            ...d,
            originalData: Array.isArray(d.data) ? [...d.data] : []
        }));

		// Ensure an external legend container exists (scrollable) in the card header (always visible)
		let legendContainer = document.getElementById('chartHtmlLegend');
		if (!legendContainer) {
			const section = document.querySelector('.chart-section');
			const header = section ? section.querySelector('.card-header') : null;
			legendContainer = document.createElement('div');
			legendContainer.id = 'chartHtmlLegend';
			legendContainer.style.maxHeight = '260px';
			legendContainer.style.overflow = 'auto';
			legendContainer.style.marginTop = '8px';
			legendContainer.style.display = 'flex';
			legendContainer.style.flexWrap = 'wrap';
			legendContainer.style.gap = '8px';
			legendContainer.style.alignItems = 'center';
			legendContainer.style.fontSize = '11px';
			legendContainer.style.paddingBottom = '8px';
			if (header) header.appendChild(legendContainer);
		}

		// Custom HTML legend plugin (renders all items, clickable to toggle)
		const htmlLegendPlugin = {
			id: 'htmlLegend',
			afterUpdate(chart, args, options) {
				const container = document.getElementById(options.containerID);
				if (!container) return;
				// Clear
				while (container.firstChild) {
					container.firstChild.remove();
				}
				const list = document.createElement('div');
				list.style.display = 'flex';
				list.style.flexWrap = 'wrap';
				list.style.gap = '8px';
				const items = chart.options.plugins.legend.labels.generateLabels(chart);
				items.forEach(item => {
					const button = document.createElement('button');
					button.type = 'button';
					button.style.display = 'inline-flex';
					button.style.alignItems = 'center';
					button.style.gap = '6px';
					button.style.border = '1px solid #e2e8f0';
					button.style.borderRadius = '12px';
					button.style.padding = '4px 8px';
					button.style.background = '#fff';
					button.style.cursor = 'pointer';
					button.style.fontSize = '11px';
					button.style.lineHeight = '1.2';
					button.style.maxWidth = '100%';
					button.title = item.text;
					// Color dot
					const box = document.createElement('span');
					box.style.width = '10px';
					box.style.height = '10px';
					box.style.display = 'inline-block';
					box.style.borderRadius = '50%';
					box.style.background = item.fillStyle;
					box.style.border = '1px solid rgba(0,0,0,0.1)';
					// Label
					const text = document.createElement('span');
					text.textContent = item.text;
					text.style.whiteSpace = 'nowrap';
					text.style.overflow = 'hidden';
					text.style.textOverflow = 'ellipsis';
					if (item.hidden) {
						button.style.opacity = '0.5';
					}
					button.onclick = () => {
						const { type } = chart.config;
						if (type === 'pie' || type === 'doughnut') {
							chart.toggleDataVisibility(item.index);
						} else {
							chart.setDatasetVisibility(item.datasetIndex, !chart.isDatasetVisible(item.datasetIndex));
						}
						chart.update();
					};
					button.appendChild(box);
					button.appendChild(text);
					list.appendChild(button);
				});
				container.appendChild(list);
			}
		};

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
					legend: { display: false },
					htmlLegend: { containerID: 'chartHtmlLegend' },
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
                                if (value === null || value === undefined || Number.isNaN(value)) {
                                    return label + ': n/a';
                                }
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
			},
			plugins: [htmlLegendPlugin]
		});
        
        // Hide loader after chart is initialized
        const loader = document.getElementById('pageLoader');
        if (loader) {
            loader.style.display = 'none';
        }
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
            const numericValues = originalData.filter(v => v !== null && v !== undefined && !Number.isNaN(v));
            const min = numericValues.length ? Math.min(...numericValues) : 0;
            const max = numericValues.length ? Math.max(...numericValues) : 1;
            const range = (max - min) || 1; // Avoid division by zero
            
            dataset.data = originalData.map(value => {
                if (value === null || value === undefined || Number.isNaN(value)) return null;
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

// Handle geography change - show loader and submit form
function handleGeographyChange() {
    // Show loader before submitting form
    const loader = document.getElementById('pageLoader');
    if (loader) {
        loader.style.display = 'flex';
    }
    document.getElementById('filterForm').submit();
}

// Export for use in other scripts
window.AlterDashboard = AlterDashboard;