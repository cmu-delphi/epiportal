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
        this.initChartHint();
    }
    
    initChartHint() {
        // Check if hint was previously dismissed
        if (localStorage.getItem('chartHintDismissed') === 'true') {
            const hint = document.getElementById('chartHint');
            if (hint) {
                hint.style.display = 'none';
            }
        } else {
            // Auto-hide hint after 10 seconds
            autoHideChartHint();
        }
    }

    initChart() {
        const ctx = document.getElementById('indicatorChart');
        if (!ctx) return;

        // Require backend-provided chartData
        if (!window.chartData || !Array.isArray(window.chartData.datasets)) {
            return;
        }
        const palette = ['#2563eb','#16a34a','#dc2626','#a855f7','#f59e0b','#0ea5e9','#ef4444','#10b981'];
        
        // Use dayLabels as the base timeline, fallback to labels if dayLabels not available
        const dayLabels = Array.isArray(window.chartData.dayLabels)
            ? window.chartData.dayLabels.map(l => String(l))
            : (Array.isArray(window.chartData.labels) ? window.chartData.labels.map(l => String(l)) : []);
        const weekLabels = Array.isArray(window.chartData.labels)
            ? window.chartData.labels.map(l => String(l))
            : [];
        const timePositions = Array.isArray(window.chartData.timePositions)
            ? window.chartData.timePositions
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
        const datasets = window.chartData.datasets.map((ds, i) => {
            const timeType = ds.timeType || 'week';
            const isWeekly = timeType === 'week';
            
            return {
                label: (ds.label === null || ds.label === undefined) ? '' : String(ds.label),
                data: alignData(Array.isArray(ds.data) ? ds.data.map(sanitizeValue) : [], dayLabels.length),
                borderColor: sanitizeColor(ds.borderColor, palette[i % palette.length]),
                backgroundColor: sanitizeColor(ds.backgroundColor, (palette[i % palette.length] + '33')),
                borderWidth: 2,
                fill: true,
                tension: 0, // No bezier curves for better performance
                pointRadius: isWeekly ? 3 : 0, // Show points for weekly indicators
                pointHoverRadius: isWeekly ? 6 : 4, // Larger hover radius for weekly
                pointBackgroundColor: isWeekly ? sanitizeColor(ds.borderColor, palette[i % palette.length]) : undefined,
                pointBorderColor: isWeekly ? '#fff' : undefined,
                pointBorderWidth: isWeekly ? 1.5 : 0,
                spanGaps: isWeekly ? true : false, // Connect across gaps for weekly data (to link weekly points)
                timeType: timeType // Store timeType for reference
            };
        });

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

		// Dual-level X-axis plugin (weeks on top, days below)
		// Optimized to reduce redraws during pan/zoom
		const dualAxisPlugin = {
			id: 'dualAxis',
			afterDraw(chart) {
				// Skip redraw only during active animations for better performance
				if (chart.animating) return;
				
				const ctx = chart.ctx;
				const xAxis = chart.scales.x;
				const chartArea = chart.chartArea;
				const weekLabels = window.chartData?.labels || [];
				const dayLabels = window.chartData?.dayLabels || [];
				
				if (!xAxis || !chartArea || weekLabels.length === 0 || dayLabels.length === 0) {
					console.log('Dual axis: Missing data', {
						hasXAxis: !!xAxis,
						hasChartArea: !!chartArea,
						weekLabelsLength: weekLabels.length,
						dayLabelsLength: dayLabels.length
					});
					return;
				}
				
				ctx.save();
				ctx.font = 'bold 11px Inter, sans-serif';
				ctx.textAlign = 'center';
				ctx.textBaseline = 'top';
				ctx.fillStyle = '#64748b';
				
				// Draw week labels above the chart
				// Only draw labels for visible ticks to improve performance
				const weekLabelY = chartArea.top - 20;
				
				// Get visible ticks from the x-axis
				if (!xAxis.ticks || xAxis.ticks.length === 0) {
					ctx.restore();
					return;
				}
				
				const visibleTicks = xAxis.ticks.filter(tick => {
					const dataIndex = tick.value;
					return dataIndex >= 0 && dataIndex < weekLabels.length && 
					       weekLabels[dataIndex] && weekLabels[dataIndex].trim() !== '';
				});
				
				// Limit the number of labels drawn to improve performance
				const maxLabels = 50;
				if (visibleTicks.length > maxLabels) {
					// Sample labels if too many
					const step = Math.ceil(visibleTicks.length / maxLabels);
					visibleTicks.forEach((tick, index) => {
						if (index % step === 0) {
							const dataIndex = tick.value;
							const label = weekLabels[dataIndex];
							if (label && label.trim() !== '') {
								ctx.fillText(label, tick.x, weekLabelY);
							}
						}
					});
				} else {
					visibleTicks.forEach((tick) => {
						const dataIndex = tick.value;
						const label = weekLabels[dataIndex];
						if (label && label.trim() !== '') {
							ctx.fillText(label, tick.x, weekLabelY);
						}
					});
				}
				
				ctx.restore();
			}
		};

		this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dayLabels, // Use day labels as base timeline
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 30 // Add padding for week labels
                    }
                },
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
                        enabled: function(context) {
                            // Disable tooltips during pan/zoom for better performance
                            const chart = context.chart;
                            return !chart._isPanning && !chart._isZooming;
                        },
                        filter: function(tooltipItem) {
                            // Only show tooltips for visible datasets
                            return !tooltipItem.hidden;
                        },
                        callbacks: {
                            title: function(context) {
                                const dayLabel = dayLabels[context[0].dataIndex] || '';
                                const weekLabel = weekLabels[context[0].dataIndex] || '';
                                if (weekLabel && weekLabel.trim() !== '') {
                                    return 'Week: ' + weekLabel + ' | Day: ' + dayLabel;
                                }
                                return 'Date: ' + dayLabel;
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
                    },
                    // Zoom and pan configuration
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'x',
                            modifierKey: null, // No modifier key needed for panning
                            threshold: 5,
                            speed: 1
                        },
                        zoom: {
                            wheel: {
                                enabled: true,
                                speed: 0.1
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'x',
                            limits: {
                                x: {
                                    min: 0,
                                    max: dayLabels.length - 1
                                }
                            }
                        },
                        limits: {
                            x: {
                                min: 0,
                                max: dayLabels.length - 1
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
                                size: 10
                            },
                            color: '#64748b',
                            maxTicksLimit: 20, // Show more ticks for daily data
                            autoSkip: true, // Automatically skip ticks when crowded
                            autoSkipPadding: 5,
                            callback: function(value, index) {
                                // Show day labels, but only for selected ticks
                                const label = dayLabels[index];
                                if (!label) return '';
                                // Format date to be more compact
                                try {
                                    const date = new Date(label);
                                    const month = date.getMonth() + 1;
                                    const day = date.getDate();
                                    return month + '/' + day;
                                } catch (e) {
                                    return label;
                                }
                            },
                            maxRotation: 45,
                            minRotation: 45
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
                    intersect: false,
                    // Allow panning even when hovering over data points
                    includeInvisible: true
                },
                animation: {
                    duration: 1000,
                    easing: 'easeInOutQuart',
                    // Disable animations during interactions for better performance
                    onProgress: function() {
                        // Throttle updates during animation
                    },
                    onComplete: function() {
                        // Re-enable full rendering after animation
                    }
                },
                // Performance optimizations
                elements: {
                    point: {
                        radius: 0, // Hide points by default (only show for weekly)
                        hoverRadius: 4
                    },
                    line: {
                        borderWidth: 2,
                        tension: 0 // Disable bezier curves for better performance
                    }
                },
                // Optimize tooltip rendering
                hover: {
                    animationDuration: 0 // Disable hover animations
                },
                // Reduce unnecessary redraws
                transitions: {
                    active: {
                        animation: {
                            duration: 0
                        }
                    }
                }
			},
			plugins: [htmlLegendPlugin, dualAxisPlugin]
		});
        
        // Set initial zoom to last 12 months after chart is created
        setTimeout(() => {
            if (window.chartData?.initialViewStart && window.chartData?.initialViewEnd && this.chart) {
                const initialStart = window.chartData.initialViewStart;
                const initialEnd = window.chartData.initialViewEnd;
                
                // Find indices in dayLabels that match the initial view dates
                let startIndex = dayLabels.findIndex(d => d >= initialStart);
                let endIndex = dayLabels.findIndex(d => d > initialEnd);
                
                // If exact match not found, use closest
                if (startIndex === -1) startIndex = 0;
                if (endIndex === -1) endIndex = dayLabels.length - 1;
                
                // Ensure valid range
                if (startIndex >= 0 && endIndex > startIndex && endIndex < dayLabels.length) {
                    // Zoom to the last 12 months using the zoom plugin API
                    try {
                        // Use zoomScale method if available (chartjs-plugin-zoom v2)
                        if (typeof this.chart.zoomScale === 'function') {
                            this.chart.zoomScale('x', {
                                min: startIndex,
                                max: endIndex
                            });
                        } else {
                            // Fallback: set scale min/max directly
                            const xScale = this.chart.scales.x;
                            if (xScale) {
                                xScale.options.min = startIndex;
                                xScale.options.max = endIndex;
                                this.chart.update('none');
                            }
                        }
                    } catch (e) {
                        console.warn('Could not set initial zoom:', e);
                    }
                }
            }
        }, 100);
        
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
}

