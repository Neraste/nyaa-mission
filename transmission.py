import urllib
import re
import requests


TOKEN = 'X-Transmission-Session-Id'
REGEX_TOKEN = r'<code>' + TOKEN + ': (.*?)</code>'


def token_required(fun):
    """ Decorator for authentification
    """
    def call(self, *args, **kwargs):
        if self.token is None:
            message = "No connection established"
            raise TransmissionConnectorError(message)
        return fun(self, *args, **kwargs)
    return call


class TransmissionConnector:
    """ Class to describe a connexion with a Transmission server API
    """

    def __init__(self, host, credentials, ssl_verify = True):
        self.host = host
        self.token = None
        self.headers = {}
        self.credentials = credentials
        self.ssl_verify = ssl_verify

    def set_token(self):
        """ Authenticate on server and set token
        """
        request = requests.get(
                self.host,
                auth=self.credentials,
                verify=self.ssl_verify
                )

        if request.ok:
            return

        if request.status_code == 409:
            token = re.findall(REGEX_TOKEN, request.text)
            if token:
                self.token = token[0]
                self.headers = {
                        TOKEN: self.token,
                        }
                return

        raise TransmissionConnectorError(
                "Unable to connect to host: error " + str(request.status_code)
                )

    @token_required
    def add_torrent(self, directory, torrent_url):
        """ Set a torrent in queue
        """
        data = {
                'method': 'torrent-add',
                'arguments': {
                    'download-dir': directory,
                    'filename': torrent_url,
                    },
                }

        request = requests.post(
                self.host,
                json=data,
                auth=self.credentials,
                headers=self.headers,
                verify=self.ssl_verify
                )

        if not request.ok:
            raise TransmissionConnectorError(
                    "Unable to add torrent: error " + str(request.status_code)
                    )

        result = request.json()
        if 'arguments' in result and 'torrent-added' in result['arguments']:
            return True

        return False

    @token_required
    def get_all_torrents(self):
        """ Get all torrents currently in queue or finished
        """
        data = {
                'method': 'torrent-get',
                'arguments': {
                    'fields': [
                        'name',
                        ],
                    },
                }

        request = requests.post(
                self.host,
                json=data,
                auth=self.credentials,
                headers=self.headers,
                verify=self.ssl_verify
                )

        if not request.ok:
            raise TransmissionConnectorError(
                    "Unable to get torrents: error " + str(request.status_code)
                    )

        result = request.json()
        if 'arguments' in result \
                and 'torrents' in result['arguments'] \
                and result['arguments']['torrents']:

            return [t['name'] for t in result['arguments']['torrents']]

        return None



class TransmissionConnectorError(Exception):
    """ Class for connexion errors
    """
