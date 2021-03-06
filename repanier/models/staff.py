# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from mptt.fields import TreeForeignKey
from mptt.managers import TreeManager
from mptt.models import MPTTModel
from parler.managers import TranslatableQuerySet, TranslatableManager
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *


class StaffQuerySet(TranslatableQuerySet):
    pass


class StaffManager(TreeManager, TranslatableManager):
    queryset_class = StaffQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(self.tree_id_attr, self.left_attr)


@python_2_unicode_compatible
class Staff(MPTTModel, TranslatableModel):
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_("login"))
    customer_responsible = models.ForeignKey(
        'Customer', verbose_name=_("customer_responsible"),
        on_delete=models.PROTECT, blank=True, null=True, default=None)
    login_attempt_counter = models.DecimalField(
        _("login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    translations = TranslatedFields(
        long_name=models.CharField(_("long_name"), max_length=100, db_index=True, null=True, default=EMPTY_STRING),
        function_description=HTMLField(_("function_description"), configuration='CKEDITOR_SETTINGS_MODEL2',
                                       blank=True, default=EMPTY_STRING),
    )
    is_reply_to_order_email = models.BooleanField(_("is_reply_to_order_email"),
                                                  default=False)
    is_reply_to_invoice_email = models.BooleanField(_("is_reply_to_invoice_email"),
                                                    default=False)
    is_contributor = models.BooleanField(_("is_contributor"),
                                         default=False)
    is_webmaster = models.BooleanField(_("is_webmaster"),
                                       default=False)
    is_coordinator = models.BooleanField(_("is_coordinator"),
                                         default=False)
    is_tester = models.BooleanField(_("is_tester"),
                                         default=False)
    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True, default=None)
    is_active = models.BooleanField(_("is_active"), default=True)

    def get_customer_phone1(self):
        try:
            return self.customer_responsible.phone1
        except:
            return "----"

    get_customer_phone1.short_description = (_("phone1"))
    get_customer_phone1.allow_tags = False

    @property
    def title_for_admin(self):
        if self.customer_responsible is not None:
            tester = _(" who is also tester ") if self.is_tester else EMPTY_STRING
            return '%s : %s%s (%s)' % (
                self.safe_translation_getter('long_name', any_language=True),
                self.customer_responsible.long_basket_name,
                tester,
                self.customer_responsible.phone1
            )
        else:
            return '%s' % self.safe_translation_getter('long_name', any_language=True)

    objects = StaffManager()

    def __str__(self):
        return self.long_name

    class Meta:
        verbose_name = _("staff member")
        verbose_name_plural = _("staff members")


@receiver(pre_save, sender=Staff)
def staff_pre_save(sender, **kwargs):
    staff = kwargs["instance"]
    staff.login_attempt_counter = DECIMAL_ZERO


@receiver(post_save, sender=Staff)
def staff_post_save(sender, **kwargs):
    staff = kwargs["instance"]
    if staff.id is not None:
        user = staff.user
        user.groups.clear()
        if staff.is_reply_to_order_email:
            group_id = Group.objects.filter(name=ORDER_GROUP).first()
            user.groups.add(group_id)
        if staff.is_reply_to_invoice_email:
            group_id = Group.objects.filter(name=INVOICE_GROUP).first()
            user.groups.add(group_id)
        if staff.is_webmaster:
            group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
            user.groups.add(group_id)
        if staff.is_contributor:
            group_id = Group.objects.filter(name=CONTRIBUTOR_GROUP).first()
            user.groups.add(group_id)
        if staff.is_coordinator:
            group_id = Group.objects.filter(name=COORDINATION_GROUP).first()
            user.groups.add(group_id)


@receiver(post_delete, sender=Staff)
def staff_post_delete(sender, **kwargs):
    staff = kwargs["instance"]
    user = staff.user
    user.delete()
