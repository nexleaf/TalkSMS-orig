# talk app

import re, json
from datetime import datetime, timedelta

import rapidsms
import rapidsms.contrib.scheduler.app as sched
from rapidsms.contrib.scheduler.models import EventSchedule, ALL

import tasks.sms as sms
import tasks.appt_tree
import tasks.appointment_request
import tasks.appointment_reminder
import tasks.appointment_followup


from taskmanager.models import *

class App (rapidsms.apps.base.AppBase):

    def start (self):        
        self.tasklist=[]
        self.tm = sms.TaskManager(self)
        self.tm.run()
        self.debug('start time: %s', datetime.now())

    def handle (self, message):
        self.debug('in App.handle(): message type: %s, message.text: %s', type(message),  message.text)
        response = self.tm.recv(message)
        self.debug("message.subject: %s; responding: %s", message.subject, response)
        message.respond(response)

    def send(self, ident, s):
        self.debug('in App.send():')
        try:
            from rapidsms.models import Backend 
            bkend, createdbkend = Backend.objects.get_or_create(name="email")        
            conn, createdconn = rapidsms.models.Connection.objects.get_or_create(backend=bkend, identity=ident)
            message = rapidsms.messages.outgoing.OutgoingMessage(conn, s)
            message.subject='testing '+ str(self.__class__)
            if message.send():
                self.debug('sent message.text: %s', s)
        except Exception as e:
            self.debug('problem sending outgoing message: createdbkend?:%s; createdconn?:%s; exception: %s', createdbkend, createdconn, e)

    # just schedules reminder to respond messages...it needs a better name
    def schedule_response_reminders(self, d):
        self.debug('in App.schedulecallback(): self.router: %s', self.router)
        cb = d.pop('callback')
        m = d.pop('minutes')
        reps = d.pop('repetitions')
        self.debug('callback:%s; minutes:%s; repetitions:%s; kwargs:%s',cb,m,reps,d)
        
        t = datetime.now()
        s = timedelta(minutes=m)
        one = timedelta(minutes=1)
    
        # for n in [(t + 1*s), (t + 2*s), ... (t + r+s)], where r goes from [1, reps+1)
        for n in [t + r*s for r in range(1,reps+1)]:
            st,et = n,n+one
            self.debug('scheduling a reminder to fire between [%s, %s]', st, et)
            schedule = EventSchedule(callback=cb, minutes=ALL, callback_kwargs=d, start_time=st, end_time=et)
            schedule.save()               
              
    def resend(self, msgid=None, identity=None):
        self.debug('in App.resend():')        
        statemachine = self.findstatemachine(msgid, identity)

        if statemachine:
            assert(isinstance(statemachine, sms.StateMachine)==True)
            assert(statemachine.msgid==msgid)
            sm = statemachine
            cn = statemachine.node

            self.debug('sm: %s; cn: %s; sm.node: %s; sm.node.sentcount: %s', sm, cn, sm.node, sm.node.sentcount)
            # if we're still waiting for a response, send a reminder and update sentcount
            if (sm.node.sentcount < sms.StateMachine.MAXSENTCOUNT):
                sm.node.sentcount += 1
                self.debug('sm.node.sentcount incremented to: %s', sm.node.sentcount)
                self.tm.send(statemachine)
        

    # move to sms.Taskmanager
    def findstatemachine(self, msgid, identity):
        self.debug('in App.findstatemachine(): msgid:%s, identity: %s', msgid, identity)
        cl = []
        for sm in self.tm.uism:
            if (sm.msgid == msgid) and (sm.user.identity == identity):
                cl.append(sm)
                
        if len(cl) > 1:
            self.error('found more than one statemachine, candidate list: %s', cl)
            statemachine = None
        elif len(cl) == 0:
            self.debug('found no matching statemachine, candidate list: %s', cl)
            statemachine = None
        else:
            assert(len(cl)==1)
            self.debug('found statemachine: %s', cl)
            statemachine = cl[0]

        return statemachine
        
    # move to TaskManager.finduser()
    def finduser(self, identity=None, firstname=None, lastname=None):
        """find or create user"""
        # should be a db look up
        for statemachine in self.tm.uism:
            if statemachine.user.identity in identity:
                return statemachine.user

        try:
            user = sms.User(identity=identity, firstname=firstname, lastname=lastname)
        except Exception as e:
            user = None
            self.error('Could not create user using identity: %s; Exception: %s', identity, e)
        return user
        

    def ajax_GET_status(self, getargs, postargs=None):
        #return self.dispatch
        return {}

    # another way to implement schedule()...or actually it just calls schedule.
    # def ajax_GET_exec(self, getargs, postargs=None):


    def ajax_POST_exec(self, getargs, postargs=None):
        self.debug("in app.ajax_POST_exec:")
        task = Task.objects.get(pk=postargs['task'])
        user = User.objects.get(pk=postargs['user'])
        args = json.loads(postargs['arguments'])

        smsuser = self.finduser(user.address, user.first_name, user.last_name)
        module = '%s.%s' % (task.module, task.className)
        print module
        print type(module)
        if not args:
            t = eval(module)(smsuser)
        else:
            t = eval(module)(smsuser, args)

        # TODO: move this to TaskManager.createtask()
        #       or TaskManager.starttask() or something similar
        self.tasklist.append(t)
        sm = sms.StateMachine(self, smsuser, t.interaction)
        self.tm.addstatemachines(sm)
        self.tm.run()

        return {'status': 'OK'}


def callresend(router, **kwargs):
    from datetime import datetime
    
    app = router.get_app('taskmanager')
    assert (app.router==router)
    
    app.debug('found app/taskmanager:%s', app)
    app.debug('%s', datetime.now())
    app.debug('router: %s; received: kwargs:%s' % (router, kwargs))

### need to delete last event from the db:
    # look up by kwargs and if now > insert timestamp...    
    app.resend(kwargs['msgid'], kwargs['identity'])




