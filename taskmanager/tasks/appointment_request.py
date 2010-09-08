# tasks.appointment_request.AppointmentRequest

import sms

from datetime import datetime, timedelta
import json, re

class AppointmentRequest(object):
    def __init__(self, user, *args):

        if args:
            self.drname = args[0]
        else:
            self.drname = 'your doctor'

        if isinstance(user, sms.User):
            self.user = user
        else:
            raise ValueError('unknown type given for user: %s' % user)

        # m1
        q1 = """Hello {firstname}, you're due for a checkup with {drname} soon.
                If you would like to schedule one now, text me back a preferred date and time like this (mm/dd/yyyy hh:ss).
                Or respond with 'no' if you don't want to
                schedule anything now.""".format(firstname=self.user.firstname, drname=self.drname)
        r1 = sms.Response('no', r'n|N', 'no')
        r2 = sms.Response('8/30/2010 16:30', r'\d+/\d+/\d+\s\d+:\d+', label='datetime', callback=self.schedule_new_appointment)
        m1 = sms.Message(q1, [r1,r2])

        # m2
        q2 = 'No appointment has been scheduled for you as you have requested.'
        m2 = sms.Message(q2, [])

        # m3
        q3 = """Thank you, your appointment with {drname} is being scheduled. We will send you details soon.""".format(drname=self.drname)
        m3 = sms.Message(q3, [])
        
        self.graph = { m1: [m2, m3],
                       m2: [],
                       m3: [] }

        self.interaction = sms.Interaction(self.graph, m1, self.__class__.__name__ + '_interaction')

    
    def schedule_new_appointment(self, *args, **kwargs):
        ndatetime = kwargs['response']
#        assert(re.match(r'\d+/\d+/\d+\s\d+:\d+', ndatetime) is not None)
        print 'in %s.%s: user responsed with date: %s' % (self.__class__, self.__class__.__name__, kwargs['response'])

        # search appointment calendar for nearest open appointment returning datetime (ndatetime used here)
        t = datetime.strptime(ndatetime, "%m/%d/%Y %H:%M:%S")
        s = timedelta(days=3)
        i = timedelta(microseconds=1)

        appttime = t.isoformat()
        remindertime = (t-s+i).isoformat()
        
        # scheduler does this by executing immediately, any new tasks scheduled to start before 'now':
        # if remindertime is earlier than now,
        #   schedule the reminder to be sent immediately.

        #callback_args = json.JSONEncoder().encode([self.drname, appttime])
        d = {'task': 'reminder', 'user':self.user.identity, 'args': [self.drname, appttime], 'schedule_date':remindertime}
        pf = [('sarg', json.dumps(d))]

        try:
            sms.TaskManager.schedule(pf)
        except:
            print 'error: could not schedule a new appointment'

        
