// /** @odoo-module */
// import { _t } from "@web/core/l10n/translation";

// (function () {
//   let dialogShown = false;
//   let pollingStarted = false;
//   let pendingValue = null;

//   function getRecordIdFromURL() {
//     const urlParams = new URLSearchParams(
//       window.location.hash.split("?")[0].replace("#", "?")
//     );
//     return parseInt(urlParams.get("id"), 10);
//   }

//   function saveForm() {
//     const formController = document.querySelector(".o_form_view");
//     if (formController && formController.owl) {
//       const comp = formController.owl;
//       if (comp && typeof comp.saveRecord === "function") {
//         return comp.saveRecord();
//       }
//     }
//     return Promise.resolve();
//   }

//   function showCustomModal(newValue, state, onConfirm, onCancel = () => {}) {
//     if (dialogShown) return;
//     dialogShown = true;
//     pendingValue = newValue;

//     const dialogOverlay = document.createElement("div");
//     Object.assign(dialogOverlay.style, {
//       position: "fixed",
//       top: 0,
//       left: 0,
//       width: "100%",
//       height: "100%",
//       backgroundColor: "rgba(0,0,0,0.5)",
//       display: "flex",
//       alignItems: "center",
//       justifyContent: "center",
//       zIndex: 9999,
//     });

//     const dialogBox = document.createElement("div");
//     Object.assign(dialogBox.style, {
//       backgroundColor: "#fff",
//       borderRadius: "8px",
//       width: "400px",
//       padding: "20px",
//       textAlign: "center",
//       boxShadow: "0 4px 8px rgba(0,0,0,0.2)",
//     });

//     const icon = document.createElement("div");
//     icon.textContent = "!";
//     Object.assign(icon.style, {
//       width: "60px",
//       height: "60px",
//       borderRadius: "50%",
//       background: "rgba(255,160,110,0.2)",
//       border: "3px solid rgb(255,160,110)",
//       display: "flex",
//       alignItems: "center",
//       justifyContent: "center",
//       fontSize: "36px",
//       fontWeight: "bold",
//       color: "rgb(255,160,110)",
//       margin: "0 auto 15px",
//     });

//     const title = document.createElement("h3");
//     title.textContent = _t("Are you sure?");
//     title.style = "margin: 10px 0 20px; font-size:24px; color:#333;";

//     const message = document.createElement("p");
//     message.textContent = _t(
//       'Do you want to search rooms for check-in date "%s"?',
//       newValue
//     );
//     message.style = "margin:0 0 25px; color:#666; font-size:16px;";

//     const btnContainer = document.createElement("div");
//     btnContainer.style = "display:flex; justify-content:center; gap:10px;";

//     const cancelBtn = document.createElement("button");
//     cancelBtn.textContent = _t("Cancel");
//     Object.assign(cancelBtn.style, {
//       padding: "10px 20px",
//       backgroundColor: "#D9D9D9",
//       border: "none",
//       borderRadius: "5px",
//       color: "#333",
//       fontSize: "14px",
//       cursor: "pointer",
//     });

//     const confirmBtn = document.createElement("button");
//     confirmBtn.textContent = _t("Yes, search rooms!");
//     Object.assign(confirmBtn.style, {
//       padding: "10px 20px",
//       backgroundColor: "#F0826C",
//       border: "none",
//       borderRadius: "5px",
//       color: "#fff",
//       fontSize: "14px",
//       cursor: "pointer",
//     });

//     btnContainer.append(cancelBtn, confirmBtn);
//     dialogBox.append(icon, title, message, btnContainer);
//     dialogOverlay.appendChild(dialogBox);
//     document.body.appendChild(dialogOverlay);

//     const remove = () => {
//       if (dialogOverlay.parentNode) {
//         dialogOverlay.parentNode.removeChild(dialogOverlay);
//       }
//       dialogShown = false;
//     };

