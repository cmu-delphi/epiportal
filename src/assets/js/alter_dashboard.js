/**
 * Alternative Dashboard JavaScript
 * Enhanced dashboard with EpiVis-like features: interactive controls, normalization, and advanced chart options
 */

// Constants
const CHART_PALETTE = ['#2563eb','#16a34a','#dc2626','#a855f7','#f59e0b','#0ea5e9','#ef4444','#10b981'];
const TYPING_SPEED = 300;
const DELETE_SPEED = 50;
const PAUSE_BEFORE_DELETE = 2000;
const PAUSE_AFTER_DELETE = 500;
const MAX_GEOGRAPHY_NAMES = 25;
const MAX_DUAL_AXIS_LABELS = 50;
const INITIAL_ZOOM_DELAY = 100;
const CHART_REDRAW_DELAY = 100;
const CHART_RESIZE_DELAY = 10;
const TYPING_ANIMATION_DELAY = 500;
const BLUR_DELAY = 100;
const CHART_UPDATE_THROTTLE = 16; // ~60fps for smooth interactions

// Utility functions
const ChartUtils = {
    sanitizeValue(v) {
        if (v === null || v === undefined) return null;
        if (typeof v === 'number') return Number.isFinite(v) ? v : null;
        if (typeof v === 'string') {
            const s = v.trim().toLowerCase();
            if (s === '' || s === 'none' || s === 'null' || s === 'nan') return null;
            const num = parseFloat(s);
            return Number.isFinite(num) ? num : null;
        }
        return null;
    },

    sanitizeColor(c, fallback) {
        if (c === null || c === undefined) return fallback;
        if (typeof c === 'string') {
            const s = c.trim().toLowerCase();
            if (s === 'none' || s === 'null' || s === '') return fallback;
        }
        return c;
    },

    alignData(arr, targetLen) {
        const a = Array.isArray(arr) ? arr : [];
        if (a.length > targetLen) return a.slice(0, targetLen);
        if (a.length < targetLen) return a.concat(Array(targetLen - a.length).fill(null));
        return a;
    },

    processLabels(chartData) {
        const dayLabels = Array.isArray(chartData.dayLabels)
            ? chartData.dayLabels.map(l => String(l))
            : (Array.isArray(chartData.labels) ? chartData.labels.map(l => String(l)) : []);
        const weekLabels = Array.isArray(chartData.labels)
            ? chartData.labels.map(l => String(l))
            : [];
        return { dayLabels, weekLabels };
    },

    formatDateLabel(label) {
        try {
            const parts = String(label).match(/^(\d{4})-(\d{2})-(\d{2})$/);
            if (!parts) return label;
            
            const year = parseInt(parts[1], 10);
            const month = parseInt(parts[2], 10) - 1;
            const day = parseInt(parts[3], 10);
            
            const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const monthName = monthNames[month];
            
            return month === 0 
                ? `${monthName} ${day} ${year}`
                : `${monthName} ${day}`;
        } catch (e) {
            return label;
        }
    },

    createDataset(ds, i, dayLabelsLength) {
        const timeType = ds.timeType || 'week';
        const isWeekly = timeType === 'week';
        const isLargeDataset = dayLabelsLength > 1000;
        // Always use palette color based on index for consistency between chart and legend
        const color = CHART_PALETTE[i % CHART_PALETTE.length];
        
        return {
            label: (ds.label === null || ds.label === undefined) ? '' : String(ds.label),
            data: ChartUtils.alignData(Array.isArray(ds.data) ? ds.data.map(ChartUtils.sanitizeValue) : [], dayLabelsLength),
            // Use palette color to ensure consistency with legend
            borderColor: color,
            backgroundColor: color + '33',
            borderWidth: isLargeDataset ? 1.5 : 2, // Thinner lines for large datasets
            fill: true,
            tension: 0,
            pointRadius: isLargeDataset ? 0 : (isWeekly ? 3 : 0), // No points for large datasets
            pointHoverRadius: isLargeDataset ? 3 : (isWeekly ? 6 : 4),
            pointBackgroundColor: isLargeDataset ? undefined : (isWeekly ? color : undefined),
            pointBorderColor: isLargeDataset ? undefined : (isWeekly ? '#fff' : undefined),
            pointBorderWidth: isLargeDataset ? 0 : (isWeekly ? 1.5 : 0),
            spanGaps: isWeekly,
            timeType: timeType,
            // Performance optimizations for large datasets
            pointHitRadius: isLargeDataset ? 5 : undefined, // Smaller hit radius for large datasets
            pointHoverBorderWidth: isLargeDataset ? 0 : undefined
        };
    }
};

