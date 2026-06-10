function onEdit(e) {
  // Define the sheet and columns to monitor
  var sheetName = 'Product Database';
  var dateColumn = 14; // Column N (14th column)
  var entryColumn = 12; // Column L (10th column)
  var formulaColumn = 15; // Column O (15th column)

  // Get the active sheet and edited cell range
  var sheet = e.source.getActiveSheet();
  var range = e.range;
  
  // Check if the edited sheet is "Orders" and edited column is J
  if (sheet.getName() === sheetName && range.getColumn() === entryColumn) {
    var row = range.getRow();
    
    // Add today's date to column N
    sheet.getRange(row, dateColumn).setValue(new Date());
    
    // Add the formula to column O
    var formula = `=IF(N${row}<TODAY()-5,0,K${row})`;
    sheet.getRange(row, formulaColumn).setFormula(formula);
  }
}

function copyProductData() {
  // Open the spreadsheet by ID
  var ss = SpreadsheetApp.openById('1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY');
  
  // Access the 'Product Database' and 'Purchase List' sheets
  var productSheet = ss.getSheetByName('Product Database');
  var purchaseSheet = ss.getSheetByName('Purchase List');
  
  // Clear content of row 3 and delete all rows from 4 onwards
  purchaseSheet.getRange(3, 1, 1, purchaseSheet.getLastColumn()).clearContent(); // Clear row 3
  var lastRowInPurchaseSheet = purchaseSheet.getLastRow();
  if (lastRowInPurchaseSheet > 3) {
    purchaseSheet.deleteRows(4, lastRowInPurchaseSheet - 3); // Delete all rows from row 4 onwards
  }

  // Get the data from 'Product Database' starting from row 3
  var lastRow = productSheet.getLastRow();
  var productData = productSheet.getRange(3, 1, lastRow - 2, 26).getValues(); 

  // Create a new array with reordered data, ensuring only rows with Product Database Column S > 0 are copied
  var reorderedData = [];
  productData.forEach(function(row, index) {
    if (row[18] > 0) {  // Only proceed if the value in Column S (Restock) in Product Database is greater than 0
      reorderedData.push([
        row[3],  // Supplier (D in Product Database)
        row[0],  // SKU (A in Product Database)
        row[2],  // ASIN (C in Product Database)
        row[1],  // Name (B in Product Database)
        row[4],  // Qtys (E in Product Database)
        row[5],  // Barcode (F in Product Database)
        row[6],  // Supply Code (G in Product Database)
        row[7] !== "#REF!" && row[7] !== "" ? row[7] : 0,  // CPU (H in Product Database) <- Replace #REF! or empty with 0
        '',  // Placeholder for formula in Column I (will be set later dynamically)
        row[13] + row[14] + row[15] + row[16] + row[17], // Sum of N, O, P, Q, R to column J
        row[10],  // K -> K
        row[11],  // L -> L
        '',  // Placeholder for formula in Column M (will be set later dynamically)
        row[20],  // U -> N
        row[18],  // S -> O
        '',       // Blank column S
        '',       // Blank column T
        ''        // Placeholder for tick box U
      ]);
    }
  });

  // Paste the reordered data into the 'Purchase List' starting from row 3
  if (reorderedData.length > 0) {
    purchaseSheet.getRange(3, 1, reorderedData.length, reorderedData[0].length).setValues(reorderedData);
    Logger.log("Filtered product data copied successfully.");
  } else {
    Logger.log("No rows to copy. All rows had Restock value <= 0.");
  }

  var lastDataRow = purchaseSheet.getLastRow(); // Get the last row with data

  // Apply dynamic formulas to columns I and M
  for (var i = 3; i <= lastDataRow; i++) {
    var formulaI = '=SUMIF(Orders!C:C, B' + i + ', Orders!M:M)';
    purchaseSheet.getRange(i, 9).setFormula(formulaI); // Set formula in column I dynamically

    var formulaM = '=(I' + i + '+J' + i + ')/L' + i;
    purchaseSheet.getRange(i, 13).setFormula(formulaM); // Set formula in column M dynamically
  }

  // Add tick boxes to columns P, Q, R, and U
  var tickBoxRangePQR = purchaseSheet.getRange(3, 16, lastDataRow - 2, 3); // Columns P, Q, R
  tickBoxRangePQR.insertCheckboxes();
  
  var tickBoxU = purchaseSheet.getRange(3, 21, lastDataRow - 2, 1); // Column U
  tickBoxU.insertCheckboxes();
  
  // Apply formulas to columns V and W dynamically
  for (var i = 3; i <= lastDataRow; i++) {
    var formulaV = '=IF(S' + i + '>0,G' + i + '&" x "&S' + i + ',"")';
    purchaseSheet.getRange(i, 22).setFormula(formulaV); // Set formula in column V dynamically

    var formulaW = '=IF(H' + i + '>0,H' + i + '*O' + i + ')';
    purchaseSheet.getRange(i, 23).setFormula(formulaW); // Set formula in column W dynamically
  }

  // Sort the data alphabetically by column A (Supplier) from A3 down to the last row with data
  if (lastDataRow > 3) {
    purchaseSheet.getRange(3, 1, lastDataRow - 2, 15).sort(1); // Sort the range A3:O by column A (index 1)
    Logger.log("Data sorted alphabetically by Supplier.");
  }

  // Add timestamp (date and time) to A1 in 'Purchase List'
  var currentDate = new Date(); // Get current date and time
  purchaseSheet.getRange("A1").setValue(currentDate); // Set the current date/time in A1 of Purchase List
  SpreadsheetApp.flush(); // Ensure the update is applied immediately

  // Delete all unused rows below the last data row
  var lastRowInSheet = purchaseSheet.getMaxRows();
  if (lastDataRow < lastRowInSheet) {
    purchaseSheet.deleteRows(lastDataRow + 1, lastRowInSheet - lastDataRow);
  }

  // Delete rows with no value in column A
  for (var i = lastDataRow; i >= 3; i--) {
    if (purchaseSheet.getRange(i, 1).getValue() === "") {
      purchaseSheet.deleteRow(i);
    }
  }

  Logger.log("Tick boxes added, formulas applied, timestamp (date and time) added, unused rows deleted, and rows with no value in column A deleted.");
}