//     cancelBtn.addEventListener("click", () => {
//       remove();
//       pendingValue = null;
//       const input = document.querySelector(
//         '[name="checkin_date"] input.o_input'
//       );
//       if (input && input.__checkin_date_old) {
//         input.value = input.__checkin_date_old;
//         input.dispatchEvent(new Event("input", { bubbles: true }));
//         input.dispatchEvent(new Event("change", { bubbles: true }));
//         saveForm().then(() => {
//           console.log("✅ check-in date reverted and saved after Cancel.");
//         });
//       }
//       onCancel();
//     });

//     confirmBtn.addEventListener("click", () => {
//       confirmBtn.disabled = true;
//       confirmBtn.style.opacity = "0.5";
//       confirmBtn.style.cursor = "not-allowed";
//       const input = document.querySelector(
//         '[name="checkin_date"] input.o_input'
//       );
//       if (input) {
//         input.__checkin_date_old = pendingValue;
//       }
//       remove();
//       setTimeout(() => onConfirm(state), 50);
//     });
//   }

//   function showErrorModal(message) {
//     if (dialogShown) return;
//     dialogShown = true;

//     const overlay = document.createElement("div");
//     Object.assign(overlay.style, {
//       position: "fixed",
//       top: 0,
//       left: 0,
//       width: "100%",
//       height: "100%",
//       backgroundColor: "rgba(0,0,0,0.5)",
//       display: "flex",
//       alignItems: "center",
//       justifyContent: "center",
//       zIndex: 9999,
//     });

//     const box = document.createElement("div");
//     Object.assign(box.style, {
//       backgroundColor: "#fff",
//       borderRadius: "8px",
//       width: "360px",
//       padding: "20px",
//       textAlign: "center",
//       boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
//     });

//     const icon = document.createElement("div");
//     icon.innerHTML = "&#9888;"; // ⚠
//     Object.assign(icon.style, {
//       fontSize: "48px",
//       color: "#D04437",
//       marginBottom: "10px",
//     });

//     const text = document.createElement("p");
//     text.textContent = message;
//     Object.assign(text.style, {
//       fontSize: "16px",
//       color: "#333",
//       marginBottom: "20px",
//     });

//     const btn = document.createElement("button");
//     btn.textContent = _t("OK");
//     Object.assign(btn.style, {
//       padding: "10px 20px",
//       border: "none",
//       borderRadius: "4px",
//       backgroundColor: "#D04437",
//       color: "#fff",
//       cursor: "pointer",
//       fontSize: "14px",
//     });
//     btn.addEventListener("click", () => {
//       document.body.removeChild(overlay);
//       dialogShown = false;
//     });

//     box.append(icon, text, btn);
//     overlay.appendChild(box);
//     document.body.appendChild(overlay);
//   }

//   function normalizeDateInput(dateStr) {
//     if (!dateStr) return null;
//     // 1) Try Odoo-style "DD/MM/YYYY HH:mm:ss"
//     const dm = dateStr
//       .trim()
//       .match(
//         /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$/
//       );
//     if (dm) {
//       const [, dd, mm, yyyy, hh, min, ss] = dm;
//       return new Date(
//         parseInt(yyyy, 10),
//         parseInt(mm, 10) - 1,
//         parseInt(dd, 10),
//         hh ? parseInt(hh, 10) : 0,
//         min ? parseInt(min, 10) : 0,
//         ss ? parseInt(ss, 10) : 0
//       );
//     }

//     // 2) Fallback: Arabic→Latin digits
//     const arabicDigitsMap = {
//       "٠": "0",
//       "١": "1",
//       "٢": "2",
//       "٣": "3",
//       "٤": "4",
//       "٥": "5",
//       "٦": "6",
//       "٧": "7",
//       "٨": "8",
//       "٩": "9",
//     };
//     dateStr = dateStr.replace(/[٠-٩]/g, (d) => arabicDigitsMap[d] || d);

