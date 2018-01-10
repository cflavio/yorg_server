import argparse
import sqlite3
import pprint


class SupporterMgr(object):

    def __init__(self):
        self.conn = sqlite3.connect('supporters.db')
        self.cur = self.conn.cursor()
        self.cur.execute('CREATE TABLE if not exists supporters (name text)')
        self.conn.commit()

    def list(self):
        self.cur.execute('SELECT * from supporters')
        supporters = list(self.cur.fetchall())
        pprint.pprint(supporters)

    def add(self, name):
        self.cur.execute("INSERT INTO supporters VALUES ('%s')" % name)
        self.conn.commit()

    def remove(self, name):
        self.cur.execute("DELETE FROM supporters WHERE name=?", (name,))
        self.conn.commit()


parser = argparse.ArgumentParser()
parser.add_argument('--list', action='store_true')
parser.add_argument('--add')
parser.add_argument('--remove')
args = parser.parse_args()
supp_mgr = SupporterMgr()
if args.list:
    supp_mgr.list()
if args.add:
    supp_mgr.add(args.add)
if args.remove:
    supp_mgr.remove(args.remove)
