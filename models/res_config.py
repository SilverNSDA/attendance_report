# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models,api


class BaseConfigSettings(models.TransientModel):
    _inherit = 'base.config.settings'

    atd_table_period = fields.Selection([('month','Month'),('week','Week'),('day','Day')],string='Attendance Table Period',
        help='Default value for the time ranges in Master Production Schedule Report')

    @api.model
    def get_default_atd_table_period(self, fields):
        return {
            'atd_table_period': self.env['ir.config_parameter'].get_param( 'jy_attendance_table.atd_table_period', 'month')
        }

    @api.multi
    def set_atd_table_period(self):
        self.ensure_one()
        self.env['ir.config_parameter'].set_param('jy_attendance_table.atd_table_period', self.atd_table_period)
