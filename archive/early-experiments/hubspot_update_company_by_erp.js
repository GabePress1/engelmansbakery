/**
 * Updates a HubSpot company record looked up by ERP Account Number.
 *
 * Step 1 — Search: finds the company whose custom property
 *   `erp_account_number` matches the given value.
 * Step 2 — Update: patches the company with the supplied properties.
 *
 * Usage (n8n Code node, or plain Node.js with HUBSPOT_API_KEY set):
 *
 *   const result = await updateCompanyByErpAccount("ERP-001234", {
 *     name: "Engelman's Bakery",
 *     city: "Chicago",
 *   });
 */

const HUBSPOT_API_BASE = "https://api.hubapi.com";

async function searchCompanyByErpAccount(erpAccountNumber, apiKey) {
  const response = await fetch(`${HUBSPOT_API_BASE}/crm/v3/objects/companies/search`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      filterGroups: [
        {
          filters: [
            {
              propertyName: "erp_account_number",
              operator: "EQ",
              value: erpAccountNumber,
            },
          ],
        },
      ],
      properties: ["erp_account_number", "name", "domain"],
      limit: 1,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`HubSpot search failed (${response.status}): ${err}`);
  }

  const data = await response.json();
  if (!data.results || data.results.length === 0) {
    throw new Error(`No company found with ERP Account Number: ${erpAccountNumber}`);
  }

  return data.results[0];
}

async function updateCompany(companyId, properties, apiKey) {
  const response = await fetch(`${HUBSPOT_API_BASE}/crm/v3/objects/companies/${companyId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ properties }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`HubSpot update failed (${response.status}): ${err}`);
  }

  return response.json();
}

async function updateCompanyByErpAccount(erpAccountNumber, propertiesToUpdate, apiKey) {
  apiKey = apiKey ?? process.env.HUBSPOT_API_KEY;

  const company = await searchCompanyByErpAccount(erpAccountNumber, apiKey);
  const companyId = company.id;

  const updated = await updateCompany(companyId, propertiesToUpdate, apiKey);
  return { companyId, updated };
}

module.exports = { updateCompanyByErpAccount };
