function importStockReport() {
  var labelName = 'Sellerboard Stock'; // Label for unprocessed emails
  var processedLabelName = 'Sellerboard Stock/Processed'; // Full path to the sub-label for processed emails
  var roiSheetName = 'ROI Data';
  var stockDataSheetName = 'Stock Data';
  var spreadsheetId = '1F4he4z06NppO7fWhsQ-NKCYxIxokxt16Gj09x1d0lR0';

  // Define column indices
  var asinIndex = 0;
  var skuIndex = 1;
  var roiIndex = 3;
  var fbaStockIndex = 4;
  var salesVelocityIndex = 6;
  var stockIndex = 4;
  var reservedIndex = 10;
  var sentToFbaIndex = 11;

  var label = GmailApp.getUserLabelByName(labelName);
  var processedLabel = GmailApp.getUserLabelByName(processedLabelName);
  var spreadsheet = SpreadsheetApp.openById(spreadsheetId);

  if (!label || !processedLabel) {
    Logger.log('Labels not found. Exiting...');
    return;
  }

  var roiSheet = spreadsheet.getSheetByName(roiSheetName);
  var stockDataSheet = spreadsheet.getSheetByName(stockDataSheetName);

  if (!roiSheet) {
    Logger.log(`ROI Sheet '${roiSheetName}' not found. Creating new sheet...`);
    roiSheet = spreadsheet.insertSheet(roiSheetName);
    roiSheet.appendRow(["Timestamp", "ASIN", "SKU", "ROI, %", "Estimated Sales Velocity"]);
  }

  if (!stockDataSheet) {
    Logger.log(`Stock Data Sheet '${stockDataSheetName}' not found. Creating new sheet...`);
    stockDataSheet = spreadsheet.insertSheet(stockDataSheetName);
    stockDataSheet.appendRow(["Timestamp", "ASIN", "SKU", "Stock", "Reserved", "Sent to FBA"]);
  }

  var threads = GmailApp.search(`label:"${labelName}" is:unread`);
  Logger.log(`Found ${threads.length} threads`);

  if (threads.length === 0) {
    MailApp.sendEmail({
      to: "luke@drjhardware.co.uk",
      subject: "Sellerboard Stock Report Missing",
      body: "No unread Sellerboard stock report emails were found today. Please check if the report was sent or if the label is missing."
    });
    return;
  }

  for (var i = 0; i < threads.length; i++) {
    var messages = threads[i].getMessages();
    for (var j = 0; j < messages.length; j++) {
      var message = messages[j];
      Logger.log(`Processing email with subject: ${message.getSubject()}`);
      var attachments = message.getAttachments();

      for (var k = 0; k < attachments.length; k++) {
        var attachment = attachments[k];

        if (attachment.getContentType() === 'text/csv') {
          var csvData = attachment.getDataAsString();
          var csvRows = Utilities.parseCsv(csvData);
          var currentDate = new Date();

          for (var r = 1; r < csvRows.length; r++) {
            if (csvRows[r].length < 18) continue; // skip bad rows
            if (csvRows[r][17] !== "Amazon.co.uk") continue; // only keep Amazon UK

            var fbaStock = parseFloat(csvRows[r][fbaStockIndex]);

            if (fbaStock > 0) {
              var roiRowData = [
                currentDate,
                csvRows[r][asinIndex],
                csvRows[r][skuIndex],
                csvRows[r][roiIndex],
                csvRows[r][salesVelocityIndex]
              ];
              roiSheet.appendRow(roiRowData);
            }

            var stockRowData = [
              currentDate,
              csvRows[r][asinIndex],
              csvRows[r][skuIndex],
              csvRows[r][stockIndex],
              csvRows[r][reservedIndex],
              csvRows[r][sentToFbaIndex]
            ];
            stockDataSheet.appendRow(stockRowData);
          }

          message.markRead();
          threads[i].removeLabel(label);
          threads[i].addLabel(processedLabel);
          Logger.log(`CSV data imported successfully and email moved to processed label`);
        }
      }
    }
  }
}
