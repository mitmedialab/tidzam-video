from django.conf.urls import url
from . import views
from django.views.generic.base import TemplateView

urlpatterns = [
	url(r'^$', TemplateView.as_view(template_name='home.html'), name='home'),
	url(r'^camera/$', TemplateView.as_view(template_name='camera.html'), name='camera'),
] 
