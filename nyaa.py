import requests
import urllib
import re
import html
import logging


REGEX_TID = r'tid=(\d+)'
REGEX_NAME = r'<a href=".*?' + REGEX_TID + '">{name}</a>'


logger = logging.getLogger('nyaa')


class NyaaConnector:
    """ Class to describe a connexion with the NyaaTorrent website

        Attributes:
            scheme (str): HTTP or HTTPS connection.
            host (str): the URL to NyaaTorent, without the scheme.

        Args:
            host (str): Address of the NyaaTorrent website.
    """

    def __init__(self, host=None):
        if host is None:
            raise NyaaConnectorError("Parameter 'host' missing in config file")

        host_split = urllib.parse.urlsplit(host)
        self.scheme = host_split[0]
        self.host = host_split[1]

    def get_id_from_url(self, name):
        """ Get torrent ID from URL

            Args:
                name (str): Querry string to search.

            Returns:
                (str): torrent ID. `None` if the name has not been found.
        """
        name_term = name.format(garbage='*', variation='').encode(
                'ascii',
                errors='ignore'
                )

        url = urllib.parse.urlunsplit((
                self.scheme,
                self.host,
                '',
                urllib.parse.urlencode({
                    'page': 'search',
                    'term': name_term,
                    }),
                '',
                ))

        logger.debug("Requesting ID from name: '{}'".format(
                    name_term.decode('ascii')
                    ))

        request = requests.get(url)
        if not request.ok:
            raise NyaaConnectorError(
                    "Unable to connect to server: error {}".format(request.status_code)
                    )

        tid = re.findall(REGEX_TID, request.url)
        if not tid:
            logger.debug("Request has responded no ID")

            # try to search in the page recieved
            result = self.get_id_from_page(
                    page=request.text,
                    name=name
                    )

            # result can be None if there is nothing found
            return result

        logger.debug("Request has responded one ID: {}".format(tid[0]))
        return tid[0]

    def get_id_from_page(self, page, name):
        """ Get torrent ID from a result page.

            Looks for the first torrent ID corresponding to the name on a given
            page used when the the search doesn't lead to a single result, but a
            candidates list.

            Args:
                page (str): HTML document, contains a list of results.
                name (str): Querry string to search.

            Returns:
                (str): torrent ID. `None` if the name has not been found.
        """
        page = html.unescape(page)
        name_reg = re.escape(name)\
                .replace('\\{variation\\}', '(?:v\d+)?')\
                .replace('\\{garbage\\}', '.*?')

        logger.debug("Searching ID in page from name: '{}'".format(name_reg))
        regex = re.compile(REGEX_NAME.format(name=name_reg))
        tid = re.findall(regex, page)
        if not tid:
            logger.debug("No ID found")
            return None

        logger.debug("Found at least one ID: {}".format(tid[0]))
        return tid[0]


    def get_url_from_id(self, tid):
        """ Get the torrent URL from the torrent ID

            Args:
                tid (str): Torrent ID for NyaaTorrent.

            Returns:
                (str): URL of the torrent on the NyaaTorrent website.
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
