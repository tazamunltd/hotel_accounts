/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useState } = owl;

/* Date: 2025-01-13 Time: 01:39:40
 * Custom Dashboard Component for Hotel Management
 * Handles room metrics and chart visualizations
 */
class CustomDashBoard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        
        // Initialize chart instances
        this.charts = {
            occupancyStatus: null,
            dailyOccupancy: null,
            arrivalsVsDepartures: null,
            roomTypeDistribution: null,
            roomStatusByType: null,
            roomAvailabilityTimeline: null
        };
        
        // Initialize state with all required metrics
        this.state = useState({
            // Room metrics
            expected_arrivals: 0,
            out_of_order: 0,
            rooms_on_hold: 0,
            out_of_service: 0,
            inhouse: 0,
            expected_departures: 0,
            house_use_count: 0,
            complementary_use_count: 0,
            available: 0,
            expected_inhouse: 0,
            free_to_sell: 0,
            total_rooms: 0,
            reserved: 0,
            
            // Chart data
            occupancyHistory: {
                dates: [],
                rates: []
            },
            arrivalsVsDepartures: {
                dates: [],
                arrivals: [],
                departures: []
            },
            roomTypeDistribution: {
                types: [],
                counts: []
            },
            roomStatusByType: {
                types: [],
                available: [],
                occupied: [],
                reserved: [],
                outOfOrder: []
            },
            availabilityTimeline: {
                dates: [],
                available: [],
                total: []
            }
        });

        // Setup lifecycle hooks
        onWillStart(async () => {
            await this._getInitialState();
        });

        onMounted(() => {
            this.renderAllCharts();
        });
    }

    /* Date: 2025-01-13 Time: 02:04:55
     * Method to get initial state data
     */
    async _getInitialState() {
        try {
            await Promise.all([
                this.fetchExpectedArrivals(),
                this.fetchOccupancyHistory(),
                this.fetchArrivalsVsDepartures(),
                this.fetchRoomTypeDistribution(),
                this.fetchRoomStatusByType(),
                this.fetchAvailabilityTimeline()
            ]);
        } catch (error) {
            console.error('Error fetching initial state:', error);
        }
    }

    /* Date: 2025-01-13 Time: 02:04:55
     * Method to render all charts
     */
    async renderAllCharts() {
        try {
            // Cleanup existing charts
            this.cleanupCharts();

            // Render each chart
            await Promise.all([
                this.renderRoomOccupancyStatusChart(),
                this.renderDailyOccupancyChart(),
                this.renderArrivalsVsDeparturesChart(),
                this.renderRoomTypeDistributionChart(),
                this.renderRoomStatusByTypeChart(),
                this.renderRoomAvailabilityTimelineChart()
            ]);
        } catch (error) {
            console.error('Error rendering charts:', error);
        }
    }

    async fetchExpectedArrivals() {
        try {
            // Helper method to get company and system date
            const getCompanySystemDate = async () => {
                // Comprehensive fallback for company retrieval
                let companyIds = [];

                // Try multiple ways to get company IDs
                if (this.env.services.company.currentCompany.id) {
                    companyIds = Object.values(this.env.services.company.allowedCompanies)
                        .map(company => company.id);
                }

                // Use the current company
                var current_company_id = this.env.services.company.currentCompany.id;

                // Fetch company details
                const companies = await this.orm.call('res.company', 'search_read', [
                    [['id', 'in', companyIds]],
                    ['id', 'system_date', 'name']
                ]);

                // Find the system date for the current company
                var current_company = companies.find(company => company.id === current_company_id);
                
                // Validate system date
                var system_date = current_company && current_company.system_date ? current_company.system_date : formattedDate;
                
                // Parse the original system date
                var parsedDate = new Date(system_date);
                
                // Format the date to YYYY-MM-DD
                system_date = parsedDate.toISOString().split('T')[0];

                return {
                    current_company_id: current_company_id,
                    system_date: system_date
                };
            };

            // Get company and system date
            const { current_company_id, system_date } = await getCompanySystemDate();

            // Fetch dashboard metrics
            const result = await this.orm.call(
                'hotel.room.result',
                'get_dashboard_room_metrics',
                [current_company_id, system_date]
            );
            
            console.log("Received dashboard metrics:", result);

            // Set default values if not provided
            this.state.expected_arrivals = result.expected_arrivals || 0;
            this.state.out_of_order = result.out_of_order || 0;
            this.state.rooms_on_hold = result.rooms_on_hold || 0;
            this.state.out_of_service = result.out_of_service || 0;
            this.state.inhouse = result.inhouse || 0;
            this.state.expected_departures = result.expected_departures || 0;
            this.state.house_use_count = result.house_use_count || 0;
            this.state.complementary_use_count = result.complementary_use_count || 0;
            this.state.expected_occupied_rate = result.expected_occupied_rate || 0;
            this.state.available = result.available || 0;
            this.state.expected_inhouse = result.expected_inhouse || 0;
            this.state.free_to_sell = result.free_to_sell || 0;
            this.state.total_rooms = result.total_rooms || 0;
            this.state.reserved = result.reserved || 0;

            console.log("Updated state:", this.state);

        } catch (error) {
            console.error("Error fetching expected arrivals:", error);
        }
    }

    /* Date: 2025-01-13 Time: 01:14:29
     * Method to fetch occupancy history for the last 7 days
     */
    async fetchOccupancyHistory() {
        try {
            console.log("Fetching occupancy history");
            const result = await this.orm.call(
                'hotel.room.result',
                'get_occupancy_history',
                [this.env.services.company.currentCompany.id, 7]  // Fetch last 7 days
            );
            
            this.state.occupancyHistory.dates = result.dates || [];
            this.state.occupancyHistory.rates = result.rates || [];
            
            console.log("Received occupancy history:", this.state.occupancyHistory);
        } catch (error) {
            console.error("Error fetching occupancy history:", error);
        }
    }

    async fetchArrivalsVsDepartures() {
        try {
            console.log("Fetching arrivals vs departures data");
            const result = await this.orm.call(
                'hotel.room.result',
                'get_arrivals_departures_history',
                [this.env.services.company.currentCompany.id, 7]  // Fetch last 7 days
            );
            
            this.state.arrivalsVsDepartures = result;
            console.log("Received arrivals vs departures data:", result);
        } catch (error) {
            console.error("Error fetching arrivals vs departures data:", error);
        }
    }

    async fetchRoomTypeDistribution() {
        try {
            console.log("Fetching room type distribution");
            const result = await this.orm.call(
                'hotel.room.result',
                'get_room_type_distribution',
                [this.env.services.company.currentCompany.id]
            );
            
            this.state.roomTypeDistribution = result;
            console.log("Received room type distribution:", result);
        } catch (error) {
            console.error("Error fetching room type distribution:", error);
        }
    }

    async fetchRoomStatusByType() {
        try {
            console.log("Fetching room status by type");
            const result = await this.orm.call(
                'hotel.room.result',
                'get_room_status_by_type',
                [this.env.services.company.currentCompany.id]
            );
            
            this.state.roomStatusByType = result;
            console.log("Received room status by type:", result);
        } catch (error) {
            console.error("Error fetching room status by type:", error);
        }
    }

    async fetchAvailabilityTimeline() {
        try {
            console.log("Fetching availability timeline");
            const result = await this.orm.call(
                'hotel.room.result',
                'get_availability_timeline',
                [this.env.services.company.currentCompany.id, 30]  // Fetch next 30 days
            );
            
            this.state.availabilityTimeline = result;
            console.log("Received availability timeline:", result);
        } catch (error) {
            console.error("Error fetching availability timeline:", error);
        }
    }

    renderRoomOccupancyChart() {
        const ctx = document.getElementById('roomOccupancyChart');
        if (!ctx) return;

        if (window.Chart) {
            new window.Chart(ctx, {
                type: 'pie',
                data: {
                    labels: ['Occupied', 'Available'],
                    datasets: [{
                        data: [this.state.inhouse, this.state.available],
                        backgroundColor: ['#FF6384', '#36A2EB']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        },
                        title: {
                            display: true,
                            text: 'Room Occupancy'
                        }
                    }
                }
            });
        }
    }

    renderRoomOccupancyStatusChart() {
        try {
            const ctx = document.getElementById('roomOccupancyStatusChart');
            if (!ctx) {
                console.error('Canvas element for room occupancy status chart not found');
                return;
            }

            if (window.Chart) {
                const data = [
                    this.state.inhouse,
                    this.state.available,
                    this.state.reserved,
                    this.state.out_of_order,
                    this.state.house_use_count,
                    this.state.complementary_use_count
                ];
                
                this.charts.occupancyStatus = new window.Chart(ctx, {
                    type: 'pie',
                    data: {
                        labels: [
                            'In-house',
                            'Available',
                            'Reserved',
                            'Out of Order',
                            'House Use',
                            'Complementary'
                        ],
                        datasets: [{
                            data: data,
                            backgroundColor: [
                                '#4CAF50',  // Green for in-house
                                '#2196F3',  // Blue for available
                                '#FFC107',  // Amber for reserved
                                '#F44336',  // Red for out of order
                                '#9C27B0',  // Purple for house use
                                '#FF9800'   // Orange for complementary
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        layout: {
                            padding: {
                                right: 100  // Add padding for legend
                            }
                        },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'right',
                                labels: {
                                    padding: 20,
                                    generateLabels: function(chart) {
                                        const datasets = chart.data.datasets;
                                        const labels = chart.data.labels;
                                        const total = datasets[0].data.reduce((a, b) => a + b, 0);
                                        
                                        return labels.map((label, i) => ({
                                            text: `${label}: ${datasets[0].data[i]} (${((datasets[0].data[i]/total)*100).toFixed(1)}%)`,
                                            fillStyle: datasets[0].backgroundColor[i],
                                            strokeStyle: datasets[0].backgroundColor[i],
                                            lineWidth: 0,
                                            hidden: false,
                                            index: i
                                        }));
                                    },
                                    font: {
                                        size: 12
                                    },
                                    color: '#333'
                                }
                            },
                            title: {
                                display: true,
                                text: 'Room Occupancy Status Distribution',
                                padding: {
                                    top: 10,
                                    bottom: 30
                                },
                                font: {
                                    size: 16,
                                    weight: 'bold'
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.raw || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return `${label}: ${value} (${percentage}%)`;
                                    }
                                }
                            },
                            datalabels: {
                                color: '#fff',
                                font: {
                                    weight: 'bold',
                                    size: 12
                                },
                                formatter: function(value, context) {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${percentage}%`;
                                }
                            }
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error rendering room occupancy status chart:', error);
        }
    }

    async renderDailyOccupancyChart() {
        try {
            const ctx = document.getElementById('dailyOccupancyChart');
            if (!ctx) {
                console.error('Canvas element for daily occupancy chart not found');
                return;
            }

            if (window.Chart) {
                this.charts.dailyOccupancy = new window.Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: this.state.occupancyHistory.dates,
                        datasets: [{
                            label: 'Occupancy Rate (%)',
                            data: this.state.occupancyHistory.rates,
                            backgroundColor: '#2196F3',
                            borderColor: '#1976D2',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            title: {
                                display: true,
                                text: 'Daily Occupancy Rate Trend',
                                padding: {
                                    top: 10,
                                    bottom: 30
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                },
                                title: {
                                    display: true,
                                    text: 'Occupancy Rate'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Date'
                                }
                            }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return `Occupancy: ${context.raw}%`;
                                    }
                                }
                            },
                            datalabels: {
                                anchor: 'end',
                                align: 'top',
                                formatter: function(value) {
                                    return value + '%';
                                },
                                font: {
                                    weight: 'bold'
                                },
                                color: '#1976D2'
                            }
                        }
                    },
                    plugins: [{
                        afterDraw: function(chart) {
                            var ctx = chart.ctx;
                            chart.data.datasets.forEach(function(dataset) {
                                chart.getDatasetMeta(0).data.forEach(function(bar, index) {
                                    var data = dataset.data[index];
                                    ctx.fillStyle = '#1976D2';
                                    ctx.textAlign = 'center';
                                    ctx.textBaseline = 'bottom';
                                    ctx.font = 'bold 12px Arial';
                                    ctx.fillText(data + '%', bar.x, bar.y - 5);
                                });
                            });
                        }
                    }]
                });
            }
        } catch (error) {
            console.error('Error rendering daily occupancy chart:', error);
        }
    }

    async renderArrivalsVsDeparturesChart() {
        try {
            const ctx = document.getElementById('arrivalsVsDeparturesChart');
            if (!ctx) {
                console.error('Canvas element not found: arrivalsVsDeparturesChart');
                return;
            }

            this.charts.arrivalsVsDepartures = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: this.state.arrivalsVsDepartures.dates,
                    datasets: [{
                        label: 'Arrivals',
                        data: this.state.arrivalsVsDepartures.arrivals,
                        backgroundColor: 'rgba(75, 192, 192, 0.8)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    }, {
                        label: 'Departures',
                        data: this.state.arrivalsVsDepartures.departures,
                        backgroundColor: 'rgba(255, 99, 132, 0.8)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering arrivals vs departures chart:', error);
        }
    }

    async renderRoomTypeDistributionChart() {
        try {
            const ctx = document.getElementById('roomTypeDistributionChart');
            if (!ctx) {
                console.error('Canvas element not found: roomTypeDistributionChart');
                return;
            }

            this.charts.roomTypeDistribution = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: this.state.roomTypeDistribution.types,
                    datasets: [{
                        data: this.state.roomTypeDistribution.counts,
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.8)',
                            'rgba(54, 162, 235, 0.8)',
                            'rgba(255, 206, 86, 0.8)',
                            'rgba(75, 192, 192, 0.8)',
                            'rgba(153, 102, 255, 0.8)'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top'
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering room type distribution chart:', error);
        }
    }

    async renderRoomStatusByTypeChart() {
        try {
            const ctx = document.getElementById('roomStatusByTypeChart');
            if (!ctx) {
                console.error('Canvas element not found: roomStatusByTypeChart');
                return;
            }

            this.charts.roomStatusByType = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: this.state.roomStatusByType.types,
                    datasets: [{
                        label: 'Available',
                        data: this.state.roomStatusByType.available,
                        backgroundColor: 'rgba(75, 192, 192, 0.8)',
                        stack: 'Stack 0',
                    }, {
                        label: 'Occupied',
                        data: this.state.roomStatusByType.occupied,
                        backgroundColor: 'rgba(255, 99, 132, 0.8)',
                        stack: 'Stack 0',
                    }, {
                        label: 'Reserved',
                        data: this.state.roomStatusByType.reserved,
                        backgroundColor: 'rgba(255, 206, 86, 0.8)',
                        stack: 'Stack 0',
                    }, {
                        label: 'Out of Order',
                        data: this.state.roomStatusByType.outOfOrder,
                        backgroundColor: 'rgba(153, 102, 255, 0.8)',
                        stack: 'Stack 0',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top'
                        }
                    },
                    scales: {
                        x: {
                            stacked: true
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering room status by type chart:', error);
        }
    }

    async renderRoomAvailabilityTimelineChart() {
        try {
            const ctx = document.getElementById('roomAvailabilityTimelineChart');
            if (!ctx) {
                console.error('Canvas element not found: roomAvailabilityTimelineChart');
                return;
            }

            this.charts.roomAvailabilityTimeline = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: this.state.availabilityTimeline.dates,
                    datasets: [{
                        label: 'Available Rooms',
                        data: this.state.availabilityTimeline.available,
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        fill: true
                    }, {
                        label: 'Total Rooms',
                        data: this.state.availabilityTimeline.total,
                        borderColor: 'rgba(153, 102, 255, 1)',
                        backgroundColor: 'rgba(153, 102, 255, 0.2)',
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering room availability timeline chart:', error);
        }
    }

    renderRevenueGauge() {
        const ctx = document.getElementById('revenueGauge');
        if (!ctx) return;

        if (window.Chart) {
            new window.Chart(ctx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [this.state.expected_occupied_rate, 100 - this.state.expected_occupied_rate],
                        backgroundColor: ['#4CAF50', '#EEEEEE']
                    }]
                },
                options: {
                    circumference: 180,
                    rotation: -90,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Occupancy Rate'
                        }
                    }
                }
            });
        }
    }

    /* Date: 2025-01-13 Time: 01:18:18
     * Method to cleanup existing charts before re-rendering
     */
    cleanupCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.destroy();
            }
        });
    }

    async getArrivalsVsDepartures() {
        try {
            const result = await this.orm.call(
                'hotel.room.result',
                'get_arrivals_departures_history',
                [this.env.services.company.currentCompany.id]
            );

            const ctx = document.getElementById('arrivalsVsDeparturesChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: result.dates,
                    datasets: [{
                        label: 'Arrivals',
                        data: result.arrivals,
                        backgroundColor: 'rgba(75, 192, 192, 0.8)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    }, {
                        label: 'Departures',
                        data: result.departures,
                        backgroundColor: 'rgba(255, 99, 132, 0.8)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error fetching arrivals vs departures data:', error);
        }
    }

    async getRoomTypeDistribution() {
        try {
            const result = await this.orm.call(
                'hotel.room.result',
                'get_room_type_distribution',
                [this.env.services.company.currentCompany.id]
            );

            const ctx = document.getElementById('roomTypeDistributionChart').getContext('2d');
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: result.types,
                    datasets: [{
                        data: result.counts,
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.8)',
                            'rgba(54, 162, 235, 0.8)',
                            'rgba(255, 206, 86, 0.8)',
                            'rgba(75, 192, 192, 0.8)',
                            'rgba(153, 102, 255, 0.8)'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: false
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error fetching room type distribution data:', error);
        }
    }

    async getRoomStatusByType() {
        try {
            const result = await this.orm.call(
                'hotel.room.result',
                'get_room_status_by_type',
                [this.env.services.company.currentCompany.id]
            );

            const ctx = document.getElementById('roomStatusByTypeChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: result.types,
                    datasets: [{
                        label: 'Available',
                        data: result.available,
                        backgroundColor: 'rgba(75, 192, 192, 0.8)',
                        stack: 'Stack 0',
                    }, {
                        label: 'Occupied',
                        data: result.occupied,
                        backgroundColor: 'rgba(255, 99, 132, 0.8)',
                        stack: 'Stack 0',
                    }, {
                        label: 'Reserved',
                        data: result.reserved,
                        backgroundColor: 'rgba(255, 206, 86, 0.8)',
                        stack: 'Stack 0',
                    }, {
                        label: 'Out of Order',
                        data: result.outOfOrder,
                        backgroundColor: 'rgba(153, 102, 255, 0.8)',
                        stack: 'Stack 0',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            stacked: true,
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error fetching room status by type data:', error);
        }
    }

    async getRoomAvailabilityTimeline() {
        try {
            const result = await this.orm.call(
                'hotel.room.result',
                'get_availability_timeline',
                [this.env.services.company.currentCompany.id]
            );

            const ctx = document.getElementById('roomAvailabilityTimelineChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: result.dates,
                    datasets: [{
                        label: 'Available Rooms',
                        data: result.available,
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        fill: true
                    }, {
                        label: 'Total Rooms',
                        data: result.total,
                        borderColor: 'rgba(153, 102, 255, 1)',
                        backgroundColor: 'rgba(153, 102, 255, 0.2)',
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error fetching room availability timeline data:', error);
        }
    }

    async start() {
        await this._super(...arguments);
        await this._getInitialState();
        this.getOccupancyStatusChart();
        this.getDailyOccupancyChart();
        this.getArrivalsVsDepartures();
        this.getRoomTypeDistribution();
        this.getRoomStatusByType();
        this.getRoomAvailabilityTimeline();
    }

    cleanupCharts() {
        const charts = [
            'roomOccupancyStatusChart',
            'dailyOccupancyChart',
            'arrivalsVsDeparturesChart',
            'roomTypeDistributionChart',
            'roomStatusByTypeChart',
            'roomAvailabilityTimelineChart'
        ];
        
        charts.forEach(chartId => {
            const chartElement = document.getElementById(chartId);
            if (chartElement) {
                const chart = Chart.getChart(chartElement);
                if (chart) {
                    chart.destroy();
                }
            }
        });
    }
}

CustomDashBoard.template = 'CustomDashBoard';
registry.category("actions").add("custom_dashboard_tags", CustomDashBoard);