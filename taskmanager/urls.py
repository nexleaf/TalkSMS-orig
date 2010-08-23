#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.conf.urls.defaults import *
import taskmanager.views as views

urlpatterns = patterns('',
    (r'^taskmanager/$', views.taskmanager),
    (r'^taskmanager/scheduler/?$', views.scheduler),
    (r'^taskmanager/scheduler/check_service$', views.check_scheduler),
    (r'^taskmanager/scheduler/add/?$', views.add_scheduled_task),
)
