/* @odoo-module */

(function () {
    /**
     * Simple handler for room_count field changes.
     * This implementation uses a basic window.confirm dialog with a title
     * but ensures the field remains editable.
     */
    function attachRoomCountHandler() {
        // Find the room_count input field
        const input = document.querySelector('[name="room_count"] input.o_input');
        
        // If not found or already processed, exit
        if (!input || input.__rcp_attached) return;
        
        // Mark as processed so we don't attach multiple handlers
        input.__rcp_attached = true;
        
        // Store the initial value
        input.__rcp_old = parseInt(input.value || "0", 10);
        console.log("🏨 room_count handler attached (old=" + input.__rcp_old + ")");
        
        // Use change event instead of blur to ensure editing works properly
        input.addEventListener("change", function (e) {
            // Get new value
            const newValue = parseInt(e.target.value || "0", 10);
            
            // Skip if no change
            if (newValue === input.__rcp_old) return;
            
            // Use setTimeout to ensure field value is properly updated first
            setTimeout(function() {
                // Create a custom styled confirmation dialog like the image
                const dialogOverlay = document.createElement('div');
                dialogOverlay.style.position = 'fixed';
                dialogOverlay.style.top = '0';
                dialogOverlay.style.left = '0';
                dialogOverlay.style.width = '100%';
                dialogOverlay.style.height = '100%';
                dialogOverlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
                dialogOverlay.style.display = 'flex';
                dialogOverlay.style.alignItems = 'center';
                dialogOverlay.style.justifyContent = 'center';
                dialogOverlay.style.zIndex = '9999';
                dialogOverlay.setAttribute('id', 'room-booking-dialog');
                
                const dialogBox = document.createElement('div');
                dialogBox.style.backgroundColor = 'white';
                dialogBox.style.borderRadius = '8px';
                dialogBox.style.width = '400px';
                dialogBox.style.maxWidth = '90%';
                dialogBox.style.padding = '20px';
                dialogBox.style.textAlign = 'center';
                dialogBox.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
                
                // Create icon container - exclamation mark in circle
                const iconContainer = document.createElement('div');
                iconContainer.style.width = '60px';
                iconContainer.style.height = '60px';
                iconContainer.style.borderRadius = '50%';
                iconContainer.style.backgroundColor = 'rgba(255, 160, 110, 0.2)';
                iconContainer.style.border = '3px solid rgb(255, 160, 110)';
                iconContainer.style.margin = '0 auto 15px';
                iconContainer.style.display = 'flex';
                iconContainer.style.alignItems = 'center';
                iconContainer.style.justifyContent = 'center';
                iconContainer.style.fontSize = '36px';
                iconContainer.style.fontWeight = 'bold';
                iconContainer.style.color = 'rgb(255, 160, 110)';
                iconContainer.textContent = '!';
                
                // Create title
                const title = document.createElement('h3');
                title.style.margin = '10px 0 20px';
                title.style.fontSize = '24px';
                title.style.color = '#333';
                title.textContent = 'Are you sure?';
                
                // Create message
                const message = document.createElement('p');
                message.style.margin = '0 0 25px';
                message.style.color = '#666';
                message.style.fontSize = '16px';
                message.textContent = 'Do you want to search rooms for count ' + newValue + '?';
                
                // Create buttons container
                const btnContainer = document.createElement('div');
                btnContainer.style.display = 'flex';
                btnContainer.style.justifyContent = 'center';
                btnContainer.style.gap = '10px';
                
                // Cancel button
                const cancelBtn = document.createElement('button');
                cancelBtn.style.padding = '10px 20px';
                cancelBtn.style.backgroundColor = '#D9D9D9';
                cancelBtn.style.border = 'none';
                cancelBtn.style.borderRadius = '5px';
                cancelBtn.style.color = '#333';
                cancelBtn.style.fontSize = '14px';
                cancelBtn.style.cursor = 'pointer';
                cancelBtn.textContent = 'Cancel';
                
                // Confirm button
                const confirmBtn = document.createElement('button');
                confirmBtn.style.padding = '10px 20px';
                confirmBtn.style.backgroundColor = '#F0826C';
                confirmBtn.style.border = 'none';
                confirmBtn.style.borderRadius = '5px';
                confirmBtn.style.color = 'white';
                confirmBtn.style.fontSize = '14px';
                confirmBtn.style.cursor = 'pointer';
                confirmBtn.textContent = 'Yes, search rooms!';
                
                // Build the dialog
                btnContainer.appendChild(cancelBtn);
                btnContainer.appendChild(confirmBtn);
                dialogBox.appendChild(iconContainer);
                dialogBox.appendChild(title);
                dialogBox.appendChild(message);
                dialogBox.appendChild(btnContainer);
                dialogOverlay.appendChild(dialogBox);
                document.body.appendChild(dialogOverlay);
                
                // Function to remove dialog
                const removeDialog = () => {
                    document.body.removeChild(dialogOverlay);
                };
                
                // Handle cancel button click
                cancelBtn.addEventListener('click', function() {
                    removeDialog();
                    // Revert the value
                    e.target.value = input.__rcp_old;
                    e.target.dispatchEvent(new Event("input", { bubbles: true }));
                });
                
                // Handle confirm button click
                confirmBtn.addEventListener('click', function() {
                    removeDialog();
                    // User confirmed - call the API
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const recordId = parseInt(params.get("id"), 10);
                    
                    console.log("recordId=", recordId);
                    
                    // Call action_search_rooms API
                    fetch("/web/dataset/call_button", {
                        method: "POST",
                        credentials: "same-origin",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            params: {
                                model: "room.booking",
                                method: "action_search_rooms",
                                args: [[recordId]],
                                kwargs: {},
                            }
                        }),
                    })
                    .then(response => response.json())
                    .then(() => {
                        console.log("🏨 search_rooms called for", recordId);
                        
                        // Update stored old value
                        input.__rcp_old = newValue;
                        
                        // Click the Search button if it exists
                        const searchButton = document.querySelector('button[name="action_search_rooms"]');
                        if (searchButton) {
                            console.log("🏨 clicking Search button");
                            searchButton.click();
                        } else {
                            console.warn("🏨 Search button not found");
                        }
                    })
                    .catch(error => {
                        console.error("Error calling action_search_rooms:", error);
                    });
                });
            }, 50); // Small delay before showing confirm dialog
        });
    }

    /**
     * Initialize: run once on DOM ready, then observe all future mutations.
     */
    function init() {
      attachRoomCountHandler();
      const observer = new MutationObserver(attachRoomCountHandler);
      // Observe whole document (element must exist by now)
      observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  })();