// Typing animation manager
class TypingAnimation {
    constructor(elementId, selectId, namesKey) {
        this.typingElement = null;
        this.selectElement = null;
        this.namesKey = namesKey;
        this.timeoutId = null;
        this.changeHandler = null;
        this.focusHandler = null;
        this.blurHandler = null;
        this.currentIndex = 0;
        this.currentText = '';
        this.isDeleting = false;
        
        this.init(elementId, selectId);
    }

    init(elementId, selectId) {
        this.typingElement = document.getElementById(elementId);
        this.selectElement = document.getElementById(selectId);
        
        if (!this.typingElement || !this.selectElement) {
            return;
        }

        this.cleanup();
        this.setupHandlers();
        this.checkSelection();
        
        setTimeout(() => {
            if (!this.selectElement.value && document.activeElement !== this.selectElement && !this.selectElement.disabled) {
                this.typingElement.style.display = 'block';
                this.typingElement.textContent = '|';
                this.typeCharacter();
            }
        }, TYPING_ANIMATION_DELAY);
    }

    cleanup() {
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        
        if (this.selectElement) {
            if (this.changeHandler) {
                this.selectElement.removeEventListener('change', this.changeHandler);
            }
            if (this.focusHandler) {
                this.selectElement.removeEventListener('focus', this.focusHandler);
            }
            if (this.blurHandler) {
                this.selectElement.removeEventListener('blur', this.blurHandler);
            }
        }
        
        if (this.typingElement) {
            this.typingElement.style.display = 'none';
        }
        
        this.currentText = '';
        this.isDeleting = false;
        this.currentIndex = 0;
    }

    setupHandlers() {
        this.changeHandler = () => this.checkSelection();
        this.focusHandler = () => {
            if (this.typingElement) {
                this.typingElement.style.display = 'none';
            }
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
                this.timeoutId = null;
            }
        };
        this.blurHandler = () => {
            setTimeout(() => this.checkSelection(), BLUR_DELAY);
        };
        
        if (this.selectElement) {
            this.selectElement.addEventListener('change', this.changeHandler);
            this.selectElement.addEventListener('focus', this.focusHandler);
            this.selectElement.addEventListener('blur', this.blurHandler);
        }
    }

    checkSelection() {
        if (!this.selectElement || !this.typingElement) return;
        
        if (this.selectElement.disabled) {
            this.typingElement.style.display = 'none';
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
                this.timeoutId = null;
            }
            return;
        }
        
        if (this.selectElement.value) {
            this.typingElement.style.display = 'none';
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
                this.timeoutId = null;
            }
        } else if (document.activeElement !== this.selectElement) {
            this.typingElement.style.display = 'block';
            if (!this.timeoutId) {
                this.currentText = '';
                this.isDeleting = false;
                this.currentIndex = 0;
                this.typingElement.textContent = '|';
                this.typeCharacter();
            }
        }
    }

    typeCharacter() {
        const names = window[this.namesKey] || [];
        if (names.length === 0) {
            if (this.typingElement) {
                this.typingElement.style.display = 'none';
            }
            return;
        }

        const currentName = names[this.currentIndex];
        
        if (this.selectElement.value) {
            if (this.typingElement) {
                this.typingElement.style.display = 'none';
            }
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
                this.timeoutId = null;
            }
            return;
        }
        
        if (this.typingElement) {
            this.typingElement.style.display = 'block';
        }
        
        if (!this.isDeleting && this.currentText.length < currentName.length) {
            this.currentText = currentName.substring(0, this.currentText.length + 1);
            if (this.typingElement) {
                this.typingElement.textContent = this.currentText + '|';
            }
            this.timeoutId = setTimeout(() => this.typeCharacter(), TYPING_SPEED);
        } else if (!this.isDeleting && this.currentText.length === currentName.length) {
            if (this.typingElement) {
                this.typingElement.textContent = this.currentText;
            }
            this.timeoutId = setTimeout(() => {
                this.isDeleting = true;
                this.timeoutId = setTimeout(() => this.typeCharacter(), DELETE_SPEED);
            }, PAUSE_BEFORE_DELETE);
        } else if (this.isDeleting && this.currentText.length > 0) {
            this.currentText = this.currentText.substring(0, this.currentText.length - 1);
            if (this.typingElement) {
                this.typingElement.textContent = this.currentText + '|';
            }
            this.timeoutId = setTimeout(() => this.typeCharacter(), DELETE_SPEED);
        } else if (this.isDeleting && this.currentText.length === 0) {
            this.isDeleting = false;
            this.currentIndex = (this.currentIndex + 1) % names.length;
            if (this.typingElement) {
                this.typingElement.textContent = '|';
            }
            this.timeoutId = setTimeout(() => this.typeCharacter(), PAUSE_AFTER_DELETE);
        }
    }
}

