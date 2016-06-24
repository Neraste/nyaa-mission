import requests
import urllib
import re
import html


REGEX_TID = r'tid=(\d+)'
REGEX_NAME = r'<a href=".*?' + REGEX_TID + '">{name}</a>'


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
            # try to search in the page recieved
            result = self.get_id_from_page(
                    page=request.text,
                    name=name
                    )

            # result can be None if there is nothing found
            return result

        return tid[0]

    def get_id_from_page(self, page, name):
        """ Get the first torrent ID corresponding to
            a name on a given page
        """
        page = html.unescape(page)
        regex = re.compile(REGEX_NAME.format(name=re.escape(name).replace('\*', '.*?')))
        tid = re.findall(regex, page)
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
