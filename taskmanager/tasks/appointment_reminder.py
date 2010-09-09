# tasks/appointment_reminder.py

import sms

from datetime import datetime, timedelta
import json, re

class AppointmentReminder(object):
    def __init__(self, user, *args):

        print 'in appointment reminder: args: %s' % args
        args = eval(args[0])
        print 'in appointment reminder: args: %s' % args
        
        assert(isinstance(args, list))
        print 'args: %s; args[0]:%s; args[1]:%s' % (args, args[0], args[1])
        self.drname = args[0]
        self.appttime = datetime.strptime(args[1], "%Y-%m-%dT%H:%M:%S")
            
        if isinstance(user, sms.User):
            self.user = user
        else:
            raise ValueError('in %s: unknown type given for user: %s', self.__class__, user)
        
        # m1
        q1 = """Hello {firstname}, you scheduled an appointment with {drname} for {date}.
                If this is good for you, reply 'ok'.
                If you would like to reschedule, text back a date like this (mm/dd/yyyy hh:mm:ss).
                Otherwise, if you would like to cancel the appointment,
                reply 'cancel' or 'no'.""".format(firstname=self.user.firstname, drname=self.drname, date=self.appttime)
        r1 = sms.Response('ok', r'ok|OK|Ok')
        r2 = sms.Response('12/31/2012 15:30:00', r'\d+/\d+/\d+\s\d+:\d+:\d+', callback=self.reschedule)
        r3 = sms.Response('cancel', r'cancel|no', callback=self.cancel)
        m1 = sms.Message(q1, [r1,r2,r3])
    
        # m2
        q2 = 'Great, see you then.'
        m2 = sms.Message(q2, [])
        
        # m3
        q3 = 'Ok, we will send you details about rescheduling soon.'
        m3 = sms.Message(q3, [])
        
        # m4
        q4 = 'Ok, we have cancelled your appointment as you have requested.'
        m4 = sms.Message(q4, [])
        
        self.graph = { m1: [m2, m3, m4],
                       m2: [],
                       m3: [],
                       m4: [] }
        
        self.interaction = sms.Interaction(self.graph, m1, self.__class__.__name__ + '_interaction')

    def reschedule(self, *args, **kwargs):
        ndatetime = kwargs['response']
        assert(re.match(r'\d+/\d+/\d+.\d+:\d+:\d+', ndatetime) is not None)
        print 'in %s.%s: user responsed with date: %s' % (self.__class__, self.__class__.__name__, kwargs['response'])

        # find old appointment and cancel
        # search appointment calendar for the nearest open appointment returning datetime (ndatetime used here)
        t = datetime.strptime(ndatetime, "%m/%d/%Y %H:%M:%S")
        s = timedelta(days=3)
        i = timedelta(microseconds=1)

        appttime = t.isoformat()
        remindertime = (t-s+i).isoformat()

        # scheduler does this:
        # if remindertime is earlier than now,
        #   schedule the reminder to be sent immediately.

        callback = 'tasks.appointment_reminder.AppointmentReminder'

        d = {'task': 'reminder', 'user':self.user.identity, 'args':[self.drname, appttime], 'schedule_date':remindertime}
        pf = [( 'sarg', json.dumps(d) )]

        try:
            sms.TaskManager.schedule(pf)
        except:
            print 'error: could not schedule '

    def cancel(self, *args, **kwargs):
        # search for user's current appointment with drname and cancel
        print 'in %s.%s: user responsed with date: %' % (self.__class__, self.__class__.__name__, response)
        print 'cancelling current appointment'
