from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext
from taskmanager.models import *
from django.views.decorators.csrf import csrf_protect

from datetime import datetime

def taskmanager(request):
    return render_to_response('taskmanager.html', {})

@csrf_protect
def scheduler(request):
    task_types = {
            'pending_tasks': ScheduledTask.objects.get_pending_tasks(),
            'due_tasks': ScheduledTask.objects.get_due_tasks(),
            'past_tasks': ScheduledTask.objects.get_past_tasks(),
            'all_tasks': ScheduledTask.objects.all().order_by('schedule_date')
        }
    
    field_vars = {
            'machines': Task.objects.all(),
            'users': User.objects.all(),
            'current_time': datetime.now(),
        }

    if 'task_filter' in request.GET:
        field_vars['tasks'] = task_types.get(request.GET['task_filter'], 'all_tasks')
        field_vars['task_filter'] = request.GET['task_filter']
    else:
        field_vars['tasks'] = task_types['all_tasks']
        field_vars['task_filter'] = 'all_tasks'

    return render_to_response("scheduler.html", field_vars,
                               context_instance=RequestContext(request))
#    return render_to_response('scheduler.html', field_vars)

@csrf_protect
def add_scheduled_task(request):
    try:
        nt = ScheduledTask(
            user = User.objects.get(pk=int(request.POST['user'])),
            task = Task.objects.get(pk=int(request.POST['task'])),
            schedule_date = datetime.strptime(request.POST['date'] + " " + request.POST['time'], "%m/%d/%Y %I:%M%p")
        )
        nt.save()

        return HttpResponseRedirect(reverse('taskmanager.views.scheduler'))
    except:
        response = HttpResponse()
        response.write("<b>error:</b> task could not be scheduled...did you forget a field?")
        return response

# lifted from the AJAX module
# basically it just proxies the request to a different server
# to circumvent XSS protection
import urllib, urllib2
def check_scheduler(request):
    url = "http://localhost:8080/status"
    
    try:
        # attempt to fetch the requested url from the
        # backend, and proxy the response back as-sis
        args = [url]
        code = 200
        
        # if this was a POST, included exactly
        # the same form data in the subrequest
        if request.method == "POST":
            args.append(request.POST.urlencode())
        
        out = urllib2.urlopen(*args)
    
    # the request was successful, but the server
    # returned an error. as above, proxy it as-is,
    # so we can receive as much debug info as possible
    except urllib2.HTTPError, err:
        out = err.read()
        code = err.code
    
    # the server couldn't be reached. we have no idea
    # why it's down, so just return a useless error
    except urllib2.URLError, err:
        out = "Couldn't reach the backend."
        code = 500
    
    # attempt to fetch the content type of the
    # response we received, or default to text
    try:    ct = out.info()["content-type"]
    except: ct = "text/plain"
    
    # whatever happend during the subrequest, we
    # must return a response to *this* request
    return HttpResponse(out, status=code, content_type=ct)
