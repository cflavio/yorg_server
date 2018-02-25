from collections import namedtuple
from yyagl.build.build import set_path, files, devinfo_fpath, pdf_fpath
from yyagl.build.devinfo import bld_devinfo
from yyagl.build.pdf import bld_pdfs


arg_info = [  # (argname, default value)
    ('path', 'built'), ('devinfo', 0), ('pdf', 0)]
args = {arg: ARGUMENTS.get(arg, default) for (arg, default) in arg_info}
path = set_path(args['path'])
app_name = 'yorg_server'
path_args = {'dst_dir': path, 'appname': app_name}
devinfo_path = devinfo_fpath.format(**path_args)
pdf_path = pdf_fpath.format(**path_args)
bld_devinfo = Builder(action=bld_devinfo)
bld_pdfs = Builder(action=bld_pdfs)
env = Environment(BUILDERS={'devinfo': bld_devinfo, 'pdf': bld_pdfs})
env['APPNAME'] = app_name
PDFInfo = namedtuple('PDFInfo', 'lng root fil excl')
yorg_fil_dirs = ['yyagl', 'menu', 'yorg', 'licenses', 'assets', 'venv',
                 'build', 'built']
yorg_fil = ['./%s/*' % dname for dname in yorg_fil_dirs]
yorg_lst = [PDFInfo('python', '.', '*.py SConstruct *.md', yorg_fil)]
env['PDF_CONF'] = {'yorg_server': yorg_lst}
env['DEV_CONF'] = {'devinfo': lambda s: str(s).startswith('yyagl/')}
VariantDir(path, '.')
excl_paths = ['venv', 'thirdparty']
if args['devinfo']: env.devinfo([devinfo_path], files(['py'], excl_paths))
if args['pdf']: env.pdf([pdf_path], files(['py'], excl_paths))
