# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class QuickReconcile(models.Model):
    _name = 'quick.reconcile'
    _order = "date desc, name desc, id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'journal_id'

    @api.depends('bank_statment_balance', 'reconcile_ending_balance')
    def _compute_amount_to_reconcile(self):
        for stmt in self:
            stmt.amount_to_reconcile = stmt.bank_statment_balance - stmt.reconcile_ending_balance

    @api.depends('line_ids', 'manual_line_ids')
    def _compute_computed_ending_balance(self):
        for stmt in self:
            sequence = 0
            balance = 0
            for line in stmt.line_ids:
                if line.sequence > sequence:
                    balance = line.statement_balance
                    sequence = line.sequence
            stmt.computed_ending_balance = balance + sum(
                stmt.manual_line_ids.filtered(
                    lambda x: x.transaction_type in ['ar', 'br']).mapped(
                    'amount')) - sum(stmt.manual_line_ids.filtered(
                lambda x: x.transaction_type in ['ap', 'bp', 'conrta']).mapped(
                'amount'))

    def _get_moves_count(self):
        for transaction in self:
            transaction.move_count = len(
                self.line_ids.filtered(lambda x: x.is_marked == True).mapped(
                    'counterpart_aml_id.move_id')) + len(
                self.manual_line_ids.mapped('move_id'))

    @api.onchange('journal_id', 'date')
    def _onchange_journal_id(self):
        if self.journal_id and self.date:
            # if self.date < self.date_start:
            #     raise ValidationError(_("To date is less than From Date"))
            self.line_ids = [(5,)]
            values = {}
            domain = [
                # ('account_internal_type', 'in', ('receivable', 'payable')),
                # ('reconciled', '=', False),
                ('parent_state', '=', 'posted'),
                '|',
                ('account_id', '=', self.journal_id.default_account_id.id),
                ('journal_id', '=', self.journal_id.id),
                ('date', '<=', self.date),
                # ('reconciled', '!=', True),
                # ('is_bank_reconciled', '!=', True)
            ]
            move_lines = self.env['account.move.line'].search(domain,
                                                              limit=200)
            print(move_lines)
            vals_list = []
            sequence = 1
            for line in move_lines:
                values = {}
                values['sequence'] = sequence
                values['payment_ref'] = line.name
                values['date'] = line.date
                values['counterpart_aml_id'] = line.id
                values['partner_id'] = line.partner_id
                values['receipt'] = line.debit
                values['payment'] = line.credit
                values['line_id'] = line.id
                values['is_reconciled'] = line.reconciled
                values['payment_id'] = line.payment_id.id
                vals_list.append((0, 0, values))
                sequence += 1
            self.line_ids = vals_list

    @api.depends('line_ids', 'manual_line_ids')
    def _compute_reconcile_ending_balance(self):
        for stmt in self:
            sequence = 0
            balance = 0
            for line in stmt.line_ids:
                if line.is_marked == True and line.sequence > sequence:
                    balance = line.statement_balance
                    sequence = line.sequence
            reconcile_ending_balance = balance + sum(
                stmt.manual_line_ids.filtered(
                    lambda x: x.transaction_type in ['ar', 'br']).mapped(
                    'amount')) - sum(stmt.manual_line_ids.filtered(
                lambda x: x.transaction_type in ['ap', 'bp', 'conrta']).mapped(
                'amount'))
            if reconcile_ending_balance:
                stmt.reconcile_ending_balance = reconcile_ending_balance
            else:
                stmt.reconcile_ending_balance = stmt.balance_start

    @api.depends('date', 'journal_id')
    def _get_previous_statement(self):
        for st in self:
            domain = [('date', '<', st.date),
                      ('journal_id', '=', st.journal_id.id),
                      ('state', '=', 'validated')]
            # The reason why we have to perform this test is because we have two use case here:
            # First one is in case we are creating a new record, in that case that new record does
            # not have any id yet. However if we are updating an existing record, the domain date <= st.date
            # will find the record itself, so we have to add a condition in the search to ignore self.id

            previous_reconcile = self.env['quick.reconcile'].search(domain,
                                                                    limit=1,
                                                                    order='date desc, id desc')
            st.previous_reconcile_id = previous_reconcile.id

    @api.depends('previous_reconcile_id',
                 'previous_reconcile_id.bank_statment_balance')
    def _compute_starting_balance(self):
        for statement in self:
            if statement.previous_reconcile_id.bank_statment_balance != statement.balance_start:
                statement.balance_start = statement.previous_reconcile_id.bank_statment_balance
            else:
                # Need default value
                statement.balance_start = statement.balance_start or 0.0

    @api.depends('journal_id')
    def _compute_currency(self):
        for statement in self:
            statement.currency_id = statement.journal_id.currency_id or statement.company_id.currency_id

    @api.constrains('journal_id', 'state')
    def _check_multiple_entry(self):
        if self.env['quick.reconcile'].search(
                [('journal_id', '=', self.journal_id.id),
                 ('state', '=', 'draft'), ('id', '!=', self.id)]):
            raise ValidationError(
                'Please validate the previous entry for the same bank..!')

    @api.constrains('journal_id', 'state', 'date')
    def _check_same_date_entry(self):
        if self.env['quick.reconcile'].search(
                [('journal_id', '=', self.journal_id.id),
                 ('date', '=', self.date), ('id', '!=', self.id),
                 ('state', '!=', 'cancel')]):
            raise ValidationError(
                'Multiple records for the same date is not allowed !..!')

    name = fields.Char()
    journal_id = fields.Many2one('account.journal', "Bank",
                                 domain=[('type', '=', ['bank', 'cash'])],

                                 states={'validated': [('readonly', True)],
                                         'cancel': [('readonly', True)]},
                                 required=True)
    # date = fields.Date(required=True,
    #                    states={'validated': [('readonly', True)],
    #                            'cancel': [('readonly', True)]}, index=True,
    #                    copy=False, default=fields.Date.context_today)
    date = fields.Date(required=True, string="Date")
    # date_start = fields.Date(required=True, string="Date")
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True,
                                 default=lambda self: self.env.company)
    balance_start = fields.Monetary(string='Starting Balance',
                                    states={'validated': [('readonly', True)],
                                            'cancel': [('readonly', True)]},
                                    compute='_compute_starting_balance',
                                    readonly=False, store=True, tracking=True)

    currency_id = fields.Many2one('res.currency', compute='_compute_currency',
                                  string="Currency")

    balance_end = fields.Float()
    reconcile_ending_balance = fields.Float(
        compute="_compute_reconcile_ending_balance")

    bank_statment_balance = fields.Float('Bank Statement Balance', states={
        'validated': [('readonly', True)], 'cancel': [('readonly', True)]})
    computed_ending_balance = fields.Float(
        compute="_compute_computed_ending_balance")
    amount_to_reconcile = fields.Float(compute="_compute_amount_to_reconcile")
    previous_reconcile_id = fields.Many2one('quick.reconcile',
                                            help='technical field to compute starting balance correctly',
                                            compute='_get_previous_statement',
                                            store=True)

    state = fields.Selection(selection=[
        ('draft', 'New'),
        ('validated', 'Validated'),
        ('cancel', 'Cancelled')], default='draft',
        string="Reconcilation Status", readonly=True, tracking=True)
    # line_ids = fields.One2many('quick.reconcile.line', 'reconcile_id',
    #                            states={'validated': [('readonly', True)],
    #                                    'cancel': [('readonly', True)]})
    line_ids = fields.One2many('quick.reconcile.line', 'reconcile_id')
    # manual_line_ids = fields.One2many('manual.operation.line', 'reconcile_id',
    #                                   states={
    #                                       'validated': [('readonly', True)],
    #                                       'cancel': [('readonly', True)]})
    manual_line_ids = fields.One2many('manual.operation.line', 'reconcile_id')
    move_count = fields.Integer(string='Move Count'
                                , readonly=True)

    def excel_download(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/quick/reconcile/excel/report/%s' % (self.id),
            'target': 'new',
        }

    def get_report_lines(self):
        vals = {
            'bank': self.journal_id.name,
            'todate': self.date,
            'balance_start': self.balance_start,
            'bank_statment_balance': self.bank_statment_balance,
            'balance_end': self.balance_end,
            'reconcile_ending_balance': self.reconcile_ending_balance
        }
        line_vals = self.env['quick.reconcile.line'].search_read(
            [('reconcile_id', '=', self.id),
             ('is_marked', '=', False),
             ('is_reconciled', '=', False)])
        vals['line_ids'] = line_vals
        return vals

    # compute = '_get_moves_count'
    # TODO add all doamin to get all bank transfers

    def action_validate(self):
        for line in self.line_ids:
            if line.is_marked and not line.counterpart_aml_id.reconciled:
                if line.counterpart_aml_id.payment_id.payment_type == 'inbound':
                    line_ids_list = []
                    payment_id = line.counterpart_aml_id.payment_id
                    vals = {
                        'journal_id': payment_id.journal_id.id,
                        'currency_id': payment_id.currency_id.id,
                        'date': payment_id.date,
                        'partner_id': payment_id.partner_id.id,
                        'move_type': 'entry'
                    }
                    line_ids_list.append((0, 0, {
                        'account_id': payment_id.journal_id.default_account_id.id,
                        'partner_id': payment_id.partner_id.id,
                        'name': payment_id.name,
                        'debit': payment_id.amount,
                        'credit': 0.0,
                        'currency_id': payment_id.currency_id.id}))
                    line_ids_list.append((0, 0, {
                        'account_id': line.counterpart_aml_id.account_id.id,
                        'partner_id': payment_id.partner_id.id,
                        'name': payment_id.name,
                        'debit': 0.0,
                        'credit': payment_id.amount,
                        'currency_id': payment_id.currency_id.id}))
                    vals['line_ids'] = line_ids_list
                    self.create_move_and_reconcile(vals,
                                                   line.counterpart_aml_id)
                    self.write({'state': 'validated'})
                if line.counterpart_aml_id.payment_id.payment_type == 'outbound':
                    payment_id = line.counterpart_aml_id.payment_id
                    currency_id = line.counterpart_aml_id.currency_id
                    vals = {
                        'journal_id': payment_id.journal_id.id,
                        'currency_id': payment_id.currency_id.id,
                        'date': payment_id.date,
                        'partner_id': payment_id.partner_id.id,
                        'move_type': 'entry'
                    }
                    line_ids_list = self.prepare_line_vals(line, payment_id,
                                                           currency_id)
                    vals['line_ids'] = line_ids_list
                    self.create_move_and_reconcile(vals,
                                                   line.counterpart_aml_id)
                    self.write({'state': 'validated'})
                # self.create_history()
        self._get_moves_count()

    def create_move_and_reconcile(self, vals, counterpart_aml_id):
        """create journal entry and reconcile lines"""
        move = self.env['account.move'].create(vals)
        move.action_post()
        if counterpart_aml_id.payment_id.payment_type == "inbound":
            line_1 = move.line_ids.filtered(lambda
                                                line: line.credit == counterpart_aml_id.payment_id.amount)
        elif counterpart_aml_id.payment_id.payment_type == "outbound":
            line_1 = move.line_ids.filtered(lambda
                                                line: line.debit == counterpart_aml_id.payment_id.amount)
        line_2 = counterpart_aml_id
        res = (line_1 + line_2).reconcile()
        move.line_ids.filtered(lambda
                                   t: t.account_id.id == self.journal_id.default_account_id.id).mark_as_bank_reconciled()

    def prepare_line_vals(self, line, payment_id, currency_id):
        """prepare invoice line for outbound payment type"""
        line_ids_list = []
        company_id = line.counterpart_aml_id.company_id
        if line.counterpart_aml_id.currency_id == line.counterpart_aml_id.company_id.currency_id:
            balance = payment_id.amount

        else:
            amount_currency = payment_id.amount
            balance = currency_id._convert(amount_currency,
                                           company_id.currency_id,
                                           company_id,
                                           fields.Date.today())
            # debit = balance > 0.0 and balance or 0.0
            # credit = balance < 0.0 and -balance or 0.0
        line_ids_list.append((0, 0, {
            'account_id': payment_id.journal_id.default_account_id.id,
            'partner_id': payment_id.partner_id.id,
            'name': payment_id.name,
            'amount_currency': -(payment_id.amount),
            'credit': balance,
            'debit': 0.0,
            'currency_id': payment_id.currency_id.id}))
        line_ids_list.append((0, 0, {
            'account_id': line.counterpart_aml_id.account_id.id,
            'partner_id': payment_id.partner_id.id,
            'name': payment_id.name,
            'amount_currency': -(payment_id.amount),
            'credit': 0.0,
            'debit': balance,
            'currency_id': payment_id.currency_id.id}))
        return line_ids_list

    # line.counterpart_aml_id.mark_as_bank_reconciled()

    # moves = self.line_ids.filtered(lambda x: x.is_marked == True).mapped('counterpart_aml_id.move_id')
    # manual = self.manual_line_ids.mapped('move_id')
    # if moves:
    #     for moves in moves:
    #         if moves.statement_id.state != 'posted':
    #             moves.statement_id.button_post()
    #         moves.statement_id.action_reconcile()
    # if manual:
    #     print('manual')

    # for manual_line in self.manual_line_ids:
    #     manual_move = manual_line.create_journal_entry(self.journal_id, self.company_id)
    #     manual_move.line_ids.filtered(lambda t: t.account_id.id == self.journal_id.default_account_id.id).mark_as_bank_reconciled()
    # self.create_history()
    # self.write({'state': 'validated'})

    def create_history(self):
        History = self.env['reconcile.history']
        cleared_deposit = sum(
            self.line_ids.filtered(lambda x: x.is_marked == True).mapped(
                'receipt'))
        cleared_payment = sum(
            self.line_ids.filtered(lambda x: x.is_marked == True).mapped(
                'payment'))
        uncleared_deposit = sum(
            self.line_ids.filtered(lambda x: x.is_marked != True).mapped(
                'receipt'))
        uncleared_payment = sum(
            self.line_ids.filtered(lambda x: x.is_marked != True).mapped(
                'payment'))
        History.create({
            'date': self.date,
            'journal_id': self.journal_id.id,
            'cleared_deposit': cleared_deposit,
            'cleared_payment': cleared_payment,
            'open_recon_balance': self.balance_start,
            'current_recon_balance': self.balance_start + cleared_deposit - cleared_payment,
            'recon_stmt_balance': self.computed_ending_balance,
            'uncleared_deposit': uncleared_deposit,
            'uncleared_payment': uncleared_payment,
            'balance': self.computed_ending_balance + uncleared_payment - uncleared_payment
        })

    def unlink(self):
        for record in self:
            if record.state == 'validated':
                raise ValidationError(
                    _('Cannot delete records which are in Validated state'))

        super(QuickReconcile, self).unlink()

    def action_view_journal_entry(self):
        moves = self.line_ids.filtered(lambda x: x.is_marked == True).mapped(
            'counterpart_aml_id.move_id') | self.manual_line_ids.mapped(
            'move_id')
        action = self.env["ir.actions.actions"]._for_xml_id(
            "zb_sbl_bank_reconciliation.action_move_journal_line_reconcile")
        if len(moves) > 1:
            action['domain'] = [('id', 'in', moves.ids)]
        elif len(moves) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in
                                               action['views'] if
                                               view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = moves.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def button_cancel(self):
        print("sfsdfd")
        for line in self.line_ids:
            if line.is_marked:
                line.counterpart_aml_id.unmark_as_bank_reconciled()
        for manual_line in self.manual_line_ids:
            manual_line.move_id.button_draft()
            manual_line.move_id.button_cancel()
        self.write({'state': 'cancel'})
        self._get_moves_count()

    def select_all(self):
        for line in self.line_ids:
            line.write({'is_marked': True})

    def unselect_all(self):
        for line in self.line_ids:
            line.write({'is_marked': False})


