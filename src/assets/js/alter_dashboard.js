/**
 * Alternative Dashboard JavaScript
 * Simple dashboard with efficient rendering and modal functionality
 */

class AlterDashboard {
    constructor() {
        this.init();
    }

    init() {
        this.initChart();
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
            }
        ];

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
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: {
                            size: 14,
                            weight: '600'
                        },
                        bodyFont: {
                            size: 12
                        },
                        displayColors: true,
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(2);
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
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(226, 232, 240, 0.8)',
                            drawBorder: false
                        },
                        ticks: {
                            font: {
                                size: 11
                            },
                            color: '#64748b',
                            callback: function(value) {
                                return value.toFixed(1);
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
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new AlterDashboard();
});

// Export for use in other scripts
window.AlterDashboard = AlterDashboard;