/* @odoo-module */
(function () {
    let dialogShown = false;
    let pollingStarted = false;
    let pendingValue = null;
  
    function getRecordIdFromURL() {
      const urlParams = new URLSearchParams(window.location.hash.split("?")[0].replace("#", "?"));
      return parseInt(urlParams.get("id"), 10);
    }
    
    // Function to check if state is 'confirmed' or 'block'
    function isValidState() {
      const stateField = document.querySelector('[name="state"] .o_field_widget');
      if (stateField) {
        const stateValue = stateField.dataset.value || stateField.textContent.trim().toLowerCase();
        return ['confirmed', 'block'].includes(stateValue.toLowerCase());
      }
      return false;
    }
  
    function saveForm() {
      const formController = document.querySelector(".o_form_view");
      if (formController && formController.owl) {
        const comp = formController.owl;
        if (comp && typeof comp.saveRecord === "function") {
          return comp.saveRecord();
        }
      }
      return Promise.resolve();
    }
  
    function showCustomModal(newValue, onConfirm, onCancel) {
      if (dialogShown) return;
      dialogShown = true;
      pendingValue = newValue;
  
      const dialogOverlay = document.createElement("div");
      dialogOverlay.style = `
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999;
      `;
      dialogOverlay.id = "checkout-date-dialog";
  
      const dialogBox = document.createElement("div");
      dialogBox.style = `
        background-color: white;
        border-radius: 8px;
        width: 400px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
      `;
  
      const icon = document.createElement("div");
      icon.textContent = "!";
      icon.style = `
        width: 60px; height: 60px;
        border-radius: 50%;
        background: rgba(255, 160, 110, 0.2);
        border: 3px solid rgb(255, 160, 110);
        display: flex; align-items: center; justify-content: center;
        font-size: 36px; font-weight: bold; color: rgb(255, 160, 110);
        margin: 0 auto 15px;
      `;
  
      const title = document.createElement("h3");
      title.textContent = "Are you sure?";
      title.style = "margin: 10px 0 20px; font-size: 24px; color: #333;";
  
      const message = document.createElement("p");
      message.textContent = `Do you want to search rooms for check-out date "${newValue}"?`;
      message.style = "margin: 0 0 25px; color: #666; font-size: 16px;";
  
      const btnContainer = document.createElement("div");
      btnContainer.style = "display: flex; justify-content: center; gap: 10px;";
  
      const cancelBtn = document.createElement("button");
      cancelBtn.textContent = "Cancel";
      cancelBtn.style = `
        padding: 10px 20px;
        background-color: #D9D9D9;
        border: none;
        border-radius: 5px;
        color: #333;
        font-size: 14px;
        cursor: pointer;
      `;
  
      const confirmBtn = document.createElement("button");
      confirmBtn.textContent = "Yes, search rooms!";
      confirmBtn.style = `
        padding: 10px 20px;
        background-color: #F0826C;
        border: none;
        border-radius: 5px;
        color: white;
        font-size: 14px;
        cursor: pointer;
      `;
  
      btnContainer.append(cancelBtn, confirmBtn);
      dialogBox.append(icon, title, message, btnContainer);
      dialogOverlay.appendChild(dialogBox);
      document.body.appendChild(dialogOverlay);
  
      const removeDialog = () => {
        if (document.body.contains(dialogOverlay)) {
          document.body.removeChild(dialogOverlay);
          dialogShown = false;
        }
      };
  
      cancelBtn.addEventListener("click", () => {
        removeDialog();
        pendingValue = null;
  
        const input = document.querySelector('[name="checkout_date"] input.o_input');
        const nightsInput = document.querySelector('[name="no_of_nights"] input.o_input'); 
  
        // Always revert checkout_date
        if (input && input.__checkout_date_old) {
          input.value = input.__checkout_date_old;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
  
        // Conditionally revert no_of_nights
        if (
          nightsInput &&
          nightsInput.__no_of_nights_old !== undefined &&
          nightsInput.value !== nightsInput.__no_of_nights_old
        ) {
          nightsInput.value = nightsInput.__no_of_nights_old;
          nightsInput.dispatchEvent(new Event("input", { bubbles: true }));
          nightsInput.dispatchEvent(new Event("change", { bubbles: true }));
          console.log(" no_of_nights reverted");
        } else {
          console.log(" no_of_nights unchanged, not reverted");
        }
  
        saveForm().then(() => {
          console.log(" checkout_date and optionally no_of_nights reverted and saved after Cancel.");
        });
  
        onCancel();
      });
  
      confirmBtn.addEventListener("click", () => {
        removeDialog();
        onConfirm();
      });
    }
  
    function startCheckoutPolling() {
      if (pollingStarted) return;
      pollingStarted = true;
  
      setInterval(() => {
        const input = document.querySelector('[name="checkout_date"] input.o_input');
        const nightsInput = document.querySelector('[name="no_of_nights"] input.o_input'); 
  
        if (!input) return;
  
        const newVal = input.value;
        const nightsVal = nightsInput ? nightsInput.value : null;
  
        if (!input.__checkout_date_old) {
          input.__checkout_date_old = newVal;
          if (nightsInput && nightsInput.__no_of_nights_old === undefined) {
            nightsInput.__no_of_nights_old = nightsVal; 
          }
          return;
        }
  
        if (
          newVal &&
          newVal !== input.__checkout_date_old &&
          newVal !== pendingValue &&
          !dialogShown &&
          isValidState() 
        ) {
          const recordId = getRecordIdFromURL();
          if (!recordId) return;
  
          showCustomModal(newVal, () => {
            pendingValue = null;
            input.__checkout_date_old = newVal;
            if (nightsInput) {
              nightsInput.__no_of_nights_old = nightsVal;
            }
  
            saveForm().then(() => {
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
                  },
                }),
              })
                .then((res) => res.json())
                .then(() => {
                  const btn = document.querySelector('button[name="action_search_rooms"]');
                  if (btn) btn.click();
                });
            });
          }, () => {
            // handled in cancel
          });
        }
      }, 1000);
    }
  
    function init() {
      startCheckoutPolling();
      const observer = new MutationObserver(() => {
        startCheckoutPolling();
      });
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