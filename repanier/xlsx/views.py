# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _


def import_xslx_view(admin_ui, admin, request, queryset, sub_title, handle_uploaded_file, action, form_klass):
    if 'apply' in request.POST:
        form = form_klass(request.POST, request.FILES)
        if form.is_valid():
            file_to_import = request.FILES['file_to_import']
            if ('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
                producer = form.cleaned_data.get('producer')
                invoice_reference = form.cleaned_data.get('invoice_reference')
                error, error_msg = handle_uploaded_file(request, queryset, file_to_import, producer, invoice_reference)
                if error:
                    if error_msg is None:
                        admin_ui.message_user(request,
                                              _("Error when importing %s : Content not valid") % (file_to_import.name),
                                              level=messages.WARNING
                                              )
                    else:
                        admin_ui.message_user(request,
                                              _("Error when importing %(file_name)s : %(error_msg)s") % {
                                                  'file_name': file_to_import.name, 'error_msg': error_msg},
                                              level=messages.ERROR
                                              )
                else:
                    admin_ui.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
                    split_path = request.get_full_path().split('/')
                    if len(split_path) == 7:
                        return HttpResponseRedirect("/".join(split_path[:-2]))
            else:
                admin_ui.message_user(request,
                                      _(
                                          "Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (
                                          file_to_import.name),
                                      level=messages.ERROR
                                      )
        else:
            admin_ui.message_user(request, _("No file to import."), level=messages.WARNING)
        return HttpResponseRedirect(request.get_full_path())
    elif 'cancel' in request.POST:
        admin_ui.message_user(request, _("Action canceled by the user."), level=messages.INFO)
        split_path = request.get_full_path().split('/')
        if len(split_path) == 7:
            return HttpResponseRedirect("/".join(split_path[:-2]))
        return HttpResponseRedirect(request.get_full_path())
    form = form_klass(
        initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
    )
    return render(request, form.template, {
        'sub_title'           : sub_title,
        'queryset'            : queryset,
        'form'                : form,
        'action'              : action,
        'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
    })
