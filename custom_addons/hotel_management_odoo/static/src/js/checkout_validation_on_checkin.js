/** @odoo-module **/
(function () {
  console.log("✅ Check-In state date validation loaded.");

  // Custom message box function
  function showMessageBox(title, message, isSuccess = false) {
    const container = document.createElement("div");
    Object.assign(container.style, {
      position: "fixed",
      top: "0",
      left: "0",
      right: "0",
      bottom: "0",
      backgroundColor: "rgba(0,0,0,0.5)",
      zIndex: "9999",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    });

    const modalBox = document.createElement("div");
    Object.assign(modalBox.style, {
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

    const messageElem = document.createElement("p");
    messageElem.textContent = message;
    messageElem.style = "margin-bottom: 20px; color:#666; font-size:16px;";

    const okBtn = document.createElement("button");
    okBtn.textContent = "OK";
    Object.assign(okBtn.style, {
      backgroundColor: isSuccess ? "#4bb543" : "#ff7043",
      color: "white",
      border: "none",
      borderRadius: "4px",
      padding: "10px 25px",
      fontSize: "16px",
      cursor: "pointer",
      fontWeight: "bold",
    });
    okBtn.addEventListener("click", () => {
      document.body.removeChild(container);
    });

    modalBox.append(icon, titleElem, messageElem, okBtn);
    container.appendChild(modalBox);
    document.body.appendChild(container);
  }

  let pollingStarted = false;
  let previousValue = null;

  function getRecordIdFromURL() {
    const urlParams = new URLSearchParams(
      window.location.hash.split("?")[0].replace("#", "?")
    );
    return parseInt(urlParams.get("id"), 10);
  }

  function parseDDMMYYYY(dateStr) {
    const parts = dateStr.split("/");
    if (parts.length !== 3 && parts.length !== 2) return null;
    const [day, month, rest] = parts;
    const [year, time] = rest.split(" ");
    return new Date(`${year}-${month}-${day} ${time || "00:00"}`);
  }

  function startCheckinPolling() {
    if (pollingStarted) return;
    pollingStarted = true;

    // Wait for the checkout date input field to exist
    const intervalId = setInterval(() => {
      const input = document.querySelector(
        '[name="checkout_date"] input.o_input'
      );
      if (input) {
        clearInterval(intervalId); // Stop waiting once the input field is found
        console.log("✅ Found checkout_date input field.");
        handleCheckoutDateChange(input); // Start handling date changes
      }
    }, 1000); // Check every 1 second
  }

  function handleCheckoutDateChange(input) {
    setInterval(() => {
      const newVal = input.value;
      if (!previousValue) {
        previousValue = newVal;
        return;
      }

      const newDate = parseDDMMYYYY(newVal);
      const prevDate = parseDDMMYYYY(previousValue);

      if (
        newVal &&
        newVal !== previousValue &&
        newDate instanceof Date &&
        prevDate instanceof Date &&
        !isNaN(newDate.getTime()) &&
        !isNaN(prevDate.getTime()) &&
        newDate > prevDate
      ) {
        const recordId = getRecordIdFromURL();
        if (!recordId) return;

        // Step 1: Read current state
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
            const state = data?.result?.[0]?.state;
            console.log("Current state:", state);

            if (state === "check_in") {
              console.log(
                "🔁 Checking room conflicts for new checkout date:",
                newVal
              );

              // Step 2: Call backend method
              fetch("/web/dataset/call_kw", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  jsonrpc: "2.0",
                  method: "call",
                  params: {
                    model: "room.booking",
                    method: "check_extended_room_conflicts",
                    args: [recordId, newVal],
                    kwargs: {},
                  },
                  id: Date.now(),
                }),
              })
                .then((res) => res.json())
                .then((result) => {
                  const conflict = result?.result?.has_conflict;
                  const rooms = result?.result?.conflicted_rooms || [];

                  console.log("Conflict result:", conflict);
                  console.log("Conflicted rooms:", rooms);

                  if (conflict) {
                    // Show custom message box
                    showMessageBox(
                      "Room Not Available",
                      `Room is not available!\nAlready booked: ${rooms.join(
                        ", "
                      )}\nReverting to previous checkout date.`,
                      false
                    );
                    input.value = previousValue;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));

                    // Trigger blur to make sure change is committed without reloading
                    setTimeout(() => {
                      input.blur();
                    }, 100); // give browser time to update field
                  } else {
                    // Show custom message box
                    showMessageBox(
                      "Success",
                      "Room is available. Checkout extended.",
                      true
                    );

                    previousValue = newVal;
                  }
                })
                .catch((err) => {
                  console.error("Room conflict check failed:", err);
                });
            } else {
              console.log("Skipping conflict check: state is not 'check_in'");
              // Keep previousValue unchanged to re-check later if state changes to 'check_in'
            }
          })
          .catch((err) => {
            console.error("Error checking booking state:", err);
          });
      }
    }, 1000); // Check every 1 second
  }

  function init() {
    startCheckinPolling();
    new MutationObserver(startCheckinPolling).observe(
      document.documentElement,
      {
        childList: true,
        subtree: true,
      }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
