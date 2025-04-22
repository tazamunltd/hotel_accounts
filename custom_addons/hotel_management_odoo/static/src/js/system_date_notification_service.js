/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

/**
 * Service for managing system date change notifications
 * Modified: 2025-01-15T00:30:58+05:00
 */
export const SystemDateNotificationService = {
    dependencies: ["notification"],
    
    start(env) {
        // Store last system date per company
        const lastSystemDates = new Map();
        
        // Global listeners for system date changes
        const systemDateListeners = new Set();

        return {
            /**
             * Check and broadcast system date change
             * @param {string} newSystemDate - New system date
             * @param {Object} companyInfo - Company information
             */
            broadcastSystemDateChange(newSystemDate, companyInfo) {
                if (!newSystemDate || !companyInfo || !companyInfo.id) {
                    console.warn("Invalid parameters for system date change broadcast", { newSystemDate, companyInfo });
                    return;
                }

                const companyId = companyInfo.id;
                const lastDate = lastSystemDates.get(companyId);

                console.log("Broadcasting system date change:", {
                    companyId,
                    companyName: companyInfo.name,
                    lastDate,
                    newSystemDate
                });

                // Only proceed if the system_date has actually changed for this company
                if (lastDate !== newSystemDate) {
                    console.log(`System date changed for company ${companyId}: ${lastDate} -> ${newSystemDate}`);
                    
                    const eventData = {
                        oldDate: lastDate || 'Initial',
                        newDate: newSystemDate,
                        companyName: companyInfo.name || 'Unknown Company',
                        companyId: companyId,
                        timestamp: new Date().toISOString()
                    };

                    // Update the stored system date for this company
                    lastSystemDates.set(companyId, newSystemDate);

                    // Only show notification if oldDate doesn't contain 'Initial'
                    if (!eventData.oldDate.includes('Initial')) {
                        // Show notification using Odoo's notification service
                        env.services.notification.add(
                            `System Date Changed: ${eventData.oldDate} → ${eventData.newDate}`,
                            {
                                type: 'warning',
                                title: `${companyInfo.name} - System Date Update`,
                                sticky: true
                            }
                        );
                    }

                    // Notify all registered listeners
                    console.log(`Broadcasting to ${systemDateListeners.size} listeners`);
                    systemDateListeners.forEach(listener => {
                        try {
                            listener(eventData);
                        } catch (error) {
                            console.error('Error in system date change listener:', error);
                        }
                    });
                } else {
                    console.log(`System date unchanged for company ${companyId}: ${newSystemDate}`);
                }
            },

            /**
             * Add a listener for system date changes
             * @param {Function} listener - Callback function for date changes
             */
            addSystemDateListener(listener) {
                systemDateListeners.add(listener);
                console.log(`Added system date listener. Total listeners: ${systemDateListeners.size}`);
            },

            /**
             * Remove a listener for system date changes
             * @param {Function} listener - Callback function to remove
             */
            removeSystemDateListener(listener) {
                systemDateListeners.delete(listener);
                console.log(`Removed system date listener. Total listeners: ${systemDateListeners.size}`);
            }
        };
    },
};

// Register the service
registry.category("services").add("system_date_notification", SystemDateNotificationService);