class QuickReconcileLine(models.Model):
    _name = 'quick.reconcile.line'
    _order = "sequence"

    @api.depends('reconcile_id', 'sequence', 'receipt', 'payment')
    def _compute_statement_balance(self):
        for st_line in self:
            st_lines = st_line.reconcile_id.line_ids.filtered(
                lambda x: x.sequence <= st_line.sequence)
            st_line.statement_balance = st_line.reconcile_id.balance_start + sum(
                st_lines.mapped('receipt')) - sum(st_lines.mapped('payment'))

    sequence = fields.Integer(index=True,
                              help="Gives the sequence order when displaying a list of bank statement lines.",
                              default=1)
    date = fields.Date(readonly="1")
    payment_ref = fields.Char(readonly="1")
    partner_id = fields.Many2one('res.partner', readonly="1")
    receipt = fields.Float(readonly="1")
    payment = fields.Float(readonly="1")
    reconcile_id = fields.Many2one('quick.reconcile')
    payment_id = fields.Many2one('account.payment')
    is_reconciled = fields.Boolean()
    parent_state = fields.Selection([
        ('draft', 'New'),
        ('validated', 'Validated'),
        ('cancel', 'Cancelled')], compute="_compute_parent_state")
    is_marked = fields.Boolean(string='check')
    counterpart_aml_id = fields.Many2one('account.move.line')
    statement_balance = fields.Float(compute="_compute_statement_balance",
                                     string="Balance")
    company_id = fields.Many2one(related='reconcile_id.company_id', store=True,
                                 readonly=True,
                                 default=lambda self: self.env.company)
    line_id = fields.Many2one('account.move.line')

    @api.depends('reconcile_id', 'reconcile_id.state', 'parent_state',
                 'is_marked')
    def _compute_parent_state(self):
        for rec in self:
            rec.parent_state = rec.reconcile_id.state if rec.reconcile_id else rec.parent_state == 'draft'

    def action_view_transaction(self):
        return {
            'name': _('Leads'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id),
                       ('journal_id', '=', self.reconcile_id.journal_id.id),
                       '|',
                       ('debit', '=', self.receipt),
                       ('credit', '=', self.receipt)
                       ],
            'context': {'create': False, 'write': False},
        }

    # @api.onchange('is_marked')
    # def _onchange_is_marked(self):
    #     for rec in self:
    #         if rec.is_marked:
    #             rec.is_reconciled = True
    #         else:
    #             rec.is_reconciled = False

    def action_mark(self):
        if not self.is_marked:
            self.is_marked = True

    def action_unmark(self):
        if self.is_marked:
            self.is_marked = False

    # def action_mark(self):
    #     print('x')
    #     for line in self:
    #         last_marked_line = self.env['quick.reconcile.line'].search(
    #             [('reconcile_id', '=', line.reconcile_id.id),
    #              ('id', '!=', line.id), ('is_marked', '=', True)],
    #             order='sequence desc', limit=1)
    #         line.write({'is_marked': True, 'sequence': last_marked_line.sequence + 1})
    #         unmarked_lines = self.env['quick.reconcile.line'].search(
    #             [('reconcile_id', '=', line.reconcile_id.id),
    #              ('is_marked', '!=', True)], order='sequence')
    #         new_sequence = line.sequence + 1
    #         for unmarked_line in unmarked_lines:
    #             unmarked_line.write({'sequence': new_sequence})
    #             new_sequence += 1
    #
    # def action_unmark(self):
    #     for line in self:
    #         old_line_sequence = line.sequence
    #         last_marked_line = self.env['quick.reconcile.line'].search(
    #             [('reconcile_id', '=', line.reconcile_id.id),
    #              ('is_marked', '=', True)], order='sequence desc', limit=1)
    #         line.write(
    #             {'is_marked': False, 'sequence': last_marked_line.sequence})
    #         marked_lines = self.env['quick.reconcile.line'].search(
    #             [('reconcile_id', '=', line.reconcile_id.id),
    #              ('is_marked', '=', True),
    #              ('sequence', '>', old_line_sequence)], order='sequence desc')
    #         for marked_line in marked_lines:
    #             marked_line.write({'sequence': marked_line.sequence - 1})

    # @api.onchange('is_marked')
    # def onchage_is_marked(self):
    #     for line in self:
    #         if not line.is_marked:
    #             old_line_sequence = line.sequence
    #             last_marked_line = self.env['quick.reconcile.line'].search(
    #                 [('reconcile_id', '=', line.reconcile_id._origin.id),
    #                  ('is_marked', '=', True)], order='sequence desc', limit=1)
    #             line.write(
    #                 {'is_marked': False,
    #                  'sequence': last_marked_line.sequence})
    #             marked_lines = self.env['quick.reconcile.line'].search(
    #                 [('reconcile_id', '=', line.reconcile_id._origin.id),
    #                  ('is_marked', '=', True),
    #                  ('sequence', '>', old_line_sequence)],
    #                 order='sequence desc')
    #             for marked_line in marked_lines:
    #                 marked_line.write({'sequence': marked_line.sequence - 1})
    #         else:
    #             last_marked_line = self.env['quick.reconcile.line'].search(
    #                 [('reconcile_id', '=', line.reconcile_id._origin.id),
    #                  ('id', '!=', line._origin.id), ('is_marked', '=', True)],
    #                 order='sequence desc', limit=1)
    #             line.write({'is_marked': True,
    #                         'sequence': last_marked_line.sequence + 1})
    #             unmarked_lines = self.env['quick.reconcile.line'].search(
    #                 [('reconcile_id', '=', line.reconcile_id._origin.id),
    #                  ('is_marked', '!=', True)], order='sequence')
    #             new_sequence = line.sequence + 1
    #             for unmarked_line in unmarked_lines:
    #                 unmarked_line.write({'sequence': new_sequence})
    #                 new_sequence += 1


