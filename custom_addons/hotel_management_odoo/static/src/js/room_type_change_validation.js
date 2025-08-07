/* @odoo-module */
import { _t } from "@web/core/l10n/translation";

(function () {
  /**
   * Extracts the current record’s ID from the URL hash.
   */
  function getRecordIdFromURL() {
    const urlParams = new URLSearchParams(
      window.location.hash.split("?")[0].replace("#", "?")
    );
    const id = parseInt(urlParams.get("id"), 10);
    console.log("🆔 Record ID from URL:", id);
    return id;
  }

  /**
   * Manually saves the form by invoking the Owl component’s saveRecord() method.
   */
  function saveForm() {
    const formController = document.querySelector(".o_form_view");
    if (formController && formController._owl_) {
      const comp = formController._owl_;
      if (comp && typeof comp.saveRecord === "function") {
        console.log("💾 Saving form...");
        return comp.saveRecord();
      }
    }
    console.warn("⚠ Cannot find form controller to save.");
    return Promise.resolve();
  }

  /**
   * Builds and displays a custom modal (styled like your first JS example).
   * - newValue: the newly entered room type string
   * - onConfirm: callback invoked if the user clicks “Yes, search rooms!”
   * - onCancel: callback invoked if the user clicks “Cancel”
   */
  function showCustomModal(newValue, onConfirm, onCancel) {
    // Create the dark semi-transparent overlay
    const dialogOverlay = document.createElement("div");
    dialogOverlay.style.position = "fixed";
    dialogOverlay.style.top = "0";
    dialogOverlay.style.left = "0";
    dialogOverlay.style.width = "100%";
    dialogOverlay.style.height = "100%";
    dialogOverlay.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
    dialogOverlay.style.display = "flex";
    dialogOverlay.style.alignItems = "center";
    dialogOverlay.style.justifyContent = "center";
    dialogOverlay.style.zIndex = "9999";
    dialogOverlay.setAttribute("id", "room-type-dialog-overlay");

    // Create the white dialog box container
    const dialogBox = document.createElement("div");
    dialogBox.style.backgroundColor = "white";
    dialogBox.style.borderRadius = "8px";
    dialogBox.style.width = "400px";
    dialogBox.style.maxWidth = "90%";
    dialogBox.style.padding = "20px";
    dialogBox.style.textAlign = "center";
    dialogBox.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.2)";
    dialogBox.setAttribute("id", "room-type-dialog-box");

    // Exclamation‐in‐circle icon container
    const iconContainer = document.createElement("div");
    iconContainer.style.width = "60px";
    iconContainer.style.height = "60px";
    iconContainer.style.borderRadius = "50%";
    iconContainer.style.backgroundColor = "rgba(255, 160, 110, 0.2)";
    iconContainer.style.border = "3px solid rgb(255, 160, 110)";
    iconContainer.style.margin = "0 auto 15px";
    iconContainer.style.display = "flex";
    iconContainer.style.alignItems = "center";
    iconContainer.style.justifyContent = "center";
    iconContainer.style.fontSize = "36px";
    iconContainer.style.fontWeight = "bold";
    iconContainer.style.color = "rgb(255, 160, 110)";
    iconContainer.textContent = "!";

    // Title (“Are you sure?”)
    const title = document.createElement("h3");
    title.style.margin = "10px 0 20px";
    title.style.fontSize = "24px";
    title.style.color = "#333";
    title.textContent = _t("Are you sure?");

    // Message (“Do you want to search rooms for room type X?”)
    const message = document.createElement("p");
    message.style.margin = "0 0 25px";
    message.style.color = "#666";
    message.style.fontSize = "16px";
    // message.textContent = _t(`Do you want to search rooms for room type "${newValue}"?`);
    message.textContent = _t(`Do you want to search rooms for room type "%s"?`, newValue);

    // Buttons container (Cancel / Yes, search rooms!)
    const btnContainer = document.createElement("div");
    btnContainer.style.display = "flex";
    btnContainer.style.justifyContent = "center";
    btnContainer.style.gap = "10px";

    // Cancel button
    const cancelBtn = document.createElement("button");
    cancelBtn.style.padding = "10px 20px";
    cancelBtn.style.backgroundColor = "#D9D9D9";
    cancelBtn.style.border = "none";
    cancelBtn.style.borderRadius = "5px";
    cancelBtn.style.color = "#333";
    cancelBtn.style.fontSize = "14px";
    cancelBtn.style.cursor = "pointer";
    cancelBtn.textContent = _t("Cancel");

    // Confirm button
    const confirmBtn = document.createElement("button");
    confirmBtn.style.padding = "10px 20px";
    confirmBtn.style.backgroundColor = "#F0826C";
    confirmBtn.style.border = "none";
    confirmBtn.style.borderRadius = "5px";
    confirmBtn.style.color = "white";
    confirmBtn.style.fontSize = "14px";
    confirmBtn.style.cursor = "pointer";
    confirmBtn.textContent = _t("Yes, search rooms!");

    // Assemble dialog
    btnContainer.appendChild(cancelBtn);
    btnContainer.appendChild(confirmBtn);
    dialogBox.appendChild(iconContainer);
    dialogBox.appendChild(title);
    dialogBox.appendChild(message);
    dialogBox.appendChild(btnContainer);
    dialogOverlay.appendChild(dialogBox);
    document.body.appendChild(dialogOverlay);

    // Function to remove the entire modal
    const removeDialog = () => {
      const existing = document.getElementById("room-type-dialog-overlay");
      if (existing) {
        document.body.removeChild(existing);
      }
    };

    // If user clicks “Cancel”
    cancelBtn.addEventListener("click", function () {
      removeDialog();
      onCancel();
    });

    // If user clicks “Yes, search rooms!”
    confirmBtn.addEventListener("click", function () {
      removeDialog();
      onConfirm();
    });
  }

  /**
   * Attaches a blur handler to the hotel_room_type many2one input.
   * If the user changes the value, our custom modal appears.
   * On confirm: we save the form, call action_search_rooms, update old value.
   * On cancel: we trigger Odoo’s default Discard (click the Discard button).
   */
  function attachRoomTypeHandler() {
    // Locate the visible autocomplete <input> for hotel_room_type//
    const input = document.querySelector('#hotel_room_type_0.o_input');
    if (!input || input.__rcp_attached) {
      return;
    }
    input.__rcp_attached = true;

    // Store the “old” label (so we can still detect changes)
    input.__rcp_old = input.value || "";
    console.log(
      "🏨 hotel_room_type handler attached (oldLabel=" + input.__rcp_old + ")"
    );

    input.addEventListener("blur", function (e) {
      // Delay slightly so Odoo’s JS has a chance to update the hidden ID behind the scenes
      setTimeout(() => {
        const nv = e.target.value || "";
        // If nothing changed, do nothing
        if (nv === input.__rcp_old) {
          return;
        }

        // Instead of window.confirm, show our custom modal
        showCustomModal(
          nv,
          /* onConfirm */ function () {
            const recordId = getRecordIdFromURL();
            if (!recordId) {
              console.error("❌ Cannot determine record ID from URL.");
              return;
            }

            // 1) Save the form with the new room type
            saveForm().then(() => {
              // 2) After save succeeds, call action_search_rooms
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
                .then((response) => response.json())
                .then(() => {
                  console.log("🏨 search_rooms called for", recordId);

                  // 3) Update the old value since the change is confirmed
                  input.__rcp_old = nv;

                  // 4) If there’s a “Search” button for rooms, click it
                  const searchButton = document.querySelector(
                    'button[name="action_search_rooms"]'
                  );
                  if (searchButton) {
                    console.log("🏨 clicking Search button");
                    searchButton.click();
                  } else {
                    console.warn("🏨 Search button not found");
                  }
                })
                .catch((error) => {
                  console.error("Error calling action_search_rooms:", error);
                });
            });
          },
          /* onCancel */ function () {
            // **New behavior**: trigger Odoo’s Discard changes
            console.log("↩ User cancelled change → clicking Odoo’s Discard");
            // const discardButton = document.querySelector('button[name="discard"]');
            const discardButton = document.querySelector(
              "button.o_form_button_cancel"
            );
            if (discardButton) {
              discardButton.click();
            } else {
              console.warn(
                "⚠ Cannot find Odoo’s Discard button. Please make sure your form view has a button[name='discard']."
              );
            }
          }
        );
      }, 1);
    });
  }

  /**
   * Initialize: attach once on DOM ready, then observe future DOM mutations
   * so that if Odoo re-renders the field (e.g. switching records), we re-attach.
   */
  function init() {
    attachRoomTypeHandler();
    const observer = new MutationObserver(attachRoomTypeHandler);
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
