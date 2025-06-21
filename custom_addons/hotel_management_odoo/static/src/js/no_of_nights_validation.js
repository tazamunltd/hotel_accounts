/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";

(function () {
  function attachNoOfNightsHandler() {
    const input = document.querySelector('[name="no_of_nights"] input.o_input');
    if (!input || input.__non_attached) return;

    input.__non_attached = true;
    input.__non_old = parseInt(input.value || "0", 10);
    console.log(
      "🌙 no_of_nights handler attached (old=" + input.__non_old + ")"
    );

    input.addEventListener("change", function (e) {
      const newValue = parseInt(e.target.value || "0", 10);
      if (newValue === input.__non_old) return;

      setTimeout(() => {
        const dialogOverlay = document.createElement("div");
        dialogOverlay.style = `
                    position: fixed;
                    top: 0; left: 0;
                    width: 100%; height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    display: flex; align-items: center; justify-content: center;
                    z-index: 9999;
                `;
        dialogOverlay.id = "no-of-nights-dialog";

        const dialogBox = document.createElement("div");
        dialogBox.style = `
                    background-color: white;
                    border-radius: 8px;
                    width: 400px;
                    max-width: 90%;
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
        title.textContent = _t("Are you sure?");
        title.style = "margin: 10px 0 20px; font-size: 24px; color: #333;";

        const message = document.createElement("p");
        message.textContent = _t(
          "Do you want to search rooms for %(count)s nights?",
          { count: newValue }
        );
        message.style = "margin: 0 0 25px; color: #666; font-size: 16px;";

        const btnContainer = document.createElement("div");
        btnContainer.style =
          "display: flex; justify-content: center; gap: 10px;";

        const cancelBtn = document.createElement("button");
        cancelBtn.textContent = _t("Cancel");
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
        confirmBtn.textContent = _t("Yes, search rooms!");
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

        const removeDialog = () => document.body.removeChild(dialogOverlay);

        cancelBtn.addEventListener("click", () => {
          removeDialog();
          e.target.value = input.__non_old;
          e.target.dispatchEvent(new Event("input", { bubbles: true }));
        });

        confirmBtn.addEventListener("click", () => {
          removeDialog();
          const hash = window.location.hash.substring(1);
          const params = new URLSearchParams(hash);
          const recordId = parseInt(params.get("id"), 10);

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
              console.log("🌙 search_rooms called for", recordId);
              input.__non_old = newValue;
              const searchButton = document.querySelector(
                'button[name="action_search_rooms"]'
              );
              if (searchButton) searchButton.click();
            })
            .catch((err) => {
              console.error("Error calling action_search_rooms:", err);
            });
        });
      }, 50);
    });
  }

  function init() {
    attachNoOfNightsHandler();
    const observer = new MutationObserver(attachNoOfNightsHandler);
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
