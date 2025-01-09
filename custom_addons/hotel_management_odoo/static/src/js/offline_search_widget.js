/** @odoo-module **/

/**
 * Offline Search Widget - Hotel Management Module
 * 
 * Comprehensive error handling and logging for robust widget functionality
 * @version 1.1.0
 * @date 2025-01-08T16:55:00+05:00
 */

// Core Owl imports
import { Component, onWillStart, useState, onError } from "@odoo/owl";

// Utility imports
import { debounce } from "@web/core/utils/timing";

// Service imports
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Custom Error class for widget-specific errors
 * Provides more detailed error information
 */
class OfflineSearchWidgetError extends Error {
    constructor(message, code, details = {}) {
        super(message);
        this.name = 'OfflineSearchWidgetError';
        this.code = code;
        this.details = details;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Generates a comprehensive error log
     * @returns {Object} Detailed error information
     */
    toLogObject() {
        return {
            name: this.name,
            message: this.message,
            code: this.code,
            details: this.details,
            timestamp: this.timestamp,
            stack: this.stack
        };
    }
}

/**
 * OfflineSearchWidget: Main component for hotel booking and guest information
 * 
 * @class
 * @extends Component
 */
export class OfflineSearchWidget extends Component {
    /**
     * Prop Definitions
     * Allows flexible configuration of the widget
     */
    static props = {
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
        options: { type: Object, optional: true }
    };

    /**
     * Default Props Configuration
     */
    static defaultProps = {
        readonly: false,
        options: {}
    };

    /**
     * Component Setup Method with Enhanced Error Handling
     * @date 2025-01-08T16:55:00+05:00
     */
    setup() {
        // Initialize error tracking services
        this.notification = useService('notification');
        this.orm = useService('orm');

        // Initialize state with comprehensive error tracking
        this.state = useState({
            // Core data fields
            hotel: "",
            hotels: [],
            
            // Booking details
            dateOfOrder: new Date().toISOString().slice(0, 16),
            checkInDate: "",
            noOfNights: 1,
            checkOutDate: "",
            
            // Guest information
            rooms: 1,
            adults: 1,
            children: 0,
            infants: 0,
            
            // Room and search data
            roomTypes: [],
            searchResults: [],
            
            // Error and system state tracking
            isLoading: false,
            hasError: false,
            errorMessage: null,
            errorDetails: null,
            
            // Additional system fields
            systemDate: null,
            readonly: this.props.readonly || false
        });

        // Global error handler for the widget
        onError((error) => {
            this.handleWidgetError(error);
        });

        // Lifecycle hook with enhanced error management
        onWillStart(async () => {
            this.state.isLoading = true;
            this.state.hasError = false;
            this.state.errorMessage = null;

            try {
                await Promise.all([
                    this.fetchCompanies(),
                    this.fetchRoomTypes()
                ]);
            } catch (error) {
                this.handleWidgetError(error);
            } finally {
                this.state.isLoading = false;
            }
        });
    }

    /**
     * Centralized Error Handling Method
     * @param {Error} error - The error to be handled
     */
    handleWidgetError(error) {
        // Convert to custom error if not already
        const widgetError = error instanceof OfflineSearchWidgetError 
            ? error 
            : new OfflineSearchWidgetError(
                error.message || 'Unexpected Widget Error', 
                'WIDGET_UNKNOWN_ERROR',
                { originalError: error }
            );

        // Update widget state
        this.state.hasError = true;
        this.state.errorMessage = widgetError.message;
        this.state.errorDetails = widgetError.toLogObject();

        // Log to console for debugging
        console.error('Offline Search Widget Error:', widgetError.toLogObject());

        // Show user-friendly notification
        this.notification.add(_t('An error occurred in the Offline Search Widget. Please try again.'), {
            type: 'danger',
            sticky: false
        });
    }

    /**
     * Fetch Companies with Robust Error Handling
     * @throws {OfflineSearchWidgetError}
     */
    async fetchCompanies() {
        try {
            const companies = await this.orm.searchRead(
                'res.company',
                [],
                ['id', 'name', 'system_date'],
                { order: 'name ASC', limit: 100 }
            );

            if (!companies || companies.length === 0) {
                throw new OfflineSearchWidgetError(
                    'No companies found',
                    'FETCH_COMPANIES_EMPTY',
                    { searchDomain: [] }
                );
            }

            this.state.hotels = companies;
            this.initializeDefaultHotel(companies[0]);

        } catch (error) {
            throw new OfflineSearchWidgetError(
                'Failed to fetch companies',
                'FETCH_COMPANIES_FAILED',
                { 
                    originalError: error.message,
                    stack: error.stack 
                }
            );
        }
    }

    /**
     * Initialize Default Hotel with Comprehensive Validation
     * @param {Object} firstCompany - First company from the list
     */
    initializeDefaultHotel(firstCompany) {
        if (!firstCompany) {
            throw new OfflineSearchWidgetError(
                'Cannot initialize default hotel',
                'INIT_HOTEL_FAILED',
                { reason: 'No company data available' }
            );
        }

        this.state.hotel = firstCompany.id;
        
        // Validate and set system date
        if (firstCompany.system_date) {
            try {
                const systemDate = new Date(firstCompany.system_date);
                
                if (isNaN(systemDate.getTime())) {
                    throw new Error('Invalid date format');
                }

                this.state.systemDate = systemDate.toISOString().slice(0, 10);
                this.state.checkInDate = this.state.systemDate;
                // Ensure default nights is set
                this.state.noOfNights = this.state.noOfNights || 1;
                // Update check-out date based on new check-in date
                this.updateCheckOutDate();
            } catch (dateError) {
                console.warn('Date initialization failed:', dateError);
                // Fallback to current date
                this.state.systemDate = new Date().toISOString().slice(0, 10);
                this.state.checkInDate = this.state.systemDate;
            }
        }
    }

    /**
     * Fetch Room Types with Comprehensive Error Handling
     * @throws {OfflineSearchWidgetError}
     */
    async fetchRoomTypes() {
        try {
            const roomTypes = await this.orm.searchRead(
                'hotel.room.type',
                [],
                ['id', 'name', 'description'],
                { order: 'name ASC', limit: 50 }
            );

            if (!roomTypes || roomTypes.length === 0) {
                throw new OfflineSearchWidgetError(
                    'No room types available',
                    'FETCH_ROOM_TYPES_EMPTY',
                    { searchDomain: [] }
                );
            }

            this.state.roomTypes = roomTypes;

        } catch (error) {
            throw new OfflineSearchWidgetError(
                'Failed to fetch room types',
                'FETCH_ROOM_TYPES_FAILED',
                { 
                    originalError: error.message,
                    stack: error.stack 
                }
            );
        }
    }

