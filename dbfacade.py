from argparse import ArgumentParser
from logging import info, debug
from sqlite3 import connect
from pprint import pprint
from datetime import date, datetime
from random import choice
from string import ascii_letters, digits
from hashlib import sha512


class DBFacade(object):

    def __init__(self):
        debug('creating db facade')
        self.conn = connect('yorg.db')
        self.cur = self.conn.cursor()
        user_columns = [
            'uid text primary key', 'pwd text', 'salt text', 'email text',
            'is_supporter integer', 'reg_date text', 'last_access text']
        activation_columns = [
            'uid text primary key', 'activation text']
        reset_columns = [
            'uid text primary key', 'email text', 'reset text']
        _info = [('users', user_columns), ('activation', activation_columns),
                 ('reset', reset_columns)]
        for table, columns in _info:
            columns = ', '.join(columns)
            query = 'CREATE TABLE if not exists %s (%s)' % (table, columns)
            self.__sql(query, True)

    def __sql(self, cmd, commit=False):
        if type(cmd) in [str, unicode]: cmd = [cmd]
        debug('sql (commit: %s): %s' % (commit, cmd))
        self.cur.execute(*cmd)
        if commit: self.conn.commit()

    def list(self, _print=False):
        ret_val = []
        for table in ['users', 'activation', 'reset']:
            self.__sql('SELECT * from ' + table)
            if _print: pprint(list(self.cur.fetchall()))
            ret_val += [[elm for elm in self.cur.fetchall()]]
        return ret_val

    def activate(self, uid, activation_code):
        info('activate %s %s' % (uid, activation_code))
        self.__sql(["DELETE FROM activation WHERE uid=? and activation=?",
                   (uid, activation_code)], True)
        self.clean()

    @staticmethod
    def __rnd_seq(length):
        return ''.join(choice(ascii_letters + digits) for i in range(length))

    def reset(self, uid, pwd):
        info('reset %s' % uid)
        salt = self.__rnd_seq(8)
        new_pwd = sha512(pwd + salt).hexdigest()
        query = 'UPDATE users SET pwd = "%s", salt = "%s" WHERE uid = "%s"'
        query = query % (new_pwd, salt, uid)
        self.__sql(query, True)
        self.__sql(["DELETE FROM reset WHERE uid=?", (uid,)], True)

    def is_user(self, uid, email):
        query = "SELECT * FROM users WHERE uid=? and email=?"
        self.__sql([query, (uid, email)])
        return [elm for elm in self.cur.fetchall()]

    def is_valid_reset(self, uid, reset_code):
        query = "SELECT * FROM reset WHERE uid=? and reset=?"
        self.__sql([query, (uid, reset_code)])
        return [elm for elm in self.cur.fetchall()]

    def is_supporter(self, uid):
        query = "SELECT uid, is_supporter FROM users WHERE uid=?"
        self.__sql([query, (uid,)])
        return [elm for elm in self.cur.fetchall()][0][1]

    def add(self, uid, pwd, salt, email, activation):
        info('add %s %s' % (uid, email))
        quoted = ['"%s"' % elm for elm in [uid, pwd, salt, email]]
        today = '"%s"' % date.today().isoformat()
        quoted += ['0', today, today]
        vals = ', '.join(quoted)
        self.__sql("INSERT INTO users VALUES (%s)" % vals, True)
        quoted = ['"%s"' % elm for elm in [uid, activation]]
        vals = ', '.join(quoted)
        self.__sql("INSERT INTO activation VALUES (%s)" % vals, True)

    def add_reset(self, uid, email, reset_code):
        info('add reset %s %s' % (uid, email))
        self.__sql(["DELETE FROM reset WHERE uid=?", (uid,)], True)
        quoted = ['"%s"' % elm for elm in [uid, email, reset_code]]
        vals = ', '.join(quoted)
        self.__sql("INSERT INTO reset VALUES (%s)" % vals, True)

    def login(self, uid, pwd):
        query = "SELECT * FROM users WHERE uid=? and pwd=?"
        self.__sql([query, (uid, pwd)])
        return bool([elm for elm in self.cur.fetchall()])

    def remove(self, uid):
        info('remove %s' % uid)
        self.__sql(["DELETE FROM users WHERE uid=?", (uid,)], True)

    def clean(self):
        self.__sql('SELECT users.uid, last_access FROM users INNER JOIN ' + \
                   'activation ON users.uid = activation.uid')
        users = [elm for elm in self.cur.fetchall()]

        def dist(_date):
            today = datetime.today()
            return (today - datetime.strptime(_date, '%Y-%m-%d')).days
        rmusr = [usr[0] for usr in users if dist(usr[1]) > 2]
        for usr in rmusr:
            self.__sql(["DELETE FROM users WHERE uid=?", (usr,)], True)
            self.__sql(["DELETE FROM activation WHERE uid=?", (usr,)], True)

        cmd = 'SELECT users.uid, last_access FROM users INNER JOIN reset ' + \
              'ON users.uid = reset.uid'
        self.__sql(cmd)
        users = [elm for elm in self.cur.fetchall()]

        def dist2(_date):
            today = datetime.today()
            return (today - datetime.strptime(_date, '%Y-%m-%d')).days
        rmusr = [usr[0] for usr in users if dist2(usr[1]) > 2]
        for usr in rmusr:
            self.__sql(["DELETE FROM reset WHERE uid=?", (usr,)], True)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--add', nargs='*')
    parser.add_argument('--remove')
    args = parser.parse_args()
    db = DBFacade()
    if args.list: db.list(True)
    if args.add: db.add(*args.add)
    if args.remove: db.remove(args.remove)
