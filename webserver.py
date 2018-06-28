from BaseHTTPServer import BaseHTTPRequestHandler
from urlparse import urlparse
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


class GetHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urlparse(self.path)
        page = self.page(parsed_path.path, parsed_path.query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def page(self, filename, args):
        if filename != '/activate.html': return emptypage
        args = dict(arg.split('=') for arg in args.split('&'))
        db.activate(args['uid'], args['activation_code'])
        return actpage.format(uid=args['uid'])


db = DBFacade()
if __name__ == '__main__':
    from BaseHTTPServer import HTTPServer
    server = HTTPServer(('localhost', 9090), GetHandler)
server.serve_forever()