//     // 3) Arabic month names → English
//     const arabicMonths = {
//       يناير: "January",
//       فبراير: "February",
//       مارس: "March",
//       أبريل: "April",
//       مايو: "May",
//       يونيو: "June",
//       يوليو: "July",
//       أغسطس: "August",
//       سبتمبر: "September",
//       أكتوبر: "October",
//       نوفمبر: "November",
//       ديسمبر: "December",
//     };
//     for (const [ara, eng] of Object.entries(arabicMonths)) {
//       if (dateStr.includes(ara)) {
//         dateStr = dateStr.replace(ara, eng);
//         break;
//       }
//     }

//     dateStr = dateStr.replace(/[،,]/g, "");
//     const parsed = new Date(dateStr.trim());
//     return isNaN(parsed) ? null : parsed;
//   }

//   function startCheckinPolling() {
//     if (pollingStarted) return;
//     pollingStarted = true;

//     setInterval(() => {
//       const input = document.querySelector(
//         '[name="checkin_date"] input.o_input'
//       );
//       if (!input) return;

//       const newVal = input.value;
//       if (!input.__checkin_date_old) {
//         input.__checkin_date_old = newVal;
//         return;
//       }

//       if (
//         newVal &&
//         newVal !== input.__checkin_date_old &&
//         newVal !== pendingValue &&
//         !dialogShown
//       ) {
//         const recordId = getRecordIdFromURL();
//         if (!recordId) {
//           console.warn("Could not determine record ID");
//           return;
//         }

//         // Read current state & company
//         fetch("/web/dataset/call_kw", {
//           method: "POST",
//           credentials: "same-origin",
//           headers: { "Content-Type": "application/json" },
//           body: JSON.stringify({
//             jsonrpc: "2.0",
//             method: "call",
//             params: {
//               model: "room.booking",
//               method: "read",
//               args: [[recordId], ["state", "company_id"]],
//               kwargs: {},
//             },
//             id: Date.now(),
//           }),
//         })
//           .then((res) => res.json())
//           .then((data) => {
//             if (data.error) {
//               console.error("RPC error:", data.error);
//               return;
//             }
//             const { state, company_id } = data.result[0];
//             const companyId = company_id && company_id[0];

//             if (companyId) {
//               // Fetch system_date
//               fetch("/web/dataset/call_kw", {
//                 method: "POST",
//                 credentials: "same-origin",
//                 headers: { "Content-Type": "application/json" },
//                 body: JSON.stringify({
//                   jsonrpc: "2.0",
//                   method: "call",
//                   params: {
//                     model: "res.company",
//                     method: "read",
//                     args: [[companyId], ["system_date"]],
//                     kwargs: {},
//                   },
//                   id: Date.now(),
//                 }),
//               })
//                 .then((res) => res.json())
//                 .then((compData) => {
//                   if (compData.error) {
//                     console.error(compData.error);
//                     return;
//                   }
//                   const sysDateStr = compData.result[0].system_date;
//                   const sysDate = sysDateStr ? new Date(sysDateStr) : null;
//                   const newDateObj = normalizeDateInput(newVal);

//                   // <-- FIXED: only if new < system do we error -->
//                   if (sysDate && newDateObj < sysDate) {
//                     showErrorModal(
//                       _t("Check-in date should not be less than system date")
//                     );
//                     input.value = input.__checkin_date_old;
//                     input.dispatchEvent(new Event("input", { bubbles: true }));
//                     input.dispatchEvent(new Event("change", { bubbles: true }));
//                     saveForm();
//                     return;
//                   }

