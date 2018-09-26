from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
from os.path import exists
from os import mkdir
from urlparse import urlparse, parse_qs
from logging import basicConfig, DEBUG, getLogger, info, debug, Formatter
from logging.handlers import TimedRotatingFileHandler
from dbfacade import DBFacade


emptypage = '''\
<html>
<body>
<h1>Yorg</h1>
<p>Hi! This is an auxiliary site for <em>Yorg</em>.</p>
<p>Please go on <a href="http://www.ya2.it">our site</a> for more info.</p>
</body>
</html>
'''


actpage = '''\
<html>
<body>
<h1>Yorg</h1>
<p>Hi <em>{uid}</em>!</p>
<p>Your account has been activated. Now you can use it for playing <em>Yorg</em> online!</p>
</body>
</html>
'''


resetpage_ok = '''\
<html>
<body>
<h1>Yorg</h1>
<p>Hi <em>{uid}</em>!</p>
<form action="reset_ok.html" method="post">
Insert your new password:<br>
<input type="password" name="pwd">
<input type="hidden" name="uid" value="{uid}" />
</form>
</body>
</html>
'''


resetpage_ko = '''\
<html>
<body>
<h1>Yorg</h1>
<p>Hi <em>{uid}</em>!</p>
<p>This reset request is invalid. Perhaps, it is too old or you've submitted
other reset requests after this one or you've already resetted your password.
Please retry.</p>
</body>
</html>
'''


resetok_page = '''\
<html>
<body>
<h1>Yorg</h1>
<p>Your password has been resetted. Now you can use it for playing <em>Yorg</em> online!</p>
</body>
</html>
'''


if not exists('logs'): mkdir('logs')
basicConfig(level=DEBUG, format='%(levelname)-8s %(message)s')
handler = TimedRotatingFileHandler('logs/yorg_server_web.log', 'midnight')
handler.suffix = '%Y%m%d'
formatter = Formatter('%(asctime)s%(msecs)03d%(levelname).1s %(message)s',
                      datefmt='%y%m%d%H%M%S')
handler.setFormatter(formatter)
getLogger().addHandler(handler)


class SimpleHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urlparse(self.path)
        page = self.page(parsed_path.path, parsed_path.query)
        if not page:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if not self.rfile: return
        length = int(self.headers['Content-Length'])
        args = dict(parse_qs(self.rfile.read(length)))
        args = {key: val[0] for key, val in args.items()}
        page = self.page(parsed_path.path, args)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def page(self, filename, args):
        db = DBFacade()
        if filename == '/activate.html':
            args = dict(arg.split('=') for arg in args.split('&'))
            db.activate(args['uid'], args['activation_code'])
            return actpage.format(uid=args['uid'])
        if filename == '/reset.html':
            args = dict(arg.split('=') for arg in args.split('&'))
            if db.is_valid_reset(args['uid'], args['reset_code']):
                return resetpage_ok.format(uid=args['uid'])
            else:
                return resetpage_ko.format(uid=args['uid'])
        if filename == '/reset_ok.html':
            db.reset(args['uid'], args['pwd'])
            return resetok_page
        if filename in ['/', '/index.html']: return emptypage

    def log_message(self, format, *args):
        pass  # otherwise the backgrounded process prints stuff in the output
              # in place of stdout and the server outputs a 502 error


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer): pass


if __name__ == '__main__':
    server = ThreadedHTTPServer(('localhost', 9090), SimpleHandler)
    try:
        server.serve_forever()
    except Exception as e:
        import traceback; traceback.print_exc()
        with open('logs/yorg_server_web.log', 'a') as f:
            import traceback; traceback.print_exc(file=f)
