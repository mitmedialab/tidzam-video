# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render

from channels import Channel

# Create your views here.
def home(request):
	message={}
	Channel('background-hello').send(message)
	return render(request, 'home.html',dict(message),)

def camera(request):
	return render(request, 'camera.html')