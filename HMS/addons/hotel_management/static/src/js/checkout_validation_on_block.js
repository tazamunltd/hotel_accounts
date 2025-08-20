/** @odoo-module **/
(function () {
  console.log("🚀 Block-state reservation validator initialized.");
  let pollingStarted = false;
  let prevCheckin = null;
  let prevCheckout = null;

  // import the same showMessageBox from check-in validation
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

  function getRecordIdFromURL() {
    const urlParams = new URLSearchParams(
      window.location.hash.split("?")[0].replace("#", "?")
    );
    return parseInt(urlParams.get("id"), 10);
  }

  function parseDDMMYYYY(dateStr) {
    const parts = dateStr.split("/");
    if (parts.length < 2) return null;
    const [day, month, rest] = parts;
    const [year, time] = rest.split(" ");
    return new Date(`${year}-${month}-${day} ${time || "00:00"}`);
  }

  function startBlockPolling() {
    if (pollingStarted) return;
    pollingStarted = true;

    setInterval(() => {
      const checkinInput = document.querySelector(
        '[name="checkin_date"] input.o_input'
      );
      const checkoutInput = document.querySelector(
        '[name="checkout_date"] input.o_input'
      );
      if (!checkinInput || !checkoutInput) return;

      const newCheckin = checkinInput.value;
      const newCheckout = checkoutInput.value;
      if (prevCheckin === null) prevCheckin = newCheckin;
      if (prevCheckout === null) prevCheckout = newCheckout;

      const dtIn = parseDDMMYYYY(newCheckin),
        dtOut = parseDDMMYYYY(newCheckout);
      const pvIn = parseDDMMYYYY(prevCheckin),
        pvOut = parseDDMMYYYY(prevCheckout);

      if (
        (newCheckin !== prevCheckin && dtIn > pvIn) ||
        (newCheckout !== prevCheckout && dtOut > pvOut)
      ) {
        const recordId = getRecordIdFromURL();
        if (!recordId) return;

        // read state
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
          .then((data) => {
            if (data?.result?.[0]?.state === "block") {
              // call backend
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
                    method: "check_extended_reservation_conflicts",
                    args: [recordId, newCheckin, newCheckout],
                    kwargs: {},
                  },
                }),
              })
                .then((r) => r.json())
                .then((res) => {
                  const conflict = res.result.has_conflict;
                  const rooms = res.result.conflicted_rooms || [];
                  if (conflict) {
                    showMessageBox(
                      "Room Not Available",
                      `Room(s) unavailable: ${rooms.join(
                        ", "
                      )}\nReverting to previous checkout date.`,
                      false
                    );
                    // revert only checkout date
                    checkoutInput.value = prevCheckout;
                    checkoutInput.dispatchEvent(
                      new Event("change", { bubbles: true })
                    );
                  } else {
                    showMessageBox(
                      "Success",
                      "Reservation window is free.",
                      true
                    );
                    prevCheckin = newCheckin;
                    prevCheckout = newCheckout;
                  }
                })
                .catch((err) => console.error("conflict check failed:", err));
            }
          })
          .catch((err) => console.error("state read failed:", err));
      }
    }, 1000);
  }

  function init() {
    startBlockPolling();
    new MutationObserver(startBlockPolling).observe(document.documentElement, {
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
