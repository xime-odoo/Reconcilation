# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_bank_reconciled = fields.Boolean("Is Bank Reconciled", default=False)

    def mark_as_bank_reconciled(self):
        for line in self:
            line.write({'is_bank_reconciled': True, 'reconciled': True})

    def unmark_as_bank_reconciled(self):
        for line in self:
            line.write({'is_bank_reconciled': False,'reconciled': False})
