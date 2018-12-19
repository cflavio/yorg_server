from sqlite3 import connect
from pprint import pprint
from dbapp import DBApp
from args import set_args


class SupporterMgr(DBApp):

    def __init__(self): DBApp.__init__(self, 'supporters')

    def _create_tables(self):
        self._sql('CREATE TABLE if not exists supporters (name text)', True)

    def list(self, _print=False):
        ret = self._sql('SELECT * from supporters')
        if _print: pprint(ret)
        return ret

    def add(self, name):
        self._sql("INSERT INTO supporters VALUES ('%s')" % name, True)

    def remove(self, name):
        self._sql(['DELETE FROM supporters WHERE name=?', (name,)], True)


if __name__ == '__main__':
    args = [('--list', {'action': 'store_true'}), ('--add', {}),
            ('--remove', {})]
    args = set_args(args)
    supp_mgr = SupporterMgr()
    if args.list: supp_mgr.list(True)
    if args.add: supp_mgr.add(args.add)
    if args.remove: supp_mgr.remove(args.remove)
