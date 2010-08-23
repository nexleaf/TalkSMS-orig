# tasks.appt_tree.AppointmentTree

import sms

from datetime import datetime, timedelta

class AppointmentTree(object):
    def __init__(self, user, drname='your doctor'):

        # assume user is a user obj; drname is a string.
        self.drname = drname
        self.user = user

        # define the interaction
        # ask if they have an appointment
        q_askappt = "Have you made an appointment with %s? Resp with yes or no" % (self.drname)      
        r_yes = sms.Response('yes', r'y|Y', 'yes')
        r_no = sms.Response('no', r'n|N', label='no', callback=self.reask_question)
        m1 = sms.Message(q_askappt, [r_yes, r_no])

        # ask when their appointment is
        q_whenappt = "When is your appointment with %s? Resp with mm/dd/yy hh:mm" % (self.drname)
        r_date = sms.Response('3/3/3 3:3', r'\d+/\d+/\d+\s\d+:\d+', label='mm/dd/yyyy hh:ss', callback=self.reminder_schedule)
        m2 = sms.Message(q_whenappt, [r_date])

        # tell them to set an appointment, and schedule a reminder
        q_setappt = "Please set an appointment with %s. Will check back in 5 days" % (self.drname)
        m3 = sms.Message(q_setappt, [])

        # thank
        q_thankappt = "Thank you, I will remind you the day before your appointment with %s" % (self.drname)
        m4 = sms.Message(q_thankappt, [])

        self.graph = {m1: [m2, m3],
                      m2: [m4],
                      m3: [],
                      m4: []}

        self.interaction = sms.Interaction(self.graph, m1, self.__class__.__name__ + '_interaction')

    # define callbacks for responses here...
    def reask_question(self, *args):
        t = datetime.now()
        five_days = timedelta(days=5)
        timestr=(t+five_days).isoformat()
        
        d ={'task':'appointment tree', 'user':self.user, 'args':self.drname, 'schedule_date':timestr}
        pf=[('sarg', json.dumps(d))]
        
        try: 
            sms.TaskManager.schedule(pf)
        except:
            print 'error: could not schedule callback AppointmentTree.reask_question()'


    def reminder_schedule(self, *args):
        # AppointmentReminder is another class like this one

        t = datetime.now()
        one_day = timedelta(days=1)
        timestr = (t-one_day).isoformat()

        d ={'task':'appointment tree', 'user':self.user, 'args':self.drname, 'schedule_date':timestr}
        pf=[('sarg', json.dumps(d))]

        try:
            sms.TaskManager.schedule(pf)
        except:
            print 'error: could not schedule callback AppointmentTree.reminder_schedule()'
            
