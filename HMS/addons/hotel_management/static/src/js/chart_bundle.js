/* Date: 2025-01-20 Time: 12:07:19 */
(function (global, factory) {
    typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory() :
    typeof define === 'function' && define.amd ? define(factory) :
    (global = typeof globalThis !== 'undefined' ? globalThis : global || self, global.Chart = factory());
})(this, (function () { 'use strict';

    // Import the minified version of Chart.js
    const script = document.createElement('script');
    script.src = '/hotel_management/static/lib/chartjs/chart.umd.js';
    document.head.appendChild(script);

    return window.Chart;
}));
