# sms.py: TalkSMS library

import string
import re
from collections import deque
import itertools

class Response(object):

    def __init__(self, text, regex, label='', callback=None, *args, **kwargs):
        if not re.compile(regex).match(text):
            raise ValueError('Response.regex must re.match() Response.text')
        self.text = text
        self.regex = re.compile(regex)
        self.label = label
        if callback:
            self.callback = callback
            self.args = args
            self.kwargs = kwargs

    def match(self, sometext):
        'return None if there is no match, and the MatchObject otherwise'
        return self.regex.match(sometext)

    def __str__(self):
        return '%s:%s' % (self.__class__.__name__, (self.label if self.label else repr(self) ))


class Message(object):

    def __init__(self, question, responselist=[], autoresend=0, label=''):
        self.question = question
        self.responselist = responselist
        self.autoresend = autoresend
        self.label = label
        
        self.__sentcount = 0
    
    @property
    def sentcount(self):
        return self.__sentcount
    @sentcount.setter
    def sentcount(self, n):
        if not n or (n == self.sentcount+1):
            self.__sentcount = n
        else:
            raise ValueError ('Message.sentcount can only be incremented by 1.')

    def __str__(self):
        return '%s:%s %s' % ( self.__class__.__name__, \
                             (self.label if self.label else repr(self)), \
                             [str(r) for r in self.responselist] )


class Interaction(object):

    def __init__(self, graph, initialnode, label=''):

        Interaction.isvalid(graph, initialnode)

        if label is None:
            self.label = self.__class__.__name__
        else:
            self.label = label
        self.initialnode = initialnode
        self.graph = graph

    def mapsTo(self, m, r):
        """
        say i is an Interaction with graph g.
        then m,m1 are Messages, m->m1 is an edge, and r is
        the transition mapping m to m1 in g.
        then i.mapsTo(m,r) returns m1
        """
        if not isinstance(m, Message):
            raise TypeError ('%s in not Message type' % (str(m)))
        if not isinstance(r, Response):
            raise TypeError ('%s is not Response type' % (str(m)))
        if not r in m.responselist:
            raise ValueError ('Response %s is not in %s responslist' % (str(r),str(m)))
        if not m in self.graph.keys():
            raise ValueError ('%s is not a key in this Interaction graph.' % (str(m)))
        
        return self.graph[m][m.responselist.index(r)]

    @classmethod
    def isvalid(cls, graph, initialnode):
        # check that each msg node has the same number of responses as children
        for msg in graph.keys():
            if not len(graph[msg]) == len(msg.responselist):
                raise ValueError("bad mapping.")
        # check initialnode is in interaction graph
        if not initialnode in graph:
            raise ValueError("missing initial message node in interaction graph.")
        # TODO: check ensure no cycles in interaction graph


    def __str__(self):
        'returns a bfs of the graph.'
        s = '\t'
        q = deque()
        string = ''
        q.append( (self.initialnode, 0) )
        while q:
            cn,n = q.popleft()
            string += s*n + ( cn.label if cn.label else str(cn) )  + ' : \n'
            for r,m in zip(cn.responselist, self.graph[cn]):
                string += s*n + ( r.label if r.label else str(r) ) + ' -> ' \
                              + ( m.label if m.label else str(m) ) + '\n'
                if m.responselist:
                    q.append( (m, n+1) )
            string += '\n'
        string += ('.' if not q else str(q)) 
        return string


class User(object):

    MAXMSGID = 99
    
    def __init__(self, identity=None, firstname=None, lastname=None, label=None):
        # handy?
        #for k,v in attributes.iteritems():
        #    setattr(self,k,v)
        if identity is None:
            raise ValueError("Phone number or email required.")
        elif re.match(r'.+@.+', identity):
            self.identity = identity
            self.identityType = 'email'
        elif re.match(r'^\d+', self.identity):
            self.identity = identity
            self.identityType = 'phone'
        else:
            raise ValueError("Unknown identity type.")

        self.firstname = firstname
        self.lastname = lastname

        if label is None:
            self.label = self.__class__.__name__
        else:
            self.label = label

        # possible memory hog when msgid is large
        self.msgid = itertools.cycle(range(User.MAXMSGID+1))

    @property
    def username(self):
        return self.firstname + ' ' + self.lastname
        