//                   // existing confirm/search logic
//                   if (state === "confirmed" || state === "block") {
//                     showCustomModal(newVal, state, (currentState) => {
//                       pendingValue = null;
//                       input.__checkin_date_old = newVal;
//                       saveForm().then(() => {
//                         fetch("/web/dataset/call_button", {
//                           method: "POST",
//                           credentials: "same-origin",
//                           headers: { "Content-Type": "application/json" },
//                           body: JSON.stringify({
//                             params: {
//                               model: "room.booking",
//                               method: "action_search_rooms",
//                               args: [[recordId]],
//                               kwargs: {},
//                             },
//                           }),
//                         })
//                           .then((r) => r.json())
//                           .then(() => {
//                             const btn = document.querySelector(
//                               'button[name="action_search_rooms"]'
//                             );
//                             if (btn) btn.click();
//                             if (currentState === "block") {
//                               setTimeout(() => window.location.reload(), 15000);
//                             }
//                           });
//                       });
//                     });
//                   } else {
//                     input.__checkin_date_old = newVal;
//                   }
//                 });
//             }
//           })
//           .catch((err) => console.error("Fetch error:", err));
//       }
//     }, 1000);
//   }

//   function init() {
//     startCheckinPolling();
//     new MutationObserver(startCheckinPolling).observe(
//       document.documentElement,
//       {
//         childList: true,
//         subtree: true,
//       }
//     );
//   }

//   if (document.readyState === "loading") {
//     document.addEventListener("DOMContentLoaded", init);
//   } else {
//     init();
//   }
// })();

/** @odoo-module */
// import { _t } from "@web/core/l10n/translation";

// (function () {
//   // let dialogShown = false;
//   // let pollingStarted = false;
//   // let pendingValue = null;

//   function normalizeDateInput(dateStr) {
//     if (!dateStr) return null;
//     // 1) Try Odoo-style "DD/MM/YYYY HH:mm:ss"
//     const dm = dateStr
//       .trim()
//       .match(
//         /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$/
//       );
//     if (dm) {
//       const [, dd, mm, yyyy, hh, min, ss] = dm;
//       return new Date(
//         parseInt(yyyy, 10),
//         parseInt(mm, 10) - 1,
//         parseInt(dd, 10),
//         hh ? parseInt(hh, 10) : 0,
//         min ? parseInt(min, 10) : 0,
//         ss ? parseInt(ss, 10) : 0
//       );
//     }

//     // 2) Fallback: Arabic→Latin digits
//     const arabicDigitsMap = {
//       "٠": "0",
//       "١": "1",
//       "٢": "2",
//       "٣": "3",
//       "٤": "4",
//       "٥": "5",
//       "٦": "6",
//       "٧": "7",
//       "٨": "8",
//       "٩": "9",
//     };
//     dateStr = dateStr.replace(/[٠-٩]/g, (d) => arabicDigitsMap[d] || d);

//     // 3) Arabic month names → English
//     const arabicMonths = {
//       يناير: "January",
//       فبراير: "February",
//       مارس: "March",
//       أبريل: "April",
//       مايو: "May",
//       يونيو: "June",
//       يوليو: "July",
//       أغسطس: "August",
//       سبتمبر: "September",
//       أكتوبر: "October",
//       نوفمبر: "November",
//       ديسمبر: "December",
//     };
//     for (const [ara, eng] of Object.entries(arabicMonths)) {
//       if (dateStr.includes(ara)) {
//         dateStr = dateStr.replace(ara, eng);
//         break;
//       }
//     }

//     dateStr = dateStr.replace(/[،,]/g, "");
//     const parsed = new Date(dateStr.trim());
//     return isNaN(parsed) ? null : parsed;
//   }

//   function showErrorModal(message) {
//     // if (dialogShown) return;
//     // dialogShown = true;

//     const overlay = document.createElement("div");
//     Object.assign(overlay.style, {
//       position: "fixed",
//       top: 0,
//       left: 0,
//       width: "100%",
//       height: "100%",
//       backgroundColor: "rgba(0,0,0,0.5)",
//       display: "flex",
//       alignItems: "center",
//       justifyContent: "center",
//       zIndex: 9999,
//     });

//     const box = document.createElement("div");
//     Object.assign(box.style, {
//       backgroundColor: "#fff",
//       borderRadius: "8px",
//       width: "360px",
//       padding: "20px",
//       textAlign: "center",
//       boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
//     });

