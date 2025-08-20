/* Date: 2025-01-20 Time: 12:16:15 */
odoo.define('hotel_management.ChartInit', function (require) {
    'use strict';

    // Load dependencies
    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');

    // Create a Chart.js initializer
    const ChartInitializer = AbstractAction.extend({
        start: function () {
            return new Promise((resolve) => {
                if (window.Chart) {
                    resolve(window.Chart);
                } else {
                    // If Chart is not loaded yet, wait for it
                    const checkChart = setInterval(() => {
                        if (window.Chart) {
                            clearInterval(checkChart);
                            resolve(window.Chart);
                        }
                    }, 100);
                }
            });
        }
    });

    // Register the action
    core.action_registry.add('hotel_management.ChartInit', ChartInitializer);

    return ChartInitializer;
});
