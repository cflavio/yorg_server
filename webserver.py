from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
from os import mkdir
from urllib.parse import urlparse, parse_qs
from traceback import print_exc
from log import set_log
from dbfrontend import DBFrontend


emptypage = '''<p>Hi! This is an auxiliary site for <em>Yorg</em>.</p>
<p>Please go on <a href="http://www.ya2.it">our site</a> for more info.</p>'''


activationpage = '''<p>Hi <em>{uid}</em>!</p>
<p>Your account has been activated.
Now you can use it for playing <em>Yorg</em> online!</p>'''


resetpage = '''<p>Hi <em>{uid}</em>!</p>
<form action="reset_ok.html" method="post">
Insert your new password:<br>
<input type="password" name="pwd">
<input type="hidden" name="uid" value="{uid}" />
</form>'''


resetpage_ok = '''<p>Your password has been resetted.
Now you can use it for playing <em>Yorg</em> online!</p>'''


resetpage_ko = '''<p>Hi <em>{uid}</em>!</p>
<p>This reset request is invalid. Perhaps, it is too old or you've submitted
other reset requests after this one or you've already resetted your password.
Please retry.</p>'''

pre = '<html><body>\n<h1>Yorg</h1>\n'
post = '\n</body>\n</html>'
def bld_page(page): return pre + page + post
emptypage = bld_page(emptypage)
activationpage = bld_page(activationpage)
resetpage = bld_page(resetpage)
resetpage_ok = bld_page(resetpage_ok)
resetpage_ko = bld_page(resetpage_ko)


set_log('yorg_server_web')


class RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        self.db = DBFrontend('yorg')
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        page = self.bld_page(parsed_path.path, parsed_path.query)
        if not page:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(page)))
        self.end_headers()
        self.wfile.write(page.encode())

    def do_POST(self):
        if not self.rfile: return
        length = int(self.headers['Content-Length'])
        args = dict(parse_qs(self.rfile.read(length)))
        args = {key: val[0] for key, val in args.items()}
        page = self.bld_page(urlparse(self.path).path, args)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(page)))
        self.end_headers()
        self.wfile.write(page.encode())

    def bld_page(self, filename, args):
        if filename in ['/', '/index.html']: return emptypage
        mth = '_' + filename[1:-5]
        if filename[0] + filename[-5:] == '/.html' and hasattr(self, mth):
            return getattr(self, mth)(args)

    def _activate(self, args):
        args = dict(arg.split('=') for arg in args.split('&'))
        self.db.activate(args['uid'], args['activation_code'])
        return activationpage.format(uid=args['uid'])

    def _reset(self, args):
        args = dict(arg.split('=') for arg in args.split('&'))
        if self.db.valid_reset(args['uid'], args['reset_code']):
            return resetpage.format(uid=args['uid'])
        else: return resetpage_ko.format(uid=args['uid'])

    def _reset_ok(self, args):
        self.db.reset(args[b'uid'], args[b'pwd'])
        return resetpage_ok

    def log_message(self, format_, *args): pass
    # otherwise the backgrounded process prints stuff in the output in place
    # of stdout and the server outputs a 502 error


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer): pass


if __name__ == '__main__':
    server = ThreadedHTTPServer(('localhost', 9090), RequestHandler)
    try: server.serve_forever()
    except Exception as exc:
        print_exc()
        with open('logs/yorg_server_web.log', 'a') as f: print_exc(file=f)
