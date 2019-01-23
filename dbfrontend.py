from logging import info, debug
from itertools import product
from collections import namedtuple
from sqlite3 import connect
from pprint import pprint
from datetime import date, datetime
from random import choice
from string import ascii_letters as letters, digits
from hashlib import sha512
from dbapp import DBApp
from args import set_args


class DBFrontend(DBApp):

    def __init__(self, appname):
        debug('creating db frontend')
        DBApp.__init__(self, appname)

    def _create_tables(self):
        self.user_columns = [
            'uid text primary key', 'pwd text', 'salt text', 'email text',
            'supporter integer', 'reg_date text', 'last_access text']
        self.activation_columns = [
            'uid text primary key', 'activation_code text']
        self.reset_columns = [
            'uid text primary key', 'email text', 'reset_code text']
        tables = [('users', self.user_columns),
                  ('activation', self.activation_columns),
                  ('reset', self.reset_columns)]
        for name, columns in tables:
            columns = ', '.join(columns)
            query = 'CREATE TABLE if not exists %s (%s)' % (name, columns)
            self._sql(query, True)

    def _migrate_tables(self):
        self._migrate_table('users', self.user_columns, 'is_supporter', 'supporter')
        self._migrate_table('activation', self.activation_columns, 'activation', 'activation_code')
        self._migrate_table('reset', self.reset_columns, 'reset', 'reset_code')

    def _migrate_table(self, table, columns, old_field, new_field):
        # they introduced ALTER TABLE with 3.25
        if old_field not in self.__column_names(table): return
        cols = [field.split()[0] for field in columns]
        replace = lambda elm: new_field if elm == old_field else elm
        cmds = [
            'ALTER TABLE %s RENAME TO tmp_%s;' % (table, table),
            'CREATE TABLE %s (%s);' % (table, ', '.join(columns)) +
            'INSERT INTO %s (%s) ' % (table, ', '.join(cols)) +
            'SELECT %s ' % ', '.join([replace(col) for col in cols]) +
            'FROM tmp_users;',
            'DROP TABLE tmp_users;'
            ]
        for cmd in cmds: self._sql(cmd, True)

    def list(self, table, _print=False):
        ret = self._sql('SELECT * from ' + table)
        if _print:
            print(table, ':')
            pprint(ret)
            print('\n')
        Row = namedtuple(table + '_row', self.__column_names(table))
        return [Row(*row) for row in list(ret)]

    def list_all(self, _print):
        tables = ['users', 'activation', 'reset']
        return [self.list(table, _print) for table in tables]

    def __column_names(self, table):
        cursor = self.conn.execute('select * from ' + table)
        return [desc[0] for desc in cursor.description]

    def activate(self, uid, activation_code):
        info('activate %s %s' % (uid, activation_code))
        cmd = 'DELETE FROM activation WHERE uid=? and activation_code=?'
        self._sql([cmd, (uid, activation_code)], True)
        self.clean()

    @staticmethod
    def __rnd_str(lgt):
        return ''.join(choice(letters + digits) for i in range(lgt))

    def reset(self, uid, pwd):
        info('reset %s' % uid)
        salt = self.__rnd_str(8)
        new_pwd = sha512(pwd + salt).hexdigest()
        query = 'UPDATE users SET pwd = "%s", salt = "%s" WHERE uid = "%s"'
        query = query % (new_pwd, salt, uid)
        self._sql(query, True)
        self._sql(['DELETE FROM reset WHERE uid=?', (uid,)], True)

    def exists_user(self, uid, email):
        query = 'SELECT * FROM users WHERE uid=? and email=?'
        return self._sql([query, (uid, email)])

    def valid_reset(self, uid, reset_code):
        query = 'SELECT * FROM reset WHERE uid=? and reset_code=?'
        return self._sql([query, (uid, reset_code)])

    def supporter(self, uid):
        query = 'SELECT uid, supporter FROM users WHERE uid=?'
        return self._sql([query, (uid,)])[0][1]

    def __vals(self, lst): return ', '.join(['"%s"' % elm for elm in lst])

    def add(self, uid, pwd, salt, email, activation):
        info('add %s %s' % (uid, email))
        today = date.today().isoformat()
        vals = self.__vals([uid, pwd, salt, email, 0, today, today])
        self._sql('INSERT INTO users VALUES (%s)' % vals, True)
        vals = self.__vals([uid, activation])
        self._sql('INSERT INTO activation VALUES (%s)' % vals, True)

    def add_reset(self, uid, email, reset_code):
        info('add reset %s %s' % (uid, email))
        self._sql(['DELETE FROM reset WHERE uid=?', (uid,)], True)
        vals = self.__vals([uid, email, reset_code])
        self._sql('INSERT INTO reset VALUES (%s)' % vals, True)

    def login(self, uid, pwd):
        query = 'SELECT * FROM users WHERE uid=? and pwd=?'
        return bool(self._sql([query, (uid, pwd)]))

    def remove(self, uid):
        info('remove %s' % uid)
        self._sql(['DELETE FROM users WHERE uid=?', (uid,)], True)

    def clean(self):
        query = ('SELECT users.uid, last_access FROM users INNER JOIN '
                 'activation ON users.uid = activation.uid')
        users = self._sql(query)
        rmusr = [usr[0] for usr in users if self.__dist_days(usr[1]) > 2]
        for usr, table in product(rmusr, ['users', 'activation']):
            self._sql(['DELETE FROM %s WHERE uid=?' % table, (usr,)], True)
        cmd = ('SELECT users.uid, last_access FROM users INNER JOIN reset '
               'ON users.uid = reset.uid')
        users = self._sql(cmd)
        rmusr = [usr[0] for usr in users if self.__dist_days(usr[1]) > 2]
        for usr in rmusr:
            self._sql(['DELETE FROM reset WHERE uid=?', (usr,)], True)

    def __dist_days(self, _date):
        today = datetime.today()
        return (today - datetime.strptime(_date, '%Y-%m-%d')).days


if __name__ == '__main__':
    args = [('--list', {'action': 'store_true'}), ('--add', {'nargs': '*'}),
            ('--remove', {})]
    args = set_args(args)
    db = DBFrontend('yorg')
    if args.list: db.list_all(True)
    if args.add: db.add(*args.add)
    if args.remove: db.remove(args.remove)
