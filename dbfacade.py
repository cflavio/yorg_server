from argparse import ArgumentParser
from sqlite3 import connect
from pprint import pprint
from datetime import date, datetime


class DBFacade(object):

    def __init__(self):
        self.conn = connect('yorg.db')
        self.cur = self.conn.cursor()
        user_columns = [
            'uid text primary key', 'pwd text', 'salt text', 'email text',
            'is_supporter integer', 'reg_date text', 'last_access text']
        activation_columns = [
            'uid text primary key', 'activation text']
        info = [('users', user_columns), ('activation', activation_columns)]
        for table, columns in info:
            columns = ', '.join(columns)
            query = 'CREATE TABLE if not exists %s (%s)' % (table, columns)
            self.__sql(query, True)


        self.clean()

    def __sql(self, cmd, commit=False):
        if type(cmd) in [str, unicode]: cmd = [cmd]
        self.cur.execute(*cmd)
        if commit: self.conn.commit()

    def list(self, _print=False):
        ret_val = []
        for table in ['users', 'activation']:
            self.__sql('SELECT * from ' + table)
            if _print: pprint(list(self.cur.fetchall()))
            ret_val += [[elm for elm in self.cur.fetchall()]]
        return ret_val

    def activate(self, uid, activation_code):
        self.__sql(["DELETE FROM activation WHERE uid=? and activation=?", (uid, activation_code)], True)
        self.clean()

    def add(self, uid, pwd, salt, email, activation):
        quoted = ['"%s"' % elm for elm in [uid, pwd, salt, email]]
        today = '"%s"' % date.today().isoformat()
        quoted += ['0', today, today]
        vals = ', '.join(quoted)
        self.__sql("INSERT INTO users VALUES (%s)" % vals, True)
        quoted = ['"%s"' % elm for elm in [uid, activation]]
        vals = ', '.join(quoted)
        self.__sql("INSERT INTO activation VALUES (%s)" % vals, True)

    def remove(self, uid):
        self.__sql(["DELETE FROM users WHERE uid=?", (uid,)], True)

    def clean(self):
        self.__sql('SELECT users.uid, last_access FROM users INNER JOIN activation ON users.uid = activation.uid')
        users = [elm for elm in self.cur.fetchall()]
        def dist(_date):
            today = datetime.today()
            return (today - datetime.strptime(_date, '%Y-%m-%d')).days
        rmusr = [usr[0] for usr in users if dist(usr[1]) > 2]
        for usr in rmusr:
            self.__sql(["DELETE FROM users WHERE uid=?", (usr,)], True)
            self.__sql(["DELETE FROM activation WHERE uid=?", (usr,)], True)


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
