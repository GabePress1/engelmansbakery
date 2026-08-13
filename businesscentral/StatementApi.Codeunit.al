namespace EngelmansBakery.Statements;

using Microsoft.Sales.Customer;
using System.Text;
using System.Utilities;

/// <summary>
/// Renders the customer statement as a PDF and returns it base64 encoded, so the n8n
/// "Emailing Letter + Statement Draft Workflow" can attach it to a draft email.
///
/// Business Central has no way to return a report as a PDF over a plain OData query -
/// $format=PDF is not supported on report web services - so the report has to be rendered
/// in AL and handed back as text. This codeunit is the smallest thing that does that.
///
/// Publish it as a web service named StatementApi (Web Services page, Object Type =
/// Codeunit, Object ID = 50100, Service Name = StatementApi, Published = yes). It is then
/// callable as an OData V4 unbound action:
///
///   POST /v2.0/{tenant}/{environment}/ODataV4/StatementApi_GetCustomerStatementPdf?company={company}
///   { "customerNo": "10981", "requestPageXml": "" }
///
/// The response is { "@odata.context": "...", "value": "<base64 pdf>" }.
/// </summary>
[ServiceEnabled]
codeunit 50100 "Statement Api"
{
    Access = Public;

    /// <summary>
    /// Returns the statement for one customer as a base64 encoded PDF.
    /// </summary>
    /// <param name="customerNo">The customer number, e.g. 10981. Required.</param>
    /// <param name="requestPageXml">
    /// The report's saved request page parameters, which is what controls open-items-only.
    /// Pass an empty string to accept the report's own defaults.
    /// </param>
    [ServiceEnabled]
    procedure GetCustomerStatementPdf(customerNo: Code[20]; requestPageXml: Text): Text
    var
        Customer: Record Customer;
        TempBlob: Codeunit "Temp Blob";
        Base64Convert: Codeunit "Base64 Convert";
        CustomerRecRef: RecordRef;
        StatementOutStream: OutStream;
        StatementInStream: InStream;
    begin
        if customerNo = '' then
            Error(MissingCustomerNoErr);

        Customer.SetRange("No.", customerNo);
        if Customer.IsEmpty() then
            Error(CustomerNotFoundErr, customerNo);

        // Scope the report to this one customer. The statement report's top level dataitem is
        // Customer, so the view on the RecordRef is what limits the PDF to a single account.
        CustomerRecRef.GetTable(Customer);
        CustomerRecRef.SetView(Customer.GetView());

        TempBlob.CreateOutStream(StatementOutStream);
        Report.SaveAs(
            Report::"Standard Statement",
            requestPageXml,
            ReportFormat::Pdf,
            StatementOutStream,
            CustomerRecRef);

        TempBlob.CreateInStream(StatementInStream);
        exit(Base64Convert.ToBase64(StatementInStream));
    end;

    var
        MissingCustomerNoErr: Label 'A customer number is required to render a statement.';
        CustomerNotFoundErr: Label 'No customer found with No. %1.', Comment = '%1 = the customer number that was requested';
}
