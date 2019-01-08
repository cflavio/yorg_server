from states import waiting


class Room(object):

    def __init__(self, name, srv_usr):
        self.name = name
        self.srv_usr = srv_usr
        self.users = []
        self.ready = []
        self.ready_cd = []  # players ready at countdown
        self.uid2car = {}
        self.uid2drvidx = {}
        self.uid2props = {}  # uid: i, speed, adherence, stability
        self.state = waiting
        self.track = ''

    def add_usr(self, usr): self.users += [usr]

    def rm_usr(self, usr):
        if usr in self.users: self.users.remove(usr)
        else: debug('user %s already removed' % usr.uid)
        # it may happen on user's removal

    @property
    def users_uid(self): return [usr.uid for usr in self.users]

    @property
    def empty(self): return not self.users