function processDoneTicksAndDelete() {
  var ss = SpreadsheetApp.openById('1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY');
  
  // Access the 'Purchase List', 'Product Database', and 'Orders' sheets
  var purchaseSheet = ss.getSheetByName('Purchase List');
  var productSheet = ss.getSheetByName('Product Database');
  var ordersSheet = ss.getSheetByName('Orders');
  
  // Get the range of tick boxes in 'Purchase List' (Columns P, Q, R, S, and U starting from row 3)
  var lastRowPurchase = purchaseSheet.getLastRow();
  var tickRangeP = purchaseSheet.getRange(3, 16, lastRowPurchase - 2, 1); // Column P (Disc)
  var tickRangeQ = purchaseSheet.getRange(3, 17, lastRowPurchase - 2, 1); // Column Q (Drop)
  var tickRangeR = purchaseSheet.getRange(3, 18, lastRowPurchase - 2, 1); // Column R (Snze)
  var tickRangeS = purchaseSheet.getRange(3, 19, lastRowPurchase - 2, 1); // Column S (Ordered)
  var tickRangeU = purchaseSheet.getRange(3, 21, lastRowPurchase - 2, 1); // Column U (Done)
  var tickValuesP = tickRangeP.getValues();
  var tickValuesQ = tickRangeQ.getValues();
  var tickValuesR = tickRangeR.getValues();
  var tickValuesS = tickRangeS.getValues();
  var tickValuesU = tickRangeU.getValues();
  
  // Get the SKU and other relevant columns in 'Purchase List'
  var skuRangePurchase = purchaseSheet.getRange(3, 2, lastRowPurchase - 2, 1); // Column B (SKU)
  var sValuesPurchase = purchaseSheet.getRange(3, 19, lastRowPurchase - 2, 1).getValues(); // Column S (Ordered)
  var tValuesPurchase = purchaseSheet.getRange(3, 20, lastRowPurchase - 2, 1).getValues(); // Column T (Price)
  var skuValuesPurchase = skuRangePurchase.getValues();
  
  // Get the SKU column in 'Product Database' (Column A)
  var lastRowProduct = productSheet.getLastRow();
  var skuRangeProduct = productSheet.getRange(3, 1, lastRowProduct - 2, 1); // Column A (SKU)
  var skuValuesProduct = skuRangeProduct.getValues();
  
  // Calculate the next Sunday for Column T and today's date for Orders
  var today = new Date();
  var dayOfWeek = today.getDay(); // 0 = Sunday, 6 = Saturday

  // Calculate how many days to add to reach the next Sunday
  var daysUntilSunday = (7 - dayOfWeek) % 7;
  if (daysUntilSunday === 0) {
    daysUntilSunday = 7; // If today is Sunday, set it to the next Sunday (7 days ahead)
  }

  var nextSunday = new Date(today);
  nextSunday.setDate(today.getDate() + daysUntilSunday);

  var formattedNextSunday = Utilities.formatDate(nextSunday, Session.getScriptTimeZone(), "yyyy-MM-dd");
  var todayFormatted = Utilities.formatDate(today, Session.getScriptTimeZone(), "dd/MM/yy");

  // Loop through the tick boxes in 'Purchase List' for Columns P, Q, R, S, and U
  for (var i = 0; i < tickValuesP.length; i++) {
    var purchaseSKU = skuValuesPurchase[i][0]; // Get the SKU for the current row
    
    // Find the matching SKU in 'Product Database'
    for (var j = 0; j < skuValuesProduct.length; j++) {
      if (skuValuesProduct[j][0] === purchaseSKU) {
        
        // Check Column P: If TRUE, set Column K to TRUE in Product Database (ROI column is now Column K)
        if (tickValuesP[i][0] === true) {
          productSheet.getRange(j + 3, 9).setValue(true); // Column K (ROI)
        }
        
        // Check Column Q: If TRUE, set Column L to TRUE in Product Database (Sales Velocity column is now Column L)
        if (tickValuesQ[i][0] === true) {
          productSheet.getRange(j + 3, 10).setValue(true); // Column L (Sales Velocity)
        }
        
        // Check Column R in 'Purchase List': If TRUE, set Column T (index 20) to the date 1 week from today in 'Product Database'
        if (tickValuesR[i][0] === true) {
          productSheet.getRange(j + 3, 20).setValue(formattedNextSunday); // Corrected: Column T (Snooze)
        }

        // Check Column U: If ticked (TRUE), process Column S
        if (tickValuesU[i][0] === true) {
          var sValue = sValuesPurchase[i][0];
        
          if (sValue === "" || sValue === null) {
            Logger.log("Value in Column S for SKU " + purchaseSKU + " is empty or null.");
          } else if (!isNaN(parseFloat(sValue)) && parseFloat(sValue) > 0) {
            // Valid number greater than 0

            // Find the next available visible row in Orders
            var nextOrderRow = getNextVisibleRow(ordersSheet);
            
            // Copy the SKU to Column C in Orders
            ordersSheet.getRange(nextOrderRow, 3).setValue(purchaseSKU); // Column C (SKU)
            
            // Copy the value from Column S to Column J in Orders
            ordersSheet.getRange(nextOrderRow, 10).setValue(parseFloat(sValue)); // Column J (Ordered amount)
            
            // Copy the value from Column T to Column H in Orders
            var tValue = tValuesPurchase[i][0];
            ordersSheet.getRange(nextOrderRow, 8).setValue(tValue); // Column H (Price)
            
            // Add today's date in DD/MM/YY format to Column I in Orders
            ordersSheet.getRange(nextOrderRow, 9).setValue(todayFormatted); // Column I (Date)
          }
        }
        
        break; // Stop searching once the SKU is found
      }
    }
  }

  // Now delete rows where Column U is ticked
  for (var i = tickValuesU.length - 1; i >= 0; i--) { // Loop in reverse to avoid index shifting issues
    if (tickValuesU[i][0] === true) {
      purchaseSheet.deleteRow(i + 3); // Delete the row where Column U is ticked (starting from row 3)
    }
  }
}

