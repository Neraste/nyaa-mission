import requests
import urllib
import re
import html
import logging


REGEX_TID = r'tid=(\d+)'
REGEX_NAME = r'<a href=".*?' + REGEX_TID + '">{name}</a>'


class NyaaConnector:
    """ Class to describe a connexion with the NyaaTorrent website
    """

    def __init__(self, host):
        """ Constructor

            host
                address of the NyaaTorrent website
        """
        host_split = urllib.parse.urlsplit(host)
        self.scheme = host_split[0]
        self.host = host_split[1]

    def get_id_from_name(self, name):
        """ Get torrent ID from a file name
            Return None if name not found

            name
                querry string to search
        """
        name_term = name.format(garbage='*', variation='').encode('ascii', errors='ignore')
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

        logging.debug("Requesting ID from name: " + str(name_term))
        request = requests.get(url)
        if not request.ok:
            raise NyaaConnectorError(
                    "Unable to connect to server: error " + str(request.status_code)
                    )

        tid = re.findall(REGEX_TID, request.url)
        if not tid:
            logging.debug("Request has responded no ID")

            # try to search in the page recieved
            result = self.get_id_from_page(
                    page=request.text,
                    name=name
                    )

            # result can be None if there is nothing found
            return result

        logging.debug("Request has responded ID" + str(tid[0]))
        return tid[0]

    def get_id_from_page(self, page, name):
        """ Get the first torrent ID corresponding to
            a name on a given page
            used when the the search doesn't lead to a single result,
            but a results list

            page
                HTML document, contains a list of results

            name
                querry string to search
        """
        page = html.unescape(page)
        name_reg = re.escape(name)\
                .replace('\\{variation\\}', '(?:v\d+)?')\
                .replace('\\{garbage\\}', '.*?')

        logging.debug("Searching ID in page from name: " + str(name_reg))
        regex = re.compile(REGEX_NAME.format(name=name_reg))
        tid = re.findall(regex, page)
        if not tid:
            logging.debug("No ID found")
            return None

        logging.debug("Found at least one ID: " + str(tid[0]))
        return tid[0]


    def get_url_from_id(self, tid):
        """ Get the torrent URL from the torrent ID

            tid
                torrent ID for NyaaTorrent
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