// Typing animation instances
let pathogenTypingAnimation = null;
let geographyTypingAnimation = null;

class AlterDashboard {
    constructor() {
        this.originalDatasets = [];
        this.normalized = true;
        this.updateThrottleTimer = null;
        this.init();
    }

    init() {
        this.initChart();
        this.initControls();
        this.initLegendInteractivity();
        this.initChartHint();
    }
    
    initChartHint() {
        const hint = document.getElementById('chartHint');
        if (!hint) return;
        
        // Ensure hint is visible on every page load
        hint.style.display = 'flex';
        hint.classList.remove('hidden');
    }

    initChart() {
        const ctx = document.getElementById('indicatorChart');
        if (!ctx) return;

        if (!window.chartData || !Array.isArray(window.chartData.datasets)) {
            window.chartData = {
                labels: [],
                dayLabels: [],
                timePositions: [],
                datasets: []
            };
        }
        
        const { dayLabels, weekLabels } = ChartUtils.processLabels(window.chartData);
        const timePositions = Array.isArray(window.chartData.timePositions)
            ? window.chartData.timePositions
            : [];
        
        const datasets = (window.chartData.datasets || []).map((ds, i) => 
            ChartUtils.createDataset(ds, i, dayLabels.length)
        );

        // Ensure all datasets are visible by default
        datasets.forEach((ds) => {
            ds.hidden = false;
        });

        this.originalDatasets = datasets.map(d => ({
            ...d,
            originalData: Array.isArray(d.data) ? [...d.data] : []
        }));

        this.createLegendContainer();
        const htmlLegendPlugin = this.createHtmlLegendPlugin();
        const xAxisTickMarksPlugin = this.createXAxisTickMarksPlugin();
        const dualAxisPlugin = this.createDualAxisPlugin();

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dayLabels,
                datasets: datasets
            },
            options: this.getChartOptions(dayLabels),
            plugins: [htmlLegendPlugin, dualAxisPlugin, xAxisTickMarksPlugin]
        });
        
        this.setInitialZoom(dayLabels);
        this.hidePageLoader();
    }

    createLegendContainer() {
        let legendContainer = document.getElementById('chartHtmlLegend');
        if (!legendContainer) {
            const section = document.querySelector('.chart-section');
            const header = section?.querySelector('.card-header');
            if (header) {
                legendContainer = document.createElement('div');
                legendContainer.id = 'chartHtmlLegend';
                Object.assign(legendContainer.style, {
                    maxHeight: '260px',
                    overflow: 'auto',
                    marginTop: '8px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px',
                    alignItems: 'center',
                    fontSize: '11px',
                    paddingBottom: '8px'
                });
                header.appendChild(legendContainer);
            }
        }
    }

    createHtmlLegendPlugin() {
        return {
            id: 'htmlLegend',
            afterUpdate(chart, args, options) {
                const container = document.getElementById(options.containerID);
                if (!container) return;
                
                while (container.firstChild) {
                    container.firstChild.remove();
                }
                
                const list = document.createElement('div');
                Object.assign(list.style, {
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px'
                });
                
                const items = chart.options.plugins.legend.labels.generateLabels(chart);
                items.forEach(item => {
                    // Get the actual line color (borderColor) from the dataset
                    // For line charts, strokeStyle matches borderColor, which is what we want
                    const lineColor = item.strokeStyle || item.fillStyle || '#2563eb';
                    
                    const button = document.createElement('button');
                    button.type = 'button';
                    Object.assign(button.style, {
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        border: '1px solid #e2e8f0',
                        borderRadius: '12px',
                        padding: '4px 8px',
                        background: '#fff',
                        cursor: 'pointer',
                        fontSize: '11px',
                        lineHeight: '1.2',
                        maxWidth: '100%',
                        opacity: item.hidden ? '0.5' : '1'
                    });
                    button.title = item.text;
                    
                    const box = document.createElement('span');
                    Object.assign(box.style, {
                        width: '10px',
                        height: '10px',
                        display: 'inline-block',
                        borderRadius: '50%',
                        background: lineColor,
                        border: '1px solid rgba(0,0,0,0.1)'
                    });
                    
                    const text = document.createElement('span');
                    text.textContent = item.text;
                    Object.assign(text.style, {
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                    });
                    
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
    }

    createXAxisTickMarksPlugin() {
        return {
            id: 'xAxisTickMarks',
            afterDraw(chart) {
                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const chartArea = chart.chartArea;
                
                if (!xAxis || !chartArea) return;
                
                let ticks = [];
                if (xAxis.ticks && Array.isArray(xAxis.ticks) && xAxis.ticks.length > 0) {
                    ticks = xAxis.ticks;
                } else if (xAxis._ticks && Array.isArray(xAxis._ticks) && xAxis._ticks.length > 0) {
                    ticks = xAxis._ticks;
                } else if (typeof xAxis.getTicks === 'function') {
                    ticks = xAxis.getTicks();
                }
                
                ctx.save();
                ctx.strokeStyle = '#64748b';
                ctx.lineWidth = 1;
                
                const tickLength = 4;
                const tickY = chartArea.bottom;
                
                if (ticks.length > 0) {
                    ticks.forEach((tick) => {
                        let tickX = null;
                        
                        if (tick && typeof tick.x === 'number' && !isNaN(tick.x)) {
                            tickX = tick.x;
                        } else if (xAxis && typeof xAxis.getPixelForValue === 'function') {
                            if (tick && typeof tick.value === 'number') {
                                tickX = xAxis.getPixelForValue(tick.value);
                            } else if (typeof tick === 'number') {
                                tickX = xAxis.getPixelForValue(tick);
                            }
                        }
                        
                        if (tickX !== null && typeof tickX === 'number' && !isNaN(tickX) && 
                            tickX >= chartArea.left && tickX <= chartArea.right) {
                            ctx.beginPath();
                            ctx.moveTo(tickX, tickY);
                            ctx.lineTo(tickX, tickY + tickLength);
                            ctx.stroke();
                        }
                    });
                } else if (xAxis && typeof xAxis.getPixelForValue === 'function' && chart.data && chart.data.labels) {
                    const labels = chart.data.labels;
                    const min = xAxis.min !== undefined ? xAxis.min : 0;
                    const max = xAxis.max !== undefined ? xAxis.max : labels.length - 1;
                    const numTicks = Math.min(20, labels.length);
                    const step = (max - min) / (numTicks - 1);
                    
                    for (let i = 0; i < numTicks; i++) {
                        const value = min + (i * step);
                        const tickX = xAxis.getPixelForValue(value);
                        
                        if (tickX !== null && typeof tickX === 'number' && !isNaN(tickX) && 
                            tickX >= chartArea.left && tickX <= chartArea.right) {
                            ctx.beginPath();
                            ctx.moveTo(tickX, tickY);
                            ctx.lineTo(tickX, tickY + tickLength);
                            ctx.stroke();
                        }
                    }
                }
                
                ctx.restore();
            }
        };
    }

    createDualAxisPlugin() {
        return {
            id: 'dualAxis',
            afterDraw(chart) {
                if (chart.animating) return;
                
                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const chartArea = chart.chartArea;
                const weekLabels = window.chartData?.labels || [];
                const dayLabels = window.chartData?.dayLabels || [];
                
                if (!xAxis || !chartArea || weekLabels.length === 0 || dayLabels.length === 0) {
                    return;
                }
                
                ctx.save();
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillStyle = '#64748b';
                
                const weekLabelY = chartArea.top - 20;
                
                if (!xAxis.ticks || xAxis.ticks.length === 0) {
                    ctx.restore();
                    return;
                }
                
                const visibleTicks = xAxis.ticks.filter(tick => {
                    const dataIndex = tick.value;
                    return dataIndex >= 0 && dataIndex < weekLabels.length && 
                           weekLabels[dataIndex] && weekLabels[dataIndex].trim() !== '';
                });
                
                const maxLabels = MAX_DUAL_AXIS_LABELS;
                if (visibleTicks.length > maxLabels) {
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
    }

    getChartOptions(dayLabels) {
        const isLargeDataset = dayLabels.length > 1000;
        
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false, // Disable animations for better performance
            transitions: {
                active: {
                    animation: {
                        duration: 0 // Disable transitions during updates
                    }
                }
            },
            layout: {
                padding: { top: 30 }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: { display: false },
                htmlLegend: { containerID: 'chartHtmlLegend' },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.85)',
                    padding: 14,
                    titleFont: { size: 14, weight: '600' },
                    bodyFont: { size: 12, weight: '400' },
                    displayColors: true,
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    position: isLargeDataset ? 'nearest' : 'average',
                    enabled: function(context) {
                        const chart = context.chart;
                        return !chart._isPanning && !chart._isZooming;
                    },
                    filter: function(tooltipItem) {
                        return !tooltipItem.hidden;
                    },
                    callbacks: {
                        title: function(context) {
                            const chart = context.chart;
                            let dayLabels = [];
                            let weekLabels = [];
                            
                            if (chart?.data?.labels) {
                                dayLabels = chart.data.labels;
                            }
                            
                            if (window.chartData) {
                                weekLabels = window.chartData.labels || [];
                                if (dayLabels.length === 0 && window.chartData.dayLabels) {
                                    dayLabels = window.chartData.dayLabels;
                                }
                            }
                            
                            const dataIndex = context[0].dataIndex;
                            const dayLabel = dayLabels[dataIndex] || '';
                            const weekLabel = weekLabels[dataIndex] || '';
                            
                            if (weekLabel && weekLabel.trim() !== '') {
                                return `Week: ${weekLabel} | Day: ${dayLabel}`;
                            }
                            return `Date: ${dayLabel}`;
                        },
                        label: function(context) {
                            const label = context.dataset.label || '';
                            const value = context.parsed.y;
                            if (value === null || value === undefined || Number.isNaN(value)) {
                                return `${label}: n/a`;
                            }
                            return `${label}: ${value.toFixed(1)}`;
                        }
                    }
                },
                zoom: {
                    pan: {
                        enabled: true,
                        mode: 'x',
                        modifierKey: null,
                        threshold: 5,
                        speed: 1
                    },
                    zoom: {
                        wheel: { enabled: true, speed: 0.1 },
                        pinch: { enabled: true },
                        mode: 'x',
                        limits: {
                            x: { min: 0, max: dayLabels.length - 1 }
                        }
                    },
                    limits: {
                        x: { min: 0, max: dayLabels.length - 1 }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: true,
                        color: 'rgba(226, 232, 240, 0.5)',
                        drawBorder: false,
                        lineWidth: 1
                    },
                    ticks: {
                        font: { size: 10 },
                        color: '#64748b',
                        maxTicksLimit: isLargeDataset ? 15 : 20, // Reduce ticks for large datasets
                        autoSkip: true,
                        autoSkipPadding: 5,
                        display: true,
                        sampleSize: isLargeDataset ? 100 : undefined, // Sample ticks for performance
                        callback: function(value) {
                            const chart = this.chart;
                            if (!chart?.data?.labels) return '';
                            
                            const dayLabels = chart.data.labels;
                            const dataIndex = Math.round(value);
                            if (dataIndex < 0 || dataIndex >= dayLabels.length) return '';
                            const label = dayLabels[dataIndex];
                            if (!label) return '';
                            
                            return ChartUtils.formatDateLabel(label);
                        },
                        maxRotation: 45,
                        minRotation: 45
                    },
                    drawOnChartArea: true,
                    drawTicks: true
                },
                y: {
                    display: true,
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(226, 232, 240, 0.8)',
                        drawBorder: false
                    },
                    ticks: {
                        font: { size: 11 },
                        color: '#64748b',
                        callback: (value) => `${value.toFixed(0)}`
                    },
                    title: {
                        display: true,
                        text: 'Scaled value',
                        font: { size: 12, weight: '500' },
                        color: '#64748b',
                        padding: { top: 5, bottom: 5 }
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false,
                includeInvisible: false // Exclude invisible datasets for performance
            },
            elements: {
                point: {
                    radius: isLargeDataset ? 0 : 0, // No points for large datasets
                    hoverRadius: isLargeDataset ? 3 : 4,
                    hitRadius: isLargeDataset ? 5 : 10 // Smaller hit radius for performance
                },
                line: {
                    borderWidth: isLargeDataset ? 1.5 : 2, // Thinner lines for large datasets
                    tension: 0,
                    cubicInterpolationMode: 'default' // Use default interpolation for performance
                }
            },
            hover: {
                animationDuration: 0,
                mode: 'index',
                intersect: false
            },
            transitions: {
                active: {
                    animation: { duration: 0 }
                }
            }
        };
    }

    setInitialZoom(dayLabels) {
        setTimeout(() => {
            if (window.chartData?.initialViewStart && window.chartData?.initialViewEnd && this.chart) {
                const initialStart = window.chartData.initialViewStart;
                const initialEnd = window.chartData.initialViewEnd;
                
                let startIndex = dayLabels.findIndex(d => d >= initialStart);
                let endIndex = dayLabels.findIndex(d => d > initialEnd);
                
                if (startIndex === -1) startIndex = 0;
                if (endIndex === -1) endIndex = dayLabels.length - 1;
                
                if (startIndex >= 0 && endIndex > startIndex && endIndex < dayLabels.length) {
                    try {
                        if (typeof this.chart.zoomScale === 'function') {
                            this.chart.zoomScale('x', { min: startIndex, max: endIndex });
                        } else {
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
        }, INITIAL_ZOOM_DELAY);
    }

    hidePageLoader() {
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

    showAllDatasets() {
        if (!this.chart) return;
        
        this.chart.data.datasets.forEach((dataset, index) => {
            const meta = this.chart.getDatasetMeta(index);
            meta.hidden = false;
        });
        
        this.chart.update();
    }

    initControls() {
        let controlsContainer = document.getElementById('chartControls');
        if (!controlsContainer) {
            const chartSection = document.querySelector('.chart-section');
            const cardHeader = chartSection?.querySelector('.card-header');
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

        const showAllBtn = document.getElementById('showAllBtn');
        if (showAllBtn) {
            showAllBtn.addEventListener('click', () => this.showAllDatasets());
        }
    }

    initLegendInteractivity() {
        // Legend interactivity is handled in Chart.js config
    }

    updateChart(chartData) {
        if (!this.chart || !chartData) return;

        const { dayLabels, weekLabels } = ChartUtils.processLabels(chartData);
        const datasets = chartData.datasets.map((ds, i) => 
            ChartUtils.createDataset(ds, i, dayLabels.length)
        );

        this.originalDatasets = datasets.map(d => ({
            ...d,
            originalData: Array.isArray(d.data) ? [...d.data] : []
        }));

        // Ensure all datasets are visible
        datasets.forEach((ds, index) => {
            ds.hidden = false;
        });

        this.chart.data.labels = dayLabels;
        this.chart.data.datasets = datasets;

        window.chartData = {
            labels: weekLabels,
            dayLabels: dayLabels,
            timePositions: chartData.timePositions || [],
            datasets: datasets,
            initialViewStart: chartData.initialViewStart,
            initialViewEnd: chartData.initialViewEnd
        };

        this.updateZoomLimits(dayLabels);
        this.updateScaleConfiguration(dayLabels);
        
        // Optimize: use requestAnimationFrame for smoother updates with large datasets
        const isLargeDataset = dayLabels.length > 1000;
        if (isLargeDataset) {
            requestAnimationFrame(() => {
                this.chart.update('none');
                setTimeout(() => {
                    this.setInitialZoom(dayLabels);
                }, INITIAL_ZOOM_DELAY);
            });
        } else {
            // Single update with animation disabled, then set zoom
            this.chart.update('none');
            setTimeout(() => {
                this.setInitialZoom(dayLabels);
            }, INITIAL_ZOOM_DELAY);
        }
    }

    updateZoomLimits(dayLabels) {
        if (this.chart.options.plugins?.zoom) {
            if (this.chart.options.plugins.zoom.zoom?.limits) {
                this.chart.options.plugins.zoom.zoom.limits.x = {
                    min: 0,
                    max: dayLabels.length - 1
                };
            }
            if (this.chart.options.plugins.zoom.limits) {
                this.chart.options.plugins.zoom.limits.x = {
                    min: 0,
                    max: dayLabels.length - 1
                };
            }
        }
    }

    updateScaleConfiguration(dayLabels) {
        if (this.chart.options.scales?.x) {
            this.chart.options.scales.x.min = undefined;
            this.chart.options.scales.x.max = dayLabels.length - 1;
            
            if (this.chart.options.scales.x.ticks) {
                this.chart.options.scales.x.ticks.display = true;
            }
            
            if (this.chart.scales?.x) {
                const xScale = this.chart.scales.x;
                xScale.options.min = undefined;
                xScale.options.max = dayLabels.length - 1;
            }
        }
    }

    forceRedraw() {
        setTimeout(() => {
            if (this.chart?.scales?.x) {
                this.chart.resize();
                setTimeout(() => {
                    if (this.chart) {
                        this.chart.update('none');
                    }
                }, CHART_RESIZE_DELAY);
            }
        }, CHART_REDRAW_DELAY);
    }
}

// Chart hint functions
function dismissChartHint() {
    const hint = document.getElementById('chartHint');
    if (hint) {
        // Add animation
        hint.style.animation = 'fadeOut 0.3s ease-out';
        // Hide after animation completes
        setTimeout(() => {
            hint.style.display = 'none';
            hint.classList.add('hidden');
        }, 300);
    }
}

// Make function globally accessible
window.dismissChartHint = dismissChartHint;

// Initialize typing animations
function initPathogenTypingAnimation() {
    if (pathogenTypingAnimation) {
        pathogenTypingAnimation.cleanup();
    }
    pathogenTypingAnimation = new TypingAnimation('pathogenTypingAnimation', 'pathogenSelect', 'pathogenNames');
}

function initGeographyTypingAnimation() {
    if (geographyTypingAnimation) {
        geographyTypingAnimation.cleanup();
    }
    geographyTypingAnimation = new TypingAnimation('geographyTypingAnimation', 'geographySelect', 'geographyNames');
}

function updateGeographySelectState() {
    const pathogenSelect = document.getElementById('pathogenSelect');
    const geographySelect = document.getElementById('geographySelect');
    
    if (!pathogenSelect || !geographySelect) return;
    
    const hasPathogen = pathogenSelect.value && pathogenSelect.value !== '';
    geographySelect.disabled = !hasPathogen;
    
    if (!hasPathogen && geographySelect.value) {
        geographySelect.value = '';
    }
}

// Initialize dashboard
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new AlterDashboard();
    initPathogenTypingAnimation();
    initGeographyTypingAnimation();
    updateGeographySelectState();
});

// Handle pathogen change
async function handlePathogenChange() {
    const typingElement = document.getElementById('pathogenTypingAnimation');
    if (typingElement) {
        typingElement.style.display = 'none';
    }
    
    const pathogenSelect = document.getElementById('pathogenSelect');
    const geographySelect = document.getElementById('geographySelect');
    
    if (!pathogenSelect || !geographySelect) return;
    
    const selectedPathogen = pathogenSelect.value;
    
    const geographyTypingElement = document.getElementById('geographyTypingAnimation');
    if (geographyTypingElement) {
        geographyTypingElement.style.display = 'none';
    }
    if (geographyTypingAnimation) {
        geographyTypingAnimation.cleanup();
    }
    
    geographySelect.value = '';
    
    if (!selectedPathogen) {
        geographySelect.innerHTML = '<option value=""></option>';
        geographySelect.disabled = true;
        window.geographyNames = [];
        initGeographyTypingAnimation();
        return;
    }
    
    geographySelect.disabled = true;
    
    const geographyLoader = document.getElementById('geographyLoader');
    if (geographyLoader) {
        geographyLoader.style.display = 'block';
    }
    
    try {
        const url = window.getAvailableGeosUrl || '/api/get_available_geos';
        const response = await fetch(`${url}?pathogen=${encodeURIComponent(selectedPathogen)}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.csrfToken || '',
            },
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        geographySelect.innerHTML = '<option value=""></option>';
        
        if (data.available_geos && Array.isArray(data.available_geos)) {
            data.available_geos.forEach(group => {
                if (group.children && Array.isArray(group.children)) {
                    const optgroup = document.createElement('optgroup');
                    optgroup.label = group.text;
                    
                    group.children.forEach(child => {
                        const option = document.createElement('option');
                        option.value = child.id;
                        option.textContent = child.text;
                        optgroup.appendChild(option);
                    });
                    
                    geographySelect.appendChild(optgroup);
                }
            });
        }
        
        window.geographyNames = [];
        if (data.available_geos && Array.isArray(data.available_geos)) {
            data.available_geos.forEach(group => {
                if (group.children && Array.isArray(group.children)) {
                    group.children.slice(0, parseInt(MAX_GEOGRAPHY_NAMES / data.available_geos.length)).forEach(child => {
                        window.geographyNames.push(child.text);
                    });
                }
            });
        }
        
        if (window.geographyNames.length > MAX_GEOGRAPHY_NAMES) {
            window.geographyNames = window.geographyNames.slice(0, MAX_GEOGRAPHY_NAMES);
        }
        
        geographySelect.disabled = !selectedPathogen;
        
        setTimeout(() => {
            initGeographyTypingAnimation();
        }, INITIAL_ZOOM_DELAY);
        
    } catch (error) {
        console.error('Error fetching available geos:', error);
        geographySelect.disabled = !selectedPathogen;
    } finally {
        if (geographyLoader) {
            geographyLoader.style.display = 'none';
        }
    }
}

// Handle geography change
async function handleGeographyChange() {
    const typingElement = document.getElementById('geographyTypingAnimation');
    if (typingElement) {
        typingElement.style.display = 'none';
    }
    
    const pathogenSelect = document.getElementById('pathogenSelect');
    const geographySelect = document.getElementById('geographySelect');
    
    if (!pathogenSelect || !geographySelect) return;
    
    const selectedPathogen = pathogenSelect.value;
    const selectedGeography = geographySelect.value;
    
    if (!selectedGeography) {
        if (dashboard?.chart) {
            dashboard.chart.data.datasets = [];
            dashboard.chart.data.labels = [];
            dashboard.chart.update();
        }
        return;
    }
    
    const chartLoader = document.getElementById('chartLoader');
    if (chartLoader) {
        chartLoader.style.display = 'block';
    }
    
    try {
        const url = window.getChartDataUrl || '/api/get_chart_data';
        const response = await fetch(`${url}?pathogen=${encodeURIComponent(selectedPathogen)}&geography=${encodeURIComponent(selectedGeography)}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.csrfToken || '',
            },
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.chart_data && dashboard) {
            dashboard.updateChart(data.chart_data);
            document.getElementById('chartTitle').textContent = `${selectedPathogen} in ${geographySelect.options[geographySelect.selectedIndex].text}`;
        } else {
            document.getElementById('chartTitle').textContent = '';
        }
        
    } catch (error) {
        console.error('Error fetching chart data:', error);
    } finally {
        if (chartLoader) {
            chartLoader.style.display = 'none';
        }
    }
}

// Export for use in other scripts
window.AlterDashboard = AlterDashboard;