class ManualOperationLine(models.Model):
    _name = 'manual.operation.line'

    @api.onchange('transaction_type', 'company_id')
    def onchange_transaction_type(self):
        domain = [('deprecated', '=', False),
                  ('company_id', '=', self.company_id.id),
                  ('is_off_balance', '=', False)]
        bank_accounts = self.env['account.journal'].search(
            [('type', '=', 'bank')]).mapped('default_account_id').ids
        if self.transaction_type == 'conrta':
            domain += [('id', 'in', bank_accounts)]
        else:
            domain += [('id', 'not in', bank_accounts)]

        res = {'value': {'partner_id': False, 'account_id': False},
               'domain': {'account_id': domain}}
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.transaction_type == 'ap':
            self.account_id = self.partner_id.property_account_payable_id.id
        if self.transaction_type == 'ar':
            self.account_id = self.partner_id.property_account_receivable_id.id

    reconcile_id = fields.Many2one('quick.reconcile')
    date = fields.Date(required=True)
    company_id = fields.Many2one(related='reconcile_id.company_id', store=True,
                                 readonly=True,
                                 default=lambda self: self.env.company)
    account_id = fields.Many2one('account.account', "Account", required=True)
    move_id = fields.Many2one('account.move', "Journal Entry")
    transaction_type = fields.Selection(selection=[
        ('ap', 'AP'),
        ('ar', 'AR'),
        ('bp', 'BP'),
        ('br', 'BR'),
        ('conrta', 'Contra'),
    ], string='Type', required=True, copy=False, tracking=True)
    amount = fields.Float()
    name = fields.Char("Name", required=True)
    partner_id = fields.Many2one('res.partner')
    amount = fields.Float()

    def create_journal_entry(self, journal_id, company_id):
        for record in self:
            currency_id = journal_id.currency_id.id or company_id.currency_id.id or self.env.company.currency_id.id
            vals = {
                'journal_id': journal_id.id,
                'currency_id': currency_id
            }

            line_ids_list = []
            account_debit = 0
            account_credit = 0
            bank_debit = 0
            bank_credit = 0
            if record.transaction_type in ['ap', 'bp', 'conrta']:
                bank_credit = record.amount
                account_debit = record.amount
            if record.transaction_type in ['ar', 'br']:
                bank_debit = record.amount
                account_credit = record.amount
            line_ids_list.append((0, 0, {
                'account_id': journal_id.default_account_id.id,
                'partner_id': record.partner_id.id,
                'name': record.name, 'debit': bank_debit,
                'credit': bank_credit, 'currency_id': currency_id}))
            line_ids_list.append((0, 0, {'account_id': record.account_id.id,
                                         'partner_id': record.partner_id.id,
                                         'name': record.name,
                                         'debit': account_debit,
                                         'credit': account_credit,
                                         'currency_id': currency_id}))
            vals['date'] = record.date
            vals['line_ids'] = line_ids_list
            vals['partner_id'] = record.partner_id.id
            move = self.env['account.move'].create(vals)
            move.action_post()
            record.write({'move_id': move.id})
            return move

# domain = ['|',
#                       # ('parent_state', '=', 'posted'),
#                       # ('account_internal_type', 'in', ('receivable', 'payable')),
#                       # ('reconciled', '=', False),
#                       ('parent_state', '=', 'posted'),
#                       ('account_id', '=', self.journal_id.default_account_id.id),
#                       ('journal_id', '=', self.journal_id.id),
#                       '|', '&',
#                       ('payment_id.payment_type', '=', 'inbound'),
#                       ('debit', '>', 0),
#                       '&',
#                       ('payment_id.payment_type', '=', 'outbound'),
#                       ('credit', '>', 0),
#                       ('date', '>=', self.date_start),
#                       ('date', '<=', self.date),
#                       ('is_bank_reconciled', '!=', True),
#                       ('reconciled', '!=', True)
#                       ]
