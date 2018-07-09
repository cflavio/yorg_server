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
from logging import basicConfig, DEBUG, getLogger, info, debug
from logging.handlers import TimedRotatingFileHandler
from random import choice, randint
from sleekxmpp import ClientXMPP
from sleekxmpp.jid import JID
from dbfacade import DBFacade
from yyagl.game import Game, GameLogic
from yyagl.engine.configuration import Cfg, GuiCfg, ProfilingCfg, LangCfg, \
    CursorCfg, DevCfg


class User(object):

    def __init__(self, uid, is_supporter):
        self.uid = uid
        self.is_supporter = is_supporter
        self.is_playing = False


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


mail_reset_content = \
    'Hi {uid}!\n\nPlease go here and insert your new password:\n\n' + \
    'http://yorg.ya2tech.it/reset.html?uid={uid}&reset_code={reset_code}' + \
    "\n\nThank you so much!\n\nYorg's team"


class MailSender(object):

    def __init__(self):
        self.server = None
        self.connect()

    def connect(self):
        self.server = SMTP('mail.ya2.it', 2525)
        self.server.starttls()
        with open('pwd.txt') as f: pwd = f.read().strip()
        self.server.login('noreply@ya2.it', pwd)
        debug('connected to the smtp server')

    def _send_mail(self, email, subj, body):
        if not self.is_connected(): self.connect()
        msg = MIMEMultipart()
        msg['From'] = 'noreply@ya2.it'
        msg['To'] = email
        msg['Subject'] = subj
        msg.attach(MIMEText(body, 'plain'))
        self.server.sendmail('noreply@ya2.it', email, msg.as_string())
        info('sent email to %s: %s' % (email, subj))

    def send_mail(self, uid, email, activation_code):
        subj = 'Yorg: activation of the user ' + uid
        body = mail_content.format(uid=uid, activation_code=activation_code)
        self._send_mail(email, subj, body)

    def send_mail_reset(self, uid, email, reset_code):
        subj = "Yorg: %s's password reset" % uid
        body = mail_reset_content.format(uid=uid, reset_code=reset_code)
        self._send_mail(email, subj, body)

    def is_connected(self):
        try: status = self.server.noop()[0]
        except: status = None
        return status == 250

    def destroy(self):
        self.server.quit()
        self.server = None


class Room(object):

    def __init__(self, name):
        self.name = name
        self.users = []

    def add_usr(self, uid): self.users += [uid]

    @property
    def is_empty(self): return not self.users


