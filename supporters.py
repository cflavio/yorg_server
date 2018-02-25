from argparse import ArgumentParser
from sqlite3 import connect
from pprint import pprint


class SupporterMgr(object):

    def __init__(self):
        self.conn = connect('supporters.db')
        self.cur = self.conn.cursor()
        self.__sql('CREATE TABLE if not exists supporters (name text)', True)

    def __sql(self, cmd, commit=False):
        if type(cmd) == str: cmd = [cmd]
        self.cur.execute(*cmd)
        if commit: self.conn.commit()

    def list(self, _print=False):
        self.__sql('SELECT * from supporters')
        if _print: pprint(list(self.cur.fetchall()))
        return [elm[0] for elm in self.cur.fetchall()]

    def add(self, name):
        self.__sql("INSERT INTO supporters VALUES ('%s')" % name, True)

    def remove(self, name):
        self.__sql(["DELETE FROM supporters WHERE name=?", (name,)], True)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--list', action='store_true')
    map(parser.add_argument, ['--add', '--remove'])
    args = parser.parse_args()
    supp_mgr = SupporterMgr()
    if args.list: supp_mgr.list(True)
    if args.add: supp_mgr.add(args.add)
    if args.remove: supp_mgr.remove(args.remove)
