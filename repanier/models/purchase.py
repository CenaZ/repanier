# -*- coding: utf-8
from __future__ import unicode_literals

# import copy

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_init, pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

import invoice
import offeritem
import producer
import repanier.apps
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.box import BoxContent
from repanier.tools import get_or_create_offer_item


@python_2_unicode_compatible
class Purchase(models.Model):
    permanence = models.ForeignKey(
        'Permanence', verbose_name=repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT,
        db_index=True)
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("invoice_status"))
    permanence_date = models.DateField(_("permanence_date"))
    offer_item = models.ForeignKey(
        'OfferItem', verbose_name=_("offer_item"), blank=True, null=True, on_delete=models.PROTECT)
    producer = models.ForeignKey(
        producer.Producer, verbose_name=_("producer"), blank=True, null=True, on_delete=models.PROTECT)
    customer = models.ForeignKey(
        'Customer', verbose_name=_("customer"), blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    customer_who_pays = models.ForeignKey(
        'Customer', verbose_name=_("customer"), related_name='purchase_paid', blank=True, null=True,
        on_delete=models.PROTECT, db_index=True)
    customer_producer_invoice = models.ForeignKey(
        'CustomerProducerInvoice', verbose_name=_("customer_producer_invoice"),
        # related_name = 'purchase_invoiced',
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    producer_invoice = models.ForeignKey(
        'ProducerInvoice', verbose_name=_("producer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    customer_invoice = models.ForeignKey(
        'CustomerInvoice', verbose_name=_("customer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)

    is_box_content = models.BooleanField(_("is_box"), default=False)

    quantity_ordered = models.DecimalField(
        _("quantity ordered"),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
    # 0 if this is not a KG product -> the preparation list for this product will be produced by family
    # qty if not -> the preparation list for this product will be produced by qty then by family
    quantity_for_preparation_sort_order = models.DecimalField(
        _("quantity for preparation order_by"),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
    # If Permanence.status < SEND this is the order quantity
    # During sending the orders to the producer this become the invoiced quantity
    # via tools.recalculate_order_amount(..., send_to_producer=True)
    quantity_invoiced = models.DecimalField(
        _("quantity invoiced"),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
    purchase_price = ModelMoneyField(
        _("producer row price"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    selling_price = ModelMoneyField(
        _("customer row price"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)

    producer_vat = ModelMoneyField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    customer_vat = ModelMoneyField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)])

    vat_level = models.CharField(
        max_length=3,
        choices=settings.LUT_VAT,
        default=settings.DICT_VAT_DEFAULT,
        verbose_name=_("tax"))

    price_list_multiplier = models.DecimalField(
        _("Customer price list multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ONE, max_digits=5, decimal_places=4, blank=True,
        validators=[MinValueValidator(0)])
    comment = models.CharField(
        _("comment"), max_length=100, default=EMPTY_STRING, blank=True, null=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True, db_index=True)

    def get_customer_unit_price(self, with_price_list_multiplier=True):
        offer_item = self.offer_item
        customer_unit_price = offer_item.customer_unit_price.amount
        if self.price_list_multiplier == DECIMAL_ONE or not with_price_list_multiplier:
            return customer_unit_price
        else:
            return (customer_unit_price * self.price_list_multiplier).quantize(TWO_DECIMALS)

    get_customer_unit_price.short_description = (_("customer unit price"))
    get_customer_unit_price.allow_tags = False

    def get_unit_deposit(self):
        return self.offer_item.unit_deposit.amount

    def get_customer_unit_vat(self):
        if self.price_list_multiplier == DECIMAL_ONE:
            return self.offer_item.customer_vat.amount
        else:
            getcontext().rounding = ROUND_HALF_UP
            return (self.offer_item.customer_vat.amount * self.price_list_multiplier).quantize(FOUR_DECIMALS)

    def get_producer_unit_vat(self):
        if self.price_list_multiplier == DECIMAL_ONE:
            return self.offer_item.producer_vat.amount
        else:
            getcontext().rounding = ROUND_HALF_UP
            return (self.offer_item.producer_vat.amount * self.price_list_multiplier).quantize(FOUR_DECIMALS)

    def get_selling_price(self):
        # workaround for a display problem with Money field in the admin list_display
        return self.selling_price

    get_selling_price.short_description = (_("customer row price"))
    get_selling_price.allow_tags = False

    def get_producer_unit_price(self, with_price_list_multiplier=True):
        offer_item = self.offer_item
        if offer_item.manage_production:
            return self.get_customer_unit_price(with_price_list_multiplier)
        return offer_item.producer_unit_price.amount

    get_producer_unit_price.short_description = (_("producer unit price"))
    get_producer_unit_price.allow_tags = False

    def get_html_producer_unit_price(self):
        if self.offer_item is not None:
            return _("<b>%(price)s</b>") % {'price': self.get_producer_unit_price()}
        return EMPTY_STRING

    get_html_producer_unit_price.short_description = (_("producer unit price"))
    get_html_producer_unit_price.allow_tags = True

    def get_html_unit_deposit(self):
        if self.offer_item is not None:
            return _("<b>%(price)s</b>") % {'price': self.offer_item.deposit}
        return EMPTY_STRING

    get_html_unit_deposit.short_description = (_("deposit"))
    get_html_unit_deposit.allow_tags = True

    def get_permanence_display(self):
        return self.permanence.get_permanence_display(with_status=False)

    get_permanence_display.short_description = (_("permanence"))
    get_permanence_display.allow_tags = False

    def get_delivery_display(self):
        if self.customer_invoice is not None:
            return self.customer_invoice.delivery
        return None

    get_delivery_display.short_description = (_("delivery point"))
    get_delivery_display.allow_tags = False

    def get_quantity(self):
        if self.status < PERMANENCE_SEND:
            return self.quantity_ordered
        else:
            return self.quantity_invoiced

    get_quantity.short_description = (_("quantity invoiced"))
    get_quantity.allow_tags = False

    def get_long_name(self, customer_price=True):
        if self.offer_item is not None:
            if self.is_box_content:
                return "%s %s" % (
                    self.offer_item.get_long_name(
                        is_quantity_invoiced=self.status >= PERMANENCE_SEND,
                        customer_price=customer_price
                    ),
                    BOX_UNICODE
                )
            else:
                return self.offer_item.get_long_name(
                    is_quantity_invoiced=self.status >= PERMANENCE_SEND,
                    customer_price=customer_price
                )
        else:
            raise AttributeError

    @transaction.atomic
    def save(self, *args, **kwargs):
        super(Purchase, self).save(*args, **kwargs)

    @transaction.atomic
    def save_box(self):
        if self.offer_item.is_box:
            for content in BoxContent.objects.filter(box_id=self.offer_item.product_id).order_by('?'):
                content_offer_item = get_or_create_offer_item(self.permanence, content.product_id,
                                                              content.product.producer_id)
                # Select one purchase
                content_purchase = Purchase.objects.filter(
                    customer_id=self.customer_id,
                    offer_item_id=content_offer_item.id,
                    is_box_content=True
                ).order_by('?').first()
                if content_purchase is None:
                    content_purchase = Purchase.objects.create(
                        permanence=self.permanence,
                        permanence_date=self.permanence.permanence_date,
                        offer_item=content_offer_item,
                        producer=self.producer,
                        customer=self.customer,
                        quantity_ordered=self.quantity_ordered * content.content_quantity,
                        quantity_invoiced=self.quantity_invoiced * content.content_quantity,
                        is_box_content=True,
                        status=self.status
                    )
                else:
                    content_purchase.status = self.status
                    content_purchase.quantity_ordered = self.quantity_ordered * content.content_quantity
                    content_purchase.quantity_invoiced = self.quantity_invoiced * content.content_quantity
                    content_purchase.save()
                content_purchase.permanence.producers.add(content_offer_item.producer)

    def __str__(self):
        # Use to not display label (inline_admin_form.original) into the inline form (tabular.html)
        return EMPTY_STRING

    class Meta:
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")
        ordering = ("permanence", "customer", "offer_item", "is_box_content")
        unique_together = ("customer", "offer_item", "is_box_content")
        index_together = [
            ["permanence", "customer_invoice"]
        ]


@receiver(post_init, sender=Purchase)
def purchase_post_init(sender, **kwargs):
    purchase = kwargs["instance"]
    if purchase.id is not None:
        if purchase.status < PERMANENCE_WAIT_FOR_SEND:
            purchase.previous_quantity = purchase.quantity_ordered
        else:
            purchase.previous_quantity = purchase.quantity_invoiced
        purchase.previous_purchase_price = purchase.purchase_price.amount
        purchase.previous_selling_price = purchase.selling_price.amount
        purchase.previous_producer_vat = purchase.producer_vat.amount
        purchase.previous_customer_vat = purchase.customer_vat.amount
        purchase.previous_deposit = purchase.deposit.amount
        purchase.previous_comment = purchase.comment
    else:
        purchase.previous_quantity = DECIMAL_ZERO
        purchase.previous_purchase_price = DECIMAL_ZERO
        purchase.previous_selling_price = DECIMAL_ZERO
        purchase.previous_producer_vat = DECIMAL_ZERO
        purchase.previous_customer_vat = DECIMAL_ZERO
        purchase.previous_deposit = DECIMAL_ZERO
        purchase.previous_comment = EMPTY_STRING


@receiver(pre_save, sender=Purchase)
def purchase_pre_save(sender, **kwargs):
    purchase = kwargs["instance"]
    if purchase.customer_invoice is None:
        purchase.customer_invoice = invoice.CustomerInvoice.objects.filter(
            permanence_id=purchase.permanence_id,
            customer_id=purchase.customer_id).only("id").order_by('?').first()
        if purchase.customer_invoice is None:
            purchase.customer_invoice = invoice.CustomerInvoice.objects.create(
                permanence_id=purchase.permanence_id,
                customer_id=purchase.customer_id,
                status=purchase.status
            )
            purchase.customer_invoice.set_delivery(delivery=None)
            purchase.customer_invoice.save()
    if purchase.producer_invoice is None:
        purchase.producer_invoice = invoice.ProducerInvoice.objects.filter(
            permanence_id=purchase.permanence_id,
            producer_id=purchase.producer_id).only("id").order_by('?').first()
        if purchase.producer_invoice is None:
            purchase.producer_invoice = invoice.ProducerInvoice.objects.create(
                permanence_id=purchase.permanence_id,
                producer_id=purchase.producer_id,
                status=purchase.status
            )
    if purchase.customer_producer_invoice is None:
        purchase.customer_producer_invoice = invoice.CustomerProducerInvoice.objects.filter(
            permanence_id=purchase.permanence_id,
            customer_id=purchase.customer_id,
            producer_id=purchase.producer_id).only("id").order_by('?').first()
        if purchase.customer_producer_invoice is None:
            purchase.customer_producer_invoice = invoice.CustomerProducerInvoice.objects.create(
                permanence_id=purchase.permanence_id,
                customer_id=purchase.customer_id,
                producer_id=purchase.producer_id,
            )
    if purchase.status < PERMANENCE_WAIT_FOR_SEND:
        quantity = purchase.quantity_ordered
        if purchase.offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            quantity *= purchase.offer_item.order_average_weight
    else:
        quantity = purchase.quantity_invoiced
    delta_quantity = quantity - purchase.previous_quantity
    if purchase.is_box_content:
        if delta_quantity != DECIMAL_ZERO:
            offeritem.OfferItem.objects.filter(id=purchase.offer_item_id).update(
                quantity_invoiced=F('quantity_invoiced') + delta_quantity,
            )
    else:
        if purchase.offer_item.is_resale_price_fixed \
                or purchase.offer_item.price_list_multiplier < DECIMAL_ONE:
            purchase.price_list_multiplier = DECIMAL_ONE
        else:
            purchase.price_list_multiplier = purchase.customer.price_list_multiplier
        producer_unit_price = purchase.get_producer_unit_price()
        customer_unit_price = purchase.get_customer_unit_price()
        unit_deposit = purchase.get_unit_deposit()

        purchase.purchase_price.amount = (
            (producer_unit_price + unit_deposit) * quantity).quantize(TWO_DECIMALS)
        purchase.selling_price.amount = (
            (customer_unit_price + unit_deposit) * quantity).quantize(TWO_DECIMALS)
        delta_purchase_price = purchase.purchase_price.amount - purchase.previous_purchase_price
        delta_selling_price = purchase.selling_price.amount - purchase.previous_selling_price

        if (delta_quantity != DECIMAL_ZERO or
            delta_selling_price != DECIMAL_ZERO or
            delta_purchase_price != DECIMAL_ZERO):

            purchase.vat_level = purchase.offer_item.vat_level
            purchase.producer_vat.amount = purchase.get_producer_unit_vat() * quantity
            purchase.customer_vat.amount = purchase.get_customer_unit_vat() * quantity

            purchase.deposit.amount = unit_deposit * quantity
            delta_producer_vat = purchase.producer_vat.amount - purchase.previous_producer_vat
            delta_customer_vat = purchase.customer_vat.amount - purchase.previous_customer_vat
            delta_deposit = purchase.deposit.amount - purchase.previous_deposit
            offeritem.OfferItem.objects.filter(id=purchase.offer_item_id).update(
                quantity_invoiced=F('quantity_invoiced') +
                                  delta_quantity,
                total_purchase_with_tax=F('total_purchase_with_tax') +
                                        delta_purchase_price,
                total_selling_with_tax=F('total_selling_with_tax') +
                                       delta_selling_price
            )
            purchase.offer_item = offeritem.OfferItem.objects.filter(
                id=purchase.offer_item_id).order_by('?').first()
            invoice.CustomerInvoice.objects.filter(id=purchase.customer_invoice.id).update(
                total_price_with_tax=F('total_price_with_tax') +
                                     delta_selling_price,
                total_vat=F('total_vat') + delta_customer_vat,
                total_deposit=F('total_deposit') + delta_deposit
            )
            invoice.CustomerProducerInvoice.objects.filter(id=purchase.customer_producer_invoice_id).update(
                total_purchase_with_tax=F('total_purchase_with_tax') +
                                        delta_purchase_price,
                total_selling_with_tax=F('total_selling_with_tax') +
                                       delta_selling_price
            )
            if purchase.offer_item.price_list_multiplier <= DECIMAL_ONE and not purchase.offer_item.is_resale_price_fixed:
                delta_total_price_with_tax = delta_selling_price
                delta_total_vat = delta_customer_vat
                delta_total_profit_with_tax = DECIMAL_ZERO
                delta_total_profit_vat = DECIMAL_ZERO
            else:
                delta_total_price_with_tax = delta_purchase_price
                delta_total_vat = delta_producer_vat
                delta_total_profit_with_tax = delta_selling_price - delta_purchase_price
                delta_total_profit_vat = delta_customer_vat - delta_producer_vat
                # TODO : Send an alert to the coordinator if we sell at lost ie delta_total_profit < 0
            invoice.ProducerInvoice.objects.filter(id=purchase.producer_invoice_id).update(
                total_price_with_tax=F('total_price_with_tax') +
                                     delta_total_price_with_tax,
                total_vat=F('total_vat') + delta_total_vat,
                total_profit_with_tax=F('total_profit_with_tax') + delta_total_profit_with_tax,
                total_profit_vat=F('total_profit_vat') + delta_total_profit_vat,
                total_deposit=F('total_deposit') + delta_deposit
            )
    # Do not do it twice
    if purchase.status < PERMANENCE_WAIT_FOR_SEND:
        purchase.previous_quantity = purchase.quantity_ordered
    else:
        purchase.previous_quantity = purchase.quantity_invoiced
    purchase.previous_purchase_price = purchase.purchase_price.amount
    purchase.previous_selling_price = purchase.selling_price.amount
