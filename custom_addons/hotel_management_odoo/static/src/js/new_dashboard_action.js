/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
const { Component, onWillStart, onMounted, useState } = owl;

// Date: 2025-01-20 Time: 13:58:41 - Added system date initialization
class NewDashBoard extends Component {
    setup() {
        this.orm = useService("orm");
        this.user = useService("user");
        this.notification = useService("notification");
        
        // Initialize state
        this.state = useState({
            startDate: '',
            endDate: '',
            isLoading: true,
            metrics: {
                total: 0,
                confirmed: 0,
                not_confirmed: 0,
                waiting: 0,
                cancelled: 0,
                blocked: 0,
                total_reservations: 0
            },
        inventoryData: [],
        forecastData: [],
        salesData: [],
        data: null
        });

        // Initialize charts object to store chart instances
        this.charts = {};

        onWillStart(async () => {
            try {
                // Get user's company info
                const userId = this.user.userId;
                const userInfo = await this.orm.call(
                    'res.users',
                    'read',
                    [[userId]],
                    { fields: ['company_id'] }
                );

                if (userInfo && userInfo.length > 0) {
                    const companyId = userInfo[0].company_id[0];
                    const companyData = await this.orm.call(
                        'res.company',
                        'search_read',
                        [[['id', '=', companyId]]],
                        { fields: ['system_date'] }
                    );

                    if (companyData && companyData.length > 0) {
                        const systemDate =
                          companyData[0].system_date ||
                          new Date().toISOString().split("T")[0];

                        // Set start date to 3 days before the system date
                        const startDate = new Date(systemDate);
                        console.log("START DATE", startDate);
                        startDate.setDate(startDate.getDate() - 3);
                        this.state.startDate = startDate
                          .toISOString()
                          .split("T")[0];

                        // Set end date to 3 days after the system date
                        const endDate = new Date(systemDate);
                        console.log("END DATE", endDate);
                        endDate.setDate(endDate.getDate() + 3);
                        this.state.endDate = endDate
                          .toISOString()
                          .split("T")[0];
                    }
                }

                // Fetch initial dashboard data
                await this.fetchData();
            } catch (error) {
                console.error('Error in onWillStart:', error);
            }
        });

        onMounted(() => {
            // Initialize charts after DOM is ready
            setTimeout(() => {
                this.initializeCharts();
            }, 500);
        });
    }