// Dismiss chart hint function (called from HTML onclick)
function dismissChartHint() {
    const hint = document.getElementById('chartHint');
    if (hint) {
        hint.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => {
            hint.style.display = 'none';
        }, 300);
        // Store dismissal in localStorage so it doesn't show again
        localStorage.setItem('chartHintDismissed', 'true');
    }
}

// Auto-hide chart hint after 10 seconds
function autoHideChartHint() {
    const hint = document.getElementById('chartHint');
    if (hint && !localStorage.getItem('chartHintDismissed')) {
        setTimeout(() => {
            if (hint && hint.style.display !== 'none') {
                dismissChartHint();
            }
        }, 10000); // Hide after 10 seconds
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
    let typingSpeed = 300; // milliseconds per character
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
    let typingSpeed = 300; // milliseconds per character
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
        // Don't show animation if select is disabled (no pathogen selected)
        if (selectElement.disabled) {
            typingElement.style.display = 'none';
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
            return;
        }
        
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

// Update geography select enabled/disabled state based on pathogen selection
function updateGeographySelectState() {
    const pathogenSelect = document.getElementById('pathogenSelect');
    const geographySelect = document.getElementById('geographySelect');
    
    if (!pathogenSelect || !geographySelect) {
        return;
    }
    
    const hasPathogen = pathogenSelect.value && pathogenSelect.value !== '';
    
    // Enable or disable geography select based on pathogen selection
    geographySelect.disabled = !hasPathogen;
    
    // If pathogen is cleared, also clear geography selection
    if (!hasPathogen && geographySelect.value) {
        geographySelect.value = '';
    }
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new AlterDashboard();
    initPathogenTypingAnimation();
    initGeographyTypingAnimation();
    // Initialize geography select state based on pathogen selection
    updateGeographySelectState();
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
    
    // Update geography select state before submitting
    updateGeographySelectState();
    
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