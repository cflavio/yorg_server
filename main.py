from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'audio-library-name null')
import sys
from os.path import exists
from os import mkdir
from string import ascii_letters, digits
from re import match
from smtplib import SMTP
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
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


mail_content = \
    'Hi! Thank you for subscribing Yorg!\n\nIn order to activate your ' + \
    'account, you have to click the following link:\n\n' + \
    'http://yorg.ya2tech.it/activate.html?uid={uid}&activation_code={activation_code}' + \
    '\n\nAfter that, you can login to your account. Thank you so much!\n\n' + \
    "Yorg's team"


class MailSender(object):

    def __init__(self):
        self.server = None
        self.connect()

    def connect(self):
        self.server = SMTP('mail.ya2.it', 2525)
        self.server.starttls()
        with open('pwd.txt') as f: pwd = f.read().strip()
        self.server.login('noreply@ya2.it', pwd)

    def send_mail(self, uid, email, activation_code):
        if not self.is_connected(): self.connect()
        msg = MIMEMultipart()
        msg['From'] = 'noreply@ya2.it'
        msg['To'] = email
        msg['Subject'] = 'Yorg: activation of the user ' + uid
        body = mail_content.format(uid=uid, activation_code=activation_code)
        msg.attach(MIMEText(body, 'plain'))
        self.server.sendmail('noreply@ya2.it', email, msg.as_string())

    def is_connected(self):
        try: status = self.server.noop()[0]
        except: status = None
        return status == 250

    def destroy(self):
        self.server.quit()
        self.server = None


class YorgServerLogic(GameLogic):

    def __init__(self, mediator):
        GameLogic.__init__(self, mediator)
        self.jid2usr = {}
        self.registered = []
        self.db = DBFacade()
        self.mail_sender = MailSender()

    def on_start(self):
        GameLogic.on_start(self)
        self.eng.server.start(self.process_msg_srv, self.process_connection)
        self.eng.server.register_rpc(self.register)
        self.eng.server.register_rpc(self.get_salt)

    def register(self, uid, pwd, salt, email, sender):
        if not self.valid_nick(uid): return 'invalid_nick'
        if not self.valid_email(email): return 'invalid_email'
        if uid in self.users(): return 'already_used_nick'
        if email in self.emails(): return 'already_used_email'
        activation_code = self.__rnd_seq(8)
        self.db.add(uid, pwd, salt, email, activation_code)
        self.mail_sender.send_mail(uid, email, activation_code)
        return 'ok'

    def __rnd_seq(self, length):
        return ''.join(choice(ascii_letters + digits) for i in range(length))

    def get_salt(self, uid, sender):
        users_id = [usr for usr in self.users() if usr[0] == uid]
        if users_id: return users_id[0][2]
        return self.__rnd_seq(8)

    def valid_nick(self, nick):
        return all(char in ascii_letters + digits for char in nick)

    def valid_email(self, email):
        return match(r'[^@]+@[^@]+\.[^@]+', email)

    def users(self):
        users, activations = self.db.list()
        _users = []
        if users: _users = [usr[0] for usr in users]
        return _users

    def emails(self):
        users, activations = self.db.list()
        emails = []
        if users: emails = [usr[3] for usr in users]
        return emails

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
        parser = ArgumentParser()
        parser.add_argument('--port', type=int, default=0)
        args = parser.parse_args()
        dev_cfg = DevCfg(port=args.port) if args.port else DevCfg()
        init_lst = [[('logic', YorgServerLogic, [self])]]
        conf = Cfg(GuiCfg(), ProfilingCfg(), LangCfg(), CursorCfg(), dev_cfg)
        Game.__init__(self, init_lst, conf)


YorgServer().run()
