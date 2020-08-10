from logging import info, debug
from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from json import load


mail_activation = (
    'Hi! Thank you for subscribing Yorg!\n\nIn order to activate your account, '
    'you have to click the following link:\n\n'
    '{server}/activate.html?uid={uid}&activation_code='
    '{activation_code}\n\nAfter that, you can login to your account. Thank you '
    "so much!\n\nYorg's team")


mail_reset = (
    'Hi {uid}!\n\nPlease go here and insert your new password:\n\n'
    '{server}/reset.html?uid={uid}&reset_code={reset_code}'
    "\n\nThank you so much!\n\nYorg's team")


class Mail(object):

    def __init__(self):
        self.server = None
        with open('settings.json') as f_settings:
            self._settings = load(f_settings)
        self.connect()

    def connect(self):
        self.server = SMTP(self._settings['mail_server'], self._settings['mail_port'])
        self.server.starttls()
        self.server.login(self._settings['mail_address'], self._settings['mail_password'])
        debug('connected to the smtp server')

    def _send_mail(self, email, subj, body):
        if not self.connected: self.connect()
        msg = MIMEMultipart()
        pars = [('From', self._settings['mail_address']), ('To', email), ('Subject', subj)]
        for par in pars: msg[par[0]] = par[1]
        msg.attach(MIMEText(body, 'plain'))
        self.server.sendmail(self._settings['mail_address'], email, msg.as_string())
        info('sent email to %s: %s' % (email, subj))

    def send_mail_activation(self, uid, email, activation_code):
        subj = 'Yorg: activation of the user ' + uid
        body = mail_activation.format(
            server=self._settings['server'], uid=uid,
            activation_code=activation_code)
        self._send_mail(email, subj, body)

    def send_mail_reset(self, uid, email, reset_code):
        subj = "Yorg: %s's password reset" % uid
        body = mail_reset.format(
            server=self._settings['server'], uid=uid, reset_code=reset_code)
        self._send_mail(email, subj, body)

    @property
    def connected(self):
        try: status = self.server.noop()[0]
        except: status = None
        return status == 250

    def destroy(self): self.server.quit()
