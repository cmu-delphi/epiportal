/**
 * Alternative Dashboard JavaScript
 * Enhanced dashboard with EpiVis-like features: interactive controls, normalization, and advanced chart options
 */

class AlterDashboard {
    constructor() {
        this.originalDatasets = [];
        this.normalized = true; // Data is always normalized from backend
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
            tension: 0,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: false,
        }));

        // Store datasets (already normalized from backend)
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
                                // Data is always normalized from backend
                                const formattedValue = value.toFixed(1) + '%';
                                return label + ': ' + formattedValue;
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
                        beginAtZero: true, // Always normalized to 0-100%
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
                                return value.toFixed(0) + '%';
                            }
                        },
                        title: {
                            display: true,
                            text: 'Scaled value (%)',
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

    // Update legend state display
    updateLegendState() {
        // Can add custom legend state management here
    }
}

// Typing animation for pathogen select
function initPathogenTypingAnimation() {
    const typingElement = document.getElementById('pathogenTypingAnimation');
    const selectElement = document.getElementById('pathogenSelect');
    
    if (!typingElement || !selectElement) {
        console.log('Typing animation: Missing elements');
        return;
    }
    
    if (!window.pathogenNames || window.pathogenNames.length === 0) {
        console.log('Typing animation: No pathogen names available');
        return;
    }
    
    console.log('Typing animation: Initializing with', window.pathogenNames.length, 'pathogens');
    
    let currentPathogenIndex = 0;
    let currentText = '';
    let isDeleting = false;
    let typingSpeed = 100; // milliseconds per character
    let deleteSpeed = 50;
    let pauseBeforeDelete = 2000; // pause before deleting
    let pauseAfterDelete = 500; // pause before typing next
    
    let timeoutId = null;
    
    function typeCharacter() {
        const currentPathogen = window.pathogenNames[currentPathogenIndex];
        
        // Hide animation if pathogen is selected
        if (selectElement.value && selectElement.value !== '') {
            typingElement.style.display = 'none';
            if (timeoutId) clearTimeout(timeoutId);
            return;
        }
        
        // Show animation if no pathogen is selected
        typingElement.style.display = 'block';
        
        if (!isDeleting && currentText.length < currentPathogen.length) {
            // Typing forward
            currentText = currentPathogen.substring(0, currentText.length + 1);
            typingElement.textContent = currentText + '|';
            timeoutId = setTimeout(typeCharacter, typingSpeed);
        } else if (!isDeleting && currentText.length === currentPathogen.length) {
            // Pause before deleting
            typingElement.textContent = currentText;
            timeoutId = setTimeout(() => {
                isDeleting = true;
                timeoutId = setTimeout(typeCharacter, deleteSpeed);
            }, pauseBeforeDelete);
        } else if (isDeleting && currentText.length > 0) {
            // Deleting
            currentText = currentText.substring(0, currentText.length - 1);
            typingElement.textContent = currentText + '|';
            timeoutId = setTimeout(typeCharacter, deleteSpeed);
        } else if (isDeleting && currentText.length === 0) {
            // Move to next pathogen
            isDeleting = false;
            currentPathogenIndex = (currentPathogenIndex + 1) % window.pathogenNames.length;
            typingElement.textContent = '|';
            timeoutId = setTimeout(typeCharacter, pauseAfterDelete);
        }
    }
    
    // Check if pathogen is selected and update visibility
    function checkSelection() {
        if (selectElement.value && selectElement.value !== '') {
            typingElement.style.display = 'none';
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
        } else {
            // Only show and start animation if not focused
            if (document.activeElement !== selectElement) {
                typingElement.style.display = 'block';
                if (!timeoutId) {
                    // Reset animation state when restarting
                    currentText = '';
                    isDeleting = false;
                    typingElement.textContent = '|';
                    typeCharacter();
                }
            }
        }
    }
    
    // Initial check
    checkSelection();
    
    // Listen for changes
    selectElement.addEventListener('change', checkSelection);
    selectElement.addEventListener('focus', () => {
        // Always hide when focused
        typingElement.style.display = 'none';
        if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutId = null;
        }
    });
    selectElement.addEventListener('blur', () => {
        // Small delay to ensure focus is lost
        setTimeout(() => {
            checkSelection();
        }, 100);
    });
    
    // Start typing animation after a short delay
    setTimeout(() => {
        if (!selectElement.value || selectElement.value === '') {
            if (document.activeElement !== selectElement) {
                typingElement.style.display = 'block';
                typingElement.textContent = '|';
                typeCharacter();
            }
        }
    }, 500);
}

