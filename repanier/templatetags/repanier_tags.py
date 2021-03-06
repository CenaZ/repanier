# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import EMPTY_STRING, PERMANENCE_CLOSED, DECIMAL_ZERO, PERMANENCE_OPENED
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import sint, display_selected_value, display_selected_box_value

register = template.Library()


@register.simple_tag(takes_context=False)
def repanier_home(*args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_HOME_SITE
    return REPANIER_SETTINGS_HOME_SITE


@register.simple_tag(takes_context=False)
def repanier_group_name(*args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_GROUP_NAME
    return REPANIER_SETTINGS_GROUP_NAME


@register.simple_tag(takes_context=True)
def repanier_user(context, *args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_INVOICE, REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO

    request = context["request"]
    user = request.user
    if user.is_authenticated:
        nodes = ["""
            <li id="li_my_name" class="dropdown">
            <a href="#" class="dropdown-toggle" data-toggle="dropdown"><span class="glyphicon glyphicon-user" aria-hidden="true"></span> %s %s<b class="caret"></b></a>
            <ul class="dropdown-menu">
            """ % (
            _('Welkom'),
            user.username or '<span id = "my_name"></ span>'
        )]
        customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
        if customer_is_active:

            nodes.append('<li><a href="%s">%s</a></li>' % (
                reverse('send_mail_to_coordinators_view'),
                _('Send mail to coordinators')
            ))
            if REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
                nodes.append('<li><a href="%s">%s</a></li>' % (
                    reverse('send_mail_to_all_members_view'),
                    _('Send mail to all members')
                ))
                nodes.append('<li><a href="%s">%s</a></li>' % (
                    reverse('who_is_who_view'),
                    _('Who is who')
                ))
            nodes.append('<li><a href="%s">%s</a></li>' % (
                reverse('my_profile_view'),
                _('My profile')
            ))
            if REPANIER_SETTINGS_INVOICE:
                last_customer_invoice = CustomerInvoice.objects.filter(
                    customer__user_id=request.user.id,
                    invoice_sort_order__isnull=False) \
                    .only("balance", "date_balance") \
                    .order_by('-invoice_sort_order').first()
                if last_customer_invoice is not None:
                    if last_customer_invoice.balance < DECIMAL_ZERO:
                        my_balance = _('My balance : <font color="red">%(balance)s</font> at %(date)s') % {
                            'balance': last_customer_invoice.balance,
                            'date'   : last_customer_invoice.date_balance.strftime(settings.DJANGO_SETTINGS_DATE)}
                    else:
                        my_balance = _('My balance : <font color="green">%(balance)s</font> at %(date)s') % {
                            'balance': last_customer_invoice.balance,
                            'date'   : last_customer_invoice.date_balance.strftime(settings.DJANGO_SETTINGS_DATE)}
                else:
                    my_balance = _('My balance')
                nodes.append('<li><a href="%s">%s</a></li>' % (
                    reverse("customer_invoice_view", args=(0,)),
                    my_balance
                ))
            nodes.append('<li class="divider"></li>')
        nodes.append('<li><a href="%s">%s</a></li>' % (
            reverse("logout_form"), _("Logout")
        ))
        nodes.append('</ul></li>')
        p_permanence_id = sint(kwargs.get('permanence_id', 0))
        if p_permanence_id > 0:
            nodes.append('<li id="li_my_basket" style="display:none;" class="dropdown">')
            nodes.append('<a href="%s?is_basket=yes" class="btn btn-info"><span id="my_basket"></span></a>' %
                reverse("order_view", args=(p_permanence_id,))
            )
            nodes.append('</li>')
    else:
        nodes = ['<li class="dropdown"><a href="%s">%s</a></li>' % (
                reverse("login_form"),
                _("Login")
        )]

    return mark_safe("".join(nodes))


@register.simple_tag(takes_context=False)
def repanier_display_languages(*args, **kwargs):
    from django.conf import settings
    if len(settings.LANGUAGES) > 1:
        return "yes"
    return


@register.simple_tag(takes_context=False)
def repanier_display_task(*args, **kwargs):
    result = EMPTY_STRING
    p_task_id = sint(kwargs.get('task_id', 0))
    if p_task_id > 0:
        permanence_board = PermanenceBoard.objects.filter(id=p_task_id).select_related(
            "permanence_role"
        ).order_by('?').first()
        if permanence_board is not None:
            if permanence_board.permanence_role.customers_may_register:
                result = permanence_board.permanence_role
            else:
                result = '<p><b>%s</b></p>' % (permanence_board.permanence_role,)
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_select_task(context, *args, **kwargs):
    request = context['request']
    user = request.user
    result = EMPTY_STRING
    customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
    if customer_is_active:
        p_task_id = sint(kwargs.get('task_id', 0))
        if p_task_id > 0:
            permanence_board = PermanenceBoard.objects.filter(id=p_task_id).select_related(
                "customer", "permanence_role", "permanence"
            ).order_by('?').first()
            if permanence_board is not None:
                if permanence_board.customer is not None:
                    if permanence_board.customer.user_id == user.id and permanence_board.permanence.status <= PERMANENCE_CLOSED:
                        result = """
                        <b><i>
                        <select name="value" id="task{task_id}"
                        onchange="task_ajax({task_id})" class="form-control">
                        <option value="0">---</option>
                        <option value="1" selected>{long_basket_name}</option>
                        </select>
                        </i></b>
                        """.format(
                            task_id=permanence_board.id,
                            long_basket_name=user.customer.long_basket_name
                        )
                    else:
                        result = """
                        <select name="value" id="task{task_id}"
                        class="form-control">
                        <option value="0" selected>{long_basket_name}</option>
                        </select>
                        """.format(
                            task_id=permanence_board.id,
                            long_basket_name=permanence_board.customer.long_basket_name
                        )
                else:
                    if permanence_board.permanence_role.customers_may_register:
                        if permanence_board.permanence.status <= PERMANENCE_CLOSED:
                            result = """
                            <b><i>
                            <select name="value" id="task{task_id}"
                            onchange="task_ajax({task_id})" class="form-control">
                            <option value="0" selected>---</option>
                            <option value="1">{long_basket_name}</option>
                            </select>
                            </i></b>
                            """.format(
                                task_id=permanence_board.id,
                                long_basket_name=user.customer.long_basket_name
                            )
                        else:
                            result = """
                            <select name="value" id="task{task_id}"
                            class="form-control">
                            <option value="0" selected>---</option>
                            </select>
                            """.format(
                                task_id=permanence_board.id
                            )
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_select_offer_item(context, *args, **kwargs):
    request = context['request']
    user = request.user
    result = EMPTY_STRING
    customer_may_order = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
    if customer_may_order:
        offer_item = kwargs.get('offer_item', None)
        str_id = str(offer_item.id)
        if offer_item.may_order:
            purchase = PurchaseWoReceiver.objects.filter(
                customer_id=user.customer,
                offer_item_id=offer_item.id,
                is_box_content=False
            ).order_by('?').only('quantity_ordered').first()
            if purchase is not None:
                is_open=purchase.status == PERMANENCE_OPENED
                option_dict = display_selected_value(
                    offer_item,
                    purchase.quantity_ordered,
                    is_open=is_open
                )
            else:
                is_open = ProducerInvoice.objects.filter(
                    permanence__offeritem=offer_item.id,
                    producer__offeritem=offer_item.id,
                    status=PERMANENCE_OPENED
                ).order_by('?').exists()
                option_dict = display_selected_value(
                    offer_item,
                    DECIMAL_ZERO,
                    is_open=is_open
                )
            # print(option_dict)
            if is_open:
                result = '<select name="offer_item{str_id}" id="offer_item{str_id}" onchange="order_ajax({str_id})" onmouseover="show_select_order_list_ajax({str_id})" class="form-control">{option}</select>'.format(
                    str_id=str_id,
                    option=option_dict['html']
                )
            else:
                result = '<select name="offer_item{str_id}" id="offer_item{str_id}" class="form-control">{option}</select>'.format(
                    str_id=str_id,
                    option=option_dict['html']
                )
        box_purchase = PurchaseWoReceiver.objects.filter(
            customer_id=user.customer,
            offer_item_id=offer_item.id,
            is_box_content=True
        ).order_by('?').select_related('offer_item').only('offer_item', 'quantity_ordered').first()
        if box_purchase is not None:
            offer_item = box_purchase.offer_item
            option_dict = display_selected_box_value(offer_item, box_purchase.quantity_ordered)
            result = result + option_dict['html']
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_btn_like(context, *args, **kwargs):
    request = context['request']
    user = request.user
    result = EMPTY_STRING
    customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
    if customer_is_active:
        offer_item = kwargs.get('offer_item', None)
        str_id = str(offer_item.id)
        result = '<br/><span class="btn_like{str_id}" style="cursor: pointer;">{html}</span>'.format(
            str_id=str_id,
            html=offer_item.get_like(user)
        )
    return mark_safe(result)