from os.path import exists
from logging import basicConfig, INFO, DEBUG, getLogger, Formatter
from logging.handlers import TimedRotatingFileHandler


def set_log(appname, level='debug'):
    if not exists('logs'): mkdir('logs')
    level = {'info': INFO, 'debug': DEBUG}[level]
    format_tmpl = '%(asctime)s%(msecs)03d%(levelname).1s %(message)s'
    basicConfig(level=level, datefmt='%y%m%d%H%M%S', format=format_tmpl)
    handler = TimedRotatingFileHandler('logs/%s.log' % appname, 'midnight')
    handler.suffix = '%Y%m%d'
    tmpl = '%(asctime)s%(msecs)03d%(levelname).1s %(message)s'
    formatter = Formatter(format_tmpl, datefmt='%y%m%d%H%M%S')
    handler.setFormatter(formatter)
    getLogger().addHandler(handler)


