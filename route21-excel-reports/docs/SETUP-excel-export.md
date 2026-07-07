# Setup Guide: Business Central to Excel Export Workflow

This guide walks you through importing and configuring the n8n workflow for daily Business Central data exports.

## Step 1: Prepare Your n8n Instance

### 1.1 Start or Access Your n8n Installation

- If using n8n Cloud: Log into your n8n account at https://app.n8n.cloud
- If using self-hosted n8n: Navigate to your n8n instance URL (e.g., http://localhost:5678)

### 1.2 Create API Credentials (if not already done)

You'll need credentials for:
- **Business Central** (OAuth2)
- **Microsoft 365/OneDrive** (OAuth2)

See CLAUDE.md for detailed credential setup instructions.

---

## Step 2: Import the Workflow

### 2.1 Get the Workflow File

The workflow file is located at: `workflows/business-central-excel-export.json`

### 2.2 Import into n8n

1. Open n8n and go to the "Workflows" section
2. Click "Create Workflow" or the "+" button
3. Click the menu (three dots) in the top-right corner
4. Select "Import from file"
5. Choose the `business-central-excel-export.json` file
6. Click "Open" to import

The workflow will be created with all nodes and connections intact.

---

## Step 3: Configure Credentials

### 3.1 Set Up Business Central Credentials

1. In the imported workflow, open the first data retrieval node (Invoices Query)
2. Click on the "Credential" dropdown
3. Select "Create New" > "Business Central OData"
4. Enter your Business Central credentials:
   - **Tenant ID**: Your Azure AD tenant ID
   - **Client ID**: Your Business Central app registration client ID
   - **Client Secret**: Your Business Central app registration secret
5. Click "Create" to save
6. Repeat this for all four data retrieval nodes (they will share the same credential)

### 3.2 Set Up Microsoft 365 Credentials

1. In the workflow, open the "Save to OneDrive" node (last node)
2. Click on the "Credential" dropdown
3. Select "Create New" > "Microsoft 365"
4. Enter your Microsoft credentials:
   - **Client ID**: Your Azure app registration client ID
   - **Client Secret**: Your Azure app registration secret
5. Click "Create" to save

---

## Step 4: Configure Workflow Settings

### 4.1 Set the Daily Schedule

1. Open the "Schedule Trigger" node (first node in the workflow)
2. Configure the timing:
   - **Trigger Type**: "Every Day"
   - **Trigger Time**: "06:00" (6 AM UTC, or your preferred time)
3. Save the node

### 4.2 Configure OneDrive Save Location

1. Open the "Save to OneDrive" node
2. Set the **Folder Path** to where you want the Excel files saved:
   - Example: `/BusinessCentral/Route21Reports/`
3. The **File Name** field should be set to generate dynamic names:
   - `BusinessCentral_Route21_Export_{{ $now.toFormat('yyyy-MM-dd') }}.xlsx`

### 4.3 Configure Error Notification Email (Optional)

1. Open the "Send Error Email" node
2. Set the recipient email address in the "To" field
3. Save the node

---

## Step 5: Test the Workflow

### 5.1 Manual Test Run

1. In the workflow editor, click the "Execute Workflow" button (play icon) in the top-right
2. Watch the execution log at the bottom for progress
3. Check each node's output:
   - Green checkmarks = successful
   - Red X = error (click to see details)

### 5.2 Verify Data Output

1. After successful execution, check your OneDrive folder
2. You should see a new Excel file named: `BusinessCentral_Route21_Export_2024-XX-XX.xlsx`
3. Open the file and verify:
   - **Sheet 1** contains Invoices and Sales Orders
   - **Sheet 2** contains Invoice Lines and Sales Order Lines
   - All records have Shipping Agent Code = "RT 21"
   - Column headers and formatting look correct

### 5.3 Check for Errors

If the workflow fails:
1. Click on the failed node to see the error message
2. Review the CLAUDE.md troubleshooting section
3. Common issues:
   - Invalid credentials: re-authenticate
   - API rate limiting: wait a few minutes and retry
   - Data format errors: check that Business Central data format matches expectations

---

## Step 6: Enable the Daily Schedule

### 6.1 Activate the Workflow

1. In the workflow editor, click the toggle switch to turn the workflow "On"
2. You should see a confirmation message: "Workflow is now active"
3. The workflow will now execute daily at 6 AM

### 6.2 Monitor Execution

1. Go to the "Executions" tab to view workflow runs
2. Each day, you should see a new execution at 6 AM
3. Check the status:
   - Green = Successful
   - Red = Failed (click for error details)

---

## Step 7: Customize the Workflow (Optional)

### 7.1 Change the Shipping Agent Code Filter

To export data for a different route instead of "RT 21":

1. Open the "Invoices Query" node
2. Find the **URL** or **Filter** parameter
3. Change `shippingAgentCode eq 'RT 21'` to your desired code
4. Example: `shippingAgentCode eq 'RT 10'`
5. Repeat for the other three query nodes

### 7.2 Add or Remove Columns

To customize which columns appear in the Excel export:

1. Open the data processing nodes
2. Modify the column mappings in the "Transform" or "Function" node
3. Add or remove field references as needed
4. Test with a manual execution

### 7.3 Change the Schedule

To run at a different time:

1. Open the "Schedule Trigger" node
2. Change the "Trigger Time" to your preferred time
3. Example: "18:00" for 6 PM

---

## Step 8: Maintenance & Monitoring

### 8.1 Regular Checks

- **Weekly**: Review execution logs to ensure no failures
- **Monthly**: Verify OneDrive file counts and data accuracy
- **Quarterly**: Check if credential tokens need refresh

### 8.2 Credential Refresh

If you see "Invalid Credentials" errors:

1. Open the workflow
2. Click on the credential dropdown for Business Central or Microsoft 365
3. Select "Edit" and re-authenticate if prompted
4. Save and test the workflow again

### 8.3 Archiving Old Files

To prevent OneDrive from filling up:

1. Create a folder for archive: `/BusinessCentral/Route21Reports/Archive/`
2. Periodically move older export files there
3. Or, configure OneDrive to auto-delete files older than 30 days

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Workflow won't start | Check n8n service is running; verify credentials |
| "Authentication failed" | Re-authenticate credentials; check token expiration |
| No data in Excel | Verify Business Central has data with Shipping Agent Code = "RT 21" |
| Excel file not in OneDrive | Check OneDrive path configuration; verify Microsoft 365 credentials |
| Workflow runs but hangs | Check Business Central API response times; may need timeout adjustment |
| Email not sent on error | Verify error notification node has valid email address; check SMTP settings |

---

## Getting Help

For detailed troubleshooting, see the CLAUDE.md file's "Troubleshooting" section.

For n8n-specific help:
- n8n Documentation: https://docs.n8n.io
- n8n Community: https://community.n8n.io
- n8n Slack: https://n8n.io/slack
