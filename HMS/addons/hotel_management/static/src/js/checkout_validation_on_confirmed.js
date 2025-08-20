/** @odoo-module **/
(function () {
  console.log("✅ Confirmed state date validation loaded.");

  let pollingStarted = false;
  let previousCheckin = null;
  let previousCheckout = null;
  let previousState = null; // track the last-known state

  // Reusable modal message box
  function showMessageBox(title, message, isSuccess = false) {
    const container = document.createElement("div");
    Object.assign(container.style, {
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(0,0,0,0.5)",
      zIndex: 9999,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    });

    const modal = document.createElement("div");
    Object.assign(modal.style, {
      background: "#fff",
      borderRadius: "8px",
      padding: "30px",
      textAlign: "center",
      width: "400px",
      maxWidth: "90%",
      boxShadow: "0 4px 8px rgba(0,0,0,0.2)",
    });

    const icon = document.createElement("div");
    icon.textContent = isSuccess ? "✓" : "!";
    Object.assign(icon.style, {
      width: "60px",
      height: "60px",
      borderRadius: "50%",
      background: isSuccess ? "rgba(75,181,67,0.2)" : "rgba(255,160,110,0.2)",
      border: isSuccess
        ? "3px solid rgb(75,181,67)"
        : "3px solid rgb(255,160,110)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: "36px",
      fontWeight: "bold",
      color: isSuccess ? "rgb(75,181,67)" : "rgb(255,160,110)",
      margin: "0 auto 15px",
    });

    const titleElem = document.createElement("h3");
    titleElem.textContent = title;
    titleElem.style = "margin: 10px 0 20px; font-size:24px; color:#333;";

    const msgElem = document.createElement("p");
    msgElem.textContent = message;
    msgElem.style = "margin-bottom:20px; font-size:16px; color:#666;";

    const okBtn = document.createElement("button");
    okBtn.textContent = "OK";
    Object.assign(okBtn.style, {
      backgroundColor: isSuccess ? "#4bb543" : "#ff7043",
      color: "#fff",
      border: "none",
      borderRadius: "4px",
      padding: "10px 25px",
      fontSize: "16px",
      cursor: "pointer",
      fontWeight: "bold",
    });
    okBtn.addEventListener("click", () => document.body.removeChild(container));

    modal.append(icon, titleElem, msgElem, okBtn);
    container.appendChild(modal);
    document.body.appendChild(container);
  }

  // Utility to extract record ID from URL
  function getRecordIdFromURL() {
    const params = new URLSearchParams(
      window.location.hash.split("?")[0].replace("#", "?")
    );
    return parseInt(params.get("id"), 10);
  }

  // Parse DD/MM/YYYY HH:MM or DD/MM/YYYY HH:MM:SS
  function parseDDMMYYYY(dateStr) {
    if (!dateStr) return null;
    const parts = dateStr.split("/");
    if (parts.length < 3) return null;
    const [day, month, rest] = parts;
    const [year, time] = rest.split(" ");
    return new Date(`${year}-${month}-${day} ${time || "00:00"}`);
  }

  function startPolling() {
    if (pollingStarted) return;
    pollingStarted = true;

    setInterval(() => {
      const checkinInput = document.querySelector(
        '[name="checkin_date"] input.o_input'
      );
      const checkoutInput = document.querySelector(
        '[name="checkout_date"] input.o_input'
      );
      const recordId = getRecordIdFromURL();
      if (!recordId) return;

      // Seed state on first load
      if (previousState === null) {
        fetch("/web/dataset/call_kw", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            id: Date.now(),
            params: {
              model: "room.booking",
              method: "read",
              args: [[recordId], ["state"]],
              kwargs: {},
            },
          }),
        })
          .then((r) => r.json())
          .then((d) => {
            previousState = d.result[0].state;
          });
      }

      // Detect check-in change
      if (checkinInput && checkinInput.value) {
        const newVal = checkinInput.value;
        if (previousCheckin === null) previousCheckin = newVal;
        else if (newVal !== previousCheckin) {
          validateDateChange(
            recordId,
            checkinInput,
            newVal,
            previousCheckin,
            true
          );
        }
      }

      // Detect check-out change
      if (checkoutInput && checkoutInput.value) {
        const newVal = checkoutInput.value;
        if (previousCheckout === null) previousCheckout = newVal;
        else if (newVal !== previousCheckout) {
          validateDateChange(
            recordId,
            checkoutInput,
            newVal,
            previousCheckout,
            false
          );
        }
      }
    }, 1000);
  }

  function validateDateChange(recordId, input, newVal, oldVal, isCheckin) {
    // Step 1: fetch current state
    fetch("/web/dataset/call_kw", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "call",
        id: Date.now(),
        params: {
          model: "room.booking",
          method: "read",
          args: [[recordId], ["state"]],
          kwargs: {},
        },
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        const state = data.result[0].state;

        // Only validate when already in confirmed
        if (state !== "confirmed" || previousState !== "confirmed") {
          previousState = state;
          if (isCheckin) previousCheckin = newVal;
          else previousCheckout = newVal;
          return;
        }

        previousState = state;
        // Parse changed values
        const parsedNew = parseDDMMYYYY(newVal);
        const parsedOld = parseDDMMYYYY(oldVal);
        if (!parsedNew || !parsedOld) return;

        // Gather both dates for range
        const checkinVal = isCheckin
          ? newVal
          : document.querySelector('[name="checkin_date"] input.o_input').value;
        const checkoutVal = isCheckin
          ? document.querySelector('[name="checkout_date"] input.o_input').value
          : newVal;

        // Step 2: call availability check
        fetch("/web/dataset/call_kw", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            id: Date.now(),
            params: {
              model: "room.booking",
              method: "check_confirmed_availability_for_date_change",
              args: [recordId, checkinVal, checkoutVal],
              kwargs: {},
            },
          }),
        })
          .then((res) => res.json())
          .then((result) => {
            const hasConflict = result.result.has_conflict;
            const rooms = result.result.conflicted_rooms || [];

            if (hasConflict) {
              showMessageBox(
                "Room Not Available",
                `Conflict: ${rooms.join(", ")}
Reverting change.`,
                false
              );
              input.value = oldVal;
              input.dispatchEvent(new Event("input", { bubbles: true }));
              input.dispatchEvent(new Event("change", { bubbles: true }));
              setTimeout(() => input.blur(), 100);
            } else {
              showMessageBox(
                "Success",
                `${
                  isCheckin ? "Check-in" : "Check-out"
                } date updated successfully.`,
                true
              );
              if (isCheckin) previousCheckin = newVal;
              else previousCheckout = newVal;
            }
          });
      });
  }

  function init() {
    console.log("✅ Confirmed state date script initialized.");
    startPolling();
    new MutationObserver(startPolling).observe(document.documentElement, {
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
