# -*- coding: utf-8 -*-
from pprint import pformat
import sys, json, re, time

from twisted.internet import reactor
from twisted.web.client import Agent, getPage
from twisted.web.http_headers import Headers

from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol

from zope.interface import implements

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer

from twisted.python import log

class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

class BeginningPrinter(Protocol):
    def __init__(self, finished):
        self.data = ''
        self.finished = finished
        self.remaining = 2048 * 10

    def dataReceived(self, bytes):
        if self.remaining:
            display = bytes[:self.remaining]
            #print 'Some data received:'
            #print display
            self.data += display
            self.remaining -= len(display)

    def connectionLost(self, reason):
        #print 'Finished receiving body:', reason.getErrorMessage()
        self.finished.callback(self.data)

class Resolver(object):
    def __init__(self, user, pwd):
        self.agent = Agent(reactor)
        print user, pwd
        self.user = user
        self.pwd = pwd
        
        self.self_alias = None
        
        #cookies
        self.nk_session_result = None
        self.basic_auth_result = None
        self.lltkck_result = None
        
        self.base = None
        self.version = None
        self.domain = None
        self.username = None
        self.password = None
        
        #session
        self.auth = None
        self.ssid = None
        
    #EVENTS
    def onLoginInfo(self, base, domain, username, password):
        pass
    
    def onLoginFailed(self):
        pass
    
    def onServiceUnavailable(self):
        """ Called for example about 04.00 to 04.15 because of backup. """
        pass
    
    def onAuthFailed(self):
        pass
    
    def onStatusChanged(self, status_changed):
        pass

    def onOnlineList(self, onlinelist):
        pass

    def onListDownloaded(self, friendlist):
        pass
        
    #CALL-DEFINED FUNCTIONS
    def setStatus(self, status, message):
        #http://nasza-klasa.pl/nktalk/set_status?status=2&status_text=&t=4bedf6e8175393c2a8341784
        body = StringProducer(str("status=%s&status_text=%s&t=%s" % (status, message, self.auth)))
        
        headers = {}
        cookies = self.nk_session_result+" "+self.basic_auth_result
        headers['Cookie'] = [cookies]
        headers['User-Agent'] = ["Mozilla/5.0 (X11; U; Linux i686; pl-PL; rv:1.9.2.3) Gecko/20100423 Ubuntu/10.04 (lucid) Firefox/3.6.3"]
        headers['Referer'] = ['http://nk.pl/']
        headers['Accept'] = ['application/json']
        headers['X-Requested-With'] = ['XMLHttpRequest']
        headers['X-Request'] = ['JSON']
        headers['IsAjaxy'] = ['very']
        headers['Content-Type'] = ['application/x-www-form-urlencoded; charset=utf-8']
        headers = Headers(headers)
        
        d = self.agent.request(
            "POST",
            "http://nk.pl/nktalk/set_status",
            headers,
            body)
        
        d.addCallback(self.cbSetStatus)
        d.addErrback(self.cbShutdown)
    
    def getOnlineList(self):
        #http://nk.pl/online_list/33363427/1279414006?t=4c4b8942bc1cdd8b53ca1233
        
        headers = {}
        cookies = self.nk_session_result+" "+self.basic_auth_result
        headers['Cookie'] = [cookies]
        headers['User-Agent'] = ["Mozilla/5.0 (X11; U; Linux i686; pl-PL; rv:1.9.2.3) Gecko/20100423 Ubuntu/10.04 (lucid) Firefox/3.6.3"]
        headers['Referer'] = ['http://nk.pl/']
        headers['Accept'] = ['application/json']
        headers = Headers(headers)
        
        url = "http://nk.pl/online_list/%s/1?t=%s" % (self.username, self.auth)
        
        d = self.agent.request(
            "GET",
            str(url).strip(),
            headers,
            None)
        
        d.addCallback(self.cbOnlineList)
        d.addErrback(self.cbShutdown)
    
    def getFriendsList(self):
        headers = {}
        cookies = self.nk_session_result+" "+self.basic_auth_result
        cookies = cookies[:-1]
        headers['User-Agent'] = ["Mozilla/5.0 (X11; U; Linux i686; pl-PL; rv:1.9.2.3) Gecko/20100423 Ubuntu/10.04 (lucid) Firefox/3.6.3"]
        headers['Accept'] = ['*/*']
        headers['Cookie'] = [str(cookies)]
        headers = Headers(headers)
        
        url = "http://nk.pl/friends_list/%s/15/%s?t=%s" % (self.username, self.version, self.auth)
        #print 'getInfo url:', str(url)
        
        d = self.agent.request(
            "GET",
            str(url).strip(),
            headers,
            None)
        
        d.addCallback(self.cbListDownloaded)
        d.addErrback(self.cbShutdown)

    
    def getLoginInfo(self, url=None):
        body = StringProducer(str("login=%s&password=%s&manual=0" % (self.user, self.pwd)))

        headers = {}
        headers['Cookie'] = ["nk_window=focused"]
        headers['User-Agent'] = ["Mozilla/5.0 (X11; U; Linux i686; pl-PL; rv:1.9.2.3) Gecko/20100423 Ubuntu/10.04 (lucid) Firefox/3.6.3"]
        headers['Referer'] = ['http://nk.pl/']

        headers['Content-Type'] = ['application/x-www-form-urlencoded']
        
        headers = Headers(headers)
        
        d = self.agent.request(
            "POST",
            "http://nk.pl/login",
            headers,
            body)
        
        d.addCallback(self.cbLoginInfo)
        d.addErrback(self.cbShutdown)

    def cbLoginInfo(self, response):
        if response.code == 503:
            self.onServiceUnavailable()
            return
        location = 0
        loc = list(response.headers.getAllRawHeaders())
        for l in loc:
            if l[0] == "Location":
                location = 1
                # NK code sucks and they send us two basic_auth cookies Oo
                nk_session_cookie = response.headers.getRawHeaders('Set-Cookie')[0]
                #basic_auth_cookie = response.headers.getRawHeaders('Set-Cookie')[1]
                lltkck_cookie = response.headers.getRawHeaders('Set-Cookie')[2]
                basic_auth_cookie = response.headers.getRawHeaders('Set-Cookie')[3]
        
                nk_session_match = re.search("nk_session=(.*?);", nk_session_cookie)
                if nk_session_match:
                    nk_session_result = nk_session_match.group()
                else:
                    nk_session_result = None
                
                basic_auth_match = re.search("basic_auth=(.*?);", basic_auth_cookie)
                if basic_auth_match:
                    basic_auth_result = basic_auth_match.group()
                else:
                    basic_auth_result = None
                    
                lltkck_match = re.search("lltkck=(.*?);", lltkck_cookie)
                if lltkck_match:
                    lltkck_result = lltkck_match.group()
                else:
                    lltkck_result = None
                
                self.nk_session_result = nk_session_result
                self.basic_auth_result = basic_auth_result
                self.lltkck_result = lltkck_result
                
                self.auth = basic_auth_result[11:-1]
                self.ssid = nk_session_result[11:-1]
                
                url = l[1][0]
                cookies = nk_session_result+" "+basic_auth_result+" "+lltkck_result

                headers = {}
                headers['Cookie'] = [cookies]
                headers['User-Agent'] = ["Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5"]
                
                headers = Headers(headers)

                d = self.agent.request(
                    "GET",
                    url,
                    headers,
                    None)

                d.addCallback(self.cbLoginInfoSuccess)
                d.addErrback(self.cbShutdown)
        if location == 0:
            self.onAuthFailed()

    def cbLoginInfoSuccess(self, response):
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.parseLoginInfoSuccess)
        finished.addErrback(self.cbShutdown)
        return finished

    def parseLoginInfoSuccess(self, response):
        try:
            data = response.split('\n')
            for line in data:
                if line.startswith('var nk_options = '):
                    options = line[17:-9]
                    options_json = json.loads(options)
                        
                    self.base = options_json["nktalk"]["httpbase"]
                    self.version = options_json["nktalk"]["version"]
                    self.domain = options_json["nktalk"]["login"]["domain"]
                    self.username = options_json["nktalk"]["login"]["username"]
                    self.password = options_json["nktalk"]["login"]["password"]
                    
                    self.onLoginInfo(self.base, self.domain, self.username, self.password)
        except:
            self.onLoginFailed()


    def cbSetStatus(self, response):
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.parseSetStatus)
        finished.addErrback(self.cbShutdown)
        return finished
        
    def parseSetStatus(self, response):
        response = response[3:]
        if response == "1":
            status_changed = 1
        else:
            status_changed = 0
        self.onStatusChanged(status_changed)

    def cbOnlineList(self, response):
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.parseOnlineList)
        finished.addErrback(self.cbShutdown)
        return finished
        
    def parseOnlineList(self, response):
        #response = response[3:]
        try:
            onlinelist = json.loads(response)
        except:
            onlinelist = None
        self.onOnlineList(onlinelist)

    def cbListDownloaded(self, response):
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.parseDownloadedList)
        finished.addErrback(self.cbShutdown)
        return finished
        
    def parseDownloadedList(self, response):
        response = response[3:]
        try:
            friendlist = json.loads(response)
        except:
            friendlist = None
        self.onListDownloaded(friendlist)

    # teest

    def cbShutdown(self, ignored):
        print ignored
        reactor.stop()
