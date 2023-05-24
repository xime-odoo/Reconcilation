# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ReconcileHistory(models.Model):
    _name = 'reconcile.history'
    _rec_name = 'journal_id'


    date = fields.Date()
    journal_id = fields.Many2one('account.journal')
    cleared_deposit = fields.Float("Cleared Deposit")
    cleared_payment = fields.Float("Cleared Payment")
    open_recon_balance = fields.Float("Opening Reconcilied Balance")
    current_recon_balance = fields.Float("Current Reconcilied Balance")
    recon_stmt_balance = fields.Float("Reconcilied Statement Balance")
    uncleared_deposit = fields.Float("Uncleared Deposit")
    uncleared_payment = fields.Float("Uncleared Payment")
    balance = fields.Float("Balance")
