/* Date: 2025-01-20 Time: 12:18:50 */
odoo.define('hotel_management_odoo.ChartWrapper', function (require) {
    'use strict';

    // Original code - Date: 2025-01-20 Time: 12:04:09
    // const { Chart, registerables } = require('hotel_management_odoo/static/lib/chartjs/chart.js');
    // Chart.register(...registerables);
    
    // Return the global Chart instance from the UMD bundle
    const Chart = window.Chart;
    if (!Chart) {
        console.error('Chart.js not found! Make sure chart.umd.js is loaded before this file.');
    }
    
    return Chart;
});
