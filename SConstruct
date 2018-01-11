from collections import namedtuple
from yyagl.build.build import set_path, files, devinfo_fpath, pdf_fpath
from yyagl.build.devinfo import bld_devinfo
from yyagl.build.pdf import bld_pdfs


argument_info = [  # (argname, default value)
    ('path', 'built'), ('devinfo', 0), ('pdf', 0)]
args = {arg: ARGUMENTS.get(arg, default) for (arg, default) in argument_info}
path = set_path(args['path'])
app_name = 'yorg_server'

pargs = {'dst_dir': path, 'appname': app_name}
devinfo_path = devinfo_fpath.format(**pargs)
pdf_path = pdf_fpath.format(**pargs)

bld_devinfo = Builder(action=bld_devinfo)
bld_pdfs = Builder(action=bld_pdfs)

env = Environment(BUILDERS={
    'devinfo': bld_devinfo, 'pdf': bld_pdfs})
env['APPNAME'] = app_name
PDFInfo = namedtuple('PDFInfo', 'lng root fil excl')
yorg_fil_dirs = ['yyagl', 'menu', 'yorg', 'licenses', 'assets', 'venv',
                 'build', 'built']
yorg_fil = ['./%s/*' % dname for dname in yorg_fil_dirs]
yorg_lst = [
    PDFInfo('python', '.', '*.py SConstruct *.md *.txt', yorg_fil)]
pdf_conf = {'yorg_server': yorg_lst}
env['PDF_CONF'] = pdf_conf

dev_conf = {'devinfo': lambda s: str(s).startswith('yyagl/')}
env['DEV_CONF'] = dev_conf

VariantDir(path, '.')

if args['devinfo']:
    env.devinfo([devinfo_path], files(['py'], ['venv', 'thirdparty']))
if args['pdf']:
    env.pdf([pdf_path], files(['py'], ['venv', 'thirdparty']))
