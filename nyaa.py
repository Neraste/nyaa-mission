import requests
import urllib
import re


REGEX_TID = r'tid=(\d+)'


class NyaaConnector:
    """ Class to describe a connexion with the NyaaTorrent website
    """

    def __init__(self, host):
        host_split = urllib.parse.urlsplit(host)
        self.scheme = host_split[0]
        self.host = host_split[1]

    def get_id_from_name(self, name):
        """ Get torrent ID from a file name
            Return None if name not found
        """
        url = urllib.parse.urlunsplit((
                self.scheme,
                self.host,
                '',
                urllib.parse.urlencode({
                    'page': 'search',
                    'term': name.encode('ascii', errors='ignore'),
                    }),
                '',
                ))

        request = requests.get(url)
        if not request.ok:
            raise NyaaConnectorError(
                    "Unable to connect to server: error " + str(request.status_code)
                    )

        tid = re.findall(REGEX_TID, request.url)
        if not tid:
            return None

        return tid[0]

    def get_url_from_id(self, tid):
        """ Get the torrent URL from the torrent ID
        """
        url = urllib.parse.urlunsplit((
                self.scheme,
                self.host,
                '',
                urllib.parse.urlencode({
                    'page': 'download',
                    'tid': tid,
                    }),
                '',
                ))

        return url


class NyaaConnectorError(Exception):
    """ Class for connexion errors
    """