    /**
     * Update Check-out Date with Error Prevention
     */
    updateCheckOutDate() {
        try {
            if (!this.state.checkInDate || this.state.noOfNights < 1) {
                throw new OfflineSearchWidgetError(
                    'Invalid date calculation parameters',
                    'DATE_CALC_INVALID_PARAMS',
                    { 
                        checkInDate: this.state.checkInDate,
                        nights: this.state.noOfNights 
                    }
                );
            }

            const checkIn = new Date(this.state.checkInDate);
            checkIn.setDate(checkIn.getDate() + this.state.noOfNights);
            
            this.state.checkOutDate = checkIn.toISOString().slice(0, 10);
        } catch (error) {
            console.warn('Check-out date update failed:', error);
            // Fallback to default behavior
            this.state.checkOutDate = this.state.checkInDate;
        }
    }

    /**
     * Search Rooms based on input
     * Provides live search functionality with comprehensive results
     */
    async searchRooms() {
        if (this.props.readonly) return;
        if (!this.validateSearchCriteria()) {
            return;
        }

        try {
            const results = await this.searchAvailableRooms(
                this.state.checkInDate,
                this.state.checkOutDate,
                this.state.rooms
            );
            
            this.state.searchResults = results;
        } catch (error) {
            console.error('Error during room search:', error);
            this.state.searchResults = [];
        }
    }

    /**
     * Split All Rooms
     * Splits all rooms based on the current booking criteria
     */
    splitAllRooms() {
        if (this.props.readonly) return;
        console.log("Splitting all rooms");
    }

    /**
     * Clear All Rooms
     * Resets all form fields to their initial state
     */
    clearAllRooms() {
        if (this.props.readonly) return;
        // Reset all form fields to initial state, but preserve hotels list
        const currentHotels = this.state.hotels;
        Object.assign(this.state, {
            hotel: "",
            hotels: currentHotels,  // Preserve the existing hotels list
            dateOfOrder: new Date().toISOString().slice(0, 16),
            notes: "",
            rooms: 1,
            adults: 1,
            children: 0,
            infants: 0,
            checkInDate: "",
            noOfNights: 1,
            checkOutDate: "",
            roomTypes: [],  
            contactSearch: "",
            filteredContacts: [],
            nationalitySearch: "",
            filteredCountries: [],
            referenceContact: "",
            systemDate: null,
            searchResults: []  // Clear search results
        });
    }

    /**
     * Assign All Rooms
     * Assigns all rooms based on the current booking criteria
     */
    assignAllRooms() {
        if (this.props.readonly) return;
        console.log("Assigning all rooms");
    }

    /**
     * Update Contact Nationality
     * Updates the contact nationality based on the selected contact
     * 
     * @param {Object} contact - Contact object with nationality information
     */
    async updateContactNationality(contact) {
        // Reset nationality first
        this.state.nationality = false;
        this.state.nationalitySearch = '';
        
        if (contact.nationality) {
            try {
                const countryDetails = await this.orm.read(
                    'res.country',
                    [contact.nationality],
                    ['name', 'code']
                );
                if (countryDetails && countryDetails.length > 0) {
                    this.state.nationality = contact.nationality;
                    this.state.nationalitySearch = countryDetails[0].name;
                }
            } catch (error) {
                console.error('Error updating nationality:', error);
            }
        }
    }

    /**
     * Get Current System Date
     * Retrieves the current system date based on the selected hotel
     * 
     * @returns {String} Current system date in YYYY-MM-DD format
     */
    async getCurrentSystemDate() {
        if (!this.state.hotel) return null;

        const hotels = this.state.hotels;
        const selectedHotel = hotels.find(h => h.id === parseInt(this.state.hotel));
        if (selectedHotel && selectedHotel.system_date) {
            return selectedHotel.system_date.split(' ')[0];
        }
        return null;
    }

    /**
     * Validate Check-in Date
     * Validates the check-in date based on the current system date
     * 
     * @param {String} date - Check-in date in YYYY-MM-DD format
     * @returns {Boolean} True if the date is valid, false otherwise
     */
    async validateCheckInDate(date) {
        // If no date provided, set to current system date
        if (!date) {
            const currentSystemDate = await this.getCurrentSystemDate();
            this.state.checkInDate = currentSystemDate;
            
            // Set check-out date to next day
            const nextDay = new Date(currentSystemDate);
            nextDay.setDate(nextDay.getDate() + this.state.noOfNights);
            this.state.checkOutDate = nextDay.toISOString().split('T')[0];
            this.state.noOfNights = 1;
            
            return true;
        }

        // Get current system date
        const currentSystemDate = await this.getCurrentSystemDate();
        if (!currentSystemDate) {
            alert('Unable to retrieve system date. Please try again.');
            return false;
        }

        // Update state's system date
        this.state.systemDate = currentSystemDate;

        // Convert both dates to YYYY-MM-DD format for comparison
        const checkInDate = new Date(date).toISOString().split('T')[0];

        if (checkInDate < currentSystemDate) {
            // Explicitly set check-in date to current system date
            this.state.checkInDate = currentSystemDate;
            
            // Update check-out date
            const nextDay = new Date(currentSystemDate);
            nextDay.setDate(nextDay.getDate() + 1);
            this.state.checkOutDate = nextDay.toISOString().split('T')[0];
            this.state.noOfNights = 1;
            
            // Trigger UI update to reflect the new date
            const checkInInput = document.getElementById('checkInDate');
            if (checkInInput) {
                checkInInput.value = currentSystemDate;
            }
            
            alert('Check-in date cannot be in the past. Setting to current system date.');
            return false;
        }

        // If check-out date is not set or is invalid, set it to next day
        if (!this.state.checkOutDate || new Date(this.state.checkOutDate) <= new Date(checkInDate)) {
            const nextDay = new Date(checkInDate);
            nextDay.setDate(nextDay.getDate() + 1);
            this.state.checkOutDate = nextDay.toISOString().split('T')[0];
            this.state.noOfNights = 1;
        }

        return true;
    }

    /**
     * Validate Check-out Date
     * Validates the check-out date based on the check-in date
     * 
     * @param {String} date - Check-out date in YYYY-MM-DD format
     * @returns {Boolean} True if the date is valid, false otherwise
     */
    async validateCheckOutDate(date) {
        // If no date provided, set to check-in date + 1 night
        if (!date) {
            const checkInDate = new Date(this.state.checkInDate);
            const nextDay = new Date(checkInDate);
            nextDay.setDate(nextDay.getDate() + 1);
            this.state.checkOutDate = nextDay.toISOString().split('T')[0];
            this.state.noOfNights = 1;
            return true;
        }

        // Get current system date
        const currentSystemDate = await this.getCurrentSystemDate();
        if (!currentSystemDate) {
            alert('Unable to retrieve system date. Please check the console for details.');
            return false;
        }

        // Convert dates to YYYY-MM-DD format for comparison
        const checkOutDate = new Date(date).toISOString().split('T')[0];
        const checkInDate = new Date(this.state.checkInDate).toISOString().split('T')[0];

        if (checkOutDate <= checkInDate) {
            // Reset to check-in date + 1 night
            const nextDay = new Date(this.state.checkInDate);
            nextDay.setDate(nextDay.getDate() + 1);
            this.state.checkOutDate = nextDay.toISOString().split('T')[0];
            this.state.noOfNights = 1;
            
            alert('Check-out date must be after check-in date. Setting to next day.');
            return false;
        }

        // Calculate and update number of nights
        const nights = Math.ceil((new Date(checkOutDate) - new Date(checkInDate)) / (1000 * 60 * 60 * 24));
        this.state.noOfNights = nights;

        return true;
    }

