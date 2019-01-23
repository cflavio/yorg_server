from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'audio-library-name null')
from os.path import exists
from os import mkdir
from string import ascii_letters, digits
from re import match
from logging import info, debug, error
from log import set_log
from random import choice
from yyagl.game import Game, GameLogic
from yyagl.engine.configuration import Cfg, GuiCfg, ProfilingCfg, LangCfg, \
    CursorCfg, DevCfg
from dbfrontend import DBFrontend
from args import set_args
from mail import Mail
from user import User
from room import Room
from states import waiting, sel_track_cars, sel_drivers, race, statename


args = [('--port', {'type': int, 'default': 0}),
        ('--noverbose', {'action': 'store_true'}),
        ('--spam', {'action': 'store_true'})]
args = set_args(args)


set_log('yorg_server', 'info' if args.noverbose else 'debug')


class YorgServerLogic(GameLogic):

    def __init__(self, mediator):
        GameLogic.__init__(self, mediator)
        self.db = DBFrontend('yorg')
        self.mail = Mail()
        self.conn2usr = {}
        self.rooms = []
        taskMgr.add(self.__on_frame, 'on frame')

    def on_start(self):
        GameLogic.on_start(self)
        mths = [self.on_connected, self.on_disconnected]
        list(map(lambda mth: self.eng.server.attach(mth), mths))
        self.eng.server.start(self.process_msg_srv, self.process_connection)
        mths = [
            self.register, self.login, self.reset, self.get_salt,
            self.get_users, self.join_room, self.leave_room, self.invite,
            self.car_request, self.drv_request, self.rm_usr_from_match,
            self.srv_version, self.hosting]
        list(map(lambda mth: self.eng.server.register_rpc(mth), mths))
        info('server started')

    def __on_frame(self, task):
        for room in self.rooms:
            self.evaluate_starting(room)
            self.evaluate_starting_drv(room)
        return task.cont

    @staticmethod
    def on_connected(conn): info('new connection %s' % conn)

    def on_disconnected(self, conn):
        if conn in self.conn2usr: self.__disconnect_usr(conn)  # usr is logged
        else: info('lost connection %s' % conn)
        self.clean()
        self.log_users()
        self.log_rooms()

    def __disconnect_usr(self, conn):
        uid = self.conn2usr[conn].uid
        self.leave_rooms(uid)
        self.eng.server.send(['logout', uid])
        del self.conn2usr[conn]
        info('lost connection %s (%s)' % (conn, uid))

    def srv_version(self, sender): return '0.10.0'

    def register(self, uid, pwd, salt, email, sender):
        debug('registering ' + uid)
        ret = ''
        if not self.valid_nick(uid): ret = 'invalid_nick'
        if not self.valid_email(email): ret = 'invalid_email'
        if uid in self.user_names(): ret = 'already_used_nick'
        if email in self.emails(): ret = 'already_used_email'
        if ret:
            info('register result: ' + ret)
            return ret
        activation_code = self.__rnd_str(8)
        self.db.add(uid, pwd, salt, email, activation_code)
        self.mail.send_mail_activation(uid, email, activation_code)
        info('register ok')
        return 'ok'

    def login(self, uid, pwd, sender):
        debug('login ' + uid)
        ret = ''
        if not self.valid_nick(uid): ret = 'invalid_nick'
        elif uid not in self.user_names(): ret = 'unregistered_nick'
        elif not self.db.login(uid, pwd): ret = 'wrong_pwd'
        if ret:
            info('login result for user %s: %s' % (uid, ret))
            return ret
        usr = User(uid, self.db.supporter(uid))
        self.conn2usr[sender] = usr
        self.eng.server.send(['login', uid, usr.supporter, usr.playing])
        info('user %s logged in - %s' % (uid, sender))
        return 'ok'

    @property
    def users(self): return self.conn2usr.values()

    def reset(self, uid, email, sender):
        ret_val = ''
        if uid not in self.user_names(): ret_val = 'nonick'
        if email not in self.emails(): ret_val = 'nomail'
        if not self.db.exists_user(uid, email): ret_val = 'dontmatch'
        if ret_val:
            info('reset result: ' + ret_val)
            return ret_val
        reset_code = self.__rnd_str(8)
        self.db.add_reset(uid, email, reset_code)
        self.mail.send_mail_reset(uid, email, reset_code)
        return 'ok'

    @staticmethod
    def __rnd_str(lgt):
        return ''.join(choice(ascii_letters + digits) for _ in range(lgt))

    def get_salt(self, uid, sender):
        users_id = [usr for usr in self.db.list('users') if usr.uid == uid]
        return users_id[0].salt if users_id else self.__rnd_str(8)

    @staticmethod
    def valid_nick(nick):
        return all(char in ascii_letters + digits for char in nick)

    @staticmethod
    def valid_email(email): return match(r'[^@]+@[^@]+\.[^@]+', email)

    def user_names(self): return [usr.uid for usr in self.db.list('users')]

    def log_rooms(self):
        info('rooms: {\n'.join(map(self.__log_room, self.rooms)) + '}')

    def __log_room(self, room):
        users = ', '.join([usr.uid for usr in room.users])
        track = '; %s' % room.track if room.track else ''
        state = '(%s%s)' % (statename(room.state), track)
        drv = lambda uid: ':%s' % room.uid2drvidx[uid] \
            if uid in room.uid2drvidx else ''
        cars = ', '.join(['%s->%s%s' %
            (a, b, drv(a)) for a, b in room.uid2car.items()])
        return '%s %s: %s [%s]' % (room.name, state, users, cars)

    def join_room(self, room_name, sender):
        usr = self.conn2usr[sender]
        if room_name not in [room.name for room in self.rooms]:
            self.rooms += [Room(room_name, usr.uid)]
            self.eng.server.send(['update_hosting'])
            debug('send update hosting (new room by %s)' % usr.uid)
        room = self.__room(room_name)
        for _usr in room.users:
            debug('send presence_available_room %s to %s' % (usr.uid, _usr.uid))
            self.eng.server.send(
                ['presence_available_room', usr.uid, room_name],
                self.usr2conn[_usr.uid])
            self.eng.server.send(
                ['presence_available_room', _usr.uid, room_name],
                self.usr2conn[usr.uid])
        room.add_usr(usr)
        self.eng.server.send(['playing', usr.uid, 1])
        info('user %s joined the room %s' % (usr.uid, room_name))
        self.log_rooms()

    def __room(self, room_name):
        return [room for room in self.rooms if room.name == room_name][0]

    def leave_room(self, room_name, sender):
        usr = self.conn2usr[sender]
        room = [room for room in self.rooms if room.name == room_name][0]
        room.rm_usr(usr)
        for _usr in room.users:
            debug('send presence_unavailable_room %s to %s' %
                  (usr.uid, _usr.uid))
            self.eng.server.send(
                ['presence_unavailable_room', usr.uid, room_name],
                self.usr2conn[_usr.uid])
        self.eng.server.send(['playing', usr.uid, 0])
        info('user %s left the room %s' % (usr.uid, room_name))
        if usr.uid == room.srv_usr and room.state == waiting:
            self.eng.server.send(['update_hosting'])
        self.clean()
        self.log_rooms()

    def leave_rooms(self, uid):
        usr = [usr for usr in self.conn2usr.values() if usr.uid == uid][0]
        conn = [conn for conn in self.conn2usr if self.conn2usr[conn] == usr][0]
        for room in self.find_rooms_with_user(uid):
            self.leave_room(room.name, conn)

    def car_request(self, car, sender):
        uid = self.conn2usr[sender].uid
        debug('car request: %s %s' % (uid, car))
        room = self.find_room_with_user(uid, sel_track_cars)
        if car not in room.uid2car.values():
            self.__process_car_req(room, uid, car)
            return 'ok'
        else: return 'ko'

    def __process_car_req(self, room, uid, car):
        if uid in room.uid2car:
            for usr in room.users:
                tmpl = 'car deselection: %s has deselected %s to %s'
                debug(tmpl % (uid, room.uid2car[uid], usr.uid))
                self.eng.server.send(
                    ['car_deselection', room.uid2car[uid]],
                    self.usr2conn[usr.uid])
            tmpl = '%s has deselected the car %s for the room %s'
            info(tmpl % (uid, room.uid2car[uid], room.name))
        room.uid2car[uid] = car
        for usr in room.users:
            tmpl = 'car selection: %s has selected %s to %s'
            debug(tmpl % (uid, car, usr.uid))
            self.eng.server.send(['car_selection', car, uid],
                                 self.usr2conn[usr.uid])
        tmpl = '%s has selected the car %s for the room %s'
        info(tmpl % (uid, car, room.name))
        self.log_rooms()

    def drv_request(self, car, idx, speed, adherence, stability, sender):
        uid = self.conn2usr[sender].uid
        tmpl = 'drv request: %s %s %s %s %s %s'
        debug(tmpl % (uid, car, idx, speed, adherence, stability))
        room = self.find_rooms_with_user(uid, sel_drivers)[0]
        if idx not in room.uid2drvidx.values():
            self.__process_drv_req(room, uid, idx, speed, adherence, stability)
            return 'ok'
        else: return 'ko'

    def __process_drv_req(self, room, uid, idx, speed, adherence, stability):
        if uid in room.uid2drvidx:
            for usr in room.users:
                tmpl = 'driver deselection: %s has deselected %s to %s'
                debug(tmpl % (uid, room.uid2drvidx[uid], usr.uid))
                self.eng.server.send(
                    ['drv_deselection', room.uid2drvidx[uid]],
                    self.usr2conn[usr.uid])
            tmpl = '%s has deselected the driver %s for the room %s'
            info(tmpl % (uid, room.uid2drvidx[uid], room.name))
        room.uid2drvidx[uid] = idx
        room.uid2props[uid] = [idx, speed, adherence, stability]
        for usr in room.users:
            tmpl = 'driver selection: %s has selected %s to %s'
            debug(tmpl % (uid, idx, usr.uid))
            self.eng.server.send(['drv_selection', idx, uid],
                                 self.usr2conn[usr.uid])
        tmpl = '%s has selected the driver %s for the room %s'
        info(tmpl % (uid, idx, room.name))
        self.log_rooms()

    def rm_usr_from_match(self, uid, room_name, sender):
        room = self.__room(room_name)
        rm_usr = [usr for usr in self.users if usr.uid == uid][0]
        for _usr in room.users + ([rm_usr] if rm_usr not in rcv_usr else []):
            debug('send rm_usr_from_match %s to %s' % (uid, _usr.uid))
            self.eng.server.send(['rm_usr_from_match', uid, room_name],
                                 self.usr2conn[_usr.uid])
        usr = [rusr for rusr in room.users if uid == rusr.uid]
        if usr: room.rm_usr(usr[0])  # if the user hasn't accepted yet
        self.eng.server.send(['playing', uid, 0])

    def evaluate_starting(self, room):
        all_chosen = all(uid in room.uid2car for uid in room.users_uid)
        if room.state != sel_track_cars or not all_chosen: return
        room.state = sel_drivers
        packet = ['start_drivers']
        for uid, car in room.uid2car.items(): packet += [uid, car]
        for usr in room.users:
            debug('send: %s to %s' % (packet, usr.uid))
            self.eng.server.send(packet, self.usr2conn[usr.uid])

    def evaluate_starting_drv(self, room):
        all_chosen = all(uid in room.uid2drvidx for uid in room.users_uid)
        if room.state != sel_drivers or not all_chosen: return
        room.state = race
        packet = ['start_race', len(room.uid2drvidx)]
        for uid, drv in room.uid2drvidx.items():
            packet += [room.uid2props[uid][0]] + [room.uid2car[uid]]
            packet += [uid] + room.uid2props[uid][1:]
        for usr in room.users:
            debug('send: %s to %s' % (packet, usr.uid))
            self.eng.server.send(packet, self.usr2conn[usr.uid])

    def log_users(self):
        playing = lambda usr: ' (playing)' if usr.playing else ''
        pusr = lambda usr: '%s%s' % (usr.uid, playing(usr))
        info('users: ' + ', '.join([pusr(usr) for usr in self.users]))

    def get_users(self, sender):
        self.log_users()
        return [[usr.uid, usr.supporter, usr.playing] for usr in self.users]

    def emails(self): return [usr.email for usr in self.db.list('users')]

    def process_msg_srv(self, data_lst, sender):
        if args.spam or data_lst[0] not in ['player_info', 'game_packet']:
            debug('%s %s' % (data_lst, sender))
        if data_lst[0] == 'msg': self.on_msg(*data_lst[1:])
        if data_lst[0] == 'msg_room': self.on_msg_room(*data_lst[1:])
        if data_lst[0] == 'declined': self.on_declined(data_lst[1], data_lst[2])
        if data_lst[0] == 'track_selected':
            self.on_track_selected(*data_lst[1:])
        if data_lst[0] == 'client_ready':
            self.on_client_ready(self.conn2usr[sender].uid)
        if data_lst[0] == 'client_at_countdown':
            self.on_client_at_countdown(self.conn2usr[sender].uid)
        if data_lst[0] == 'player_info': self.on_player_info(data_lst)
        if data_lst[0] == 'game_packet': self.on_game_packet(data_lst)
        if data_lst[0] == 'end_race_player':
            self.on_end_race_player(self.conn2usr[sender].uid)
        if data_lst[0] == 'end_race':
            self.on_end_race(self.conn2usr[sender].uid)
        if data_lst[0] == 'room_start':
            self.on_room_start(self.conn2usr[sender].uid)

    def on_client_ready(self, uid):
        room = self.find_rooms_with_user(uid, race)[0]
        if uid not in room.ready: room.ready += [uid]
        if not all(usr.uid in room.ready for usr in room.users): return
        for usr in room.users:
            debug('begin race: %s' % usr.uid)
            self.eng.server.send(['begin_race'], self.usr2conn[usr.uid])

    def on_player_info(self, data_lst):
        room = self.find_rooms_with_user(data_lst[1], race)[0]
        if args.spam: debug('player_info to server: %s' % data_lst)
        if room.srv_usr not in self.usr2conn: return  # user has quit
        self.eng.server.send(data_lst, self.usr2conn[room.srv_usr])

    def on_game_packet(self, data_lst):
        room = self.find_rooms_with_user(data_lst[1], race)[0]
        for usr in room.users:
            if usr.uid == room.srv_usr: continue
            if args.spam: debug('game_packet to %s: %s' % (usr.uid, data_lst))
            self.eng.server.send(data_lst, self.usr2conn[usr.uid])

    def on_client_at_countdown(self, uid):
        room = self.find_rooms_with_user(uid, race)[0]
        if uid not in room.ready_cd: room.ready_cd += [uid]
        not_ready = not all(usr.uid in room.ready_cd for usr in room.users)
        not_srv_usr = room.srv_usr not in self.usr2conn
        if not_ready or not_srv_usr: return
        for usr in room.users:
            debug('start countdown: %s' % usr.uid)
            self.eng.server.send(['start_countdown'], self.usr2conn[usr.uid])

    def on_declined(self, from_, to):
        self.eng.server.send(['declined', from_], self.usr2conn[to])
        self.find_usr(from_).playing = 0
        self.eng.server.send(['playing', from_, 0])
        info("%s declined %s's invite" % (from_, to))

    def on_end_race_player(self, uid):
        room = self.find_rooms_with_user(uid, race)[0]
        self.find_usr(uid).playing = 0
        self.eng.server.send(['playing', uid, 0])
        info('end race player: %s' % uid)
        self.eng.server.send(['end_race_player', uid],
                             self.usr2conn[room.srv_usr])

    def on_end_race(self, uid):
        room = self.find_rooms_with_user(uid, race)[0]
        for usr in room.users:
            info('end race: %s' % usr.uid)
            self.eng.server.send(['end_race'], self.usr2conn[usr.uid])

    def find_room(self, room_name):
        rooms = [room for room in self.rooms if room.name == room_name]
        if rooms: return rooms[0]

    def find_room_with_user(self, uid, state=None):
        return self.find_rooms_with_user(uid, state)[0]

    def find_rooms_with_user(self, uid, state=None):
        rooms = []
        debug('looking  for user %s, state %s' % (uid, state))
        if not args.noverbose: self.log_rooms()
        for room in self.rooms:
            tmpl = 'room %s: state: %s, users: %s'
            debug(tmpl % (room.name, room.state, room.users_uid))
            if state is not None and room.state != state: continue
            if uid in room.users_uid: rooms += [room]
        debug('found rooms: %s' % rooms)
        return rooms

    @property
    def usr2conn(self):
        return {usr.uid: conn for conn, usr in self.conn2usr.items()}

    def on_msg(self, from_, to, msg):
        self.eng.server.send(['msg', from_, to, msg], self.usr2conn[to])

    def on_msg_room(self, from_, to, msg):
        room = self.find_room(to)
        for usr in room.users:
            self.eng.server.send(['msg_room', from_, to, msg],
                                 self.usr2conn[usr.uid])

    def on_track_selected(self, track, room):
        room = self.find_room(room)
        room.track = track
        for usr in room.users:
            debug('send %s to %s' % (track, usr.uid))
            self.eng.server.send(['track_selected', track],
                                 self.usr2conn[usr.uid])
        tmpl = '%s has selected the track %s for the room %s'
        info(tmpl % (room.srv_usr, track, room.name))
        self.log_rooms()

    def find_usr(self, uid):
        return [usr for usr in self.conn2usr.values() if usr.uid == uid][0]

    def invite(self, to, room_name, sender):
        usr = self.find_usr(to)
        if usr.playing: return 'ko'
        usr.playing = True
        self.eng.server.send(['playing', to, 1])
        from_ = self.conn2usr[sender].uid
        info('%s invited %s in the room %s' % (from_, to, room_name))
        self.eng.server.send(['invite_chat', from_, to, room_name],
                             self.usr2conn[to])
        return 'ok'

    @staticmethod
    def process_connection(client_address):
        info('connection from %s' % client_address)

    def clean(self):
        list(map(self.__clean_room, self.rooms[:]))

    def __clean_room(self, room):
        for usr in room.users[:]:
            if usr not in self.conn2usr.values(): room.users.remove(usr)
        if room.empty: self.rooms.remove(room)

    def hosting(self, sender):
        return [room.name for room in self.rooms if room.state==waiting]

    def on_room_start(self, uid):
        room = self.find_room_with_user(uid)
        debug('room %s start (%s)' % (room.name, uid))
        room.state = sel_track_cars
        self.eng.server.send(['update_hosting'])


class YorgServer(Game):

    def __init__(self):
        info('starting the server; using the port %s' % args.port)
        dev_cfg = DevCfg(port=args.port) if args.port else DevCfg()
        init_lst = [[('logic', YorgServerLogic, [self])]]
        conf = Cfg(GuiCfg(), ProfilingCfg(), LangCfg(), CursorCfg(), dev_cfg)
        Game.__init__(self, init_lst, conf)

    def kill(self):
        list(map(lambda obj: obj.destroy(), [self.eng.server, self.eng.client]))
        info('killed the server')


if __name__ == '__main__':
    yorg_srv = YorgServer()
    try: yorg_srv.run()
    except Exception as exc:
        #import traceback; traceback.print_exc()
        #with open('logs/yorg_server.log', 'a') as f:
        #    import traceback; traceback.print_exc(file=f)
        error('Error', exc_info=True)
        yorg_srv.kill()
