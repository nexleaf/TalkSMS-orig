# tasks.appointment_followup.AppointmentFollowup

import sms

from datetime import datetime, timedelta
import json, re

class AppointmentFollowup(object):
    def __init__(self, user, drname='your doctor'):

        self.drname = drname

        if isinstance(user, sms.User):
            self.user = user
        else:
            raise ValueError('unknown type given for user: %s' % user)

        # m1
        q1 = """Hello {firstname}, you're due back for a checkup with {drname} soon.
                If you would like to schedule one now, text me back a date like this (mm/dd/yyyy hh:ss).
                Or respond with 'no' if you don't want to
                schedule anything now.""".format(firstname=self.user.firstname, drname=self.drname)
        r1 = sms.Response('no', r'n|N', 'no')
        r2 = sms.Response('8/30/2010 16:30', r'\d+/\d+/\d+\s\d+:\d+', label='date', callback=self.schedule_new_appointment)
        m1 = sms.Message(q1, [r1,r2])

        # m2
        q2 = """Ok, as you've requested, no appointment has been scheduled for you."""
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
        assert(re.match(r'\d+/\d+/\d+\s\d+:\d+', ndatetime) is not None)
        print 'in tasks.appointment_tree.schedule_appointment: user responsed with date: %' % (response)

        # search appointment calendar for nearest open appointment returning datetime (ndatetime used here)
        t = datetime.strptime(ndatetime, "%m/%d/%Y %H:%M")
        s = timedelta(days=3, microseconds=1)

        remindertime = (t-s).isoformat()
        # scheduler does this:
        # if remindertime is earlier than now,
        #   schedule the reminder to be sent immediately.

        callback = 'tasks.appointment_reminder.AppointmentReminder'

        d = {'task':callback, 'user':self.user.identity, 'args':self.drname, 'schedule_date':remindertime}
        pf = [( 'sarg', json.dumps(d) )]

        try:
            sms.TaskManager.schedule(pf)
        except:
            print 'error: could not schedule a new appointment'

        
