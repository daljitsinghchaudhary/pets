from django.shortcuts import render
from django.views.generic.base import ContextMixin

from meupet import models


def get_kind_list():
    return models.Kind.objects.all().order_by('kind')


class MeuPetEspecieMixin(ContextMixin):

    def get_context_data(self, **kwargs):
        context = super(MeuPetEspecieMixin, self).get_context_data(**kwargs)
        context['kind_lost'] = get_kind_list()
        context['kind_adoption'] = get_kind_list()
        return context


def not_found(request):
    return render(request, 'staticpages/404.html')