    /**
     * Update Check-out Date
     * Updates the check-out date based on the number of nights
     */
    updateCheckOutDate() {
        if (this.state.checkInDate) {
            const checkIn = new Date(this.state.checkInDate);
            const checkOut = new Date(checkIn);
            checkOut.setDate(checkOut.getDate() + parseInt(this.state.noOfNights));
            this.state.checkOutDate = checkOut.toISOString().split('T')[0];
        }
    }

    /**
     * Update Nights
     * Updates the number of nights based on the check-in and check-out dates
     */
    updateNights() {
        if (this.state.checkInDate && this.state.checkOutDate) {
            const checkIn = new Date(this.state.checkInDate);
            const checkOut = new Date(this.state.checkOutDate);
            const diffTime = Math.abs(checkOut - checkIn);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            this.state.noOfNights = diffDays;
        }
    }

    /**
     * On Nights Change
     * Updates the number of nights and check-out date when the user changes the number of nights
     * 
     * @param {String} value - New number of nights
     */
    async onNightsChange(value) {
        try {
            const nights = parseInt(value) || 1;
            
            if (!this.validateNights(nights)) {
                alert(_t("Number of nights must be between 1 and 730 (2 years)."));
                // Reset to default or previous valid value
                Object.assign(this.state, {
                    noOfNights: 1
                });
            } else {
                Object.assign(this.state, {
                    noOfNights: nights
                });
            }
            
            // Update check-out date and trigger render
            this.updateCheckOutDate();
            this.render();
        } catch (error) {
            console.error('Error in onNightsChange:', error);
            this.resetDateFields();
        }
    }

    /**
     * On Hotel Change
     * Updates system date and check-in date when hotel selection changes
     * @modified 2025-01-07T22:17:08+05:00
     */
    onHotelChange() {
        // Original code preserved as comment
        /* this.state.hotel = ev.target.value;
        this.fetchRoomTypes(); */

        try {
            const selectedHotel = this.state.hotels.find(hotel => hotel.id === parseInt(this.state.hotel));
            if (selectedHotel && selectedHotel.system_date) {
                // Extract only the date part from system_date
                this.state.systemDate = selectedHotel.system_date.split(' ')[0];
                // Set check-in date equal to system date
                this.state.checkInDate = this.state.systemDate;
                // Ensure default nights is set
                this.state.noOfNights = this.state.noOfNights || 1;
                // Update check-out date based on new check-in date
                this.updateCheckOutDate();
            }
            // Fetch room types for the selected hotel
            this.fetchRoomTypes();
        } catch (error) {
            console.error('Error updating dates on hotel change:', error);
            alert(_t("Failed to update dates. Please try again."));
        }
    }

    /**
     * Update Rooms
     * Updates the number of rooms based on the user input
     * 
     * @param {String} value - New number of rooms
     */
    updateRooms(value) {
        const rooms = parseInt(value) || 1;
        if (rooms < 1) {
            this.state.rooms = 1;
            alert(_t("Number of rooms cannot be less than 1."));
        } else {
            this.state.rooms = rooms;
        }
    }

    /**
     * Update Adults
     * Updates the number of adults based on the user input
     * 
     * @param {String} value - New number of adults
     */
    updateAdults(value) {
        const adults = parseInt(value) || 0;
        if (adults <= 0) {
            this.state.adults = 1;
        } else {
            this.state.adults = adults;
        }
    }

    /**
     * Update Children
     * Updates the number of children based on the user input
     * 
     * @param {String} value - New number of children
     */
    updateChildren(value) {
        const children = parseInt(value) || 0;
        if (children < 0) {
            this.state.children = 0;
        } else {
            this.state.children = children;
        }
    }

    /**
     * Update Infants
     * Updates the number of infants based on the user input
     * 
     * @param {String} value - New number of infants
     */
    updateInfants(value) {
        const infants = parseInt(value) || 0;
        if (infants < 0) {
            this.state.infants = 0;
        } else {
            this.state.infants = infants;
        }
    }

    /**
     * On Check-in Date Change
     * Validates and updates check-out date when check-in date changes
     * @modified 2025-01-07T23:15:41+05:00
     */
    onCheckInDateChange(ev) {
        try {
            const newDate = ev.target.value;
            if (!this.validateCheckInDate(newDate)) {
                alert(_t("Check-in date cannot be earlier than system date."));
                this.state.checkInDate = this.state.systemDate;
            } else {
                this.state.checkInDate = newDate;
            }
            
            // Always update checkout date after check-in date change
            this.updateCheckOutDate();
        } catch (error) {
            console.error('Error in onCheckInDateChange:', error);
            alert(_t("Error updating check-in date."));
        }
    }

    /**
     * On Check-out Date Change
     * Validates and updates nights when check-out date changes
     * @modified 2025-01-07T21:55:31+05:00
     */
    onCheckOutDateChange() {
        // Validate check-out date
        if (!this.validateCheckOutDate(this.state.checkOutDate)) {
            alert(_t("Check-out date must be after check-in date."));
            this.updateCheckOutDate();
            return;
        }

        // Update number of nights
        this.updateNights();
    }

    /**
     * On Nights Change
     * Updates check-out date when number of nights changes
     * @param {string} value - New number of nights
     * @modified 2025-01-07T21:55:31+05:00
     */
    onNightsChange(value) {
        const nights = parseInt(value) || 1;
        if (nights < 1) {
            this.state.noOfNights = 1;
            alert(_t("Number of nights must be at least 1."));
        } else {
            this.state.noOfNights = nights;
        }
        this.updateCheckOutDate();
    }

    /**
     * Update Check-out Date
     * Calculates and updates check-out date based on check-in date and nights
     * @modified 2025-01-07T21:55:31+05:00
     */
    updateCheckOutDate() {
        if (!this.state.checkInDate) return;
        
        const checkIn = new Date(this.state.checkInDate);
        const checkOut = new Date(checkIn);
        checkOut.setDate(checkOut.getDate() + this.state.noOfNights);
        this.state.checkOutDate = checkOut.toISOString().split('T')[0];
    }

    /**
     * Update Nights
     * Calculates and updates number of nights based on check-in and check-out dates
     * @modified 2025-01-07T21:55:31+05:00
     */
    updateNights() {
        if (!this.state.checkInDate || !this.state.checkOutDate) return;

        const checkIn = new Date(this.state.checkInDate);
        const checkOut = new Date(this.state.checkOutDate);
        const diffTime = checkOut.getTime() - checkIn.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        this.state.noOfNights = diffDays > 0 ? diffDays : 1;
    }

    /**
     * Validate Check-in Date
     * @param {string} date - Date to validate
     * @returns {boolean} - True if date is valid
     * @modified 2025-01-07T21:55:31+05:00
     */
    validateCheckInDate(date) {
        if (!date || !this.state.systemDate) return true;
        return new Date(date) >= new Date(this.state.systemDate);
    }

