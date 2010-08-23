#!/usr/bin/env python

import django
from django.db import models

from datetime import datetime

class User(models.Model):
    address = models.CharField(max_length=200)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    
    def __unicode__(self):
        return "%s, %s (%s)" % (self.last_name, self.first_name, self.address)

class Task(models.Model):
    name = models.CharField(max_length=100)
    module = models.CharField(max_length=100)
    className = models.CharField(max_length=100)

    def __unicode__(self):
        return "%s (%s.%s)" % (self.name, self.module, self.className)

class RunningTask(models.Model):
    user = models.ForeignKey(User)
    task = models.ForeignKey(Task)
    add_date = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=100)
    
    def __unicode__(self):
        return "Running task for %s on %s" % (self.user.address, self.task.name)
    
class TaskUserDatapoint(models.Model):
    user = models.ForeignKey(User)
    task = models.ForeignKey(Task)
    add_date = models.DateTimeField(auto_now_add=True)
    data = models.TextField()

    def __unicode__(self):
        return "Datapoint for %s on %s" % (self.user.address, self.task.name)

class ScheduledTaskManager(models.Manager):
    def get_pending_tasks(self):
        qset = super(ScheduledTaskManager, self).get_query_set()
        return qset.filter(schedule_date__gt=datetime.now(), completed=False)

    def get_due_tasks(self):
        qset = super(ScheduledTaskManager, self).get_query_set()
        return qset.filter(schedule_date__lte=datetime.now(), completed=False)

    def get_past_tasks(self):
        qset = super(ScheduledTaskManager, self).get_query_set()
        return qset.filter(schedule_date__lte=datetime.now(), completed=True)

class ScheduledTask(models.Model):
    user = models.ForeignKey(User)
    task = models.ForeignKey(Task)
    add_date = models.DateTimeField(auto_now_add=True)
    arguments = models.TextField(blank=True)
    schedule_date = models.DateTimeField()
    completed = models.BooleanField(blank=True,default=False)
    completed_date = models.DateTimeField(blank=True,null=True)
    result = models.TextField(blank=True)

    objects = ScheduledTaskManager()

    def is_pending(self):
        return (self.schedule_date > datetime.now()) and (not self.completed)

    def is_due(self):
        return (self.schedule_date <= datetime.now()) and (not self.completed)

    def is_past(self):
        return (self.schedule_date <= datetime.now()) and (self.completed)

    def get_status(self):
        if self.is_pending(): return "pending"
        elif self.is_due(): return "due"
        elif self.is_past(): return "past"
        else: return "unknown"

    def __unicode__(self):
        return "Scheduled Task for %s on %s" % (self.user.address, self.task.name)
