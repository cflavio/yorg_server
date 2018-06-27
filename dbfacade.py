from argparse import ArgumentParser
from sqlite3 import connect
from pprint import pprint
from datetime import date


class DBFacade(object):

    def __init__(self):
        self.conn = connect('yorg.db')
        self.cur = self.conn.cursor()
        columns = [
            'uid text primary key', 'pwd text', 'salt text', 'email text',
            'is_supporter integer', 'reg_date text', 'last_access text']
        columns = ', '.join(columns)
        self.__sql('CREATE TABLE if not exists users (%s)' % columns, True)

    def __sql(self, cmd, commit=False):
        if type(cmd) in [str, unicode]: cmd = [cmd]
        self.cur.execute(*cmd)
        if commit: self.conn.commit()

    def list(self, _print=False):
        self.__sql('SELECT * from users')
        if _print: pprint(list(self.cur.fetchall()))
        return [elm for elm in self.cur.fetchall()]

    def add(self, uid, pwd, salt, email):
        quoted = ['"%s"' % elm for elm in [uid, pwd, salt, email]]
        today = '"%s"' % date.today().isoformat()
        quoted += ['0', today, today]
        vals = ', '.join(quoted)
        self.__sql("INSERT INTO users VALUES (%s)" % vals, True)

    def remove(self, uid):
        self.__sql(["DELETE FROM users WHERE uid=?", (uid,)], True)


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