    /**
     * Validate Check-out Date
     * @param {string} date - Date to validate
     * @returns {boolean} - True if date is valid
     * @modified 2025-01-07T21:55:31+05:00
     */
    validateCheckOutDate(date) {
        if (!date || !this.state.checkInDate) return true;
        return new Date(date) > new Date(this.state.checkInDate);
    }

    /**
     * On Contact Search Blur
     * Handles actions when contact search input loses focus
     */
    // onContactSearchBlur() {
    //     if (!this.state.contactSearch) {
    //         // Clear contact-related fields when search is empty
    //         this.state.contact = null;
    //         this.state.contactSearch = '';
    //     }
    // }

    /**
     * Default method for handling input events that might not be fully implemented
     * Prevents undefined handler errors
     */
    noop() {
        // No operation - prevents undefined handler errors
        console.log('No operation handler called');
    }

    // /**
    //  * Select Group Booking
    //  * Selects a group booking from the search results
    //  * 
    //  * @param {Object} groupBooking - Selected group booking object
    //  */
    // selectGroupBooking(groupBooking) {
    //     if (groupBooking) {
    //         this.state.groupBooking = groupBooking;
    //         this.state.groupBookingSearch = groupBooking.name || '';
    //         this.state.filteredGroupBookings = [];
    //     }
    // }

    // /**
    //  * Select Contact
    //  * Selects a contact from the search results
    //  * 
    //  * @param {Object} contact - Selected contact object
    //  */
    // selectContact(contact) {
    //     if (contact) {
    //         this.state.contact = contact;
    //         this.state.contactSearch = contact.name || '';
    //         this.state.filteredContacts = [];
    //     }
    // }

    // /**
    //  * Select Nationality
    //  * Selects a nationality from the search results
    //  * 
    //  * @param {Object} country - Selected country object
    //  */
    // selectNationality(country) {
    //     if (country) {
    //         this.state.nationality = country;
    //         this.state.nationalitySearch = country.name || '';
    //         this.state.filteredCountries = [];
    //     }
    // }

    // /**
    //  * Search Group Bookings based on input
    //  * @date 2025-01-07T20:20:32+05:00
    //  * Adjusted to use company field correctly linked to res.partner
    //  */
    // async onGroupBookingSearch() {
    //     try {
    //         // Safely get search term with fallback
    //         const searchTerm = (this.state.groupBookingSearch || '').trim();
            
    //         // Early return if no search term
    //         if (!searchTerm) {
    //             this.state.filteredGroupBookings = [];
    //             return;
    //         }

    //         // Construct search domain
    //         const domain = [
    //             '|', '|', '|', '|',
    //             ['name', 'ilike', searchTerm],
    //             ['group_name', 'ilike', searchTerm],
    //             ['company.name', 'ilike', searchTerm],
    //             ['company.email', 'ilike', searchTerm],
    //             ['company.phone', 'ilike', searchTerm]
    //         ];

    //         // Fetch group bookings with related details
    //         const groupBookings = await this.orm.searchRead(
    //             'group.booking',
    //             domain,
    //             [
    //                 'id',        // Unique identifier
    //                 'name',      // Booking name
    //                 'group_name', // Specific group name
    //                 'company'    // Related company information
    //             ],
    //             { 
    //                 limit: 50,
    //                 context: {
    //                     lang: this.env.lang,
    //                     tz: this.env.context.tz
    //                 }
    //             }
    //         );

    //         // Transform results safely
    //         this.state.filteredGroupBookings = groupBookings.map(groupBooking => ({
    //             id: groupBooking.id || null,
    //             name: groupBooking.name || '',
    //             groupName: groupBooking.group_name || '',
    //             companyName: groupBooking.company ? groupBooking.company[1] : '',
    //             contactDetails: {
    //                 email: groupBooking.company ? 
    //                     (this.orm.read('res.partner', [groupBooking.company[0]], ['email'])[0]?.email || '') : '',
    //                 phone: '',
    //                 address: ''
    //             }
    //         }));

    //     } catch (error) {
    //         // Comprehensive error handling
    //         console.error('Group Booking Search Error', error);
            
    //         // User-friendly notification
    //         alert('Search failed. Please try again.');
    //         // this.notification.add('Search failed. Please try again.', {
    //         //     type: 'danger',
    //         //     title: 'Search Error'
    //         // });

    //         // Reset filtered bookings on error
    //         this.state.filteredGroupBookings = [];
    //     }
    // }

    // /**
    //  * Source of Business Search Method
    //  * @description Handles searching and filtering bookings based on source of business
    //  * @param {Event} ev - The triggering event
    //  * @returns {Promise<void>}
    //  */
    // /* General Information Methods - Commented Out @date 2025-01-07T20:47:56+05:00
    //  * Including: group, contact, nationality, source of business, market segment, notes
    //  */
    
    // /**
    //  * Source of Business Search Handler
    //  * @param {Event} ev - The triggering event
    //  * @returns {Promise<void>}
    //  */
    // async _onSourceOfBusinessSearch(ev) {
    //     const sourceOfBusiness = (ev.target.value || '').trim();
    //     console.log('Source of Business Search Term:', sourceOfBusiness);
        
    //     if (!sourceOfBusiness) {
    //         this.state.filteredSourceOfBusiness = [];
    //         return;
    //     }

    //     try {
    //         const domain = [
    //             '|',
    //             ['name', 'ilike', sourceOfBusiness],
    //             ['code', 'ilike', sourceOfBusiness]
    //         ];

    //         const sources = await this.orm.searchRead(
    //             'source.of.business',
    //             domain,
    //             ['id', 'name', 'code'],
    //             { limit: 10 }
    //         );

    //         this.state.filteredSourceOfBusiness = sources.map(source => ({
    //             id: source.id,
    //             name: source.name,
    //             code: source.code
    //         }));
    //     } catch (error) {
    //         console.error('Source of Business Search Error:', error);
    //         this.state.filteredSourceOfBusiness = [];
    //     }
    // }

    // /**
    //  * Initialize Source of Business Dropdown
    //  * @returns {Promise<void>}
    //  */
    // async _initSourceOfBusinessDropdown() {
    //     try {
    //         const sourceOptions = await this.orm.searchRead(
    //             'source.of.business',
    //             [],
    //             ['id', 'name', 'code']
    //         );

    //         this.sourceOfBusinessOptions = sourceOptions.map(source => ({
    //             id: source.id,
    //             name: source.name,
    //             code: source.code
    //         }));

    //         console.log('Source of Business Options:', this.sourceOfBusinessOptions);
    //     } catch (error) {
    //         console.error('Error initializing Source of Business:', error);
    //         this.sourceOfBusinessOptions = [];
    //     }
    // }

    // /**
    //  * Select Source of Business Handler
    //  * @param {Object} source - The selected source of business
    //  */
    // selectSourceOfBusiness(source) {
    //     if (source) {
    //         this.state.sourceOfBusiness = source;
    //         this.state.sourceOfBusinessSearch = source.name || '';
    //         this.state.filteredSourceOfBusiness = [];
    //     }
    // }