// Function to get the next visible row in the Orders sheet
function getNextVisibleRow(sheet) {
  var data = sheet.getDataRange().getValues();
  for (var i = 0; i < data.length; i++) {
    if (data[i][2] === "" || data[i][2] === null) {
      return i + 1; // Return the next available row above the filter
    }
  }
  return data.length + 1; // If no visible row is found, return the next row after the last row
}

function onEdit(e) {
  // Define the sheet and columns to monitor
  var sheetName = 'Orders';
  var dateColumn = 14; // Column N (14th column)
  var entryColumn = 12; // Column L (10th column)
  var formulaColumn = 15; // Column O (15th column)

  // Get the active sheet and edited cell range
  var sheet = e.source.getActiveSheet();
  var range = e.range;
  
  // Check if the edited sheet is "Orders" and edited column is J
  if (sheet.getName() === sheetName && range.getColumn() === entryColumn) {
    var row = range.getRow();
    
    // Add today's date to column N
    sheet.getRange(row, dateColumn).setValue(new Date());
    
    // Add the formula to column O
    var formula = `=IF(N${row}<TODAY()-5,0,K${row})`;
    sheet.getRange(row, formulaColumn).setFormula(formula);
  }
}

/**
 * CONFIGURATION ────────────────────────────────────────────────────────────
 * Put your own file-ID and sheet name here so the script always touches
 * exactly the sheet you expect (even if some other sheet is active).
 */