class YorgServerLogic(GameLogic):

    def __init__(self, mediator):
        GameLogic.__init__(self, mediator)
        self.jid2usr = {}
        self.registered = []
        self.db = DBFacade()
        self.mail_sender = MailSender()
        self.conn2usr = {}
        self.rooms = []
        taskMgr.doMethodLater(60, self.clean, 'clean')

    def on_start(self):
        GameLogic.on_start(self)
        self.eng.server.attach(self.on_connected)
        self.eng.server.attach(self.on_disconnected)
        self.eng.server.start(self.process_msg_srv, self.process_connection)
        self.eng.server.register_rpc(self.register)
        self.eng.server.register_rpc(self.login)
        self.eng.server.register_rpc(self.reset)
        self.eng.server.register_rpc(self.get_salt)
        self.eng.server.register_rpc(self.get_users)
        self.eng.server.register_rpc(self.join_room)
        self.eng.server.register_rpc(self.invite)
        info('server started')

    def on_connected(self, conn):
        info('new connection %s' % conn)

    def on_disconnected(self, conn):
        self.eng.server.send(['logout', self.conn2usr[conn].uid])
        del self.conn2usr[conn]
        info('lost connection %s' % conn)

    def register(self, uid, pwd, salt, email, sender):
        debug('registering ' + uid)
        ret_val = ''
        if not self.valid_nick(uid): ret_val = 'invalid_nick'
        if not self.valid_email(email): ret_val = 'invalid_email'
        if uid in self.user_names(): ret_val = 'already_used_nick'
        if email in self.emails(): ret_val = 'already_used_email'
        if ret_val:
            info('register result: ' + ret_val)
            return ret_val
        activation_code = self.__rnd_seq(8)
        self.db.add(uid, pwd, salt, email, activation_code)
        self.mail_sender.send_mail(uid, email, activation_code)
        info('register ok')
        return 'ok'

    def login(self, uid, pwd, sender):
        debug('login ' + uid)
        ret_val = ''
        if not self.valid_nick(uid): ret_val = 'invalid_nick'
        elif uid not in self.user_names(): ret_val = 'unregistered_nick'
        elif not self.db.login(uid, pwd): ret_val = 'wrong_pwd'
        if ret_val:
            info('login result: ' + ret_val)
            return ret_val
        usr = User(uid, self.db.is_supporter(uid))
        self.conn2usr[sender] = usr
        info('user %s - %s' % (uid, sender))
        self.eng.server.send(['login', uid, usr.is_supporter, usr.is_playing])
        info('login ok')
        return 'ok'

    @property
    def current_users(self): return self.conn2usr.values()

    def reset(self, uid, email, sender):
        ret_val = ''
        if uid not in self.user_names(): ret_val = 'nonick'
        if email not in self.emails(): ret_val = 'nomail'
        if not self.db.is_user(uid, email): ret_val = 'dontmatch'
        if ret_val:
            info('reset result: ' + ret_val)
            return ret_val
        reset_code = self.__rnd_seq(8)
        self.db.add_reset(uid, email, reset_code)
        self.mail_sender.send_mail_reset(uid, email, reset_code)
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

    def user_names(self):
        users, activations, reset = self.db.list()
        _users = []
        if users: _users = [usr[0] for usr in users]
        return _users

    def users(self):
        users, activations, reset = self.db.list()
        return users

    def join_room(self, room_name, sender):
        usr = self.conn2usr[sender]
        if room_name not in [room.name for room in self.rooms]:
            self.rooms += [Room(room_name)]
        room = [room for room in self.rooms if room.name == room_name][0]
        for _usr in room.users:
            debug('send presence_available_room %s to %s' % (usr.uid, _usr.uid))
            self.eng.server.send(['presence_available_room', usr.uid, room_name], self.usr2conn[_usr.uid])
        room.add_usr(usr)
        self.eng.server.send(['is_playing', usr.uid, 1])

    def get_users(self, sender):
        debug(self.current_users)
        return [[usr.uid, usr.is_supporter, usr.is_playing] for usr in self.current_users]

    def emails(self):
        users, activations, reset = self.db.list()
        emails = []
        if users: emails = [usr[3] for usr in users]
        return emails

    def process_msg_srv(self, data_lst, sender):
        info('%s %s' % (data_lst, sender))
        #self.eng.server.send([sender.getpeername()[1]], sender)
        if data_lst[0] == 'msg':
            self.on_msg(*data_lst[1:])
        if data_lst[0] == 'msg_room':
            self.on_msg_room(*data_lst[1:])
        if data_lst[0] == 'declined':
            self.on_declined(data_lst[1], data_lst[2])

    def on_declined(self, from_, to):
        self.eng.server.send(['declined', from_], self.usr2conn[to])
        self.find_usr(from_).is_playing = 0
        self.eng.server.send(['is_playing', from_, 0])

    def find_room(self, room_name):
        for room in self.rooms:
            if room.name == room_name: return room

    @property
    def usr2conn(self):
        return {usr.uid: conn for conn, usr in self.conn2usr.iteritems()}

    def on_msg(self, from_, to, txt):
        self.eng.server.send(['msg', from_, to, txt], self.usr2conn[to])

    def on_msg_room(self, from_, to, txt):
        room = self.find_room(to)
        for usr in room.users:
            self.eng.server.send(['msg_room', from_, to, txt], self.usr2conn[usr.uid])

    def find_usr(self, uid):
        return [usr for usr in self.conn2usr.values() if usr.uid == uid][0]

    def invite(self, to, room_name, sender):
        usr = self.find_usr(to)
        if usr.is_playing: return 'ko'
        usr.is_playing = True
        self.eng.server.send(['is_playing', to, 1])
        from_ = self.conn2usr[sender].uid
        debug('invite %s %s %s' % (from_, to, room_name))
        self.eng.server.send(['invite_chat', from_, to, room_name], self.usr2conn[to])
        return 'ok'

    def process_connection(self, client_address):
        info('connection from %s' % client_address)

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

    def clean(self, task):
        for room in self.rooms[:]:
            if room.is_empty:
                self.rooms.remove(room)
        return task.again


class YorgServer(Game):

    def __init__(self):
        info('starting the server')
        parser = ArgumentParser()
        parser.add_argument('--port', type=int, default=0)
        args = parser.parse_args()
        info('using the port %s' % args.port)
        dev_cfg = DevCfg(port=args.port) if args.port else DevCfg()
        init_lst = [[('logic', YorgServerLogic, [self])]]
        conf = Cfg(GuiCfg(), ProfilingCfg(), LangCfg(), CursorCfg(), dev_cfg)
        Game.__init__(self, init_lst, conf)

    def kill(self):
        self.eng.server.destroy()
        self.eng.client.destroy()
        info('killed the server')


if __name__ == '__main__':
    yorg_srv = YorgServer()
    try:
        yorg_srv.run()
    except Exception as e:
        import traceback; traceback.print_exc()
        with open('logs/yorg_server.log', 'a') as f:
            import traceback; traceback.print_exc(file=f)
        yorg_srv.kill()