    // /**
    //  * Market Segment Search Handler
    //  * @param {Event} ev - The triggering event
    //  * @returns {Promise<void>}
    //  */
    // async _onMarketSegmentSearch(ev) {
    //     const marketSegment = (ev.target.value || '').trim();
    //     console.log('Market Segment Search Term:', marketSegment);
        
    //     if (!marketSegment) {
    //         this.state.filteredMarketSegments = [];
    //         return;
    //     }

    //     try {
    //         const domain = [
    //             '|',
    //             ['name', 'ilike', marketSegment],
    //             ['code', 'ilike', marketSegment]
    //         ];

    //         const segments = await this.orm.searchRead(
    //             'market.segment',
    //             domain,
    //             ['id', 'name', 'code'],
    //             { limit: 10 }
    //         );

    //         this.state.filteredMarketSegments = segments.map(segment => ({
    //             id: segment.id,
    //             name: segment.name,
    //             code: segment.code
    //         }));
    //     } catch (error) {
    //         console.error('Market Segment Search Error:', error);
    //         this.state.filteredMarketSegments = [];
    //     }
    // }

    // /**
    //  * Initialize Market Segment Dropdown
    //  * @returns {Promise<void>}
    //  */
    // async _initMarketSegmentDropdown() {
    //     try {
    //         const segmentOptions = await this.orm.searchRead(
    //             'market.segment',
    //             [],
    //             ['id', 'name', 'code']
    //         );

    //         this.marketSegmentOptions = segmentOptions.map(segment => ({
    //             id: segment.id,
    //             name: segment.name,
    //             code: segment.code
    //         }));

    //         console.log('Market Segment Options:', this.marketSegmentOptions);
    //     } catch (error) {
    //         console.error('Error initializing Market Segment:', error);
    //         this.marketSegmentOptions = [];
    //     }
    // }

    // /**
    //  * Select Market Segment Handler
    //  * @param {Object} segment - The selected market segment
    //  */
    // selectMarketSegment(segment) {
    //     if (segment) {
    //         this.state.marketSegment = segment;
    //         this.state.marketSegmentSearch = segment.name || '';
    //         this.state.filteredMarketSegments = [];
    //     }
    // }

    // /**
    //  * Market Segment Search Methods
    //  */
    // _onMarketSegmentSearch() {
    //     const search = this.state.marketSegmentSearch.toLowerCase().trim();
    //     if (!search) {
    //         this.state.filteredMarketSegments = [];
    //         return;
    //     }

    //     // Fetch or filter market segment options
    //     const segmentOptions = [
    //         { id: 1, name: 'Leisure' },
    //         { id: 2, name: 'Business' },
    //         { id: 3, name: 'Group' },
    //         { id: 4, name: 'MICE' },
    //         { id: 5, name: 'Government' }
    //     ];

    //     this.state.filteredMarketSegments = segmentOptions.filter(segment => 
    //         segment.name.toLowerCase().includes(search)
    //     );
    // }

    // /**
    //  * Select Market Segment
    //  * @param {Object} segment - Selected market segment
    //  */
    // selectMarketSegment(segment) {
    //     if (segment) {
    //         this.state.marketSegment = segment;
    //         this.state.marketSegmentSearch = segment.name || '';
    //         this.state.filteredMarketSegments = [];
    //     }
    // }

    /**
     * Blur event handlers for Source of Business and Market Segment
     */
//     onSourceOfBusinessBlur() {
//         if (!this.state.sourceOfBusinessSearch) {
//             this.state.sourceOfBusiness = null;
//             this.state.filteredSourceOfBusiness = [];
//         }
//     }

//     onMarketSegmentBlur() {
//         if (!this.state.marketSegmentSearch) {
//             this.state.marketSegment = null;
//             this.state.filteredMarketSegments = [];
//         }
//     }
// }

    /**
     * Reset to Default Values
     * Sets all form fields to their default values
     * @modified 2025-01-07T23:28:12+05:00
     */
    resetToDefaults() {
        this.state.checkInDate = this.state.systemDate;
        this.state.noOfNights = 1;
        this.state.rooms = 1;
        this.state.roomType = false;
        this.updateCheckOutDate();
    }

    /**
     * Reset Date Fields to Default Values
     * @modified 2025-01-08T00:19:03+05:00
     */
    resetDateFields() {
        // Original code preserved
        /* this.state.checkInDate = this.state.systemDate;
        this.state.noOfNights = 1;
        this.updateCheckOutDate(); */

        // Using Object.assign to trigger reactivity
        Object.assign(this.state, {
            checkInDate: this.state.systemDate,
            noOfNights: 1
        });
        
        // Force update check-out date
        this.updateCheckOutDate();
        
        // Trigger render
        this.render();
    }

    /**
     * On Check-in Date Change
     * @modified 2025-01-08T00:19:03+05:00
     */
    onCheckInDateChange(ev) {
        try {
            const newDate = ev.target.value;
            if (!this.validateCheckInDate(newDate)) {
                alert(_t("Check-in date cannot be earlier than system date. Setting to default values."));
                this.resetDateFields();
            } else {
                this.state.checkInDate = newDate;
                this.updateCheckOutDate();
            }
        } catch (error) {
            console.error('Error in onCheckInDateChange:', error);
            alert(_t("Error updating check-in date. Setting to default values."));
            this.resetDateFields();
        }
    }

    /**
     * On Nights Change
     * @modified 2025-01-08T00:19:03+05:00
     */
    onNightsChange(value) {
        try {
            const nights = parseInt(value) || 0;
            
            if (!this.validateNights(nights)) {
                alert(_t("Number of nights cannot be negative. Setting to default values."));
                this.resetDateFields();
            } else {
                this.state.noOfNights = nights;
                this.updateCheckOutDate();
            }
        } catch (error) {
            console.error('Error in onNightsChange:', error);
            alert(_t("Error updating nights. Setting to default values."));
            this.resetDateFields();
        }
    }

    /**
     * Update Check-out Date
     * @modified 2025-01-08T00:30:39+05:00
     */
    updateCheckOutDate() {
        // Original code preserved
        /* if (!this.state.checkInDate) return;
        const checkIn = new Date(this.state.checkInDate);
        const checkOut = new Date(checkIn);
        checkOut.setDate(checkOut.getDate() + this.state.noOfNights);
        this.state.checkOutDate = checkOut.toISOString().split('T')[0]; */

        try {
            if (!this.state.checkInDate) return;

            const checkIn = new Date(this.state.checkInDate);
            const checkOut = new Date(checkIn);
            
            // Handle special case for 0 nights
            const nights = this.state.noOfNights || 0;
            if (nights <= 0) {
                // Using Object.assign to trigger reactivity
                Object.assign(this.state, {
                    checkOutDate: this.state.checkInDate
                });
            } else {
                checkOut.setDate(checkOut.getDate() + nights);
                // Using Object.assign to trigger reactivity
                Object.assign(this.state, {
                    checkOutDate: checkOut.toISOString().split('T')[0]
                });
            }
            
            // Trigger render
            this.render();
        } catch (error) {
            console.error('Error in updateCheckOutDate:', error);
            alert(_t("Error updating check-out date."));
        }
    }