//     const icon = document.createElement("div");
//     icon.innerHTML = "&#9888;"; // ⚠
//     Object.assign(icon.style, {
//       fontSize: "48px",
//       color: "#D04437",
//       marginBottom: "10px",
//     });

//     const text = document.createElement("p");
//     text.textContent = message;
//     Object.assign(text.style, {
//       fontSize: "16px",
//       color: "#333",
//       marginBottom: "20px",
//     });

//     const btn = document.createElement("button");
//     btn.textContent = _t("OK");
//     Object.assign(btn.style, {
//       padding: "10px 20px",
//       border: "none",
//       borderRadius: "4px",
//       backgroundColor: "#D04437",
//       color: "#fff",
//       cursor: "pointer",
//       fontSize: "14px",
//     });
//     btn.addEventListener("click", () => {
//       document.body.removeChild(overlay);
//       // dialogShown = false;
//     });

//     box.append(icon, text, btn);
//     overlay.appendChild(box);
//     document.body.appendChild(overlay);
//   }

//   function startCheckinPolling() {
//     // if (pollingStarted) return;
//     // pollingStarted = true;

//     setInterval(() => {
//       const input = document.querySelector(
//         '[name="checkin_date"] input.o_input'
//       );
//       if (!input) return;

//       const newVal = input.value;
//       if (!input.__checkin_date_old) {
//         input.__checkin_date_old = newVal;
//         return;
//       }

//       if (
//         newVal &&
//         newVal !== input.__checkin_date_old
//         // && newVal !== pendingValue
//         // && !dialogShown
//       ) {
//         // Only validation logic, rest is commented
//         // You may need to get recordId, state, company_id if used elsewhere

//         // Get current room.booking ID from URL, or set it statically for your test
//         const urlParams = new URLSearchParams(
//           window.location.hash.split("?")[0].replace("#", "?")
//         );
//         const recordId = parseInt(urlParams.get("id"), 10);

//         if (!recordId) {
//           // Could not determine record ID
//           return;
//         }

//         // Get company_id and system_date via RPC
//         fetch("/web/dataset/call_kw", {
//           method: "POST",
//           credentials: "same-origin",
//           headers: { "Content-Type": "application/json" },
//           body: JSON.stringify({
//             jsonrpc: "2.0",
//             method: "call",
//             params: {
//               model: "room.booking",
//               method: "read",
//               args: [[recordId], ["company_id"]],
//               kwargs: {},
//             },
//             id: Date.now(),
//           }),
//         })
//           .then((res) => res.json())
//           .then((data) => {
//             if (data.error) {
//               console.error("RPC error:", data.error);
//               return;
//             }
//             const company_id = data.result[0].company_id[0];

//             // Now get the system_date
//             fetch("/web/dataset/call_kw", {
//               method: "POST",
//               credentials: "same-origin",
//               headers: { "Content-Type": "application/json" },
//               body: JSON.stringify({
//                 jsonrpc: "2.0",
//                 method: "call",
//                 params: {
//                   model: "res.company",
//                   method: "read",
//                   args: [[company_id], ["system_date"]],
//                   kwargs: {},
//                 },
//                 id: Date.now(),
//               }),
//             })
//               .then((res) => res.json())
//               .then((compData) => {
//                 if (compData.error) {
//                   console.error(compData.error);
//                   return;
//                 }
//                 const sysDateStr = compData.result[0].system_date;
//                 const sysDate = sysDateStr ? new Date(sysDateStr) : null;
//                 const newDateObj = normalizeDateInput(newVal);

//                 if (sysDate && newDateObj < sysDate) {
//                   showErrorModal(
//                     _t("Check-in date should not be less than system date")
//                   );
//                   input.value = input.__checkin_date_old;
//                   input.dispatchEvent(new Event("input", { bubbles: true }));
//                   input.dispatchEvent(new Event("change", { bubbles: true }));
//                   // Save form if needed
//                   // saveForm();
//                   return;
//                 }

//                 // input.__checkin_date_old = newVal;
//               });
//           })
//           .catch((err) => console.error("Fetch error:", err));
//       }
//     }, 1000);
//   }

