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
                        const systemDate = companyData[0].system_date || new Date().toISOString().split('T')[0];
                        
                        // Set start date to first day of the month
                        const startDate = new Date(systemDate);
                        startDate.setDate(1);
                        this.state.startDate = startDate.toISOString().split('T')[0];
                        
                        // Set end date to last day of the month
                        const endDate = new Date(systemDate);
                        endDate.setMonth(endDate.getMonth() + 1);
                        endDate.setDate(0);
                        this.state.endDate = endDate.toISOString().split('T')[0];
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
            }, 100);
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
                            maintainAspectRatio: false
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
                    }
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
                this.updateCharts(this.state.data);
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
            // Wait for the DOM to fully render before initializing charts
            setTimeout(() => {
                this.initializeCharts();
            }, 100);
            
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
            // Update Occupancy Chart
            if (this.charts.occupancyChart && data.occupancy_data && data.occupancy_labels) {
                console.log('Updating occupancy chart:', {
                    labels: data.occupancy_labels,
                    data: data.occupancy_data
                });
                
                this.charts.occupancyChart.data = {
                    labels: data.occupancy_labels,
                    datasets: [{
                        label: 'Occupancy Rate (%)',
                        data: data.occupancy_data,
                        borderColor: '#4e73df',
                        backgroundColor: 'rgba(78, 115, 223, 0.2)',
                        borderWidth: 2,
                        fill: true
                    }]
                };
                this.charts.occupancyChart.update('none'); // Use 'none' animation for faster updates
            }

            // Update Market Segment Chart
            if (this.charts.marketSegmentChart && data.segment_data && data.segment_labels) {
                console.log('Updating segment chart:', {
                    labels: data.segment_labels,
                    data: data.segment_data
                });
                
                this.charts.marketSegmentChart.data = {
                    labels: data.segment_labels,
                    datasets: [{
                        data: data.segment_data,
                        backgroundColor: [
                            '#4e73df',
                            '#1cc88a',
                            '#36b9cc',
                            '#f6c23e',
                            '#e74a3b'
                        ]
                    }]
                };
                this.charts.marketSegmentChart.update('none');
            }

            // Update Business Source Chart
            if (this.charts.businessSourceChart && data.source_data && data.source_labels) {
                console.log('Updating source chart:', {
                    labels: data.source_labels,
                    data: data.source_data
                });
                
                this.charts.businessSourceChart.data = {
                    labels: data.source_labels,
                    datasets: [{
                        label: 'Bookings by Source',
                        data: data.source_data,
                        backgroundColor: '#4e73df',
                        borderColor: '#4e73df',
                        borderWidth: 1
                    }]
                };
                this.charts.businessSourceChart.update('none');
            }

            // Update Expectations Chart
            if (this.charts.expectationsChart && data.expectation_data && data.expectation_labels) {
                console.log('Updating expectations chart:', {
                    labels: data.expectation_labels,
                    data: data.expectation_data
                });
                
                this.charts.expectationsChart.data = {
                    labels: data.expectation_labels,
                    datasets: [{
                        label: 'Expected Occupancy (%)',
                        data: data.expectation_data,
                        borderColor: '#1cc88a',
                        backgroundColor: 'rgba(28, 200, 138, 0.2)',
                        borderWidth: 2,
                        fill: true
                    }]
                };
                this.charts.expectationsChart.update('none');
            }

            console.log('Charts updated successfully');
        } catch (error) {
            console.error('Error updating charts:', error);
            this.notification.add(_t('Failed to update charts. Please check console for details.'), {
                type: 'warning',
                sticky: false,
            });
        }
    }
}

// Date: 2025-01-20 Time: 13:58:41 - Fixed template and action registration
NewDashBoard.template = 'hotel_management_odoo.NewDashBoard';
NewDashBoard.components = {};

// Register the client action with the correct name
registry.category("actions").add("hotel_management_odoo.new_dashboard_action", NewDashBoard);

export default NewDashBoard;