// Typing animation for geography select
function initGeographyTypingAnimation() {
    const typingElement = document.getElementById('geographyTypingAnimation');
    const selectElement = document.getElementById('geographySelect');
    
    if (!typingElement || !selectElement) {
        console.log('Geography typing animation: Missing elements');
        return;
    }
    
    if (!window.geographyNames || window.geographyNames.length === 0) {
        console.log('Geography typing animation: No geography names available');
        return;
    }
    
    console.log('Geography typing animation: Initializing with', window.geographyNames.length, 'geographies');
    
    let currentGeographyIndex = 0;
    let currentText = '';
    let isDeleting = false;
    let typingSpeed = 100; // milliseconds per character
    let deleteSpeed = 50;
    let pauseBeforeDelete = 2000; // pause before deleting
    let pauseAfterDelete = 500; // pause before typing next
    
    let timeoutId = null;
    
    function typeCharacter() {
        const currentGeography = window.geographyNames[currentGeographyIndex];
        
        // Hide animation if geography is selected
        if (selectElement.value && selectElement.value !== '') {
            typingElement.style.display = 'none';
            if (timeoutId) clearTimeout(timeoutId);
            return;
        }
        
        // Show animation if no geography is selected
        typingElement.style.display = 'block';
        
        if (!isDeleting && currentText.length < currentGeography.length) {
            // Typing forward
            currentText = currentGeography.substring(0, currentText.length + 1);
            typingElement.textContent = currentText + '|';
            timeoutId = setTimeout(typeCharacter, typingSpeed);
        } else if (!isDeleting && currentText.length === currentGeography.length) {
            // Pause before deleting
            typingElement.textContent = currentText;
            timeoutId = setTimeout(() => {
                isDeleting = true;
                timeoutId = setTimeout(typeCharacter, deleteSpeed);
            }, pauseBeforeDelete);
        } else if (isDeleting && currentText.length > 0) {
            // Deleting
            currentText = currentText.substring(0, currentText.length - 1);
            typingElement.textContent = currentText + '|';
            timeoutId = setTimeout(typeCharacter, deleteSpeed);
        } else if (isDeleting && currentText.length === 0) {
            // Move to next geography
            isDeleting = false;
            currentGeographyIndex = (currentGeographyIndex + 1) % window.geographyNames.length;
            typingElement.textContent = '|';
            timeoutId = setTimeout(typeCharacter, pauseAfterDelete);
        }
    }
    
    // Check if geography is selected and update visibility
    function checkSelection() {
        if (selectElement.value && selectElement.value !== '') {
            typingElement.style.display = 'none';
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
        } else {
            // Only show and start animation if not focused
            if (document.activeElement !== selectElement) {
                typingElement.style.display = 'block';
                if (!timeoutId) {
                    // Reset animation state when restarting
                    currentText = '';
                    isDeleting = false;
                    typingElement.textContent = '|';
                    typeCharacter();
                }
            }
        }
    }
    
    // Initial check
    checkSelection();
    
    // Listen for changes
    selectElement.addEventListener('change', checkSelection);
    selectElement.addEventListener('focus', () => {
        // Always hide when focused
        typingElement.style.display = 'none';
        if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutId = null;
        }
    });
    selectElement.addEventListener('blur', () => {
        // Small delay to ensure focus is lost
        setTimeout(() => {
            checkSelection();
        }, 100);
    });
    
    // Start typing animation after a short delay
    setTimeout(() => {
        if (!selectElement.value || selectElement.value === '') {
            if (document.activeElement !== selectElement) {
                typingElement.style.display = 'block';
                typingElement.textContent = '|';
                typeCharacter();
            }
        }
    }, 500);
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new AlterDashboard();
    initPathogenTypingAnimation();
    initGeographyTypingAnimation();
});

// Handle pathogen change - reset geography select and submit form
function handlePathogenChange() {
    // Stop typing animation
    const typingElement = document.getElementById('pathogenTypingAnimation');
    if (typingElement) {
        typingElement.style.display = 'none';
    }
    
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
    // Stop typing animation
    const typingElement = document.getElementById('geographyTypingAnimation');
    if (typingElement) {
        typingElement.style.display = 'none';
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