class StateMachine(object):
      """
      StateMachine keeps track of the flow through an Interaction.
      """
      # max number of times a message is sent when expecting a reply
      MAXSENTCOUNT = 3
      # time to resend a message in minutes
      TIMEOUT = 15
      
      def __init__(self, app, user, interaction, label=''):
          self.app = app
          self.log = app
          
          self.interaction = interaction
          self.user = user
          self.label = label
          # expected message id is set when a new message is sent
          self.msgid = None
          self.done = False
          # current node in the interaction graph
          self.node = self.interaction.initialnode
          self.event = 'SEND_MESSAGE'
          self.handler = { 'SEND_MESSAGE'     : self.send_message,
                           'WAIT_FOR_RESPONSE': self.wait_for_response,
                           'HANDLE_RESPONSE'  : self.handle_response,
                           'EXIT'             : self.close }
          self.mbox = None


      def send_message(self):     
          self.log.debug('in StateMachine.send_message(): self.event: %s' % self.event)
          self.log.debug('node: %s, node.sentcount: %s' % ( str(self.node), self.node.sentcount ))
          if self.node.sentcount < StateMachine.MAXSENTCOUNT:
              if not self.node.sentcount:
                  self.msgid = self.user.msgid.next()
              if not self.node.responselist:
                  self.event = 'EXIT'
              else:
                  self.event = 'WAIT_FOR_RESPONSE'

                  # schedule at most 3 resend's each spaced out by TIMEOUT minutes from now.
                  
                  d = {'callback':'taskmanager.app.callresend',
                       'minutes':StateMachine.TIMEOUT,
                       'repetitions':StateMachine.MAXSENTCOUNT,
                       'msgid':self.msgid,
                       'identity':self.user.identity }                 
                  self.app.schedule_response_reminders(d)

              self.node.sentcount += 1
          else:
              self.log.debug('(current message node reached maxsentcount, exiting StateMachine %s)' % self.label )
              self.event = 'EXIT'

              
      def wait_for_response(self):
          self.log.debug('in StateMachine.wait_for_response(): self.event: %s' % self.event)

          # wait_for_response() is called only when there is a response (left in mbox)
          # if there isn't one there, it used to mean a call-back timer was called
          if not self.mbox:
              self.log.debug('(timer timed_out while waiting for response; resending)')
              self.event = 'SEND_MESSAGE'
          else:
              self.event = 'HANDLE_RESPONSE'
          

      def handle_response(self):
          self.log.debug('in StateMachine.handle_response(): self.event: %s' % self.event)

          assert(self.mbox is not None)
          rnew = self.mbox
          self.log.debug('rnew: \'%s\'' % rnew)

          matches = [r.match(rnew) for r in self.node.responselist]
          matchcount = len(matches) - matches.count(None)
          self.log.debug('matches: %s' % matches)          
          self.log.debug('matchcount: %s' % matchcount)          
          if matchcount == 1:
              # find index for the match
              i = [m is not None for m in matches].index(True)
              response = self.node.responselist[i]
              # call response obj's developer defined callback
              if hasattr(response, 'callback'):
                  self.log.debug('calling callback defined in %s' % (response))
                  response.args = []
                  response.kwargs = {'response':rnew}
                  result = response.callback(*response.args, **response.kwargs)
                  self.log.debug('callback result: %s.' % (result))
              # advance to the next node
              self.node = self.interaction.mapsTo(self.node, response)
              self.log.debug('found response match, advanced curnode to %s' % (self.node))
                            
          elif matchcount == 0: 
              self.log.debug('response did not match expected list of responses, attempting to resend')
          else:
              self.log.debug('rnew: %s, matched more than one response in response list, attempting to resend' % rnew)
          self.event = 'SEND_MESSAGE'

          
      def close(self):
          """done. tell taskmanager to move me from the live list to the dead list..."""
          self.log.debug('in StateMachine.close(): self.event: %s' % self.event)
          self.done = True
          
              
      def kick(self, package=None):
          self.log.debug('in StateMachine.kick(): self.event: %s' % self.event)

          while not self.done:
              self.mbox = package
              self.handler[self.event]()
              if self.event == 'WAIT_FOR_RESPONSE':
                  break