    /**
     * Handle Check-in Date Blur
     * Validates check-in date when focus leaves the input
     * @param {Event} ev - Blur event
     * @modified 2025-01-08T00:26:21+05:00
     */
    onCheckInDateBlur(ev) {
        try {
            const currentDate = ev.target.value;
            if (!currentDate || !this.validateCheckInDate(currentDate)) {
                alert(_t("Invalid check-in date. Setting to default value."));
                this.resetDateFields();
            } else {
                // Ensure valid date is set using Object.assign
                Object.assign(this.state, {
                    checkInDate: currentDate
                });
                this.updateCheckOutDate();
            }
            // Trigger render
            this.render();
        } catch (error) {
            console.error('Error in onCheckInDateBlur:', error);
            this.resetDateFields();
        }
    }

    /**
     * Handle Check-out Date Blur
     * Validates check-out date when focus leaves the input
     * @param {Event} ev - Blur event
     * @modified 2025-01-08T00:26:21+05:00
     */
    onCheckOutDateBlur(ev) {
        try {
            const currentDate = ev.target.value;
            if (!currentDate || !this.validateCheckOutDate(currentDate)) {
                alert(_t("Invalid check-out date. Setting to default value."));
                this.resetDateFields();
            } else {
                // Ensure valid date is set using Object.assign
                Object.assign(this.state, {
                    checkOutDate: currentDate
                });
                // Calculate and update nights
                const checkIn = new Date(this.state.checkInDate);
                const checkOut = new Date(currentDate);
                const nights = Math.ceil((checkOut - checkIn) / (1000 * 60 * 60 * 24));
                Object.assign(this.state, {
                    noOfNights: nights
                });
            }
            // Trigger render
            this.render();
        } catch (error) {
            console.error('Error in onCheckOutDateBlur:', error);
            this.resetDateFields();
        }
    }

    /**
     * Validate Check-in Date
     * @param {string} date - Date to validate
     * @returns {boolean} - True if date is valid
     * @modified 2025-01-08T00:26:21+05:00
     */
    validateCheckInDate(date) {
        // Original code preserved
        /* if (!date || !this.state.systemDate) return false;
        const checkInDate = new Date(date);
        const systemDate = new Date(this.state.systemDate);
        return checkInDate >= systemDate; */

        if (!date || !this.state.systemDate) return false;
        
        try {
            const checkInDate = new Date(date);
            const systemDate = new Date(this.state.systemDate);
            
            // Reset time parts to compare only dates
            checkInDate.setHours(0, 0, 0, 0);
            systemDate.setHours(0, 0, 0, 0);
            
            return !isNaN(checkInDate) && !isNaN(systemDate) && checkInDate >= systemDate;
        } catch (error) {
            console.error('Error validating check-in date:', error);
            return false;
        }
    }

    /**
     * Validate Check-out Date
     * @param {string} date - Date to validate
     * @returns {boolean} - True if date is valid
     * @modified 2025-01-08T00:26:21+05:00
     */
    validateCheckOutDate(date) {
        // Original code preserved
        /* if (!date || !this.state.checkInDate) return false;
        const checkOut = new Date(date);
        const checkIn = new Date(this.state.checkInDate);
        return checkOut > checkIn; */

        if (!date || !this.state.checkInDate) return false;
        
        try {
            const checkOut = new Date(date);
            const checkIn = new Date(this.state.checkInDate);
            
            // Reset time parts to compare only dates
            checkOut.setHours(0, 0, 0, 0);
            checkIn.setHours(0, 0, 0, 0);
            
            return !isNaN(checkOut) && !isNaN(checkIn) && checkOut >= checkIn;
        } catch (error) {
            console.error('Error validating check-out date:', error);
            return false;
        }
    }

    /**
     * Check if date is within 2 years from reference date
     * @param {Date} dateToCheck - Date to validate
     * @param {Date} referenceDate - Reference date to check against
     * @returns {boolean} - True if date is within 2 years
     * @modified 2025-01-08T00:37:37+05:00
     */
    isWithinTwoYears(dateToCheck, referenceDate) {
        try {
            const twoYearsFromRef = new Date(referenceDate);
            twoYearsFromRef.setFullYear(twoYearsFromRef.getFullYear() + 2);
            
            // Reset time parts to compare only dates
            dateToCheck.setHours(0, 0, 0, 0);
            twoYearsFromRef.setHours(0, 0, 0, 0);
            
            return dateToCheck <= twoYearsFromRef;
        } catch (error) {
            console.error('Error in isWithinTwoYears:', error);
            return false;
        }
    }

    /**
     * Validate Check-in Date
     * @param {string} date - Date to validate
     * @returns {boolean} - True if date is valid
     * @modified 2025-01-08T00:37:37+05:00
     */
    validateCheckInDate(date) {
        // Original code preserved
        /* if (!date || !this.state.systemDate) return false;
        const checkInDate = new Date(date);
        const systemDate = new Date(this.state.systemDate);
        return checkInDate >= systemDate; */

        if (!date || !this.state.systemDate) return false;
        
        try {
            const checkInDate = new Date(date);
            const systemDate = new Date(this.state.systemDate);
            
            // Reset time parts to compare only dates
            checkInDate.setHours(0, 0, 0, 0);
            systemDate.setHours(0, 0, 0, 0);
            
            // Check if date is not before system date and within 2 years
            return !isNaN(checkInDate) && 
                   !isNaN(systemDate) && 
                   checkInDate >= systemDate &&
                   this.isWithinTwoYears(checkInDate, systemDate);
        } catch (error) {
            console.error('Error validating check-in date:', error);
            return false;
        }
    }

    /**
     * Validate Check-out Date
     * @param {string} date - Date to validate
     * @returns {boolean} - True if date is valid
     * @modified 2025-01-08T00:37:37+05:00
     */
    validateCheckOutDate(date) {
        // Original code preserved
        /* if (!date || !this.state.checkInDate) return false;
        const checkOut = new Date(date);
        const checkIn = new Date(this.state.checkInDate);
        return checkOut > checkIn; */

        if (!date || !this.state.checkInDate) return false;
        
        try {
            const checkOut = new Date(date);
            const checkIn = new Date(this.state.checkInDate);
            
            // Reset time parts to compare only dates
            checkOut.setHours(0, 0, 0, 0);
            checkIn.setHours(0, 0, 0, 0);
            
            // Check if date is after check-in and within 2 years of check-in
            return !isNaN(checkOut) && 
                   !isNaN(checkIn) && 
                   checkOut >= checkIn &&
                   this.isWithinTwoYears(checkOut, checkIn);
        } catch (error) {
            console.error('Error validating check-out date:', error);
            return false;
        }
    }

    /**
     * Validate Number of Nights
     * @param {number} nights - Number of nights to validate
     * @returns {boolean} - True if nights is valid
     * @modified 2025-01-08T00:37:37+05:00
     */
    validateNights(nights) {
        try {
            // Calculate maximum nights (2 years = 730 days)
            const MAX_NIGHTS = 730;
            return nights > 0 && nights <= MAX_NIGHTS;
        } catch (error) {
            console.error('Error validating nights:', error);
            return false;
        }
    }

