from odoo import http
from odoo.http import request
import io
from odoo.tools.misc import xlsxwriter
from odoo.http import content_disposition
from datetime import date


class InvoiceExcelReportController(http.Controller):
    @http.route(
        ['/quick/reconcile/excel/report/<model("quick.reconcile"):report_id>'],
        type='http', auth="user", csrf=False)
    def get_sale_excel_report(self, report_id=None, **args):
        response = request.make_response(None, headers=[
            ('Content-Type',
             'application/vnd.ms-excel'),
            ('Content-Disposition',
             content_disposition(
                 'Reconcile In-completion - ' + str(date.today()) + '.xlsx'))])
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        # get data for the report.

        format0 = workbook.add_format(
            {'font_size': 15, 'align': 'center', 'bold': True,
             'valign': 'vcenter'})
        format1 = workbook.add_format(
            {'font_size': 12, 'align': 'center', 'bold': True,
             'valign': 'vcenter'})
        col_left = workbook.add_format(
            {'bold': True, 'font_size': 10, 'align': 'left'})
        col_right = workbook.add_format(
            {'bold': True, 'font_size': 10, 'align': 'right'})
        row_left = workbook.add_format({'font_size': 10, 'align': 'left'})
        col_center = workbook.add_format(
            {'bold': True, 'font_size': 10, 'align': 'center',
             'valign': 'vcenter'})
        row_right = workbook.add_format({'font_size': 10, 'align': 'right'})
        row_center = workbook.add_format(
            {'font_size': 10, 'align': 'center', 'valign': 'vcenter'})
        col_length = 7
        # TODO
        report_lines = report_id.get_report_lines()
        # prepare excel sheet styles and formats
        sheet = workbook.add_worksheet("reconcile-in-completion")
        row_count = 0
        sheet.merge_range(row_count, 0, row_count + 1, col_length,
                          "Quick Reconcile In-completion Report", format0)
        row_count = row_count + 2

        sheet.merge_range(row_count, 0, row_count + 1, col_length,
                          report_lines.get('bank') + " - " + str(date.today()),
                          format1)
        row_count = row_count + 2
        sheet.write(row_count, 1, "To Date", row_left)
        sheet.write(row_count, 2,report_lines.get('todate').strftime('%d-%m--%Y'), row_left)
        row_count = row_count + 1
        sheet.write(row_count, 1, "Balance Start", row_left)
        sheet.write(row_count, 2,report_lines.get('balance_start'),row_left)
        row_count = row_count + 1
        sheet.write(row_count, 1, "Reconcile Ending Balance", row_left)
        sheet.write(row_count, 2,report_lines.get('reconcile_ending_balance'),row_left)
        row_count = row_count + 1
        sheet.write(row_count, 1, "Bank Statement Balance", row_left)
        sheet.write(row_count, 2,report_lines.get('bank_statment_balance'),row_left)
        row_count = row_count + 1
        sheet.write(row_count, 1, "Balance End", row_left)
        sheet.write(row_count, 2,report_lines.get('balance_end'),row_left)
        row_count = row_count + 1

        row_count += 2
        row_count_col = row_count
        sheet.set_row(row_count, 30)
        sheet.write(row_count, 0, "S/N", col_center)
        sheet.set_column(0, 0, 4)
        sheet.write(row_count, 1, "Date", col_left)
        sheet.set_column(1, 1, 14)
        sheet.write(row_count, 2, "Partner", col_left)
        sheet.set_column(2, 2, 24)
        sheet.write(row_count, 3, "Payment Ref", col_right)
        sheet.set_column(3, 3, 14)
        sheet.write(row_count, 4, "Receipt", col_right)
        sheet.set_column(4, 4, 10)
        sheet.write(row_count, 5, "Payment", col_left)
        sheet.set_column(5, 5, 10)
        sheet.write(row_count, 6, "Statement Balance", col_left)
        sheet.set_column(6, 6, 10)
        sheet.write(row_count, 7, "Is Reconciled", col_left)
        sheet.set_column(7, 7, 10)
        sl_no = 0

        row = 2
        number = 1
        # write the report lines to the excel document
        for line in report_lines.get('line_ids'):
            sl_no += 1
            row_count += 1
            sheet.write(row_count, 0, sl_no, row_center)
            sheet.write(row_count, 1, line.get('date').strftime('%d-%m--%Y'),
                        row_left)
            sheet.write(row_count, 2, line.get('partner_id')[1] if line.get(
                'partner_id') else '', row_left)
            sheet.write(row_count, 3, line.get('payment_ref'), row_right)
            sheet.write(row_count, 4, line.get('receipt'), row_right)
            sheet.write(row_count, 5, line.get('payment'), row_right)
            sheet.write(row_count, 6, line.get('statement_balance'), row_right)
            sheet.write(row_count, 7, str(line.get('is_reconciled')),
                        row_right)
            row += 1
            number += 1
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
        return response
