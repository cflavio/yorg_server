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
from supporters import SupporterMgr
import direct.directbase.DirectStart


if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')


class User(object):

    def __init__(self, name, is_supporter, is_playing):
        self.name = name
        self.is_supporter = is_supporter
        self.is_playing = is_playing
        self.last_seen = globalClock.get_frame_time()


class YorgServer(ClientXMPP):

    def __init__(self, jid, pwd):
        ClientXMPP.__init__(self, jid, pwd)
        self.jid2usr = {}
        self.fake_users = []
        self.registered = []
        self.supp_mgr = None
        evt_info = [
            ('session_start', self.start),
            ('message', self.on_message),
            ('presence_available', self.on_presence_available),
            ('presence_unavailable', self.on_presence_unavailable)]
        map(lambda args: self.add_event_handler(*args), evt_info)
        rnd_char = lambda: choice(letters)
        rnd_name = lambda: ''.join([rnd_char() for _ in range(randint(3, 12))])
        rnd_id = lambda: '%s@%s.%s' % (rnd_name(), rnd_name(), rnd_name())
        fake_users_names = [rnd_id() for _ in range(randint(30, 50))]
        fake_users_names = []  # uncomment this so don't use fake names
        self.fake_users = [
            User(name, self.is_supporter(name), self.is_playing(name))
            for name in fake_users_names]

    def register(self, msg): self.registered += [msg]

    def unregister(self, msg): self.registered.remove(msg)

    def is_registered(self, msg): return msg in self.registered

    def start(self, xmpp_evt):
        self.supp_mgr = SupporterMgr()  # we must create it in xmpp's thread
        self.send_presence()
        self.get_roster()
        messages = ['list_users', 'query_full', 'is_playing', 'answer_full']
        map(self.register, messages)

    def on_presence_available(self, msg):
        if msg['from'].bare == self.boundjid.bare: return
        name = msg['from']
        if name in self.jid2usr: return
        usr = User(name, self.is_supporter(name), self.is_playing(name))
        self.jid2usr[name] = usr

    def on_presence_unavailable(self, msg): del self.jid2usr[msg['from']]

    def on_list_users(self, msg):
        supp_pref = lambda name: '1' if self.is_supporter(name) else '0'
        play_pref = lambda name: '1' if self.is_playing(name) else '0'
        fake_names = [usr.name for usr in self.fake_users]
        names = self.jid2usr.keys() + fake_names
        names = [
            ''.join([supp_pref(name) + play_pref(name) + str(name)])
            for name in names]
        _from = str(msg['from'])
        if _from not in self.jid2usr:
            usr = User(_from, self.is_supporter(_from), self.is_playing(_from))
            self.jid2usr[_from] = usr
        self.send_message(
            mfrom='ya2_yorg@jabb3r.org',
            mto=msg['from'],
            mtype='ya2_yorg',
            msubject='list_users',
            mbody='\n'.join(names))

    def on_is_playing(self, msg):
        self.jid2usr[msg['from']].is_playing = int(msg['body'])

    def on_query_full(self, msg):
        self.send_message(
            mfrom=self.boundjid.full,
            mto=msg['from'],
            mtype='ya2_yorg',
            msubject='answer_full',
            mbody=self.boundjid.full)

    def on_message(self, msg):
        info('MESSAGE: ' + str(msg))
        msg2cb = {
            'list_users': self.on_list_users,
            'query_full': self.on_query_full,
            'is_playing': self.on_is_playing,
            'answer_full': lambda msg: None}
        msg2cb[msg['subject']](msg)

    def is_supporter(self, name): return JID(name).bare in self.supp_mgr.list()

    def is_playing(self, name):
        return any(usr.is_playing for jid, usr in self.jid2usr.items()
                   if JID(name).bare == JID(jid).bare)

if not exists('logs'): mkdir('logs')
basicConfig(level=DEBUG, format='%(levelname)-8s %(message)s')
handler = TimedRotatingFileHandler('logs/yorg_server.log', 'midnight')
handler.suffix = '%Y%m%d'
getLogger().addHandler(handler)

parser = ArgumentParser()
map(parser.add_argument, ['usr', 'pwd'])
args = parser.parse_args()

yorg_srv = YorgServer(args.usr, args.pwd)
plugins = [30, 4, 60, 199]  # service disco, data forms, pubsub, ping
map(yorg_srv.register_plugin, ['xep_' + '%04d' % plg for plg in plugins])
if yorg_srv.connect(): yorg_srv.process(block=False)
base.run()
