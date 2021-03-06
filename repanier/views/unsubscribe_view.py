# -*- coding: utf-8
from __future__ import unicode_literals

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier.models.customer import Customer


@csrf_protect
@never_cache
def unsubscribe_view(request, customer_id, token):
    """
    User is immediately unsubscribed
    if they came from an unexpired unsubscribe link.
    """

    customer = Customer.objects.filter(
        id=customer_id
    ).order_by('?').first()

    if customer is not None and customer.check_token(token):
        # unsubscribe them
        # customer.save(update_fields=['subscribe_to_email'])
        # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
        if customer.subscribe_to_email:
            Customer.objects.filter(id=customer.id).order_by('?').update(subscribe_to_email=False)
        return render(request, 'repanier/registration/unsubscribe.html')
    else:
        return HttpResponseRedirect("/")
