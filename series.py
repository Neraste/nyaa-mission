import glob
import os
import re
import logging


logger = logging.getLogger('series')


class Series:
    """ Class to describe a series and the amount of
        entries downloaded so far

        Attributes:
            name (str): Name of the series.
            number_format (str): Format string for the number of the series. It
                is aimed for setting the amount of zeros when querrying files.
            entries (list): List of series entries. The list is appended by
                `set_entries_from_directory` and
                `set_entries_from_transmission`.
            directory_local (str): Path to the directory of the series in the
                local disk.
            directory_server (str): Path to the directory of the series in the
                Transmission server.
            file_pattern (str): String pattern representing a series entry file
                name without number formatting.
            file_pattern_format (str): String pattern representing a series
                entry file name with number formatting.
            max_ahead (int): Amount of files to dowload past the more recent
                dowloaded.
            max_number (int): Latest entry number.

        Args:
            name (str): Name of the series.
            directory_local (str): Name of the local folder for downloaded
                files. Set to `name` by default.
            directory_server (str): Name of the folder for downloading files as
                seen by the Transmission server. Set to `name` by default.
            directory_local_prefix (str): Path to prepend to `directory_local`.
            directory_server_prefix (str): Path to prepend to
                `directory_server`.
            pattern (str): Pattern string to query the series, used by glob
                during the directory scan process and by nyaa when querrying
                NyaaTorrent server.
            number_format (str): Format string for the number of the series. It
                is aimed for setting the amount of zeros when querrying files.
                Set to 2 by default.
            max_ahead (str): Amount of series to querry in one run. If set to
                `all` or a negative number, all series entries will be
                dowloaded.
    """

    def __init__(
            self,
            name,
            directory_local=None,
            directory_server=None,
            directory_local_prefix='',
            directory_server_prefix='',
            pattern=None,
            number_format='02',
            max_ahead='5'
            ):
        """ Constructor

        """
        self.name = name
        self.number_format = number_format

        self.entries = []

        # manage all optionnal arguments
        # directory on disk
        if directory_local is None:
            directory_local = name

        self.directory_local = os.path.join(
                directory_local_prefix,
                directory_local
                )

        # directory on server as seen by Transmission
        if directory_server is None:
            directory_server = name

        self.directory_server = os.path.join(
                directory_server_prefix,
                directory_server
                )

        # file pattern of the series items
        self.file_pattern = pattern.format(
                number='{number}{variation}',
                garbage='{garbage}'
                )

        # file pattern of the series items with formatted number
        self.file_pattern_format = pattern.format(
                number='{number:' + number_format + 'n}{variation}',
                garbage='{garbage}'
                )

        # number of files to query
        # allowing spectial value `all`
        if max_ahead == 'all':
            max_ahead = -1

        try:
            self.max_ahead = int(max_ahead)

        except ValeError as error:
            raise SeriesError("Parameter 'max_ahead' must represent \
a digit or 'all'") from error

    @property
    def max_number(self):
        if self.entries:
            return max(e.number for e in self.entries)

        return 0


    def set_entries_from_directory(self):
        """ Set series entries by walking in the directory for downloaded entries
        """
        if not os.path.isdir(self.directory_local):
            raise SeriesError("Directory not found: '{}'".format(
                self.directory_local))

        pattern = os.path.join(
                self.directory_local,
                self.file_pattern
                )

        pattern_safe = pattern.replace('[', '[[]').format(
                number='*',
                garbage='*',
                variation='*'
                )

        files = glob.glob(pattern_safe)

        if not files:
            logger.debug("No files on disk found for '{}'".format(self))

            return

        regex_number = re.escape(pattern)\
                .replace('\\{number\\}', '(\d+)')\
                .replace('\\{garbage\\}', '.*?')\
                .replace('\\{variation\\}', '(?:v\d+)?')

        for file_path in files:
            number = int(re.findall(regex_number, file_path)[0])

            new_entry = SeriesEntry(
                number=number,
                file_name=os.path.basename(file_path),
                downloaded=True,
                parent=self
                )

            if new_entry not in self.entries:
                logger.debug("Found file on disk '{}'".format(file_path))

                self.entries.append(new_entry)

    def set_entries_from_transmission(self, torrents):
        """ Set series entries from the Tranimission server

            The server has already been asked for the torrent list.

            Args:
                torrents (list): The list of all torrents in the server.
        """
        if not torrents:
            logger.debug("No torrents to look in")
            return

        regex_number = re.escape(self.file_pattern)\
                .replace('\\{number\\}', '(\d+)')\
                .replace('\\{garbage\\}', '.*?')\
                .replace('\\{variation\\}', '(?:v\d+)?')

        for torrent in torrents:
            try:
                # many torrents don't correspond to the ones of the series
                # we need a simple way to pass them
                number = int(re.findall(regex_number, torrent)[0])

            except IndexError:
                continue

            new_entry = SeriesEntry(
                number=number,
                file_name=torrent,
                downloading=True,
                parent=self
                )

            if new_entry not in self.entries:
                logger.debug("Found file on torrents list '{}'".format(
                    os.path.basename(torrent)
                    ))

                self.entries.append(new_entry)

    def set_new_entries_from_nyaa(self, nyaa_connector):
        """ Query NyaaTorrent to get now series entries

            Set maximum `max_ahead` new series entries by asking the NyaaTorrent
            website.

            Args:
                nyaa_connector (NyaaConnector): Connector for the NyaaTorrent
                    website.
        """
        old_max_number = self.max_number
        i = 0
        condition_fun = (
                # always loop if max_ahead is null or negative
                lambda i: True
                ) if self.max_ahead <= 0 else (
                        # loop up to max_ahead otherwize
                        lambda i: i < self.max_ahead
                        )

        while condition_fun(i):
            number = old_max_number + i + 1
            name = self.file_pattern_format.format(
                    number=number,
                    variation='{variation}',
                    garbage='{garbage}'
                    )

            tid = nyaa_connector.get_id_from_url(name)
            if not tid:
                logger.debug("Finished looking new entries for \
'{}'".format(self))

                # if the nth entry doesn't exist, no reason for the n+1th to
                # exist
                return

            self.entries.append(SeriesEntry(
                number=number,
                file_name=name,
                tid=tid,
                parent=self
                # this entry is neither dowloaded, nor downloading, so it as to
                # be sent to Transmission by download_new_entries
                ))

            logger.debug("Adding new entry {} for '{}'".format(
                number,
                self
                ))

            # update iterator
            i += 1

    def download_new_entries(
            self,
            nyaa_connector,
            transmission_connector,
            dry_run=False
            ):
        """ Dowload the new series entries

            Ask the Transmission server to start download the new entries, which
            are entries neither downloaded nor downloading.

            Args:
                nyaa_connector (NyaaTorrent): Connector for the NyaaTorrent
                    website.
                transmission_connector (TransmissionConnector): Connector for
                    the Transmission server.
                dry_run (bool): Flag for dry run. If set to `True`, the request
                    to add torrents to the Transmission server is not sent and
                    no files are dowloaded. Set to `False` by default.
        """
        for entry in self.entries:
            if not (entry.downloaded or entry.downloading):
                if not dry_run:
                    downloading = transmission_connector.add_torrent(
                            directory=self.directory_server,
                            torrent_url=nyaa_connector.get_url_from_id(entry.tid)
                            )

                else:
                    downloading = True

                if downloading:
                    logger.debug("Set entry '{}' to download".format(entry))
                    entry.downloading = True

    def __str__(self):
        return self.name


