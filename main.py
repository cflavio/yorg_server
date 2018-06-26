from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'audio-library-name null')
import sys
from os.path import exists
from os import mkdir
from string import letters
from argparse import ArgumentParser
from logging import basicConfig, DEBUG, getLogger, info
from logging.handlers import TimedRotatingFileHandler
from random import choice, randint
from sleekxmpp import ClientXMPP
from sleekxmpp.jid import JID
from dbfacade import DBFacade
from yyagl.game import Game, GameLogic
from yyagl.engine.configuration import Cfg, GuiCfg, ProfilingCfg, LangCfg, \
    CursorCfg, DevCfg


class User(object):

    def __init__(self, name, is_supporter):
        self.name = name
        self.is_supporter = is_supporter


if not exists('logs'): mkdir('logs')
basicConfig(level=DEBUG, format='%(levelname)-8s %(message)s')
handler = TimedRotatingFileHandler('logs/yorg_server.log', 'midnight')
handler.suffix = '%Y%m%d'
getLogger().addHandler(handler)


class YorgServerLogic(GameLogic):

    def __init__(self, mediator):
        GameLogic.__init__(self, mediator)
        self.jid2usr = {}
        self.registered = []
        self.db = DBFacade()

    def on_start(self):
        GameLogic.on_start(self)
        self.eng.server.start(self.process_msg_srv, self.process_connection)

    def process_msg_srv(self, data_lst, sender):
        print data_lst, sender
        self.eng.server.send([sender.getpeername()[1]], sender)

    def process_connection(self, client_address):
        print 'connection from ' + client_address

    def on_presence_available(self, msg):
        pass
        # info('presence available before: %s %s' % (msg['from'], self.jid2usr.keys()))
        # if msg['from'].bare == self.boundjid.bare: return
        # name = msg['from']
        # for key in self.jid2usr.keys()[:]:
        #     if msg['from'].bare == JID(key).bare and str(msg['from']) != str(key):
        #         del self.jid2usr[key]
        # if name in self.jid2usr: return
        # usr = User(name, self.is_supporter(name), self.is_playing(name))
        # self.jid2usr[name] = usr
        # info('presence available after: %s' % self.jid2usr.keys())

    def on_presence_unavailable(self, msg):
        pass
        # info('presence unavailable before: %s' % self.jid2usr.keys())
        # del self.jid2usr[msg['from']]
        # info('presence unavailable after: %s' % self.jid2usr.keys())

    def on_list_users(self, msg):
        pass
        # supp_pref = lambda name: '1' if self.is_supporter(name) else '0'
        # play_pref = lambda name: '1' if self.is_playing(name) else '0'
        # names = self.jid2usr.keys()
        # names = [
        #     ''.join([supp_pref(name) + play_pref(name) + str(name)])
        #     for name in names]
        # _from = str(msg['from'])
        # if _from not in self.jid2usr:
        #     usr = User(_from, self.is_supporter(_from), self.is_playing(_from))
        #     self.jid2usr[_from] = usr
        # self.send_message(
        #     mfrom='ya2_yorg@jabb3r.org',
        #     mto=msg['from'],
        #     mtype='ya2_yorg',
        #     msubject='list_users',
        #     mbody='\n'.join(names))

    def is_supporter(self, name): return JID(name).bare in self.supp_mgr.list()


class YorgServer(Game):

    def __init__(self):
        init_lst = [[('logic', YorgServerLogic, [self])]]
        conf = Cfg(GuiCfg(), ProfilingCfg(), LangCfg(), CursorCfg(), DevCfg())
        Game.__init__(self, init_lst, conf)


YorgServer().run()