    /**
     * Handle Nights Blur
     * Validates number of nights when focus leaves the input
     * @param {string} value - Number of nights
     * @modified 2025-01-08T00:41:30+05:00
     */
    onNightsBlur(value) {
        try {
            const nights = parseInt(value) || 1;
            
            if (!this.validateNights(nights)) {
                alert(_t("Number of nights must be between 1 and 730 (2 years). Setting to default value."));
                // Reset to default value
                Object.assign(this.state, {
                    noOfNights: 1
                });
                this.updateCheckOutDate();
            } else {
                // Ensure the value is set using Object.assign
                Object.assign(this.state, {
                    noOfNights: nights
                });
                this.updateCheckOutDate();
            }
            // Trigger render
            this.render();
        } catch (error) {
            console.error('Error in onNightsBlur:', error);
            this.resetDateFields();
        }
    }

    /**
     * Get available rooms based on check-in and check-out dates
     * @param {string} fromDate - Check-in date in YYYY-MM-DD format
     * @param {string} toDate - Check-out date in YYYY-MM-DD format
     * @param {number} roomCount - Number of rooms required
     * @returns {Promise} Promise resolving to available rooms
     * @date 2025-01-08T01:48:25+05:00
     */
    async searchAvailableRooms(fromDate, toDate, roomCount) {
        try {
            // Call the backend method using ORM
            const result = await this.orm.call(
                'room.search',
                'search_available_rooms',
                [fromDate, toDate, roomCount, parseInt(this.state.hotel,10), this.state.roomType]
            );
            
            return result;
        } catch (error) {
            console.error('Error searching rooms:', error);
            alert(_t("Failed to search for available rooms. Please try again."));
            return [];
        }
    }

    /**
     * Search for available rooms
     * @returns {Promise<void>}
     * @date 2025-01-08T01:27:09+05:00
     */
    async searchRooms() {
        try {
            this.state.isSearching = true;
            this.state.searchError = null;
            this.state.searchResults = [];

            // Validate inputs
            if (!this.state.checkInDate || !this.state.checkOutDate) {
                this.state.searchError = _t("Please select check-in and check-out dates");
                return;
            }
            if (!this.state.rooms || this.state.rooms < 1) {
                this.state.searchError = _t("Please select at least one room");
                return;
            }
            if (!this.state.hotel) {
                this.state.searchError = _t("Please select a hotel");
                return;
            }

            console.log('Search params:', {
                checkInDate: this.state.checkInDate,
                checkOutDate: this.state.checkOutDate,
                rooms: this.state.rooms,
                hotel: this.state.hotel,
                roomType: this.state.selectedRoomType || false
            });

            // Call the search method
            const results = await this.orm.call(
                'room.search',
                'search_available_rooms',
                [
                    this.state.checkInDate,
                    this.state.checkOutDate,
                    this.state.rooms,
                    this.state.hotel,
                    this.state.selectedRoomType || false
                ]
            );

            console.log('Search results:', results);

            // Update state with results
            this.state.searchResults = results.map(result => ({
                ...result,
                isSelected: false,
                displayPrice: this._formatPrice(result.rate_per_night)
            }));

        } catch (error) {
            console.error('Error searching rooms:', error);
            console.error('Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack,
                data: error.data
            });
            this.state.searchError = error.data?.message || error.message || _t("Failed to search for rooms");
            alert(this.state.searchError);
        } finally {
            this.state.isSearching = false;
        }
    }

    /**
     * Format price for display
     * @param {number} price 
     * @returns {string}
     * @date 2025-01-08T01:27:09+05:00
     */
    _formatPrice(price) {
        return price ? price.toLocaleString('en-US', {
            style: 'currency',
            currency: 'USD'
        }) : 'N/A';
    }

    /**
     * Select a room type from search results
     * @param {number} roomTypeId 
     * @date 2025-01-08T01:27:09+05:00
     */
    selectRoomType(roomTypeId) {
        this.state.searchResults = this.state.searchResults.map(result => ({
            ...result,
            isSelected: result.room_type_id === roomTypeId
        }));
        this.state.selectedRoomType = roomTypeId;
    }

    validateSearchCriteria() {
        if (!this.state.hotel) {
            alert(_t("Please select a hotel"));
            return false;
        }
        if (!this.state.checkInDate) {
            alert(_t("Please select a check-in date"));
            return false;
        }
        if (!this.state.checkOutDate) {
            alert(_t("Please select a check-out date"));
            return false;
        }
        if (!this.validateCheckInDate(this.state.checkInDate)) {
            alert(_t("Invalid check-in date"));
            return false;
        }
        if (!this.validateCheckOutDate(this.state.checkOutDate)) {
            alert(_t("Invalid check-out date"));
            return false;
        }
        return true;
    }
}

// Define the Owl template for rendering
OfflineSearchWidget.template = 'hotel_management_odoo.OfflineSearchWidget';

/**
 * Validate Search Criteria with comprehensive checks
 * @returns {boolean} True if all criteria are valid, false otherwise
 * @date 2025-01-08T12:48:47+05:00
 */
validateSearchCriteria() {
    let isValid = true;
    const errorMessages = [];

    // Hotel validation
    if (!this.state.hotel) {
        errorMessages.push("Please select a hotel.");
        isValid = false;
    }

    // Check-in date validation
    if (!this.state.checkInDate) {
        errorMessages.push("Please select a check-in date.");
        isValid = false;
    }

    // Check-out date validation
    if (!this.state.checkOutDate) {
        errorMessages.push("Please select a check-out date.");
        isValid = false;
    }

    // Rooms validation
    if (!this.state.rooms || this.state.rooms < 1) {
        errorMessages.push("Number of rooms must be at least 1.");
        isValid = false;
    }

    // Nights validation
    if (!this.state.noOfNights || this.state.noOfNights < 1) {
        errorMessages.push("Number of nights must be at least 1.");
        isValid = false;
    }

    // Display error messages if any
    if (!isValid) {
        console.error("Validation Errors:", errorMessages);
    }

    return isValid;
}

/**
 * Search Rooms with enhanced filtering and error handling
 * @returns {Promise<void>}
 * @date 2025-01-08T12:48:47+05:00
 */
async searchRooms() {
    // Reset search results and no results flag before search
    this.state.searchResults = [];
    this.state.searchPerformed = true;

    if (!this.validateSearchCriteria()) {
        return;
    }

    try {
        let results = await this.searchAvailableRooms(
            this.state.checkInDate,
            this.state.checkOutDate,
            this.state.rooms
        );

        // Calculate actual free to sell including overbooking quantity
        results.forEach(room => {
            room.actualFreeToSell = room.min_free_to_sell + (room.overbooking_qty || 0);
        });

        // If no room type is selected, return all room types
        if (!this.state.roomType) {
            this.state.searchResults = results;
        } else {
            // Filter by selected room type
            this.state.searchResults = results.filter(room => 
                room.room_type_id === parseInt(this.state.roomType)
            );
        }

        // Notification for no results
        if (this.state.searchResults.length === 0) {
            this.notification.add('No rooms found matching your criteria.', {
                type: 'warning',
                sticky: false,
                title: 'Search Results'
            });
        }
    } catch (error) {
        console.error('Error during room search:', error);
        
        // Error notification
        this.notification.add('An error occurred while searching rooms. Please try again.', {
            type: 'danger',
            sticky: false,
            title: 'Search Error'
        });
        
        this.state.searchResults = [];
    }
}