class TaskManager(object):
    """
    TM holds a list of all statemachines, and manages messages to them.
    TM also interacts with the Scheduler to post/get user; task; arguments, in order to schedule start of
    future interactions. (tasks are statemachines....)
    """
    LENGTH = 30
    TRYS = 3
    
    def __init__(self, app):
        self.app = app
        self.log = app

        self.log.debug('in TaskManager.run(): Talk App: %s' % self.app)

        self.numbers = re.compile('^\d+')
        self.badmsgs = {}

        # maintain a list of all statemachines
        self.uism = []

    @staticmethod
    def schedule(pf):
        import pycurl
        c = pycurl.Curl()
        c.setopt(c.URL, 'http://localhost/schedule')
        c.setopt(c.PORT, 8080)
        print 'in TaskManager.schedule(): about to post'
        c.setopt(c.HTTPPOST, pf)
        print 'in TaskManager.schedule():'
        c.setopt(c.VERBOSE, 0)
        c.perform()
        c.close()


    def addstatemachines(self, *statemachines):
        for sm in statemachines:
            if sm not in self.uism:
                self.uism.append(sm)
                self.log.debug('in TaskManager.addstatemachines(): len(self.uism): %s'  % len(self.uism))                
                assert(len(self.uism) > 0)

    def pop(self, statemachine):
        """remove statemachine from user's and taskmanager's lists"""
        assert(statemachine in self.uism)
        assert(len(self.uism) > 0)
        try:
            i = self.uism.index(statemachine)
            self.uism.pop(i)            
        except ValueError:
            self.log.error('statemachine is not in self.uism')
            return
        except NameError:
            self.log.error('statemachine is not defined')
            return

        
    @staticmethod
    def build_send_str(node, msgid):
        s = ''.join(node.question)
        # we're getting here right after sentcount was updated in SM,
        # so pretending we're back there...
        # a cleaner solution is to put this method back in SM however, this will be messy until rapidsms releases.
        if (node.sentcount-1 > 0):
          s += '\n(resending message since the response was not understood or not received)\n'
        if node.responselist:
          s += '\nPlease prepend response with message id: \"%d\".\n' % (msgid)
        return s
                
    # the first send is app.start() -> tm.run() -> sm.kick() -> app.send().
    # then each message is received (or ping-ponged back and forth)
    # by app.handle() -> app.recv() -> sm.kick() which
    # returns a string, 'response' along the same route.     
    def send(self, statemachine):
        # it's very wrong to be updating the msgid outside of the statemachine.
        # msgid should only be updated when sm advances to the next msg node in the graph.
        # bypassing this will be messy
        # statemachine.msgid = statemachine.user.msgid.next()
        s = TaskManager.build_send_str(statemachine.node, statemachine.msgid)
        self.log.info('in TaskManager.send(): preparing to send s: %s' % s)
        self.app.send(statemachine.user.identity, s)

        
    def recv(self, rmessage):
        self.log.debug('in TaskManager.recv(): ')

        response = 'Response not understood. Please prepend the message id number to your response.'
        nid = self.numbers.match(rmessage.text)
        
        if not nid:
            # there was no msgid, send err back up to 3 or 4 times...
            # TODO: 8/4: this will be inserted into the db...
            self.log.debug('no msgid found in user response, rmessage.peer: %s' % rmessage.peer)
            peer = rmessage.peer
            if peer not in self.badmsgs:
                self.badmsgs[peer] = 0
            elif self.badmsgs[peer] < TaskManager.TRYS:  
                self.badmsgs[peer] += 1
            else:
                self.log.error('repeated responses with missing msgid...should we drop the interaction?')
            self.log.debug('self.badmsgs: %s' % self.badmsgs)

            response = '\"%s\" was not understood. Please prepend the message id number to your response.' %\
                       rmessage.text.splitlines()[0].strip()           
        else:
            # strip off msgid and text from the repsonse 
            rmsgid = nid.group()
            a,b,rtext = rmessage.text.partition(str(rmsgid))
            assert(b==rmsgid)
            rtext = rtext.splitlines()[0].strip()
            self.log.debug('found msgid in response' +\
                      'rmsgid: \'%s\'; rtext: \'%s\'; peer: \'%s\'' % (rmsgid, rtext, rmessage.peer))           
            # find the correct statemachine
            for sm in self.uism:
                self.log.debug('sm.user.identity: \'%s\'; rmessage.peer: \'%s\'; sm.msgid: \'%s\'; rmsgid: \'%s\'' %\
                          (sm.user.identity, rmessage.peer, sm.msgid, rmsgid))
                self.log.debug('sm.user.identity==rmessage.peer -> %s; sm.msgid==int(rmsgid) -> %s' %\
                          (sm.user.identity==rmessage.peer, sm.msgid==int(rmsgid)))

                if (sm.user.identity == rmessage.peer):
                    if (sm.msgid == int(rmsgid)):
                        self.log.debug('found sm')
                        sm.kick(rtext)
                        response = TaskManager.build_send_str(sm.node, sm.msgid)
                        self.log.debug('and response = %s' % response)
                    break
                # sm's are popped only after receiving the next message from app.handle().
                # since new sm's are appended onto the end of the list, sm's which are done are popped eventually.
                if sm.done:
                    self.pop(sm)

        return response
                

    def run(self):
        """ start up all statemachines"""
        self.log.debug('in TaskManager.run(): self.uism: %s' % self.uism)
        # send the first messages. once the statemachines are running,
        # responses will be ping-ponged back and forth from App.handle() to self.recv()
        for sm in self.uism:
            if sm.node == sm.interaction.initialnode:
                sm.kick()
                self.send(sm)
        


    



