import urllib
import re
import requests
import logging


TOKEN = 'X-Transmission-Session-Id'
REGEX_TOKEN = r'<code>' + TOKEN + ': (.*?)</code>'


logger = logging.getLogger('transmission')


class TransmissionConnector:
    """ Class to describe a connexion with a Transmission server API

        Attributes:
            token (str): Authentication token given by the Transmission server
                for connections.
            ssl_verify (bool): check the validity of the SSL certificate.
            host (str): Address of the Transmission server RTC API.
            credentials (tuple): login and password for authetication on the
                Transmission server.

        Args:
            host (str): Address of the Transmission server RTC API.
            login (str): login for basic authentication for the Transmission
                server.
            password (str): password for basic authentication for the
                Transmission server.
            ssl_verify (bool): check the validity of the SSL certificate. Set to
                `True` by default.
    """

    def __init__(self, host, login, password, ssl_verify=True):
        self.token = None
        self.ssl_verify = ssl_verify
        self.host = host
        self.credentials = (login, password)

    def token_required(fun):
        """ Decorator for authentification
        """
        def call(self, *args, **kwargs):
            if self.token is None:
                message = "No connection established"
                raise TransmissionConnectorError(message)

            return fun(self, *args, **kwargs)

        return call

    @token_required
    def _get_authentication_header(self):
        """ Return the authentication token in a header-dictionnary form

            Returns:
                (dictionnary): Token with proper formatting in header.
        """
        return {TOKEN: self.token}

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

        # according to Transmission documantation, successful connection
        # results in an 409 response with the token in the body
        if request.status_code == 409:
            token = re.findall(REGEX_TOKEN, request.text)
            if token:
                self.token = token[0]

                logger.debug("Conected to Transmission server with token")
                return

        # unsuccessful connection (bad login/password) leads to 401 response
        if request.status_code == 401:
            raise TransmissionConnectorError("Connection to Transmission \
server failed: wrong login or password")

        raise TransmissionConnectorError("Unable to connect to Transmission \
server: error {}".format(request.status_code))

    @token_required
    def add_torrent(self, directory, torrent_url):
        """ Set a torrent in queue

            Args:
                directory (str): Directory of the torrent on the server.
                url (str): URL of the torrent to add.

            Returns:
                (bool): status of dowload request. `True` if it was successful,
                `False` otherwize.
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
                headers=self._get_authentication_header(),
                verify=self.ssl_verify
                )

        if not request.ok:
            raise TransmissionConnectorError(
                    "Unable to add torrent: error ".format(request.status_code)
                    )

        result = request.json()
        if 'arguments' in result and 'torrent-added' in result['arguments']:
            logger.debug("Torrent sucessfuly added to download")
            return True

        return False

    @token_required
    def get_all_torrents(self):
        """ Get all torrents currently in queue or finished

            Returns:
                (list): list of all the torrents in the Transmission server.
                Returns `None` if the list is empty. Or if something went wrong?
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
                headers=self._get_authentication_header(),
                verify=self.ssl_verify
                )

        if not request.ok:
            raise TransmissionConnectorError(
                    "Unable to get torrents: error ".format(request.status_code)
                    )

        result = request.json()
        if 'arguments' in result \
                and 'torrents' in result['arguments'] \
                and result['arguments']['torrents']:

            torrents = [t['name'] for t in result['arguments']['torrents']]
            logger.debug("Get list of {} torrents".format(len(torrents)))
            return torrents

        return None


class TransmissionConnectorError(Exception):
    """ Class for connexion errors
    """
