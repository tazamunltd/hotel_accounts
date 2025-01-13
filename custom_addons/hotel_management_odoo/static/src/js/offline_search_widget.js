/** @odoo-module **/

/**
 * Offline Search Widget - Hotel Management Module
 *
 * Comprehensive error handling and logging for robust widget functionality
 * @version 1.1.0
 * @date 2025-01-08T16:55:00+05:00
 */

// Core Owl imports
import { Component, onWillStart, useState, onError, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { debounce } from "@web/core/utils/timing";
import { session } from "@web/session";

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
 * Modified: 2025-01-09T00:23:08+05:00
 */
export class OfflineSearchWidget extends Component {
    static template = "hotel_management_odoo.OfflineSearchWidget";
    static components = {};

    /**
     * Setup component
     * Modified: 2025-01-10T22:14:59+05:00
     */
    setup() {
        super.setup();
        // Initialize services
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.user = useService("user");
        this.companyService = useService("company");

        this.state = useState({
            // Default values
            hotel: "",
            rooms: 1,
            checkInDate: this.formatDateString(new Date()),
            checkOutDate: "",
            noOfNights: 1,
            adults: 1,
            children: 0,
            infants: 0,
            roomType: "",
            systemDate: "",
            lastSystemDateUpdate: "",
            searchResults: [],
            searchPerformed: false,
            searchError: null,
            isSearching: false,
//            guestContact: "",
//            guestGroup: "",
            // Other state properties
            contacts: [],
            groups: [],
            hotels: [],
            roomTypes: [],
            filteredGroupBookings: [],
            columns: [
                { name: 'room_type', label: 'Room Type', visible: true },
                { name: 'company', label: 'Company', visible: true },
                { name: 'free_to_sell', label: 'Free to Sell', visible: true },
                { name: 'total_rooms', label: 'Total Rooms', visible: true },
                { name: 'rate', label: 'Rate', visible: false },
                { name: 'capacity', label: 'Capacity', visible: false }
            ]
        });

        // System date polling interval (in milliseconds)
        this.systemDatePollInterval = 300; // 300 milliseconds
        this.systemDatePollTimer = null;

//         Debounce the updateSystemDate function
        this.debouncedUpdateSystemDate = debounce(
            this.updateSystemDate.bind(this), 300);

        // Start system date polling
        this.startSystemDatePolling();

        // Setup initial data
        onWillStart(async () => {
            await this.fetchCompanies();
            if (this.state.hotel) {
                await this.fetchRoomTypes();
                await this.updateSystemDate()
            }
//            await this.fetchContacts();
//            await this.fetchGroups();
        });
    }

    /**
     * Initialize the component
     * Modified: 2025-01-08T23:59:08+05:00
     */
    initializeComponent() {
        super.setup();
        // Initialize services
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.action = useService("action");

        /**
         * Main state
         */
        this.state = useState({
            // Hotel/Company data
            hotel: "",
            hotels: [],

            // Booking details
            dateOfOrder: new Date().toISOString().slice(0, 16),
            checkInDate: "",
            noOfNights: 0,  // Changed from 1 to 0 as default
            checkOutDate: "",

            // Guest details
            rooms: 1,
            adults: 1,
            children: 0,
            infants: 0,
            // Adding contact and group fields - 2025-01-10T11:48:27+05:00
//            guestContact: "",  // Contact information for the guest
//            guestGroup: "",    // Group information for the guest

            // Room types
            roomTypes: [],
            roomType: null, // selected roomType ID

            // Search results
            searchResults: [],
            searchPerformed: false,

            // Error/Loading flags
            isLoading: false,
            hasError: false,
            errorMessage: null,
            errorDetails: null,
            isSearching: false,
            searchError: null,

            // System date
            systemDate: null,
            lastSystemDateUpdate: null,
            maxCheckOutDate: null,

            // Additional fields visibility
            showAdditionalFields: false,

            // Room count toggle
            showRoomCount: false,  // Added for room count toggle

            // Guest information toggle
            showGuestInfo: false,

            // Column visibility
            columns: [
                { name: 'room_type_name', label: 'Room Type', visible: true },
                { name: 'company_name', label: 'Hotel', visible: true },
                { name: 'actualFreeToSell', label: 'Available Rooms', visible: true },
                { name: 'total_rooms', label: 'Total Rooms', visible: true },
                { name: 'rate', label: 'Rate', visible: false },
                { name: 'capacity', label: 'Capacity', visible: false }
            ],
            // Added group booking state - 2025-01-10T20:37:37+05:00
            groupBooking: null,
            groupBookingSearch: "",
            filteredGroupBookings: []
        });

//        // Debounce the updateSystemDate function
//        this.debouncedUpdateSystemDate = debounce(
//            this.updateSystemDate.bind(this),
//            1000 // 1 second debounce
//        );

        // Global error handler for the widget
        onError((error) => this.handleWidgetError(error));

        // Lifecycle hook
        onWillStart(async () => {
            this.state.isLoading = true;
            this.state.hasError = false;
            this.state.errorMessage = null;

            try {
                await Promise.all([
                    this.fetchCompanies(),
                    this.fetchRoomTypes(),
                    this.fetchContacts(),
                    this.fetchGroups(),
                ]);

                // Start system date polling
                this.startSystemDatePolling();
            } catch (error) {
                this.handleWidgetError(error);
            } finally {
                this.state.isLoading = false;
            }
        });

        // Cleanup on component destroy
        onWillDestroy(() => {
             this.isDestroyed = true;
            this.stopSystemDatePolling();
        });
    }

    /**
     * Start polling for system date updates
     * Modified: 2025-01-08T23:59:08+05:00
     */
    startSystemDatePolling() {
        // Clear any existing timer
        this.stopSystemDatePolling();

        // Start new polling timer
        this.systemDatePollTimer = setInterval(async () => {
//            await this.refreshSession();
            await this.debouncedUpdateSystemDate();
        }, this.systemDatePollInterval);
    }

    /**
     * Stop polling for system date updates
     * Modified: 2025-01-08T23:59:08+05:00
     */
    stopSystemDatePolling() {
        if (this.systemDatePollTimer) {
            clearInterval(this.systemDatePollTimer);
            this.systemDatePollTimer = null;
        }
    }

    /**
     * Update system date from backend
     * Modified: 2025-01-08T23:59:08+05:00
     */
    async updateSystemDate() {
        try {
//            console.log("in the update system date start::",this.state.hotel);
            if (this.isDestroyed) {
                console.warn("Component is destroyed; update system date  aborted.");
                return;
            }
//            console.log("in the update system date process::",this.state.hotel);
//            if (!this.state.hotel) return;

            // Fetch current hotel's system date
            const [hotel] = await this.orm.searchRead(
                'res.company',
                [['id', '=', this.state.hotel]],
                ['system_date'],
                { limit: 1 }
            );

            if (hotel && hotel.system_date) {
                const newSystemDate = this.formatDateString(hotel.system_date);

                // Only update if date has changed
                if (newSystemDate !== this.state.systemDate) {
                    this.state.systemDate = newSystemDate;
                    this.state.lastSystemDateUpdate = new Date().toISOString();

                    // If check-in date is invalid or not set, set it to system date
                    if (!this.state.checkInDate || !this.validateCheckInDate(this.state.checkInDate)) {
                        this.state.checkInDate = newSystemDate;
                        this.updateMaxCheckOutDate();
                        this.updateCheckOutDate();
                    }

                    // Notify user of date change
                    this.notification.add(
                        _t("System date has been updated to: ") + this.formatDateForDisplay(newSystemDate),
                        { type: 'info', sticky: false }
                    );
                    this.notification.add(_t('Check-in date updated to system date'), {
                        type: 'info',
                        sticky: false
                    });
                }
            }
        } catch (error) {
//            console.error('Error updating system date:', error);
//            this.handleWidgetError(error);
        }
    }

    /**
     * Check if current check-in date is today
     * Modified: 2025-01-08T23:59:08+05:00
     * @returns {boolean}
     */
    isCheckInToday() {
        if (!this.state.checkInDate || !this.state.systemDate) return false;
        return this.state.checkInDate === this.state.systemDate;
    }

    /**
     * Format date for display
     * Modified: 2025-01-08T23:59:08+05:00
     * @param {string} dateStr - Date string in format YYYY-MM-DD
     * @returns {string} Formatted date string
     */
    formatDateForDisplay(dateStr) {
        try {
            const date = new Date(dateStr);
            return new Intl.DateTimeFormat(undefined, {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            }).format(date);
        } catch (error) {
            console.error('Error formatting date for display:', error);
            return dateStr;
        }
    }

    //--------------------------------------------------------------------------
    // Error Handling
    //--------------------------------------------------------------------------

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
            sticky: false,
        });
    }

    //--------------------------------------------------------------------------
    // Data Fetching & Initialization
    //--------------------------------------------------------------------------
    /**
     * Fetch list of companies (hotels)
     * @throws {OfflineSearchWidgetError}
     */
    async fetchCompanies() {
    try {
        // Fetch companies with ORM query
        const companies = await this.orm.searchRead(
            'res.company',
            [], // No filter, fetch all companies
            ['id', 'name', 'system_date'], // Only required fields
            { order: 'name ASC', limit: 100 } // Sort and limit results
        );

        // Ensure the fetched companies have valid data
        const validatedCompanies = companies.map((company) => ({
            id: company.id,
            name: company.name || 'Unnamed Company', // Default name if missing
            system_date: company.system_date || null, // Include system date
        }));

        // Handle the case where no companies are found
        if (!validatedCompanies.length) {
            throw new OfflineSearchWidgetError(
                'No companies found',
                'FETCH_COMPANIES_EMPTY',
                { searchDomain: [] }
            );
        }

        // Update state with the validated companies
        this.state.hotels = validatedCompanies;

        // Get the current company ID from the service
        const currentCompanyId = this.companyService.currentCompany?.id;
//        console.log('Current company ID:', currentCompanyId);

        // Find the current company in the validated list
        const currentCompany = validatedCompanies.find(
            (company) => company.id === currentCompanyId
        );

        if (!currentCompany) {
            console.warn('Current company not found in the fetched companies list.');
        }

        // Initialize the default hotel with the current company
        this.initializeDefaultHotel(currentCompany || validatedCompanies[0]); // Fallback to the first company

        // Log success for debugging
//        console.log(
//            'Fetched and validated companies:',
//            validatedCompanies.map((company) => company.name || 'Unnamed Company')
//        );
    } catch (error) {
        // Handle errors and log details
        console.error('Error fetching companies:', error);
        throw new OfflineSearchWidgetError(
            'Failed to fetch companies',
            'FETCH_COMPANIES_FAILED',
            {
                originalError: error.message,
                stack: error.stack,
            }
        );
    }
    }
    /**
     * Fetch list of Customers
     * @throws {OfflineSearchWidgetError}
     */
    async fetchContacts() {
        try {
            // Ensure name is included in ORM query
            const contacts = await this.orm.searchRead(
                'res.partner',
                [],
                ['id', 'name'],
                { order: 'name ASC'}
            );

            // Validate and ensure each company has a name
            const validatedContacts = contacts.map(contact => ({
                ...contact,
                name: contact.name || 'Unnamed Contact'  // Provide default name if missing
            }));

            // Check if companies array is not empty before accessing properties
            if (!validatedContacts || validatedContacts.length === 0) {
                throw new OfflineSearchWidgetError(
                    'No companies found',
                    'FETCH_CONTACT_EMPTY',
                    { searchDomain: [] }
                );
            }

            // Initialize hotels state
            this.state.contacts = validatedContacts;

            // Add detailed comments with timestamp
            // 2025-01-08T21:25:01+05:00: Ensured name is included in ORM query and added fallback for logging
        } catch (error) {
            throw new OfflineSearchWidgetError(
                'Failed to fetch contacts',
                'FETCH_CONTACTS_FAILED',
                {
                    originalError: error.message,
                    stack: error.stack,
                }
            );
        }
    }

    /**
     * Fetch list of Groups
     * @throws {OfflineSearchWidgetError}
     */
    async fetchGroups() {
        try {
            // Ensure name is included in ORM query
            const groups = await this.orm.searchRead(
                'group.booking',
                [],
                ['id', 'name', 'group_name'],
            );

            // Validate and ensure each company has a name
            const validatedGroups = groups.map(group => ({
                ...group,
                name: group.group_name || group.name  // Provide default name if missing
            }));

            // Check if companies array is not empty before accessing properties
            if (!validatedGroups || validatedGroups.length === 0) {
                throw new OfflineSearchWidgetError(
                    'No Groups found',
                    'FETCH_GROUPS_EMPTY',
                    { searchDomain: [] }
                );
            }

            // Initialize hotels state
            this.state.groups = validatedGroups;

            // Add detailed comments with timestamp
            // 2025-01-08T21:25:01+05:00: Ensured name is included in ORM query and added fallback for logging
        } catch (error) {
            throw new OfflineSearchWidgetError(
                'Failed to fetch groups',
                'FETCH_GROUPS_FAILED',
                {
                    originalError: error.message,
                    stack: error.stack,
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
//        console.log("First company", firstCompany);

        // Validate and set system date
        if (firstCompany.system_date) {
//            console.log("TEST")
            try {
                const systemDate = new Date(firstCompany.system_date);
                if (isNaN(systemDate.getTime())) {
                    throw new Error('Invalid date format');
                }
//                this.state.systemDate = systemDate.toISOString().slice(0, 10);
//
//                console.log("systemDate", systemDate, typeof(this.state.systemDate), typeof(systemDate));
//
//                // Format the date to dd-mm-yyyy
//                const formattedDate = systemDate.toLocaleDateString('en-GB');
//                const finalFormattedDate = formattedDate.replace(/\//g, '-');
//                console.log("finalFormattedDate", finalFormattedDate);
//                this.state.systemDate = finalFormattedDate;
//                this.state.checkInDate = finalFormattedDate;
                this.state.systemDate = new Date().toISOString().slice(0, 10);
                this.state.checkInDate = this.state.systemDate;
                this.state.noOfNights = this.state.noOfNights || 1;

//                console.log(this.state.noOfNights);

//                const checkInDateObj = new Date(finalFormattedDate); // Use the original Date object for manipulation
//                checkInDateObj.setDate(checkInDateObj.getDate() + this.state.noOfNights); // Add the number of nights
//                const checkOutFormatted = checkInDateObj.toLocaleDateString('en-GB').replace(/\//g, '-'); // Format to dd-mm-yyyy
//                this.state.checkOutDate = checkOutFormatted;

                this.updateCheckOutDate();
                this.render();
            } catch (dateError) {
                console.warn('Date initialization failed:', dateError);
                // Fallback to current date
                this.state.systemDate = new Date().toISOString().slice(0, 10);
                this.state.checkInDate = this.state.systemDate;
            }
        }
    }

    /**
     * Initialize Default Hotel with Comprehensive Validation
     * @param {Object} firstCompany - First company from the list
     */
    initializeDefaultContact(firstContact) {
        if (!firstContact) {
            throw new OfflineSearchWidgetError(
                'Cannot initialize default contact',
                'INIT_CONTACT_FAILED',
                { reason: 'No contact data available' }
            );
        }

//        this.state.guestContact = firstContact.id;
    }

    /**
     * Fetch Room Types with Comprehensive Error Handling
     * Modified: 2025-01-08T23:31:04+05:00
     * @throws {OfflineSearchWidgetError}
     */
    async fetchRoomTypes() {
        try {
            const hotelId = this.state.hotel;

            // Get room types through hotel.inventory with overbooking info
            const inventoryItems = await this.orm.searchRead(
                'hotel.inventory',
                [['company_id', '=', hotelId]],
                [
                    'room_type',
                    'total_room_count',
                    'overbooking_allowed',
                    'overbooking_rooms',
                    'web_allowed_reservations',
                    'hotel_name',
                    'pax'
                ]
            );

            if (!inventoryItems || !inventoryItems.length) {
                console.log('No inventory items found for hotel:', hotelId);
                this.state.roomTypes = [];
                return;
            }

            // Group inventory items by hotel and room type
            const hotelInventory = {};
            const roomTypeInventory = {};

            inventoryItems.forEach(item => {
                if (!item.room_type) return;

                const hotelKey = item.hotel_name;
                const roomTypeKey = item.room_type[0];
                const roomTypeName = item.room_type[1];

                // Initialize hotel inventory if not exists
                if (!hotelInventory[hotelKey]) {
                    hotelInventory[hotelKey] = {
                        totalRooms: 0,
                        totalOverbookingRooms: 0,
                        totalWebReservations: 0,
                        totalPax: 0,
                        roomTypes: new Set()
                    };
                }

                // Update hotel totals
                hotelInventory[hotelKey].totalRooms += item.total_room_count || 0;
                hotelInventory[hotelKey].totalOverbookingRooms += item.overbooking_allowed ? (item.overbooking_rooms || 0) : 0;
                hotelInventory[hotelKey].totalWebReservations += item.web_allowed_reservations || 0;
                hotelInventory[hotelKey].totalPax += item.pax || 0;
                hotelInventory[hotelKey].roomTypes.add(roomTypeName);

                // Initialize room type inventory if not exists
                if (!roomTypeInventory[roomTypeKey]) {
                    roomTypeInventory[roomTypeKey] = {
                        id: roomTypeKey,
                        room_type: roomTypeName,
                        total_rooms: 0,
                        overbooking_rooms: 0,
                        web_reservations: 0,
                        total_pax: 0,
                        hotels: new Set()
                    };
                }

                // Update room type totals
                roomTypeInventory[roomTypeKey].total_rooms += item.total_room_count || 0;
                roomTypeInventory[roomTypeKey].overbooking_rooms += item.overbooking_allowed ? (item.overbooking_rooms || 0) : 0;
                roomTypeInventory[roomTypeKey].web_reservations += item.web_allowed_reservations || 0;
                roomTypeInventory[roomTypeKey].total_pax += item.pax || 0;
                roomTypeInventory[roomTypeKey].hotels.add(hotelKey);
            });

            // Convert room type inventory to array and sort
            const uniqueRoomTypes = Object.values(roomTypeInventory)
                .map(rt => ({
                    ...rt,
                    hotels: Array.from(rt.hotels),
                    total_capacity: rt.total_rooms + rt.overbooking_rooms
                }))
                .sort((a, b) => a.room_type.localeCompare(b.room_type));

            if (!uniqueRoomTypes.length) {
                console.log('No room types found in inventory:', inventoryItems);
                throw new OfflineSearchWidgetError(
                    'No room types found for the selected hotel',
                    'FETCH_ROOM_TYPES_EMPTY',
                    {
                        hotelId,
                        inventoryCount: inventoryItems.length,
                        hotelInventory
                    }
                );
            }

            // Store both room types and hotel inventory in state
            this.state.roomTypes = uniqueRoomTypes;
            this.state.hotelInventory = Object.entries(hotelInventory).map(([id, data]) => ({
                id,
                ...data,
                roomTypes: Array.from(data.roomTypes),
                totalCapacity: data.totalRooms + data.totalOverbookingRooms
            }));

            // Log detailed inventory information
            console.log('Hotel Inventory:', this.state.hotelInventory);
            console.log('Room Types:', uniqueRoomTypes.map(type => ({
                name: type.room_type,
                capacity: `${type.total_rooms} + ${type.overbooking_rooms} overbooking`,
                webReservations: type.web_reservations,
                pax: type.total_pax,
                hotels: type.hotels
            })));

        } catch (error) {
            console.error('Error in fetchRoomTypes:', error);
            throw new OfflineSearchWidgetError(
                'Failed to fetch room types',
                'FETCH_ROOM_TYPES_FAILED',
                {
                    originalError: error.message || error.toString(),
                    stack: error.stack,
                }
            );
        }
    }

    //--------------------------------------------------------------------------
    // Date & Nights Calculation
    //--------------------------------------------------------------------------

    /**
     * Format datetime string to date string (YYYY-MM-DD)
     * Modified: 2025-01-08T23:51:12+05:00
     * @param {string} datetime - Datetime string in format YYYY-MM-DD HH:mm:ss
     * @returns {string} Date string in format YYYY-MM-DD
     */
    formatDateString(datetime) {
        try {
            if (!datetime) return '';
            if (typeof datetime === 'string') {
                return datetime.split(' ')[0];
            }
            return datetime;
        } catch (error) {
            console.error('Error formatting date:', error);
            return '';
        }
    }

    /**
     * Update check-out date based on check-in and nights
     * Modified: 2025-01-08T23:51:12+05:00
     */
    updateCheckOutDate() {
        try {
//            console.log("TESTING", this.state.checkInDate);
            if (!this.state.checkInDate) return;

            const checkIn = new Date(this.state.checkInDate);
            const checkOut = new Date(checkIn);

            const nights = this.state.noOfNights || 0;
            if (nights <= 0) {
                // If nights is zero or negative, fallback to same day
                this.state.checkOutDate = this.state.checkInDate;
            } else {
                checkOut.setDate(checkOut.getDate() + nights);
                this.state.checkOutDate = checkOut.toISOString().split('T')[0];
            }
//            console.log("CHECKOUT DATE", this.state.checkOutDate);
        } catch (error) {
            console.error('Error in updateCheckOutDate:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Update nights based on check-in and check-out
     */
    updateNights() {
        if (!this.state.checkInDate || !this.state.checkOutDate) return;

        const checkIn = new Date(this.state.checkInDate);
        const checkOut = new Date(this.state.checkOutDate);
        const diffTime = checkOut.getTime() - checkIn.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        this.state.noOfNights = diffDays > 0 ? diffDays : 1;
    }

    //--------------------------------------------------------------------------
    // Basic Validation Logic
    //--------------------------------------------------------------------------

    /**
     * Check if `dateToCheck` is within 2 years from `referenceDate`
     * @param {Date} dateToCheck
     * @param {Date} referenceDate
     * @returns {boolean}
     */
    isWithinTwoYears(dateToCheck, referenceDate) {
        try {
            const twoYearsFromRef = new Date(referenceDate);
            twoYearsFromRef.setFullYear(twoYearsFromRef.getFullYear() + 2);

            // Compare as pure dates, ignoring time
            dateToCheck.setHours(0, 0, 0, 0);
            twoYearsFromRef.setHours(0, 0, 0, 0);

            return dateToCheck <= twoYearsFromRef;
        } catch (error) {
            console.error('Error in isWithinTwoYears:', error);
            return false;
        }
    }

    /**
     * Validate check-in date
     * @param {string} date - Date to validate (YYYY-MM-DD)
     * @returns {boolean} - True if date is valid
     */
    validateCheckInDate(date) {
        if (!date || !this.state.systemDate) return false;

        try {
            const checkInDate = new Date(date);
            const systemDate = new Date(this.state.systemDate);

            // Compare as pure dates
            checkInDate.setHours(0, 0, 0, 0);
            systemDate.setHours(0, 0, 0, 0);

            // Must not be before system date and within 2 years
            return (
                !isNaN(checkInDate) &&
                !isNaN(systemDate) &&
                checkInDate >= systemDate &&
                this.isWithinTwoYears(checkInDate, systemDate)
            );
        } catch (error) {
            console.error('Error validating check-in date:', error);
            return false;
        }
    }

    /**
     * Validate check-out date
     * Modified: 2025-01-08T23:39:34+05:00
     * @param {string} date - Date to validate (YYYY-MM-DD)
     * @returns {boolean} - True if date is valid
     */
    validateCheckOutDate(date) {
        if (!date || !this.state.checkInDate) return false;

        try {
            const checkOutDate = new Date(date);
            const checkInDate = new Date(this.state.checkInDate);
            const systemDate = new Date(this.state.systemDate);

            // Compare as pure dates
            checkOutDate.setHours(0, 0, 0, 0);
            checkInDate.setHours(0, 0, 0, 0);
            systemDate.setHours(0, 0, 0, 0);

            // Must be after or equal to check-in date and within 2 years of system date
            return (
                !isNaN(checkOutDate) &&
                !isNaN(checkInDate) &&
                checkOutDate >= checkInDate &&
                this.isWithinTwoYears(checkOutDate, systemDate)
            );
        } catch (error) {
            console.error('Error validating check-out date:', error);
            return false;
        }
    }

    /**
     * Validate number of nights
     * Modified: 2025-01-09T11:53:04+05:00
     * @param {number} nights
     * @returns {boolean}
     */
    validateNights(nights) {
        try {
            // 2 years = 730 nights
            const MAX_NIGHTS = 730;
            return nights >= 0 && nights <= MAX_NIGHTS;
        } catch (error) {
            console.error('Error validating nights:', error);
            return false;
        }
    }

    /**
     * Calculate and update the maximum allowed check-out date
     * Modified: 2025-01-08T23:39:34+05:00
     */
    updateMaxCheckOutDate() {
        if (!this.state.checkInDate) return;

        const maxDate = new Date(this.state.checkInDate);
        maxDate.setDate(maxDate.getDate() + 730); // Max 2 years from check-in
        this.state.maxCheckOutDate = maxDate.toISOString().split('T')[0];
    }

    //--------------------------------------------------------------------------
    // Handlers: Date, Nights, Hotel, etc.
    //--------------------------------------------------------------------------

    /**
     * Called when the hotel selection changes
     * Modified: 2025-01-08T23:51:12+05:00
     * @param {Event} ev
     */
    async onHotelChange(ev) {
        try {
            const hotelId = parseInt(ev.target.value);
            this.state.hotel = hotelId;

            // Find the selected hotel
            const selectedHotel = this.state.hotels.find(h => h.id === hotelId);
            if (!selectedHotel) {
                console.error('Selected hotel not found:', hotelId);
                return;
            }

            // Update system date from hotel (format to YYYY-MM-DD)
            this.state.systemDate = this.formatDateString(selectedHotel.system_date);

            // Update check-in date to hotel's system date
            this.state.checkInDate = this.state.systemDate;

            // Reset other fields
            this.state.noOfNights = 1;
            this.state.checkOutDate = '';

            // Update check-out date based on new check-in
            this.updateMaxCheckOutDate();
            this.updateCheckOutDate();

            // Fetch room types for the selected hotel
            await this.fetchRoomTypes();
        } catch (error) {
            console.error('Error in onHotelChange:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Check-in date input change handler
     * Modified: 2025-01-09T00:07:41+05:00
     * @param {Event} ev - The change event
     */
    onCheckInDateChange(ev) {
        try {
            const newDate = ev.target.value;
            if (!this.validateCheckInDate(newDate)) {
                this.notification.add(
                    _t("Check-in date must not be before hotel's system date and within 2 years"),
                    { type: 'warning' }
                );
                this.resetDateFields();
                return;
            }

            // Update check-in date and max check-out date
            this.state.checkInDate = newDate;
            this.updateMaxCheckOutDate();

            // If check-out date exists, validate and update nights
            if (this.state.checkOutDate) {
                if (!this.validateCheckOutDate(this.state.checkOutDate)) {
                    // Reset check-out date if it's now invalid
                    this.state.checkOutDate = '';
                    this.state.noOfNights = 1;
                    this.updateCheckOutDate();
                } else {
                    this.updateNights();
                }
            } else {
                // No check-out date, set default nights and calculate check-out
                this.state.noOfNights = 1;
                this.updateCheckOutDate();
            }
        } catch (error) {
            console.error('Error in onCheckInDateChange:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Check-in date blur handler
     * Modified: 2025-01-09T00:07:41+05:00
     * @param {Event} ev - The blur event
     */
    onCheckInDateBlur(ev) {
        try {
            if (!this.state.checkInDate) return;

            if (!this.validateCheckInDate(this.state.checkInDate)) {
                this.notification.add(
                    _t("Check-in date must not be before hotel's system date and within 2 years"),
                    { type: 'warning' }
                );
                this.resetDateFields();
            }
        } catch (error) {
            console.error('Error in onCheckInDateBlur:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Check-out date input change handler
     * Modified: 2025-01-09T00:07:41+05:00
     * @param {Event} ev - The change event
     */
    onCheckOutDateChange(ev) {
        try {
            const newDate = ev.target.value;
            if (!this.validateCheckOutDate(newDate)) {
                this.notification.add(
                    _t("Check-out date must be after check-in date and within 2 years"),
                    { type: 'warning' }
                );
                this.resetDateFields();
                return;
            }

            // Update check-out date and recalculate nights
            this.state.checkOutDate = newDate;
            this.updateNights();

            // Validate the resulting number of nights
            if (!this.validateNights(this.state.noOfNights)) {
                this.notification.add(
                    _t("The selected dates result in an invalid stay duration. Maximum stay is 730 nights"),
                    { type: 'warning' }
                );
                this.resetDateFields();
            }
        } catch (error) {
            console.error('Error in onCheckOutDateChange:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Check-out date blur handler
     * Modified: 2025-01-09T00:07:41+05:00
     * @param {Event} ev - The blur event
     */
    onCheckOutDateBlur(ev) {
        try {
            if (!this.state.checkOutDate) return;

            if (!this.validateCheckOutDate(this.state.checkOutDate)) {
                this.notification.add(
                    _t("Check-out date must be after check-in date and within 2 years"),
                    { type: 'warning' }
                );
                this.resetDateFields();
                return;
            }

            // Ensure nights calculation is valid
            if (!this.validateNights(this.state.noOfNights)) {
                this.notification.add(
                    _t("The selected dates result in an invalid stay duration. Maximum stay is 730 nights"),
                    { type: 'warning' }
                );
                this.resetDateFields();
            }
        } catch (error) {
            console.error('Error in onCheckOutDateBlur:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Nights input change
     * @param {string|number} value
     */
    onNightsChange(value) {
        try {
            const nights = parseInt(value) || 0;
            if (!this.validateNights(nights)) {
                this.notification.add(
                    _t("Number of nights must be between 0 and 730"),
                    { type: 'warning' }
                );
                this.resetDateFields();
            } else {
                this.state.noOfNights = nights;
                this.updateCheckOutDate();
            }
        } catch (error) {
            console.error('Error in onNightsChange:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Nights input blur handler
     * Modified: 2025-01-09T00:07:41+05:00
     * @param {string|number} value
     */
    onNightsBlur(value) {
        try {
            const nights = parseInt(value) || 0;
            if (!this.validateNights(nights)) {
                this.notification.add(
                    _t("Number of nights must be between 0 and 730"),
                    { type: 'warning' }
                );
                this.resetDateFields();
            }
        } catch (error) {
            console.error('Error in onNightsBlur:', error);
            this.handleWidgetError(error);
        }
    }

    /**
     * Reset date fields to defaults
     * Modified: 2025-01-08T23:51:12+05:00
     */
    resetDateFields() {
        // Use hotel's system date if available, otherwise use state.systemDate
        const defaultDate = this.state.hotel
            ? this.formatDateString(this.state.hotels.find(h => h.id === this.state.hotel)?.system_date)
            : this.state.systemDate;

        Object.assign(this.state, {
            checkInDate: defaultDate,
            noOfNights: 1,
            checkOutDate: ''
        });

        this.updateMaxCheckOutDate();
        this.updateCheckOutDate();
    }

    /**
     * Update room count
     * @param {string} value
     */
    updateRooms(value) {
        const rooms = parseInt(value) || 1;
        if (rooms < 1) {
            this.state.rooms = 1;
            this.notification.add(
                _t("Number of rooms cannot be less than 1"),
                { type: 'warning' }
            );
        } else {
            this.state.rooms = rooms;
        }
    }

    /**
     * Update number of adults
     * @param {string} value
     */
    updateAdults(value) {
        const adults = parseInt(value) || 0;
        this.state.adults = adults <= 0 ? 1 : adults;
    }

    /**
     * Update number of children
     * @param {string} value
     */
    updateChildren(value) {
        const children = parseInt(value) || 0;
        this.state.children = children < 0 ? 0 : children;
    }

    /**
     * Update number of infants
     * @param {string} value
     */
    updateInfants(value) {
        const infants = parseInt(value) || 0;
        this.state.infants = infants < 0 ? 0 : infants;
    }

    /**
     * Select Group Booking
     * Selects a group booking from the search results
     * Modified: 2025-01-10T20:37:37+05:00
     * @param {Object} groupBooking - Selected group booking object
     */
    selectGroupBooking(groupBooking) {
        try {
            if (groupBooking) {
                this.state.groupBooking = groupBooking;
                this.state.groupBookingSearch = groupBooking.name || '';
                this.state.filteredGroupBookings = [];
            }
        } catch (error) {
            console.error('Error in selectGroupBooking:', error);
            alert('Failed to select group booking. Please try again.');
        }
    }

    /**
     * Toggle guest information
     */
    toggleGuestInfo() {
        this.state.showGuestInfo = !this.state.showGuestInfo;
    }

    /**
     * Toggle column visibility
     * @param {string} columnName
     */
    toggleColumn(columnName) {
        const column = this.state.columns.find(c => c.name === columnName);
        if (column) {
            column.visible = !column.visible;
            this.render();
        }
    }

    /**
     * Search for available rooms
     * Modified: 2025-01-09T15:46:05+05:00
     * @returns {Promise<void>}
     */
    async searchRooms() {
        try {
            // Only clear search results while preserving other state
            this.state.searchResults = [];
            this.state.searchPerformed = true;
            this.state.searchError = null;
            this.state.isSearching = true;
            console.log("this.state.roomType", this.state.roomType);

            const results = await this.orm.call(
                'room.search',
                'search_available_rooms',
                [
                    this.state.checkInDate,
                    this.state.checkOutDate,
                    this.state.rooms,
                    this.state.hotel,
                    this.state.roomType
                ]
            );

            console.log('Raw results from server:', results); // Debug log

            let filteredResults = results;

            if (this.state.roomType) {
                const roomTypeId = Number(this.state.roomType); // Convert to a number if it's not already
                filteredResults = results.filter(result => Number(result.room_type_id) === roomTypeId);
                console.log("TEST", filteredResults);
            }

            console.log('filtered results from server:', filteredResults);

            if (Array.isArray(filteredResults)) {
                // Add derived fields including actualFreeToSell and overbooked
                this.state.searchResults = filteredResults.map(room => {
                    const minFreeToSell = room.min_free_to_sell || 0;
                    const total_overbooking_rooms = room.total_overbooking_rooms || 0;
                    const actualFreeToSell = minFreeToSell - total_overbooking_rooms;

                    return {
                        ...room,
                        actualFreeToSell: actualFreeToSell > 0 ? actualFreeToSell : 0,
                        overbooked: actualFreeToSell < 0 ? Math.abs(actualFreeToSell) : 0
                    };
                });
            }
        } catch (error) {
            console.error('Error during room search:', error);
            this.state.searchError = error.message || _t('An error occurred while searching rooms');
            this.notification.add(this.state.searchError, {
                type: 'danger',
                sticky: true,
                title: _t('Search Error')
            });
            this.state.searchResults = [];
        } finally {
            this.state.isSearching = false;
        }
    }

    /**
     * Calling Search after creating bookings
     * Modified: 2025-01-09T15:46:05+05:00
     * @returns {Promise<void>}
     */
    async actionSearchRooms(recordId) {
        try {
            const results = await this.orm.call(
                'room.booking',
                'action_search_rooms',
                [[recordId]]
            );

            console.log('calling action_search_rooms server:', results);
        } catch (error) {
            console.error('Error action search rooms:', error);
//            this.state.searchError = error.message || _t('An error occurred while searching rooms');
//            this.notification.add(this.state.searchError, {
//                type: 'danger',
//                sticky: true,
//                title: _t('Search Error')
//            });
//            this.state.searchResults = [];
        } finally {
            this.state.isSearching = false;
        }
    }

    /**
     * Call to backend method to get available rooms
     * Modified: 2025-01-09T15:38:02+05:00
     * @param {string} fromDate - Check-in date in YYYY-MM-DD
     * @param {string} toDate - Check-out date in YYYY-MM-DD
     * @param {number} roomCount
     * @returns {Promise<Array>}
     */
    async searchAvailableRooms(fromDate, toDate, roomCount) {
        try {
            // Validate parameters before making the call
            if (!fromDate) throw new Error('Check-in date is required');
            if (!toDate) throw new Error('Check-out date is required');
            if (!roomCount || roomCount < 1) throw new Error('Number of rooms must be at least 1');
            if (!this.state.hotel) throw new Error('Hotel selection is required');

            // Show searching notification
            this.notification.add(_t('Searching for available rooms...'), {
                type: 'info',
                sticky: false,
                title: _t('Search Status')
            });

            // Call the backend method
            const results = await this.orm.call(
                'room.search',
                'search_available_rooms',
                [fromDate, toDate, roomCount, this.state.hotel, this.state.roomType || false]
            );

            // Update state with results (even if empty)
            this.state.searchResults = results;
            this.state.searchPerformed = true;

            // Show appropriate notification
            if (results.length > 0) {
                this.notification.add(
                    _t('Found %s available room types', results.length),
                    { type: 'success', sticky: false }
                );
            } else {
                this.notification.add(
                    _t('No rooms available for the selected criteria'),
                    { type: 'info', sticky: false }
                );
            }

            return results;

        } catch (error) {
            console.error('Search Error:', error);

            // Update state to reflect error
            this.state.searchResults = [];
            this.state.searchPerformed = true;
            this.state.searchError = error.message || 'Failed to search rooms';

            // Show error notification
            this.notification.add(
                error.data?.message || error.message || _t('Failed to search rooms'),
                { type: 'warning', sticky: true, title: _t('Search Error') }
            );

            // Don't throw error, just return empty results
            return [];
        }
    }

    /**
     * Clear search results
     */
    clearSearch() {
        this.state = {
            ...this.state,
            company_id: false,
            checkin_date: false,
            checkout_date: false,
            room_count: 1,
            room_type_id: false,
            adult_count: 1,
            child_count: 0,
            infant_count: 0,
            searchResults: []
        };
        this.render();
    }

    /**
     * Sync booking data with the currently open room.booking form
     * @param {number} roomTypeId - ID of the room type to book
     * Modified: 2025-01-10T22:28:28+05:00
     */
    async createBooking(roomTypeId) {
        console.log('Starting createBooking with Room Type ID:', roomTypeId);
        try {
            // Validate required fields
            if (!this.state.hotel) {
                throw new Error('Hotel is required');
            }

//            // Validate required fields
//            if (!this.state.guestContact) {
//                throw new Error('Contact is required for creating booking');
//            }

            // Prepare the booking data
            const bookingData = {
                company_id: this.state.hotel,
                room_count: this.state.rooms,
                checkin_date: this.state.checkInDate,
                no_of_nights: this.state.noOfNights,
                checkout_date: this.state.checkOutDate,
                adult_count: this.state.adults,
                child_count: this.state.children,
                infant_count: this.state.infants,
//                partner_id: this.state.guestContact,
//                group_booking: this.state.guestGroup ?? '',
                state: 'not_confirmed',
                hotel_room_type: roomTypeId,
            };

            console.log('Booking Data to be sent:', bookingData);

            try {
                // Create a new record first
                console.log('Creating new booking record...');
                const newRecordId = await this.orm.call(
                    'room.booking',
                    'create',
                    [bookingData]
                );

                console.log('New record created with ID:', newRecordId);
                await this.actionSearchRooms(newRecordId);

                if (newRecordId) {
                    // Open the form view with the new record
                    const action = {
                        type: 'ir.actions.act_window',
                        res_model: 'room.booking',
                        res_id: newRecordId,
                        views: [[false, 'form']],
                        target: 'current',
                        flags: {
                            mode: 'edit'
                        }
                    };

                    // Execute the action to open the form view
                    await this.env.services.action.doAction(action);

                    this.notification.add('Booking created successfully!', {
                        type: 'success',
                        sticky: false
                    });
                } else {
                    throw new Error('Failed to create booking record');
                }
            } catch (writeError) {
                console.error('Booking creation error:', {
                    error: writeError,
                    message: writeError.message,
                    name: writeError.name,
                    data: writeError.data,
                    stack: writeError.stack
                });
                throw writeError;
            }

        } catch (error) {
            console.error('Detailed error information:', {
                message: error.message,
                name: error.name,
                stack: error.stack,
                cause: error.cause,
                data: error.data
            });

            this.notification.add(`Failed to create booking: ${error.message}`, {
                type: 'danger',
                sticky: true
            });
        }
    }

    /**
     * Handle room booking action
     * @param {number} roomTypeId - ID of the room type to book
     */
    async bookRoom(roomTypeId) {
        try {
            // Create action context with pre-filled values
            const context = {
                default_hotel_room_type_id: roomTypeId,
                default_company_id: this.state.hotel,
                default_checkin_date: this.state.checkInDate,
                default_checkout_date: this.state.checkOutDate,
                default_adult_count: this.state.adults,
                default_child_count: this.state.children,
                default_infant_count: this.state.infants,
                default_room_count: this.state.rooms
            };

            // Open the room booking form view
            await this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'room.booking',
                view_mode: 'form',
                view_type: 'form',
                views: [[false, 'form']],
                target: 'current',
                context: context,
            });
        } catch (error) {
            console.error('Error creating booking:', error);
            this.notification.notify({
                title: 'Error',
                message: 'Failed to create booking. Please try again.',
                type: 'danger'
            });
        }
    }

    /**
     * Search Group Bookings based on input
     * @date 2025-01-07T20:20:32+05:00
     * Adjusted to use company field correctly linked to res.partner
     */
    async onGroupBookingSearch() {
        try {
            // Safely get search term with fallback
            const searchTerm = (this.state.groupBookingSearch || '').trim();

            // Early return if no search term
            if (!searchTerm) {
                this.state.filteredGroupBookings = [];
                return;
            }

            // Construct search domain
            const domain = [
                '|', '|', '|', '|',
                ['name', 'ilike', searchTerm],
                ['group_name', 'ilike', searchTerm],
                ['company.name', 'ilike', searchTerm],
                ['company.email', 'ilike', searchTerm],
                ['company.phone', 'ilike', searchTerm]
            ];

            // Fetch group bookings with related details
            const groupBookings = await this.orm.searchRead(
                'group.booking',
                domain,
                [
                    'id',        // Unique identifier
                    'name',      // Booking name
                    'group_name', // Specific group name
                    'company'    // Related company information
                ],
                {
                    limit: 50,
                    context: {
                        lang: this.env.lang,
                        tz: this.env.context.tz
                    }
                }
            );

            // Transform results safely
            this.state.filteredGroupBookings = groupBookings.map(groupBooking => ({
                id: groupBooking.id || null,
                name: groupBooking.name || '',
                groupName: groupBooking.group_name || '',
                companyName: groupBooking.company ? groupBooking.company[1] : '',
                contactDetails: {
                    email: groupBooking.company ?
                        (this.orm.read('res.partner', [groupBooking.company[0]], ['email'])[0]?.email || '') : '',
                    phone: '',
                    address: ''
                }
            }));

        } catch (error) {
            // Comprehensive error handling
            console.error('Group Booking Search Error', error);

            // User-friendly notification
            alert('Search failed. Please try again.');

            // Reset filtered bookings on error
            this.state.filteredGroupBookings = [];
        }
    }
}

// Register the widget
// registry.category("fields").add("offline_search_widget", OfflineSearchWidget);
// Define the template
OfflineSearchWidget.template = "hotel_management_odoo.OfflineSearchWidget";