//   function init() {
//     startCheckinPolling();
//     // new MutationObserver(startCheckinPolling).observe(
//     //   document.documentElement,
//     //   {
//     //     childList: true,
//     //     subtree: true,
//     //   }
//     // );
//   }

//   if (document.readyState === "loading") {
//     document.addEventListener("DOMContentLoaded", init);
//   } else {
//     init();
//   }
// })();

/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
console.log("checkin_date_validation.js loaded");
(function () {
  function normalizeDateInput(dateStr) {
    console.log("normalizeDateInput called with:", dateStr);
    if (!dateStr) return null;
    // 1) Odoo-style "DD/MM/YYYY HH:mm:ss"
    const dm = dateStr
      .trim()
      .match(
        /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$/
      );
    if (dm) {
      const [, dd, mm, yyyy, hh, min, ss] = dm;
      return new Date(
        parseInt(yyyy, 10),
        parseInt(mm, 10) - 1,
        parseInt(dd, 10),
        hh ? parseInt(hh, 10) : 0,
        min ? parseInt(min, 10) : 0,
        ss ? parseInt(ss, 10) : 0
      );
    }
    // 2) Arabic→Latin digits
    const arabicDigitsMap = {
      "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
      "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    };
    dateStr = dateStr.replace(/[٠-٩]/g, (d) => arabicDigitsMap[d] || d);
    // 3) Arabic month names → English
    const arabicMonths = {
      يناير: "January", فبراير: "February", مارس: "March", أبريل: "April",
      مايو: "May", يونيو: "June", يوليو: "July", أغسطس: "August",
      سبتمبر: "September", أكتوبر: "October", نوفمبر: "November", ديسمبر: "December",
    };
    for (const [ara, eng] of Object.entries(arabicMonths)) {
      if (dateStr.includes(ara)) {
        dateStr = dateStr.replace(ara, eng);
        break;
      }
    }
    dateStr = dateStr.replace(/[،,]/g, "");
    const parsed = new Date(dateStr.trim());
    return isNaN(parsed) ? null : parsed;
  }

  function showErrorModal(message) {
    const overlay = document.createElement("div");
    Object.assign(overlay.style, {
      position: "fixed",
      top: 0,
      left: 0,
      width: "100%",
      height: "100%",
      backgroundColor: "rgba(0,0,0,0.5)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 9999,
    });

    const box = document.createElement("div");
    Object.assign(box.style, {
      backgroundColor: "#fff",
      borderRadius: "8px",
      width: "360px",
      padding: "20px",
      textAlign: "center",
      boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
    });

    const icon = document.createElement("div");
    icon.innerHTML = "&#9888;"; // ⚠
    Object.assign(icon.style, {
      fontSize: "48px",
      color: "#D04437",
      marginBottom: "10px",
    });

    const text = document.createElement("p");
    text.textContent = message;
    Object.assign(text.style, {
      fontSize: "16px",
      color: "#333",
      marginBottom: "20px",
    });

    const btn = document.createElement("button");
    btn.textContent = _t("OK");
    Object.assign(btn.style, {
      padding: "10px 20px",
      border: "none",
      borderRadius: "4px",
      backgroundColor: "#D04437",
      color: "#fff",
      cursor: "pointer",
      fontSize: "14px",
    });
    btn.addEventListener("click", () => {
      document.body.removeChild(overlay);
    });

    box.append(icon, text, btn);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
  }

  function startCheckinAndCheckoutPolling() {
    let checkinInputFound = false;
    
    setInterval(() => {
      // --- Check-in date validation (against system date) ---
      let checkinInput = document.querySelector('[name="checkin_date"] input.o_input');
      
      // Try alternative selectors if the first one doesn't work
      if (!checkinInput) {
        checkinInput = document.querySelector('[name="checkin_date"] input');
      }
      if (!checkinInput) {
        checkinInput = document.querySelector('input[name="checkin_date"]');
      }
      
      // Only log once when input is first found
      if (checkinInput && !checkinInputFound) {
        checkinInputFound = true;
      }
      
      if (checkinInput) {
        const newVal = checkinInput.value;
        
        // Initialize old value only once, when it's undefined
        if (checkinInput.__checkin_date_old === undefined) {
          checkinInput.__checkin_date_old = newVal;
        }
        
        // Check if value actually changed
        if (newVal && newVal !== checkinInput.__checkin_date_old) {
          const urlParams = new URLSearchParams(window.location.hash.split("?")[0].replace("#", "?"));
          const recordId = parseInt(urlParams.get("id"), 10);
          if (!recordId) {
            return;
          }
          // Use a simple session info call to get company_id
          fetch("/web/session/get_session_info", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          })
            .then((res) => {
              return res.json();
            })
            .then((sessionData) => {
              if (sessionData.error) {
                console.error("Error in session fetch:", sessionData.error);
                return;
              }
              
              // Try to get company_id from session data or URL
              let company_id = null;
              
              // First try to get from URL (cids parameter)
              const urlParams = new URLSearchParams(window.location.hash.split("?")[0].replace("#", "?"));
              const cidsParam = urlParams.get("cids");
              if (cidsParam) {
                company_id = parseInt(cidsParam, 10);
              }
              
              // If not found in URL, try session data
              if (!company_id) {
                if (sessionData.result && sessionData.result.company_id) {
                  company_id = sessionData.result.company_id;
                } else if (sessionData.company_id) {
                  company_id = sessionData.company_id;
                } else if (sessionData.user_companies && sessionData.user_companies.current_company) {
                  company_id = sessionData.user_companies.current_company;
                } else {
                  // Fallback: use company_id = 1 (default)
                  company_id = 1; // Default company
                }
              }
              
              // Get system_date
              fetch("/web/dataset/call_kw", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  jsonrpc: "2.0",
                  method: "call",
                  params: {
                    model: "res.company",
                    method: "read",
                    args: [[company_id], ["system_date"]],
                    kwargs: {},
                  },
                  id: Date.now(),
                }),
              })
                .then((res) => res.json())
                .then((compData) => {
                  if (compData.error) {
                    console.error("Error fetching company data:", compData.error);
                    return;
                  }
                  const sysDateStr = compData.result[0].system_date;
                  const sysDate = sysDateStr ? new Date(sysDateStr) : null;
                  const newDateObj = normalizeDateInput(newVal);
                  
                  if (sysDate && newDateObj) {
                    // Reset time to compare only dates
                    const sysDateOnly = new Date(sysDate.getFullYear(), sysDate.getMonth(), sysDate.getDate());
                    const newDateOnly = new Date(newDateObj.getFullYear(), newDateObj.getMonth(), newDateObj.getDate());
                    
                    if (newDateOnly < sysDateOnly) {
                      showErrorModal(_t("Check-in date should not be less than system date"));
                      checkinInput.value = checkinInput.__checkin_date_old;
                      checkinInput.dispatchEvent(new Event("input", { bubbles: true }));
                      checkinInput.dispatchEvent(new Event("change", { bubbles: true }));
                    } else {
                      console.log("Date validation passed, updating old value");
                      checkinInput.__checkin_date_old = newVal;
                    }
                  } else {
                    console.log("Date parsing failed - sysDate:", sysDate, "newDateObj:", newDateObj);
                    checkinInput.__checkin_date_old = newVal;
                  }
                })
                .catch((error) => {
                  console.error("Error in system date validation:", error);
                });
            });
        }
      }

      // --- Check-out date validation (cannot be before check-in date) ---
      const checkoutInput = document.querySelector('[name="checkout_date"] input.o_input');
      if (checkoutInput) {
        const checkoutVal = checkoutInput.value;
        if (!checkoutInput.__checkout_date_old) {
          checkoutInput.__checkout_date_old = checkoutVal;
        }
        if (checkoutVal && checkoutVal !== checkoutInput.__checkout_date_old) {
          const checkinInput2 = document.querySelector('[name="checkin_date"] input.o_input');
          const checkinVal = checkinInput2 ? checkinInput2.value : null;
          const checkoutDateObj = normalizeDateInput(checkoutVal);
          const checkinDateObj = normalizeDateInput(checkinVal);
          if (checkinDateObj && checkoutDateObj && checkoutDateObj < checkinDateObj) {
            showErrorModal(_t("Check-out Date cannot be before Check-in Date"));
            checkoutInput.value = checkoutInput.__checkout_date_old;
            checkoutInput.dispatchEvent(new Event("input", { bubbles: true }));
            checkoutInput.dispatchEvent(new Event("change", { bubbles: true }));
          } else {
            checkoutInput.__checkout_date_old = checkoutVal;
          }
        }
      }
    }, 1000);
  }

  function attachDirectEventListeners() {
    console.log("Attempting to attach direct event listeners");
    
    // Try to find and attach event listeners directly
    const checkinInput = document.querySelector('[name="checkin_date"] input.o_input') || 
                        document.querySelector('[name="checkin_date"] input') ||
                        document.querySelector('input[name="checkin_date"]');
    
    if (checkinInput) {
      console.log("Attaching direct event listeners to check-in input:", checkinInput);
      
      const handleCheckinChange = (event) => {
        validateCheckinDate(event.target.value, checkinInput);
      };
      
      // Attach multiple event types to catch all possible changes
      checkinInput.addEventListener('change', handleCheckinChange);
      checkinInput.addEventListener('input', handleCheckinChange);
      checkinInput.addEventListener('blur', handleCheckinChange);
    } else {
      console.log("Could not find check-in input for direct event listeners");
    }
  }
  
  function validateCheckinDate(newVal, checkinInput) {
    if (!newVal) return;
    
    
    const urlParams = new URLSearchParams(window.location.hash.split("?")[0].replace("#", "?"));
    const recordId = parseInt(urlParams.get("id"), 10);
    if (!recordId) {
      return;
    }
    
    
    // Get company_id
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
          args: [[recordId], ["company_id"]],
          kwargs: {},
        },
        id: Date.now(),
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          return;
        }
        const company_id = data.result[0].company_id[0];
        
        // Get system_date
        fetch("/web/dataset/call_kw", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: {
              model: "res.company",
              method: "read",
              args: [[company_id], ["system_date"]],
              kwargs: {},
            },
            id: Date.now(),
          }),
        })
          .then((res) => res.json())
          .then((compData) => {
            console.log("Company data response:", compData);
            if (compData.error) {
              console.error("Error fetching company data:", compData.error);
              return;
            }
            const sysDateStr = compData.result[0].system_date;
            const sysDate = sysDateStr ? new Date(sysDateStr) : null;
            const newDateObj = normalizeDateInput(newVal);
            
            if (sysDate && newDateObj) {
              // Reset time to compare only dates
              const sysDateOnly = new Date(sysDate.getFullYear(), sysDate.getMonth(), sysDate.getDate());
              const newDateOnly = new Date(newDateObj.getFullYear(), newDateObj.getMonth(), newDateObj.getDate());
              
              
              if (newDateOnly < sysDateOnly) {
                showErrorModal(_t("Check-in date should not be less than system date"));
                // Don't reset the value here since we're using direct event listeners
              } else {
                console.log("Date validation passed");
              }
            } else {
              console.log("Date parsing failed - sysDate:", sysDate, "newDateObj:", newDateObj);
            }
          })
          .catch((error) => {
            console.error("Error in system date validation:", error);
          });
      })
      .catch((error) => {
        console.error("Error fetching room booking:", error);
      });
  }

  function init() {
    startCheckinAndCheckoutPolling();
    
    // Also try direct event listeners as backup
    setTimeout(() => {
      attachDirectEventListeners();
    }, 2000); // Wait 2 seconds for the page to fully load
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
