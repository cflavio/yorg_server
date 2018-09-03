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
from logging import basicConfig, DEBUG, INFO, getLogger, info, debug
from logging.handlers import TimedRotatingFileHandler
from random import choice, randint
from dbfacade import DBFacade
from yyagl.game import Game, GameLogic
from yyagl.engine.configuration import Cfg, GuiCfg, ProfilingCfg, LangCfg, \
    CursorCfg, DevCfg


start, sel_drivers, race = range(3)

class User(object):

    def __init__(self, uid, is_supporter):
        self.uid = uid
        self.is_supporter = is_supporter
        self.is_playing = False


parser = ArgumentParser()
parser.add_argument('--port', type=int, default=0)
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--spam', action='store_true')
args = parser.parse_args()


if not exists('logs'): mkdir('logs')
log_level = DEBUG if args.verbose else INFO
basicConfig(level=log_level, format='%(levelname)-8s %(message)s')
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

    def __init__(self, name, srv_usr):
        self.name = name
        self.srv_usr = srv_usr
        self.users = []
        self.ready = []
        self.ready_cd = []
        self.car_mapping = {}
        self.drv_mapping = {}
        self.drivers = {}
        self.state = start
        self.curr_track = ''

    def add_usr(self, usr): self.users += [usr]

    def rm_usr(self, usr):
        if usr in self.users: self.users.remove(usr)
        else: debug('user %s already removed' % usr.uid)  # it may happen on user's removal

    @property
    def users_uid(self): return [usr.uid for usr in self.users]

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
        taskMgr.add(self.on_frame, 'on frame')

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
        self.eng.server.register_rpc(self.leave_room)
        self.eng.server.register_rpc(self.invite)
        self.eng.server.register_rpc(self.car_request)
        self.eng.server.register_rpc(self.drv_request)
        self.eng.server.register_rpc(self.rm_usr_from_match)
        info('server started')

    def on_frame(self, task):
        for room in self.rooms:
            self.evaluate_starting(room)
            self.evaluate_starting_drv(room)
        return task.cont

    def on_connected(self, conn):
        info('new connection %s' % conn)

    def on_disconnected(self, conn):
        uid = self.conn2usr[conn].uid
        self.leave_rooms(uid)
        self.eng.server.send(['logout', uid])
        del self.conn2usr[conn]
        info('lost connection %s (%s)' % (conn, uid))
        self.log_users()
        self.log_rooms()

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
        self.eng.server.send(['login', uid, usr.is_supporter, usr.is_playing])
        info('user %s logged in - %s' % (uid, sender))
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

    def log_rooms(self):
        msg = 'rooms: {'
        rooms_str = []
        for room in self.rooms:
            users = ', '.join([usr.uid for usr in room.users])
            track_str = '; %s' % room.curr_track if room.curr_track else ''
            state2str = {start: 'start', sel_drivers: 'sel_drivers', race: 'race'}
            state_str = '(%s%s)' % (state2str[room.state], track_str)
            drv = lambda uid: ':%s' % room.drv_mapping[uid] if uid in room.drv_mapping else ''
            cars = ', '.join(['%s->%s%s' % (a, b, drv(a)) for a, b in room.car_mapping.items()])
            rooms_str += ['%s %s: %s [%s]' % (room.name, state_str, users, cars)]
        msg += '\n'.join(rooms_str) + '}'
        info(msg)

    def join_room(self, room_name, sender):
        usr = self.conn2usr[sender]
        if room_name not in [room.name for room in self.rooms]:
            self.rooms += [Room(room_name, usr.uid)]
        room = [room for room in self.rooms if room.name == room_name][0]
        for _usr in room.users:
            debug('send presence_available_room %s to %s' % (usr.uid, _usr.uid))
            self.eng.server.send(['presence_available_room', usr.uid, room_name], self.usr2conn[_usr.uid])
            self.eng.server.send(['presence_available_room', _usr.uid, room_name], self.usr2conn[usr.uid])
        room.add_usr(usr)
        self.eng.server.send(['is_playing', usr.uid, 1])
        info('user %s joined the room %s' % (usr.uid, room_name))
        self.log_rooms()

    def leave_room(self, room_name, sender):
        self._leave_room(room_name, self.conn2usr[sender])

    def _leave_room(self, room_name, usr):
        room = [room for room in self.rooms if room.name == room_name][0]
        room.rm_usr(usr)
        for _usr in room.users:
            debug('send presence_unavailable_room %s to %s' % (usr.uid, _usr.uid))
            self.eng.server.send(['presence_unavailable_room', usr.uid, room_name], self.usr2conn[_usr.uid])
        self.eng.server.send(['is_playing', usr.uid, 0])
        info('user %s left the room %s' % (usr.uid, room_name))
        self.log_rooms()

    def leave_rooms(self, uid):
        usr = [usr for usr in self.conn2usr.values() if usr.uid == uid][0]
        for room in self.find_rooms_with_user(uid):
            self._leave_room(room.name, usr)

    def car_request(self, car, sender):
        uid = self.conn2usr[sender].uid
        debug('car request: %s %s' % (uid, car))
        room = self.find_rooms_with_user(uid, 0)[0]
        if car not in room.car_mapping.values():
            if uid in room.car_mapping:
                for usr in room.users:
                    debug('car deselection: %s has deselected %s to %s' % (uid, room.car_mapping[uid], usr.uid))
                    self.eng.server.send(['car_deselection', room.car_mapping[uid]], self.usr2conn[usr.uid])
                info('%s has deselected the car %s for the room %s' % (uid, room.car_mapping[uid], room.name))
            room.car_mapping[uid] = car
            for usr in room.users:
                debug('car selection: %s has selected %s to %s' % (uid, car, usr.uid))
                self.eng.server.send(['car_selection', car, uid], self.usr2conn[usr.uid])
            info('%s has selected the car %s for the room %s' % (uid, car, room.name))
            self.log_rooms()
            return 'ok'
        else:
            return 'ko'

    def drv_request(self, car, i, speed, adherence, stability, sender):
        uid = self.conn2usr[sender].uid
        debug('drv request: %s %s %s %s %s %s' % (uid, car, i, speed, adherence, stability))
        room = self.find_rooms_with_user(uid, 1)[0]
        if i not in room.drv_mapping.values():
            if uid in room.drv_mapping:
                for usr in room.users:
                    debug('driver deselection: %s has deselected %s to %s' % (uid, room.drv_mapping[uid], usr.uid))
                    self.eng.server.send(['drv_deselection', room.drv_mapping[uid]], self.usr2conn[usr.uid])
                info('%s has deselected the driver %s for the room %s' % (uid, room.drv_mapping[uid], room.name))
            room.drv_mapping[uid] = i
            room.drivers[uid] = [i, speed, adherence, stability]
            for usr in room.users:
                debug('driver selection: %s has selected %s to %s' % (uid, i, usr.uid))
                self.eng.server.send(['drv_selection', i, uid], self.usr2conn[usr.uid])
            info('%s has selected the driver %s for the room %s' % (uid, i, room.name))
            self.log_rooms()
            return 'ok'
        else:
            return 'ko'

    def rm_usr_from_match(self, usr_uid, room_name, sender):
        room = [room for room in self.rooms if room.name == room_name][0]
        rm_usr = [usr for usr in self.current_users if usr.uid == usr_uid][0]
        rcv_usr = room.users
        if rm_usr not in rcv_usr: rcv_usr += [rm_usr]
        for _usr in rcv_usr:
            debug('send rm_usr_from_match %s to %s' % (usr_uid, _usr.uid))
            self.eng.server.send(['rm_usr_from_match', usr_uid, room_name], self.usr2conn[_usr.uid])
        usr = None
        for _usr in room.users:
            if usr_uid == _usr.uid:
                usr = _usr
        if usr: room.rm_usr(usr)  # if the user hasn't accepted yet
        self.eng.server.send(['is_playing', usr_uid, 0])

    def evaluate_starting(self, room):
        if room.state != start or not all(uid in room.car_mapping for uid in room.users_uid): return
        room.state = sel_drivers
        packet = ['start_drivers']
        for uid, car in room.car_mapping.items():
            packet += [uid, car]
        for usr in room.users:
            debug('send: %s to %s' % (packet, usr.uid))
            self.eng.server.send(packet, self.usr2conn[usr.uid])

    def evaluate_starting_drv(self, room):
        if room.state != sel_drivers or not all(uid in room.drv_mapping for uid in room.users_uid): return
        room.state = race
        packet = ['start_race', len(room.drv_mapping)]
        for uid, drv in room.drv_mapping.items():
            packet += [room.drivers[uid][0]] + [room.car_mapping[uid]] + [uid] + room.drivers[uid][1:]
        for usr in room.users:
            debug('send: %s to %s' % (packet, usr.uid))
            self.eng.server.send(packet, self.usr2conn[usr.uid])

    def log_users(self):
        is_playing = lambda usr: ' (playing)' if usr.is_playing else ''
        users_str = ', '.join(['%s%s' % (usr.uid, is_playing(usr)) for usr in self.current_users])
        info('users: %s' % users_str)

    def get_users(self, sender):
        self.log_users()
        return [[usr.uid, usr.is_supporter, usr.is_playing] for usr in self.current_users]

    def emails(self):
        users, activations, reset = self.db.list()
        emails = []
        if users: emails = [usr[3] for usr in users]
        return emails

    def process_msg_srv(self, data_lst, sender):
        if args.spam or data_lst[0] not in ['player_info', 'game_packet']:
            debug('%s %s' % (data_lst, sender))
        #self.eng.server.send([sender.getpeername()[1]], sender)
        if data_lst[0] == 'msg':
            self.on_msg(*data_lst[1:])
        if data_lst[0] == 'msg_room':
            self.on_msg_room(*data_lst[1:])
        if data_lst[0] == 'declined':
            self.on_declined(data_lst[1], data_lst[2])
        if data_lst[0] == 'track_selected':
            self.on_track_selected(*data_lst[1:])
        if data_lst[0] == 'client_ready':
            self.on_client_ready(self.conn2usr[sender].uid)
        if data_lst[0] == 'client_at_countdown':
            self.on_client_at_countdown(self.conn2usr[sender].uid)
        if data_lst[0] == 'player_info':
            self.on_player_info(data_lst)
        if data_lst[0] == 'game_packet':
            self.on_game_packet(data_lst)
        if data_lst[0] == 'end_race_player':
            self.on_end_race_player(self.conn2usr[sender].uid)
        if data_lst[0] == 'end_race':
            self.on_end_race(self.conn2usr[sender].uid)

    def on_client_ready(self, uid):
        room = self.find_rooms_with_user(uid, 2)[0]
        if uid not in room.ready: room.ready += [uid]
        if all(usr.uid in room.ready for usr in room.users):
            for usr in room.users:
                debug('begin race: %s' % usr.uid)
                self.eng.server.send(['begin_race'], self.usr2conn[usr.uid])

    def on_player_info(self, data_lst):
        room = self.find_rooms_with_user(data_lst[1], 2)[0]
        if args.spam: debug('player_info to server: %s' % data_lst)
        if room.srv_usr not in self.usr2conn: return  # usr has quit
        self.eng.server.send(data_lst, self.usr2conn[room.srv_usr])

    def on_game_packet(self, data_lst):
        room = self.find_rooms_with_user(data_lst[1], 2)[0]
        for usr in room.users:
            if usr.uid == room.srv_usr: continue
            if args.spam: debug('game_packet to %s: %s' % (usr.uid, data_lst))
            self.eng.server.send(data_lst, self.usr2conn[usr.uid])

    def on_client_at_countdown(self, uid):
        room = self.find_rooms_with_user(uid, 2)[0]
        if uid not in room.ready_cd: room.ready_cd += [uid]
        if all(usr.uid in room.ready_cd for usr in room.users) and \
                room.srv_usr in self.usr2conn:
            for usr in room.users:
                debug('start countdown: %s' % usr.uid)
                self.eng.server.send(['start_countdown'], self.usr2conn[usr.uid])

    def on_declined(self, from_, to):
        self.eng.server.send(['declined', from_], self.usr2conn[to])
        self.find_usr(from_).is_playing = 0
        self.eng.server.send(['is_playing', from_, 0])
        info("%s declined %s's invite" % (from_, to))

    def on_end_race_player(self, uid):
        room = self.find_rooms_with_user(uid, 2)[0]
        info('end race player: %s' % uid)
        self.eng.server.send(['end_race_player', uid], self.usr2conn[room.srv_usr])

    def on_end_race(self, uid):
        room = self.find_rooms_with_user(uid, 2)[0]
        for usr in room.users:
            info('end race: %s' % usr.uid)
            self.eng.server.send(['end_race'], self.usr2conn[usr.uid])

    def find_room(self, room_name):
        for room in self.rooms:
            if room.name == room_name: return room

    def find_rooms_with_user(self, uid, state=None):
        rooms = []
        for room in self.rooms:
            if state is not None and room.state != state: continue
            if uid in room.users_uid: rooms += [room]
        return rooms

    @property
    def usr2conn(self):
        return {usr.uid: conn for conn, usr in self.conn2usr.iteritems()}

    def on_msg(self, from_, to, txt):
        self.eng.server.send(['msg', from_, to, txt], self.usr2conn[to])

    def on_msg_room(self, from_, to, txt):
        room = self.find_room(to)
        for usr in room.users:
            self.eng.server.send(['msg_room', from_, to, txt], self.usr2conn[usr.uid])

    def on_track_selected(self, track, room):
        room = self.find_room(room)
        room.curr_track = track
        for usr in room.users:
            self.eng.server.send(['track_selected', track], self.usr2conn[usr.uid])
        info('%s has selected the track %s for the room %s' % (room.srv_usr, track, room.name))
        self.log_rooms()

    def find_usr(self, uid):
        return [usr for usr in self.conn2usr.values() if usr.uid == uid][0]

    def invite(self, to, room_name, sender):
        usr = self.find_usr(to)
        if usr.is_playing: return 'ko'
        usr.is_playing = True
        self.eng.server.send(['is_playing', to, 1])
        from_ = self.conn2usr[sender].uid
        info('%s invited %s in the room %s' % (from_, to, room_name))
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
        info('starting the server; using the port %s' % args.port)
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