    initializeCharts() {
        console.log('Initializing charts...');
        return new Promise((resolve, reject) => {
            try {
                const chartConfigs = {
                    occupancyChart: {
                        type: 'line',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    max: 100
                                }
                            }
                        }
                    },
                    marketSegmentChart: {
                        type: 'pie',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    position: 'right'
                                },
                                tooltip: {
                                    enabled: true,
                                    callbacks: {
                                        label: function(context) {
                                            const value = context.raw;
                                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                            const percentage = ((value * 100) / total).toFixed(1);
                                            return `${context.label}: ${value} (${percentage}%)`;
                                        }
                                    }
                                },
                                datalabels: {
                                    display: true,
                                    color: 'white',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    },
                                    textAlign: 'center',
                                    textStrokeColor: 'black',
                                    textStrokeWidth: 1,
                                    formatter: function(value, context) {
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value * 100) / total).toFixed(1);
                                        return `${value}\n${percentage}%`;
                                    },
                                    anchor: 'center',
                                    align: 'center',
                                    offset: 0,
                                    rotation: 0
                                }
                            }
                        }
                    },
                businessSourceChart: {
                        type: 'bar',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true
                                }
                            },
                            plugins: {
                                legend: {
                                    display: true,
                                    position: 'top'
                                },
                                datalabels: {
                                    display: true,
                                    color: 'black',
                                    anchor: 'end',
                                    align: 'top',
                                    offset: 4,
                                    font: {
                                        weight: 'bold',
                                        size: 11
                                    },
                                    formatter: function(value) {
                                        return value.toFixed(0);
                                    }
                                }
                            }
                        }
                    },
                    expectationsChart: {
                        type: 'line',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    max: 100
                                }
                            }
                        }
                    },
                    countryChart: {
                        type: 'bar',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            indexAxis: 'y',  // Makes it a horizontal bar chart
                            scales: {
                                x: {
                                    beginAtZero: true,
                                    title: {
                                        display: true,
                                        text: 'Number of Bookings'
                                    }
                                }
                            },
                            plugins: {
                                legend: {
                                    display: false
                                },
                                title: {
                                    display: true,
                                    text: 'Bookings by Country'
                                }
                            }
                        }
                    },
                    arrivalDepartureChart: {
                        type: 'bar',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                x: {
                                    title: {
                                        display: true,
                                        text: 'Date'
                                    }
                                },
                                y: {
                                    title: {
                                        display: true,
                                        text: 'Count'
                                    },
                                    beginAtZero: true
                                }
                            },
                            plugins: {
                                legend: {
                                    display: true,
                                    position: 'top'
                                },
                                datalabels: {
                                    display: true,
                                    color: 'black',
                                    anchor: 'end',
                                    align: 'top',
                                    offset: 4,
                                    font: {
                                        weight: 'bold',
                                        size: 11
                                    },
                                    formatter: function(value) {
                                        return value.toFixed(0);
                                    }
                                }
                            }
                        }
                    },
                    roomTypeDistribution: {
                        type: 'bar',
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                x: { title: { display: true, text: 'Date' }},
                                y: { title: { display: true, text: 'Count' }, beginAtZero: true }
                            }
                        }
                    },
                    inventoryChart: {
                            type: 'doughnut',
                            options: { responsive: true, plugins: { datalabels: { display: true, color: 'black' } } },
                        },
                        forecastChart: {
                        type: 'bar',
                        options: {
                            responsive: true,
                            plugins: {
                                legend: {
                                    display: false  // Hide legend since it's showing undefined
                                },
                                tooltip: {
                                    enabled: true
                                },
                                datalabels: {
                                    display: true,
                                    color: 'black',
                                    anchor: 'end',
                                    align: 'top',
                                    offset: 4,
                                    font: {
                                        weight: 'bold',
                                        size: 12
                                    },
                                    formatter: function(value) {
                                        return value;
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: {
                                        display: true,
                                        text: 'Count'
                                    }
                                }
                            }
                            }
                        },
                        salesChart: {
                        type: 'pie',
                        options: {
                            responsive: true,
                            plugins: {
                                legend: {
                                    position: 'top',
                                },
                                tooltip: {
                                    enabled: true
                                },
                                datalabels: {
                                    display: true,
                                    color: 'white',
                                    font: {
                                        weight: 'bold',
                                        size: 14
                                    },
                                    formatter: function(value, context) {
                                        const dataset = context.dataset;
                                        const total = dataset.data.reduce((acc, data) => acc + data, 0);
                                        const percentage = ((value * 100) / total).toFixed(1);
                                        return percentage + '%';
                                    }
                                }
                            }
                        }
                    },
                };

                // Initialize each chart
                Object.entries(chartConfigs).forEach(([chartId, config]) => {
                    const canvas = document.getElementById(chartId);
                    if (!canvas) {
                        console.warn(`${chartId} canvas not found`);
                        return;
                    }

                    const ctx = canvas.getContext('2d');
                    if (!ctx) {
                        console.warn(`Could not get 2D context for ${chartId}`);
                        return;
                    }

                    // Destroy existing chart if it exists
                    if (this.charts[chartId]) {
                        this.charts[chartId].destroy();
                    }

                    this.charts[chartId] = new Chart(ctx, {
                        type: config.type,
                        data: {
                            labels: [],
                            datasets: [{
                                data: [],
                                backgroundColor: [
                                    '#4e73df',
                                    '#1cc88a',
                                    '#36b9cc',
                                    '#f6c23e',
                                    '#e74a3b'
                                ]
                            }]
                        },
                        options: config.options
                    });
                });

                // Update charts with initial data
                if (this.state.data) {
                    this.updateCharts(this.state.data);
                }
                resolve();
            } catch (error) {
                console.error('Error initializing charts:', error);
                reject(error);
            }
        });
    }

    async fetchData() {
        try {
            console.log('Fetching dashboard data with dates:', {
                startDate: this.state.startDate,
                endDate: this.state.endDate
            });
            
            this.state.isLoading = true;
            const data = await this.orm.call(
                'room.booking.dashboard',
                'get_dashboard_data',
                [{
                    start_date: this.state.startDate || false,
                    end_date: this.state.endDate || false
                }]
            );
            
            console.log('Received dashboard data:', data);
            
            if (!data) {
                throw new Error('No data received from server');
            }
            
            // Store the complete data in state
            this.state.data = data;
            this.state.inventoryData = data.inventoryData || [];
            this.state.forecastData = data.forecastData || [];
            this.state.salesData = data.salesData || [];
            
            // Update metrics
            this.state.metrics = {
                total: data.total || 0,
                confirmed: data.confirmed || 0,
                not_confirmed: data.not_confirmed || 0,
                waiting: data.waiting || 0,
                cancelled: data.cancelled || 0,
                blocked: data.blocked || 0,
                total_reservations: data.total_reservations || 0
            };

            // Update charts if they exist
            if (Object.keys(this.charts).length > 0) {
                await this.updateCharts(this.state.data);
            }
            
            console.log('Dashboard state updated successfully');
            
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            this.notification.add(_t('Failed to fetch dashboard data. Please check browser console for details.'), {
                type: 'danger',
                sticky: true,
            });
        } finally {
            this.state.isLoading = false;
        }
    }

    async applyDateFilter() {
        try {
            console.log('Applying date filter...');
            if (!this.state.startDate || !this.state.endDate) {
                throw new Error('Please select both start and end dates');
            }
            
            // Show loading state
            this.state.isLoading = true;
            
            // Fetch new data and update charts
            await this.fetchData();

//            // Wait for the DOM to fully render before initializing charts
//            setTimeout(() => {
//                this.initializeCharts();
//            }, 1000);
            setTimeout(() => {
            if (document.getElementById('inventoryChart')) {
                this.initializeCharts();
            }
            }, 500);

            
            console.log('Date filter applied successfully');
        } catch (error) {
            console.error('Error applying date filter:', error);
            this.notification.add(error.message || _t('Failed to apply date filter. Please try again.'), {
                type: 'danger',
                sticky: false,
            });
        } finally {
            // Hide loading state
            this.state.isLoading = false;
        }
    }

    updateCharts(data) {
        console.log('Updating charts with data:', data);
        try {
          if (
            this.charts.countryChart &&
            data.country_data &&
            data.country_labels
          ) {
            console.log("Updating country chart:", {
              labels: data.country_labels,
              data: data.country_data,
            });

            this.charts.countryChart.data = {
              labels: data.country_labels,
              datasets: [
                {
                  label: "Bookings by Country",
                  data: data.country_data,
                  backgroundColor: "#36b9cc",
                  borderColor: "#36b9cc",
                  borderWidth: 1,
                },
              ],
            };
            this.charts.countryChart.update("none");
          }

          // Update Occupancy Chart
          if (
            this.charts.occupancyChart &&
            data.occupancy_data &&
            data.occupancy_labels
          ) {
            console.log("Updating occupancy chart:", {
              labels: data.occupancy_labels,
              data: data.occupancy_data,
            });

            this.charts.occupancyChart.data = {
              labels: data.occupancy_labels,
              datasets: [
                {
                  label: "Occupancy Rate (%)",
                  data: data.occupancy_data,
                  borderColor: "#4e73df",
                  backgroundColor: "rgba(78, 115, 223, 0.2)",
                  borderWidth: 2,
                  fill: true,
                },
              ],
            };
            this.charts.occupancyChart.update("none"); // Use 'none' animation for faster updates
          }

          // Update Market Segment Chart
          if (
            this.charts.marketSegmentChart &&
            data.segment_data &&
            data.segment_labels
          ) {
            console.log("Updating segment chart:", {
              labels: data.segment_labels,
              data: data.segment_data,
            });

            this.charts.marketSegmentChart.data = {
              labels: data.segment_labels,
              datasets: [
                {
                  data: data.segment_data,
                  backgroundColor: [
                    "#4e73df",
                    "#1cc88a",
                    "#36b9cc",
                    "#f6c23e",
                    "#e74a3b",
                  ],
                },
              ],
            };
            this.charts.marketSegmentChart.update("none");
          }

          // Update Business Source Chart
          if (
            this.charts.businessSourceChart &&
            data.source_data &&
            data.source_labels
          ) {
            console.log("Updating source chart:", {
              labels: data.source_labels,
              data: data.source_data,
            });

            this.charts.businessSourceChart.data = {
              labels: data.source_labels,
              datasets: [
                {
                  label: "Bookings by Source",
                  data: data.source_data,
                  backgroundColor: "#4e73df",
                  borderColor: "#4e73df",
                  borderWidth: 1,
                },
              ],
            };
            this.charts.businessSourceChart.update("none");
          }

          // Update Expectations Chart
          if (
            this.charts.expectationsChart &&
            data.expectation_data &&
            data.expectation_labels
          ) {
            console.log("Updating expectations chart:", {
              labels: data.expectation_labels,
              data: data.expectation_data,
            });

            this.charts.expectationsChart.data = {
              labels: data.expectation_labels,
              datasets: [
                {
                  label: "Expected Occupancy (%)",
                  data: data.expectation_data,
                  borderColor: "#1cc88a",
                  backgroundColor: "rgba(28, 200, 138, 0.2)",
                  borderWidth: 2,
                  fill: true,
                },
              ],
            };
            this.charts.expectationsChart.update("none");
          }
          // Update Arrival vs Departure Chart
        if (this.charts.arrivalDepartureChart && data.arrival_labels && data.arrival_data && data.departure_data) {
            this.charts.arrivalDepartureChart.data = {
                labels: data.arrival_labels.map((date) => this.formatDate(date)),
                datasets: [
                    {
                        label: "Arrivals",
                        data: data.arrival_data,
                        backgroundColor: "rgba(54, 162, 235, 0.7)",
                        borderColor: "rgba(54, 162, 235, 1)",
                        borderWidth: 1,
                    },
                    {
                        label: "Departures",
                        data: data.departure_data,
                        backgroundColor: "rgba(255, 99, 132, 0.7)",
                        borderColor: "rgba(255, 99, 132, 1)",
                        borderWidth: 1,
                    },
                ],
            };
            this.charts.arrivalDepartureChart.update();
        }
        if (this.charts.roomTypeDistribution && data.room_type_data) {
                    // ✅ Helper Function to Generate Random Colors
           function getRandomColorForRoomType() {
                    const r = Math.floor(Math.random() * 256);
                    const g = Math.floor(Math.random() * 256);
                    const b = Math.floor(Math.random() * 256);
                    return `rgba(${r}, ${g}, ${b}, 0.7)`; // 70% opacity for better visualization
           }

            console.log("Updating Room Type Distribution Chart with Backend Data:", data.room_type_data);

            // ✅ Extract Dates (Labels) and Room Types (Datasets)
            const labels = Object.keys(data.room_type_data); // Dates like '2025-01-01', '2025-01-02', etc.

            // ✅ Gather all unique room types across all dates
            const allRoomTypes = new Set();
            labels.forEach(date => {
                const roomTypes = data.room_type_data[date];
                Object.keys(roomTypes).forEach(type => allRoomTypes.add(type));
            });

            // ✅ Create datasets for each room type
            const datasets = Array.from(allRoomTypes).map(roomType => {
                const roomTypeCounts = labels.map(date => data.room_type_data[date][roomType] || 0); // Get count or 0 if missing
                return {
                    label: roomType,
                    data: roomTypeCounts,
                    backgroundColor: getRandomColorForRoomType(), // ✅ Generate random color for each room type
                    borderColor: getRandomColorForRoomType(),
                    borderWidth: 1
                };
            });

            // ✅ Update Chart.js Data
            this.charts.roomTypeDistribution.data = {
                labels: labels, // Dates on the X-axis
                datasets: datasets
            };

            // ✅ Update the Chart
            this.charts.roomTypeDistribution.update();
        }
        const { inventoryData, forecastData, salesData } = this.state;

        if (this.charts.inventoryChart) {
            this.charts.inventoryChart.data = {
                labels: ['Total Room', 'Out of Service', 'Out of Order', 'House Use', 'Availability'],
                datasets: [{
                    data: [inventoryData.totalRoom, inventoryData.outOfService, inventoryData.outOfOrder, inventoryData.houseUse, inventoryData.availability],
                    backgroundColor: ['#4e73df', '#e74a3b', '#f6c23e', '#36b9cc', '#1cc88a']
                }]
            };
            this.charts.inventoryChart.update();
        }

        if (this.charts.forecastChart) {
            this.charts.forecastChart.data = {
                labels: ['In House', 'Out of Service', 'Out of Order', 'House Use', 'Availability'],
                datasets: [{
                    data: [forecastData.InHouse, forecastData.outOfService, forecastData.outOfOrder, forecastData.houseUse, forecastData.availability],
                    backgroundColor: '#36b9cc'
                }]
            };
            this.charts.forecastChart.update();
        }

        if (this.charts.salesChart) {
            this.charts.salesChart.data = {
                labels: ['Overbooked', 'Free to Sell'],
                datasets: [{
                    data: [salesData.overbooked, salesData.freeToSell],
                    backgroundColor: ['#e74a3b', '#1cc88a']
                }]
            };
            this.charts.salesChart.update();
        }



          console.log("Charts updated successfully");
        } catch (error) {
            console.error('Error updating charts:', error);
            this.notification.add(_t('Failed to update charts. Please check console for details.'), {
                type: 'warning',
                sticky: false,
            });
        }
    }

    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            const day = date.getDate().toString().padStart(2, '0');
            const month = date.toLocaleString('default', { month: 'short' }); // Example: Jan, Feb
            return `${day}-${month}`;
        } catch (error) {
            console.error('Error formatting date:', error);
            return dateString; // Return the original string if an error occurs
        }
    }
}

// Date: 2025-01-20 Time: 13:58:41 - Fixed template and action registration
NewDashBoard.template = 'hotel_management_odoo.NewDashBoard';
NewDashBoard.components = {};

// Register the client action with the correct name
registry.category("actions").add("hotel_management_odoo.new_dashboard_action", NewDashBoard);

export default NewDashBoard;