class SeriesEntry:
    """ Class to describe a series episode

        Attributes: same as arguments.

        Args:
            number (int): Number of the episode.
            file_name (str): Name of the file of the episode.
            dowloaded (bool): Flag for dowloaded status. If set to `True`, the
                episode has been dowloaded and is currently in the local
                directory as well as in the Transmission server torrent list.
                Set to `False` by default.
            downloading (bool): Flag for dowloading status. If set to `True`,
                the episode is currently being dowladed and is currently in the
                Transmission server torrent list.
            tid (str): Torrent ID in the NyaaTorrent website.
            parent (Series): series the episode belongs to.
    """
    def __init__(
            self,
            number,
            file_name,
            downloaded=False,
            downloading=False,
            tid='',
            parent=None,
            ):

        self.number = number
        self.file_name = file_name
        self.downloaded = downloaded
        self.downloading = downloading
        self.tid = tid
        self.parent = parent

    def __eq__(self, other):
        """ Test equality of two episodes
        """
        return self.file_name == other.file_name

    def __ne__(self, other):
        """ Test inequality of two episodes
        """
        return not self.__eq__(other)

    def __str__(self):
        if self.parent is not None:
            return "{} #{}".format(self.parent, self.number)

        else:
            return "Orphan entry #{}".format(self.number)


class SeriesError(Exception):
    """ Class for errors about series
    """