/**
     * Validate Search Criteria
     * @returns {boolean} True if all criteria are valid, false otherwise
     * @date 2025-01-08T12:26:34+05:00
     */
    validateSearchCriteria() {
        let isValid = true;
        const errorMessages = [];

        // Hotel validation
        if (!this.state.hotel) {
            errorMessages.push("Please select a hotel.");
            isValid = false;
        }

        // Check-in date validation
        if (!this.state.checkInDate) {
            errorMessages.push("Please select a check-in date.");
            isValid = false;
        }

        // Check-out date validation
        if (!this.state.checkOutDate) {
            errorMessages.push("Please select a check-out date.");
            isValid = false;
        }

        // Rooms validation
        if (!this.state.rooms || this.state.rooms < 1) {
            errorMessages.push("Number of rooms must be at least 1.");
            isValid = false;
        }

        // Nights validation
        if (!this.state.noOfNights || this.state.noOfNights < 1) {
            errorMessages.push("Number of nights must be at least 1.");
            isValid = false;
        }

        // Display error messages if any
        if (!isValid) {
            console.error("Validation Errors:", errorMessages);
        }

        return isValid;
    }

    /**
     * Search Rooms
     * @returns {Promise<void>}
     * @date 2025-01-08T12:26:34+05:00
     */
    async searchRooms() {
        // Reset search results
        this.state.searchResults = [];

        if (!this.validateSearchCriteria()) {
            return;
        }

        try {
            let results = await this.searchAvailableRooms(
                this.state.checkInDate,
                this.state.checkOutDate,
                this.state.rooms
            );

            // Calculate actual free to sell including overbooking quantity
            results.forEach(room => {
                room.actualFreeToSell = room.min_free_to_sell + (room.overbooking_qty || 0);
            });

            // If no room type is selected, return all room types
            if (!this.state.roomType) {
                this.state.searchResults = results;
            } else {
                // Filter by selected room type
                this.state.searchResults = results.filter(room => 
                    room.room_type_id === parseInt(this.state.roomType)
                );
            }

        } catch (error) {
            console.error('Error during room search:', error);
            this.state.searchResults = [];
        }
    }

/**
 * Enhanced database selection with:
 * 1. Comprehensive error tracking
 * 2. Detailed logging
 * 3. User-friendly notifications
 * 4. Robust error handling
 * 5. Detailed state management for database selection process
 */
class DatabaseSelectionError extends Error {
    constructor(message, errorCode, details = {}) {
        super(message);
        this.name = 'DatabaseSelectionError';
        this.errorCode = errorCode;
        this.details = {
            timestamp: new Date().toISOString(),
            ...details
        };
    }

    toLogObject() {
        return {
            name: this.name,
            message: this.message,
            errorCode: this.errorCode,
            details: this.details
        };
    }
}

export class OfflineSearchWidget extends Component {
    static props = {
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
        options: { type: Object, optional: true }
    };

    setup() {
        // Enhanced service initialization with error tracking
        this.orm = useService('orm');
        this.notification = useService('notification');
        this.action = useService('action');
        this.rpc = useService('rpc');

        // Comprehensive state for database selection
        this.state = useState({
            databases: [],
            selectedDatabase: null,
            isLoading: false,
            error: null,
            
            // Detailed database selection tracking
            databaseSelectionAttempts: 0,
            lastSelectedDatabaseId: null,
            databaseSelectionTimestamp: null
        });

        // Global error handler
        onError((error) => {
            this.handleDatabaseSelectionError(error);
        });

        // Initialize database selection process
        onWillStart(async () => {
            try {
                await this.initializeDatabaseList();
            } catch (error) {
                this.handleDatabaseSelectionError(error);
            }
        });
    }

    /**
     * Comprehensive Database List Initialization
     */
    async initializeDatabaseList() {
        this.state.isLoading = true;
        this.state.error = null;

        try {
            // Fetch available databases with enhanced error tracking
            const databases = await this.rpc('/web/database/list', {});

            if (!databases || databases.length === 0) {
                throw new DatabaseSelectionError(
                    'No databases available',
                    'NO_DATABASES_FOUND',
                    { availableDatabases: databases }
                );
            }

            this.state.databases = databases;
            this.state.isLoading = false;
        } catch (error) {
            throw new DatabaseSelectionError(
                'Database initialization failed',
                'DATABASE_INIT_FAILED',
                { 
                    originalError: error.message,
                    stack: error.stack
                }
            );
        }
    }

    /**
     * Enhanced Database Selection Method
     * @param {string} databaseName - Selected database name
     */
    async selectDatabase(databaseName) {
        this.state.databaseSelectionAttempts++;
        this.state.databaseSelectionTimestamp = new Date().toISOString();
        this.state.lastSelectedDatabaseId = databaseName;

        try {
            // Validate database selection
            if (!databaseName) {
                throw new DatabaseSelectionError(
                    'Invalid database selection',
                    'INVALID_DATABASE',
                    { selectedDatabase: databaseName }
                );
            }

            // Perform database selection with comprehensive logging
            const selectionResult = await this.rpc('/web/database/change', {
                db_name: databaseName
            });

            if (!selectionResult) {
                throw new DatabaseSelectionError(
                    'Database selection failed',
                    'DATABASE_CHANGE_FAILED',
                    { selectedDatabase: databaseName }
                );
            }

            // Trigger notification on successful database selection
            this.notification.add(_t('Database selected successfully'), {
                type: 'success',
                sticky: false
            });

            // Optional: Reload or redirect after database selection
            this.action.doAction({
                type: 'ir.actions.client',
                tag: 'reload'
            });

        } catch (error) {
            this.handleDatabaseSelectionError(error);
        }
    }

    /**
     * Centralized Error Handling for Database Selection
     * @param {Error} error - Error during database selection
     */
    handleDatabaseSelectionError(error) {
        const databaseError = error instanceof DatabaseSelectionError 
            ? error 
            : new DatabaseSelectionError(
                error.message || 'Unexpected Database Selection Error',
                'UNKNOWN_DATABASE_ERROR',
                { originalError: error }
            );

        // Update state with error details
        this.state.error = databaseError.toLogObject();
        this.state.isLoading = false;

        // Log detailed error
        console.error('Database Selection Error:', databaseError.toLogObject());

        // Show user-friendly error notification
        this.notification.add(
            _t('Database Selection Error: %s', databaseError.message), 
            {
                type: 'danger',
                sticky: true
            }
        );
    }
}

// Owl template reference
OfflineSearchWidget.template = 'hotel_management_odoo.OfflineSearchWidget';
