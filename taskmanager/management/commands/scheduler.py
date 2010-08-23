from twisted.web import server, resource
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from stringprod import StringProducer

import os
import time

import sys, json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from taskmanager.models import *

class HTTPCommandBase(resource.Resource):
    isLeaf = False
    
    def __init__(self):
        resource.Resource.__init__(self)
        
    def getChild(self, name, request):
        if name == '':
            return self
        return resource.Resource.getChild(self, name, request)
    
    def render_GET(self, request):
        print "[GET] /"
        return "scheduler interface"

class HTTPStatusCommand(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)

    def showStatus(self, all_tasks=False):
        out = "<table>"
        out += "<tr class='header'><td>ID</td><td>Target</td><td>Arguments</td><td>Schedule Date</td><td>Completed</td></tr>"
        
        if all_tasks:
            tasks = ScheduledTask.objects.all()
        else:
            tasks = ScheduledTask.objects.get_pending_tasks()

        for task in tasks:
            out += '''
            <tr>
                <td>%(id)s</td><td>%(target)s</td><td>%(arguments)s</td><td>%(schedule_date)s</td><td>%(completed)s</td>
            </tr>''' % {'id': task.id, 'target': task.task.name, 'arguments': task.arguments, 'schedule_date': task.schedule_date, 'completed': task.completed}

        return str('''
        <html>
            <head>
            <style>.header td { font-weight: bold }</style>
            </head>
            <body>%s</body>
        </html>''' % (out))
    
    isLeaf = True
    def render_GET(self, request):
        print "[GET] /status"
        return self.showStatus('alltasks' in request.args)
    
class HTTPScheduleCommand(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
    
    isLeaf = True
    def render_GET(self, request):
        print "[GET] /schedule"
        return "<html>schedule via POST</html>"
    
    def render_POST(self, request):
        print "[POST] /schedule"
        
        # nab the information from the post
        print 'type(request): %s' % (type(request))
        #print 'request.content:%s' % (request.content)

        # faisal: apologies for the hack...

        cdotr = request.content.read().split('\n')
        dastring=cdotr[3]
        print 'content.read():%s'%(dastring)

        newtask = json.loads(dastring)
        print 'newtask:%s' % (newtask)

        user = User.objects.get(address=newtask['user'])
        task = Task.objects.get(name=newtask['task'])
        arguments = newtask['args']
        completed = False
        schedule_date = datetime.strptime(newtask['schedule_date'], "%Y-%m-%dT%H:%M:%S.%f")

        try:
            #newtask = json.load(request.content)
            #print 'newtask:%s' % (newtask)
            
            nt = ScheduledTask(
                user = user, task = task, arguments = arguments, completed = completed, schedule_date = schedule_date
                # user = User.objects.get(address=newtask['user']).id,
                # task = Task.objects.get(name=newtask['task']).id,
                # arguments = newtask['arguments'],
                # completed = False,
                # schedule_date = datetime.strptime(newtask['schedule_date'], "%Y-%m-%dT%H:%M:%S.%f")
            )
            nt.save()
            
            print "Task scheduled: " + str(task)
        except Exception as e:
            print e
            print "ERROR: could not schedule task " + str(task)
            print "INFO: ", sys.exc_info()[0]
            
        return "<html>this is correct</html>"

def task_finished(response, sched_taskid):
    t = ScheduledTask.objects.get(pk=sched_taskid)
    t.completed = True
    t.result = response.code
    t.completed_date = datetime.now()
    t.save()
    print "- finished %d w/code %s" % (sched_taskid, str(response.code))

def task_errored(response, sched_taskid):
    t = ScheduledTask.objects.get(pk=sched_taskid)
    t.completed = False
    t.result = response.getErrorMessage()
    t.completed_date = datetime.now()
    t.save()
    print "- errored out on task %d, reason: %s" % (sched_taskid, response.getErrorMessage())
    response.printTraceback()

def check_schedule():
    tasks = ScheduledTask.objects.get_due_tasks()
    
    for sched_task in tasks:
        agent = Agent(reactor)
        
        print "Executing task: ", sched_task.task.name
        
        payload = "user=%d&task=%d&arguments=%s" % (sched_task.user.id, sched_task.task.id, json.dumps(sched_task.arguments))
        print payload
        d = agent.request(
            'POST',
            # ullr?
            #'http://ullr:8001/taskmanager/exec',
            'http://localhost:8001/taskmanager/exec',
            Headers({
                    "Content-Type": ["application/x-www-form-urlencoded;charset=utf-8"],
                    "Content-Length": [str(len(payload))]
                    }),
            StringProducer(payload))

        d.addCallback(task_finished, sched_taskid=sched_task.id)
        d.addErrback(task_errored, sched_taskid=sched_task.id)
        
    # run again in a bit
    reactor.callLater(5, check_schedule)

def main(port=8080):
    os.environ['TZ'] = 'US/Pacific'
    time.tzset()

    # construct the resource tree
    root = HTTPCommandBase()
    root.putChild('status', HTTPStatusCommand())
    root.putChild('schedule', HTTPScheduleCommand())

    print "Running scheduler on port %d..." % (int(port))
    
    site = server.Site(root)
    reactor.callLater(3, check_schedule)
    reactor.listenTCP(int(port), site)
    reactor.run()

if __name__ == '__main__':
    main()

# to allow this to be executed as a django command...
class Command(BaseCommand):
    args = '<port>'
    help = 'Runs the scheduler via twisted (weird, i know)'

    def handle(self, *args, **options):
        main(*args)

