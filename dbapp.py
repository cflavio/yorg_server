from logging import info, debug
from sqlite3 import connect


class DBApp(object):

    def __init__(self, appname):
        self.conn = connect(appname + '.db')
        self.cur = self.conn.cursor()
        self._create_tables()
        self._migrate_tables()

    def _create_tables(self): pass

    def _migrate_tables(self): pass

    def _sql(self, cmd, commit=False):
        if type(cmd) == str: cmd = [cmd]
        debug('sql (commit: %s): %s' % (commit, cmd))
        self.cur.execute(*cmd)
        if commit: self.conn.commit()
        return [elm for elm in self.cur.fetchall()]