const SPREADSHEET_ID = '1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY';
const TAB_NAME       = 'Purchase List';

/**
 * Draw a medium bottom-border whenever the supplier in column A changes.
 */
function drawSupplierBorders() {
  // Open the file & tab explicitly
  const ss     = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet  = ss.getSheetByName(TAB_NAME);

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 3) return;                           // nothing to do

  const suppliers = sheet.getRange(2, 1, lastRow - 1, 1)
                         .getValues()
                         .flat();

  // 1️⃣ clear existing horizontal borders to keep things idempotent
  sheet.getRange(2, 1, lastRow - 1, lastCol)
       .setBorder(null, null, null, null, null, null);

  // 2️⃣ re-apply the divider where the supplier changes
  for (let r = 2; r <= lastRow; r++) {
    const cur  = suppliers[r - 2];
    const next = (r === lastRow) ? null : suppliers[r - 1];
    if (cur !== next) {
      sheet.getRange(r, 1, 1, lastCol)
           .setBorder(null, null, true, null, null, null,
                      null, SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
    }
  }
}

/**
 * Trigger wrapper – fires on any change to the spreadsheet.
 * Install this in *Triggers* → *Add Trigger*:
 *   • Function → handleChange
 *   • Source   → From spreadsheet
 *   • Event    → On change
 */
function handleChange() {
  drawSupplierBorders();
}

/**
 * Nightly fill of columns K–U (row 3 ↓) in “Product Database”.
 *   – Replaces all heavy formulas.
 *   – Finishes in seconds for ~500 rows.
 *
 * Author: ChatGPT, July 2025
 */
