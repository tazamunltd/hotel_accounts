/* @odoo-module */
import { _t } from "@web/core/l10n/translation";

(function () {
  let dialogShown = false;
  let pollingStarted = false;
  let pendingValue = null;

  function getRecordIdFromURL() {
    const urlParams = new URLSearchParams(
      window.location.hash.split("?")[0].replace("#", "?")
    );
    return parseInt(urlParams.get("id"), 10);
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
    dialogOverlay.id = "checkout-date-dialog";
    Object.assign(dialogOverlay.style, {
      position: "fixed",
      top: 0, left: 0, width: "100%", height: "100%",
      backgroundColor: "rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 9999,
    });

    const dialogBox = document.createElement("div");
    Object.assign(dialogBox.style, {
      backgroundColor: "#fff",
      borderRadius: "8px",
      width: "400px",
      padding: "20px",
      textAlign: "center",
      boxShadow: "0 4px 8px rgba(0,0,0,0.2)",
    });

    const icon = document.createElement("div");
    icon.textContent = "!";
    Object.assign(icon.style, {
      width: "60px", height: "60px",
      borderRadius: "50%", background: "rgba(255,160,110,0.2)",
      border: "3px solid rgb(255,160,110)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: "36px", fontWeight: "bold", color: "rgb(255,160,110)",
      margin: "0 auto 15px",
    });

    const title = document.createElement("h3");
    title.textContent = "Are you sure?";
    title.style = "margin: 10px 0 20px; font-size:24px; color:#333;";

    const message = document.createElement("p");
    // message.textContent = `Do you want to search rooms for check-out date "${newValue}"?`;
    message.textContent = _t(
          'Do you want to search rooms for check-out date "%s"?',
          newValue
        );
    message.style = "margin:0 0 25px; color:#666; font-size:16px;";

    const btnContainer = document.createElement("div");
    btnContainer.style = "display:flex; justify-content:center; gap:10px;";

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = _t("Cancel");
    Object.assign(cancelBtn.style, {
      padding: "10px 20px",
      backgroundColor: "#D9D9D9",
      border: "none",
      borderRadius: "5px",
      color: "#333",
      fontSize: "14px",
      cursor: "pointer",
    });

    const confirmBtn = document.createElement("button");
    confirmBtn.textContent = _t("Yes, search rooms!");
    Object.assign(confirmBtn.style, {
      padding: "10px 20px",
      backgroundColor: "#F0826C",
      border: "none",
      borderRadius: "5px",
      color: "#fff",
      fontSize: "14px",
      cursor: "pointer",
    });

    btnContainer.append(cancelBtn, confirmBtn);
    dialogBox.append(icon, title, message, btnContainer);
    dialogOverlay.appendChild(dialogBox);
    document.body.appendChild(dialogOverlay);

    const remove = () => {
      if (dialogOverlay.parentNode) {
        dialogOverlay.parentNode.removeChild(dialogOverlay);
      }
      dialogShown = false;
    };

    cancelBtn.addEventListener("click", () => {
      remove();
      pendingValue = null;
      const input = document.querySelector('[name="checkout_date"] input.o_input');
      const nights = document.querySelector('[name="no_of_nights"] input.o_input');
      if (input && input.__checkout_date_old) {
        input.value = input.__checkout_date_old;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (nights && nights._no_of_nights_old != null && nights.value !== nights._no_of_nights_old) {
        nights.value = nights.__no_of_nights_old;
        nights.dispatchEvent(new Event("input", { bubbles: true }));
        nights.dispatchEvent(new Event("change", { bubbles: true }));
      }
      saveForm().then(() => console.log("Reverted and saved after Cancel."));
      onCancel();
    });

    confirmBtn.addEventListener("click", () => {
      remove();
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
        !dialogShown
      ) {
        const recordId = getRecordIdFromURL();
        if (!recordId) {
          console.warn("Missing record ID");
          return;
        }

        fetch("/web/dataset/call_kw", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: {
              model: "room.booking",
              method: "read",
              args: [[recordId], ["state"]],
              kwargs: {},
            },
            id: Date.now(),
          }),
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.error) {
              console.error("RPC error:", data.error);
              return;
            }

            const recs = data.result;
            const state = recs && recs[0] && recs[0].state;
            console.log("Checkout change: record", recordId, "state =", state);

            if (state === "confirmed" || state === "block") {
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
                    .then((r) => r.json())
                    .then(() => {
                      const btn = document.querySelector('button[name="action_search_rooms"]');
                      if (btn) btn.click();

                      if (state === "block") {
                        console.log("🕒 Waiting 3s after save before triggering 15s reload timer...");
                        setTimeout(() => {
                          console.log("✅ Form should be saved. Starting 15s countdown to reload...");
                          setTimeout(() => window.location.reload(), 15000);
                        }, 3000); // Give time for save to persist server-side
                      }
                    });
                });
              }, () => {
                // Cancel handler
              });
            } else {
              console.log("Skipping popup: state not confirmed/block");
              input.__checkout_date_old = newVal;
            }
          })
          .catch((err) => console.error("Fetch error:", err));
      }
    }, 1000);
  }

  function init() {
    startCheckoutPolling();
    new MutationObserver(startCheckoutPolling).observe(document.documentElement, {
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
