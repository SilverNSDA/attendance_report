odoo.define('jy_attendance_report.attendance_table_report', function (require) {
'use strict';

var core = require('web.core');
var Widget = require('web.Widget');
var formats = require('web.formats');
var Model = require('web.Model');
var time = require('web.time');
var ControlPanelMixin = require('web.ControlPanelMixin');
var Dialog = require('web.Dialog');
var session = require('web.session');
var framework = require('web.framework');
var crash_manager = require('web.crash_manager');
var SearchView = require('web.SearchView');
var data = require('web.data');
var data_manager = require('web.data_manager');
var pyeval = require('web.pyeval');
var formats = require('web.formats');

var QWeb = core.qweb;
var _t = core._t;

var DATE_FORMAT = "YYYY-M-D";
// var DatePicker = require('web.datepicker');
// window.myWidget = DatePicker;

var LEAVE_STATES = {
    "draft":_t("To Submit"),
    "cancel":_t("Cancel"),
    "confirm":_t("To Approve"),
    "refuse":_t("Refused"),
    "validate1":_t("Second Approval"),
    "validate":_t("Approved"),
}

var attendance_table_report = Widget.extend(ControlPanelMixin, {
    // Stores all the parameters of the action.
    events:{
        // 'change .o_mps_save_input_supply': 'on_change_quantity',
        // 'click .o_mps_generate_procurement': 'mps_generate_procurement',
        // 'mouseout .o_mps_visible_procurement': 'invisible_procurement_button',
        'click .department-name': 'open_department',
        'click .employee-name': 'open_employee',
    },
    init: function(parent, action) {
        console.info('init');

        var self = this;
        this.actionManager = parent;
        this.action = action;
        this.fields_view;
        this.searchview;
        this.domain = [];
        this.filters = {
            date_to : moment().format(DATE_FORMAT),
            date_from : moment().subtract(7, 'days').format(DATE_FORMAT),
        }
        return this._super.apply(this, arguments);
    },
    render_search_view: function(){
        console.info('render_search_view');
        var self = this;
        var defs = [];
        new Model('ir.model.data').call('get_object_reference', ['hr', 'view_employee_filter']).then(function(view_id){
            self.dataset = new data.DataSetSearch(this, 'hr.employee');
            console.log('render_search_view view_id',view_id);
            var def = data_manager
            .load_fields_view(self.dataset, view_id[1], 'search', false)
            .then(function (fields_view) {
                self.fields_view = fields_view;
                var options = {
                    $buttons: $("<div>"),
                    // $filters: $("<div>"),
                    action: this.action,
                    disable_groupby: true,
                };
                self.searchview = new SearchView(self, self.dataset, self.fields_view, options);
                self.searchview.on('search_data', self, self.on_search);
                self.searchview.appendTo($("<div>")).then(function () {
                    defs.push(self.update_cp());
                    self.$searchview_buttons = self.searchview.$buttons.contents();
                });
            });
        });
    },
    // Fetches the html and is previous report.context if any, else create it
    get_html: function() {
        console.info('get_html');
        var self = this;
        var defs = [];
        return new Model('attendance.table.report').call('get_html',
            [this.domain],
            {context: session.user_context, filters: this.filters})
        .then(function (result) {
            console.log('get_html Result',result);
            self.html = result.html;
            self.report_context = result.report_context;
            // self.render_buttons();
            // self.render_filters();
        });
    },
    willStart: function() {
        console.info('willStart');
        
        return this.get_html();
    },
    start: function() {
        console.info('start');

        var self = this;
        this.period;
        this.render_search_view();
        return this._super.apply(this, arguments).then(function () {
            // console.log('start super apply',self.html);
            self.$el.html(self.html).promise().done(function(){
                console.log('-- html is populated DONE');
                self.post_render();
            });
        });
    },
    post_render: function(){
        console.log('Post_render');
        var self = this;
        self._render_filters();
        self._render_popover();
        self._render_hover();
        self._bind_cell_events();
    },
    _render_filters: function(){
        var self = this;
        console.log('render_filters');
        self.$('.report-filters .date-filter').datetimepicker({
            'pickTime':false,
            'useSeconds':false,
        });
        self.$('.report-filters .date-filter').bind('change', function (event) {
            // console.log('Date range changed',$(this).attr('name'),$(this).val());
            self.filters[$(this).attr('name')] = moment($(this).val()).format(DATE_FORMAT);
            self.get_html().then(function() {
                self.update_cp();
                self.re_renderElement();
            });
        });
    },
    _render_popover: function(){
        console.info('_render_popover');
        var self = this;
        self.$('.atd-leave[data-toggle="popover"]').each(function () {
            // console.log('--- data toggle item',this);
            // $(this).popover();
            $(this).popover({
                html: true,
                title: function () {
                    var $title = $(QWeb.render('attendance_table_leave_popover_title', {
                        doc: {
                            id: $(this).data('id'),
                            title: $(this).data('name'),
                        },
                    }));
                    $title.on('click',
                        '.o_title_redirect', _.bind(self._onLeaveRedirect, self));
                    return $title;
                },
                container: 'body',
                placement: 'left',
                trigger: 'focus',
                content: function () {
                    var $content = $(QWeb.render('attendance_table_leave_popover_content', {
                        doc:{
                            id: $(this).data('id'),
                            name: $(this).data('display-name'),
                            state: LEAVE_STATES[$(this).data('state')] || $(this).data('state'),
                            date_from: $(this).data('date-from'),
                            date_to: $(this).data('date-to'),
                            duration: parseFloat($(this).data('duration')),
                            leave_type: $(this).data('leave-type'),
                            // direct_sub_count: parseInt($(this).data('emp-dir-subs')),
                        },
                    }));
                    // $content.on('click',
                    //     '.o_employee_sub_redirect', _.bind(self._onEmployeeSubRedirect, self));
                    return $content;
                },
                // template: $(QWeb.render('hr_orgchart_emp_popover', {})),
            });
        });

        self.$('.atd-holidays[data-toggle="popover"]').each(function(){
            $(this).popover({
                html: true,
                title: function () {
                    var $title = $(QWeb.render('attendance_table_holidays_popover_title', {
                        doc: {
                            title: $(this).data('title'),
                            id: $(this).data('id'),
                        },
                    }));
                    $title.on('click',
                        '.o_title_redirect', _.bind(self._onHolidaysRedirect, self));
                    return $title;
                },
                container: 'body',
                placement: 'left',
                trigger: 'focus',
                content: function () {
                    var $content = $(QWeb.render('attendance_table_holidays_popover_content', {
                        doc:{
                            description: $(this).data('description'),
                        },
                    }));
                    // $content.on('click',
                    //     '.o_employee_sub_redirect', _.bind(self._onEmployeeSubRedirect, self));
                    return $content;
                },
                // template: $(QWeb.render('hr_orgchart_emp_popover', {})),
            });
        });
    },
    _render_hover: function(){
        var self = this;
        self.$('.date-cell').each(function(){
            // Hover effects
            var cell = $(this);
            var eid = cell.data('eid');
            var date = cell.data('date');
            cell.hover(function(){
                // console.log('hover in',date);
                self.$('.date-cell.date-'+date).addClass('hovering');
                self.$('#attendance-table-heading .employee-row.employee-'+eid).addClass('hovering');
            },function(){
                // console.log('hover out');
                self.$('.date-cell.date-'+date).removeClass('hovering');
                self.$('#attendance-table-heading .employee-row.employee-'+eid).removeClass('hovering');
            });
        });
    },
    _bind_cell_events: function(){
        var self = this;

        self.$('.new-leave-request').on('click',function(e){
            e.preventDefault();
            var cell = $(this);
            var eid = parseInt(cell.parent().data('eid'));
            var cell_date = cell.parent().data('date');
            new Model('attendance.table.report').call('get_new_leave_request_params',[],
                {context: session.user_context, eid: eid, date_start:cell_date })
            .then(function (res) {
                return self.do_action({
                    type: 'ir.actions.act_window',
                    view_type: 'form',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'current',
                    res_model: 'hr.holidays',
                    context:{
                        'default_employee_id': eid,
                        'default_date_from': res['date_from'],
                        'default_date_to': res['date_to'],
                        // 'default_date_from': cell.data('date') + " " + self.report_context.new_leave.min_time,
                        // 'default_date_to': cell.data('date') + " " + self.report_context.new_leave.max_time,
                    }
                    // res_id: parseInt($(event.currentTarget).data('id')),
                });
            });
            
        });


        self.$('.atd-worked-hours').on('click',function(){
            var cell = $(this);
            // console.log('Gonna view worked_hours',eid,cell_date);
            return self.do_action({
                // name: _.str.sprintf(_t("Attendances of %s"), employee_name),
                name: _t("Attendances"),
                type: 'ir.actions.act_window',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
                res_model: 'hr.attendance',
                domain: [['employee_id','=',parseInt(cell.parent().data('eid'))],['check_in_date','=',cell.parent().data('date')],['worked1_hours','>',0]],
            });
        });

        
        self.$('.atd-ot-worked-hours').on('click',function(){
            var cell = $(this);
            // console.log('Gonna view worked_hours',eid,cell_date);
            return self.do_action({
                // name: _.str.sprintf(_t("Attendances of %s"), employee_name),
                name: _t("OT Attendances"),
                type: 'ir.actions.act_window',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
                res_model: 'hr.attendance',
                domain: [['employee_id','=',parseInt(cell.parent().data('eid'))],['check_in_date','=',cell.parent().data('date')],['worked2_hours','>',0]],
            });
        });



    },
    _onLeaveRedirect: function (event) {
        event.preventDefault();
        return this.do_action({
            type: 'ir.actions.act_window',
            view_type: 'form',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'current',
            res_model: 'hr.holidays',
            res_id: parseInt($(event.currentTarget).data('id')),
        });
    },
    _onHolidaysRedirect: function (event) {
        event.preventDefault();
        return this.do_action({
            type: 'ir.actions.act_window',
            view_type: 'form',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'current',
            res_model: 'hr.holidays.public',
            res_id: parseInt($(event.currentTarget).data('id')),
        });
    },
    // on_change_quantity: function(e) {
    //     var self = this;
    //     var $input = $(e.target);
    //     var target_value = formats.parse_value($input.val().replace(String.fromCharCode(8209), '-'), {type: 'float'}, false);
    //     if(isNaN(target_value) && target_value !== false) {
    //         this.do_warn(_t("Wrong value entered!"), _t("Only Integer Value should be valid."));
    //     } else {
    //         return new Model('sale.forecast').call('save_forecast_data', [
    //              parseInt($input.data('product')), target_value, $input.data('date'), $input.data('date_to'), $input.data('name')],
    //              {context: session.user_context})
    //             .then(function() {
    //                 self.get_html().then(function() {
    //                     self.re_renderElement();
    //                 });
    //         });
    //     }
    // },
    // visible_procurement_button: function(e){
    //     clearTimeout(this.hover_element);
    //     $(e.target).find('.o_mps_generate_procurement').removeClass('o_form_invisible');
    // },
    // invisible_procurement_button: function(e){
    //     clearTimeout(this.hover_element);
    //     this.hover_element = setTimeout(function() {
    //         $(e.target).find('.o_mps_generate_procurement').addClass('o_form_invisible');
    //     }, 100);
    // },
    // mps_generate_procurement: function(e){
    //     var self = this;
    //     var target = $(e.target);
    //     return new Model('sale.forecast').call('generate_procurement',
    //             [parseInt(target.data('product')), 1],
    //             {context: session.user_context})
    //     .then(function(result){
    //         if (result){
    //             self.get_html().then(function() {
    //                 self.re_renderElement();
    //             });
    //         }
    //     });
    // },
    // mps_change_auto_mode: function(e){
    //     var self = this;
    //     var target = $(e.target);
    //     return new Model('sale.forecast').call('change_forecast_mode',
    //         [parseInt(target.data('product')), target.data('date'), target.data('date_to'), parseInt(target.data('value'))],
    //         {context: session.user_context})
    //     .then(function(result){
    //         self.get_html().then(function() {
    //             self.re_renderElement();
    //         });
    //     });
    // },
    options_filter_lines: function(e){
        self.$('.employee-row').hide();
        self.$('.o_atd_table_report_show_line:checked').each(function(i,e){
            self.$('.employee-row.'+$(e).data('value')).show();
        });
    },
    re_renderElement: function() {
        console.info('re_renderElement');
        var self = this;
        this.$el.html(this.html).promise().done(function(){
            // console.log('-- html is populated DONE');
            self.post_render();
        });

    },
    // option_mps_period: function(e){
    //     var self = this;
    //     this.period = $(e.target).parent().data('value');
    //     console.log('Period',this.period);
    //     var model = new Model('mrp.mps.report');
    //     return model.call('search', [[]]).then(function(res){
    //             return model.call('write',
    //                 [res, {'period': self.period}],
    //                 {context: session.user_context})
    //             .done(function(result){
    //             self.get_html().then(function() {
    //                 self.update_cp();
    //                 self.re_renderElement();
    //             });
    //         });
    //     });
    // },
    // add_product_wizard: function(e){
    //     var self = this;
    //     return new Model('ir.model.data').call('get_object_reference', ['mrp_mps', 'attendance_table_report_view_form']).then(function(data){
    //         return self.do_action({
    //             name: _t('Add a Product'),
    //             type: 'ir.actions.act_window',
    //             res_model: 'mrp.mps.report',
    //             views: [[data[1] || false, 'form']],
    //             target: 'new',
    //         })
    //     });
    // },
    open_department: function(e){
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: "hr.department",
            res_id: parseInt($(e.target).data('id')),
            views: [[false, 'form']],
        });
    },
    open_employee: function(e){
        console.log('Employee id',$(e.target).data('id'));
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: "hr.employee",
            res_id: parseInt($(e.target).data('id')),
            views: [[false, 'form']],
        });
    },
    // mps_open_forecast_wizard: function(e){
    //     var self = this;
    //     var product = $(e.target).data('product') || $(e.target).parent().data('product');
    //     return new Model('ir.model.data').call('get_object_reference', ['mrp_mps', 'product_product_view_form_mps']).then(function(data){
    //         return self.do_action({
    //             name: _t('Forecast Product'),
    //             type: 'ir.actions.act_window',
    //             res_model: 'product.product',
    //             views: [[data[1] || false, 'form']],
    //             target: 'new',
    //             res_id: product,
    //         });
    //     });
    // },
    // mps_forecast_save: function(e){
    //     var self = this;
    //     var $input = $(e.target);
    //     var target_value = formats.parse_value($input.val().replace(String.fromCharCode(8209), '-'), {type: 'float'}, false);
    //     if(isNaN(target_value) && target_value !== false) {
    //         this.do_warn(_t("Wrong value entered!"), _t("Only Integer or Float Value should be valid."));
    //     } else {
    //         return new Model('sale.forecast').call('save_forecast_data', [
    //                 parseInt($input.data('product')), target_value, $input.data('date'), $input.data('date_to'), $input.data('name')],
    //                 {context: session.user_context})
    //             .done(function(res){
    //                 self.get_html().then(function() {
    //                     self.re_renderElement();
    //                 });
    //             })
    //     }
    // },
    on_search: function (domains) {
        console.info('on_search');

        var self = this;
        var result = pyeval.sync_eval_domains_and_contexts({
            domains: domains
        });
        this.domain = result.domain;
        this.get_html().then(function() {
            self.re_renderElement();
        });
    },
    // mps_apply: function(e){
    //     var self = this;
    //     var product = parseInt($(e.target).data('product'));
    //     return new Model('mrp.mps.report').call('update_indirect',
    //             [product],
    //             {context: session.user_context})
    //     .then(function(result){
    //         self.get_html().then(function() {
    //             self.re_renderElement();
    //         });
    //     });
    // },

    // Updates the control panel and render the elements that have yet to be rendered
    update_cp: function() {
        console.info('update_cp');
        
        var self = this;
        // if (!this.$buttons) {
        //     this.render_buttons();
        // }
        // if (!this.$filters) {
        //     this.render_filters();
        // }
        this.$searchview_buttons = $(QWeb.render("AttendanceReport.optionButton", {period: self.report_context.period}))
        // this.$searchview_buttons.siblings('.o_mps_period_filter');
        // this.$searchview_buttons.find('.o_mps_option_mps_period').bind('click', function (event) {
        //     self.option_mps_period(event);
        // });
        this.$searchview_buttons.siblings('.o_atd_table_columns_filter');
        this.$searchview_buttons.find('.o_atd_table_option_columns').bind('click', function (event) {
            self.options_filter_lines(event);
        });
        this.update_control_panel({
            breadcrumbs: this.actionManager.get_breadcrumbs(),
            cp_content: {
                $buttons: this.$buttons,
                // $filters: this.$filters,
                $searchview: this.searchview.$el,
                // $searchview_buttons: this.$searchview_buttons,
                $searchview_buttons: this.$searchview_buttons
            },
            searchview: this.searchview,
        });
    },
    do_show: function() {
        console.info('do_show');
        this._super();
        this.update_cp();
    },
    // render_filters: function(){
    //     console.log('render_filters');
    //     var self = this;
    //     this.$filters = $(QWeb.render("AttendanceReport.filters", {}));
    //     return this.$filters;
    // },
    // render_buttons: function() {
    //     console.info('render_buttons');
    //     var self = this;
    //     this.$buttons = $(QWeb.render("AttendanceReport.filters", {}));
    //     this.$buttons.on('click', function(){
    //         new Model('sale.forecast').call('generate_procurement_all',
    //             [],
    //             {context: session.user_context})
    //         .then(function(result){
    //             self.get_html().then(function() {
    //                 self.re_renderElement();
    //             });
    //         });
    //     });
    //     return this.$buttons;
    // },
});

core.action_registry.add("attendance_table_report", attendance_table_report);
return attendance_table_report;
});