function updateProductDatabaseKU() {
  /* ─────────────────────────────────────────────
     0.  Spreadsheet & sheet handles
  ───────────────────────────────────────────── */
  const DB_SS_ID   = '1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY';
  const EXT_SS_ID  = '1F4he4z06NppO7fWhsQ-NKCYxIxokxt16Gj09x1d0lR0';
  const dbSS       = SpreadsheetApp.openById(DB_SS_ID);
  const dbSheet    = dbSS.getSheetByName('Product Database');
  const ordersSht  = dbSS.getSheetByName('Orders');                // local sheet
  const extSS      = SpreadsheetApp.openById(EXT_SS_ID);
  const roiSht     = extSS.getSheetByName('ROI Data');
  const stockSht   = extSS.getSheetByName('Stock Data');

  /* ─────────────────────────────────────────────
     1.  Core ranges (row indexing starts at 3)
  ───────────────────────────────────────────── */
  const START_ROW = 3;                         // first data row to paste
  const LAST_ROW  = dbSheet.getLastRow();
  if (LAST_ROW < START_ROW) return;            // nothing to do

  const NUM_DB_ROWS = LAST_ROW - START_ROW + 1;
  const DB_READ_COLS = 20;                     // read through col T (A → T)

  // A = 1, I = 9, J = 10, T = 20
  const dbRange = dbSheet.getRange(START_ROW, 1, NUM_DB_ROWS, DB_READ_COLS);
  const dbVals  = dbRange.getValues();

  /* ─────────────────────────────────────────────
     2.  Build quick-lookup Maps for ROI & Stock
  ───────────────────────────────────────────── */
  const roiVals   = roiSht.getRange(2, 3, roiSht.getLastRow() - 1, 3).getValues(); // C:D:E
  const stockVals = stockSht.getRange(2, 3, stockSht.getLastRow() - 1, 4).getValues(); // C:D:E:F

  const roiMap   = {};  // { sku: {roi: Number, cost: Number} }
  const stockMap = {};  // { sku: {d: Number, e: Number, f: Number} }

  roiVals.forEach(r => {
    const sku = r[0];
    if (!sku) return;
    roiMap[sku] = { roi: (Number(r[1]) || 0) / 100, cost: Number(r[2]) || 0 };
  });
  stockVals.forEach(r => {
    const sku = r[0];
    if (!sku) return;
    stockMap[sku] = { d: Number(r[1]) || 0, e: Number(r[2]) || 0, f: Number(r[3]) || 0 };
  });

  /* ─────────────────────────────────────────────
     3.  Build SUMIF-style lookups from Orders
  ───────────────────────────────────────────── */
  const ordersData = ordersSht.getDataRange().getValues(); // assume headers in row 1
  const orderMap = {};   // { sku: {sumM, sumK, sumL} }

  ordersData.slice(1).forEach(r => {           // skip header
    const sku = r[2];                          // Orders!C
    if (!sku) return;
    if (!orderMap[sku]) orderMap[sku] = { sumM: 0, sumK: 0, sumL: 0 };
    orderMap[sku].sumM += Number(r[12]) || 0; // Orders!M
    orderMap[sku].sumK += Number(r[10]) || 0; // Orders!K
    orderMap[sku].sumL += Number(r[11]) || 0; // Orders!L
  });

  /* ─────────────────────────────────────────────
     4.  Row-by-row calculation (K → U)
  ───────────────────────────────────────────── */
  const out = [];                // 2-D array to write back (K:L:M:N:O:P:Q:R:S:T:U)

  dbVals.forEach(row => {
    const sku  = row[0];         // A
    const colI = row[8];         // I  (TRUE/FALSE or blank)
    const colJ = row[9];         // J
    const colT = row[19];        // T  (keep existing)

    /*  ROI & Cost  */
    const roiObj = roiMap[sku]   || { roi: 0, cost: 0 };
    const K = roiObj.roi;        // column K
    const L = roiObj.cost;       // column L

    /*  Orders  */
    const ord   = orderMap[sku]  || { sumM: 0, sumK: 0, sumL: 0 };
    const M = ord.sumM;                             // column M
    const N = ord.sumK - ord.sumL;                  // column N

    /*  Stock  */
    const st   = stockMap[sku] || { d: 0, e: 0, f: 0 };
    const O = st.f;   // Stock F  (column O)
    const P = st.f;   // duplicate – matches original sheet (column P)
    const Q = st.e;   // Stock E  (column Q)
    const R = st.d;   // Stock D  (column R)

    /*  Column U: status text  */
    const U = L === 0 ? 'No Data' : (K < 0.05 ? 'Drop' : 'Restock');

    /*  Column S: re-order qty (mirrors your nested IF)  */
    const sumOR     = O + P + Q + R;
    const sumMtoR   = M + N + sumOR;                // M+N+O+P+Q+R
    let   S = 0;

    if (!(K < 0.05 && sumOR > 0)) {                // NOT the first “block” condition
      if (!(new Date() < (colT instanceof Date ? colT : new Date(0)))) {
        if (!colJ) {
          if (!colI) {
            if (U === 'No Data') {
              S = sumMtoR > 0 ? 0 : 10;
            } else {
              const target = L * 35 - sumMtoR;
              S = target < 0 ? 0 : Math.ceil(target);
            }
          }
        }
      }
    }

    /*  Push 11-cell output row  */
    out.push([K, L, M, N, O, P, Q, R, S, colT, U]);
  });

  /* ─────────────────────────────────────────────
     5.  One fast write-back
  ───────────────────────────────────────────── */
  dbSheet.getRange(START_ROW, 11, out.length, 11)  // 11 = column K
          .setValues(out);

  /* ─────────────────────────────────────────────
     6.  Optional: simple log
  ───────────────────────────────────────────── */
  console.log(`updateProductDatabaseKU – processed ${out.length} rows`);
}

