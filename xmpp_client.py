# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from twisted.internet import reactor
from twisted.names.srvconnect import SRVConnector
from twisted.words.xish import domish
from twisted.words.protocols.jabber import xmlstream, client, jid
from BoshClient import XMPPAuthenticator, HTTPBindingStreamFactory, HTTPBClientConnector
from resolver import Resolver

from twisted.python import log

class XMPPClientConnector(SRVConnector):
    def __init__(self, reactor, domain, factory):
        SRVConnector.__init__(self, reactor, 'xmpp-client', domain, factory)


    def pickServer(self):
        host, port = SRVConnector.pickServer(self)

        if not self.servers and not self.orderedServers:
            # no SRV record, fall back..
            port = 5222

        return host, port

class Client(object):
    def __init__(self, client_jid, secret, useBosh=False, bosh_url="http://nk.pl/http-bind"):
        
        self.status = 0
        self.i = 0
        
        if(useBosh):
            auth = XMPPAuthenticator(client_jid, secret)
            f = HTTPBindingStreamFactory(auth)
        else:
            f = client.XMPPClientFactory(client_jid, secret)
         
        f.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self.connected)
        f.addBootstrap(xmlstream.STREAM_END_EVENT, self.disconnected)
        f.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self.authenticated)
        f.addBootstrap(xmlstream.INIT_FAILED_EVENT, self.init_failed)
        if(useBosh):
            connector = HTTPBClientConnector(str(bosh_url))
            connector.connect(f)
        else:
            connector = XMPPClientConnector(reactor, client_jid.host, f)
            connector.connect()

    def setPresence(self, status, message=None):
        #<presence xmlns="jabber:client" type="available"><show>away</show><status>test</status></presence>
        if status == "available" or status == "away" or status == "invisible" or status == "unavailable":
            #presence = domish.Element(('jabber:client', 'presence'), ("type", status))
            presence = domish.Element(('jabber:client', 'presence'))
            presence.addElement('show').addContent(status)
            
            if message != None:
                presence.addElement('status').addContent(message)
            
            self.xmlstream.send(presence)
        else:
            print 'Unknown presence: %s' % (status)

    def rawDataIn(self, buf):
        print "RECV: %s" % unicode(buf, 'utf-8').encode('ascii', 'replace')

    def rawDataOut(self, buf):
        print "SEND: %s" % unicode(buf, 'utf-8').encode('ascii', 'replace')

    def connected(self, xs):
        print 'Connected.'

        self.xmlstream = xs
        
        # Log all traffic
        xs.rawDataInFn = self.rawDataIn
        xs.rawDataOutFn = self.rawDataOut

    def disconnected(self, xs):
        print 'Disconnected.'
        reactor.stop()

    def authenticated(self, xs):
        print "Authenticated."

        presence = domish.Element((None, 'presence'))
        xs.send(presence)

        print 'Add gotMessage callback'
        xs.addObserver('/message', self.gotMessage)
        print 'Add * callback'
        xs.addObserver('/*', self.gotSomething)
        
        self.setPresence('away', 'test')
        self.presenceTicker()

    def init_failed(self, failure):
        print "Initialization failed."
        print failure

        self.xmlstream.sendFooter()

    def gotMessage(self, el):
        print 'Got message: %s' % str(el.attributes)

    def gotSomething(self, el):
        print unicode(str('Got something: %s -> %s' % (el.name, str(el.attributes))), 'utf-8').encode('ascii', 'replace')
        
    def presenceTicker(self):
        if self.status == 0:
            st = 'away'
        else:
            st = 'available'
        reactor.callLater(3, self.setPresence, st, str(self.i))
        self.i += 1

username = None
password = None
domain = None
base = None

def onLoginInfo(base, domain, username, password):
    print base, domain, username, password
    
    client_jid = jid.JID("%s@%s" % (username, domain))
    secret = password
    c = Client(client_jid, secret, True, base)
    username = username
    password = password
    domain = domain
    base = base
    print 'Begin to connect'
    resolv.getFriendsList()
    
def onListDownloaded(friendlist):
    print friendlist


if(__name__ == "__main__"):
    resolv = Resolver('kkszysiu', 'xxxxx')
    resolv.getLoginInfo()
    resolv.onLoginInfo = onLoginInfo
    resolv.onListDownloaded = onListDownloaded

    #log.startLogging(sys.stdout)
    reactor.run()