// === TOKEN LOGGER — SHIPMENT-AWARE ===

const CFG = {
  ORDERS: "Orders",
  SNAPSHOT: "Snapshot",
  TOKENS: "Tokens",

  ORDERKEY: "OrderKey",
  SKU: "SKU",
  COST: "Cost PU",
  SENT: "Sent to FBA",
  INTAKE_DATE_COL: "Order Date"
};

function runTokenLogger() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return;

  try {
    const ss = SpreadsheetApp.getActive();
    const orders = ss.getSheetByName(CFG.ORDERS);
    const tokens = ss.getSheetByName(CFG.TOKENS);
    let snapshot = ss.getSheetByName(CFG.SNAPSHOT);

    if (!orders || !tokens) throw new Error("Missing Orders or Tokens sheet");

    ensureTokensHeader_(tokens);

    const oData = orders.getDataRange().getValues();
    if (oData.length < 2) return;

    const headers = oData[0].map(h => String(h || "").trim());
    const rows = oData.slice(1);

    const idx = name => headers.indexOf(name);
    let cOrderKey = idx(CFG.ORDERKEY);
    const cSKU = idx(CFG.SKU);
    const cCost = idx(CFG.COST);
    const cSent = idx(CFG.SENT);
    const cDate = idx(CFG.INTAKE_DATE_COL);

    if (cOrderKey === -1) throw new Error("OrderKey column missing");
    if (cSKU < 0 || cCost < 0 || cSent < 0) {
      throw new Error("Missing required Orders headers");
    }

    // Create Snapshot if missing (baseline only)
    if (!snapshot) {
      snapshot = ss.insertSheet(CFG.SNAPSHOT);
      snapshot.getRange(1, 1, 1, 2).setValues([[CFG.ORDERKEY, CFG.SENT]]);
      const base = rows.map(r => [r[cOrderKey], toNumber_(r[cSent])]);
      snapshot.getRange(2, 1, base.length, 2).setValues(base);
      return;
    }

    // Load snapshot
    const sData = snapshot.getDataRange().getValues();
    const sMap = {};
    for (let i = 1; i < sData.length; i++) {
      sMap[sData[i][0]] = toNumber_(sData[i][1]);
    }

    const output = [];
    const today = new Date();
    const newSnapshot = [];

    for (const r of rows) {
      const orderKey = String(r[cOrderKey] || "").trim();
      if (!orderKey) continue;

      const sentNow = toNumber_(r[cSent]);
      const sentBefore = sMap[orderKey] ?? sentNow;

      if (sentNow > sentBefore) {
        output.push([
          (cDate >= 0 && r[cDate] instanceof Date) ? r[cDate] : today,
          String(r[cSKU]).trim(),
          sentNow - sentBefore,
          toMoney_(r[cCost]),
          orderKey                 // ← NEW
        ]);
      }

      newSnapshot.push([orderKey, sentNow]);
    }

    if (output.length) {
      const start = tokens.getLastRow() + 1;
      tokens.getRange(start, 1, output.length, 5).setValues(output);
    }

    snapshot.clearContents();
    snapshot.getRange(1, 1, 1, 2).setValues([[CFG.ORDERKEY, CFG.SENT]]);
    snapshot.getRange(2, 1, newSnapshot.length, 2).setValues(newSnapshot);

  } finally {
    lock.releaseLock();
  }
}

function ensureTokensHeader_(sheet) {
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "intake_date",
      "seller_sku",
      "qty",
      "cost_per_unit",
      "order_key"
    ]);
    sheet.setFrozenRows(1);
  }
}

function toNumber_(v) {
  return Number(v) || 0;
}

function toMoney_(v) {
  return Number(String(v).replace(/[^0-9.-]/g, "")) || 0;
}
