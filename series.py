import glob
import os
import re
import logging


logger = logging.getLogger('series')


class Series:
    """ Class to describe a series and the amount of
        entries downloaded so far
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
            max_ahead=5
            ):
        """ Constructor

            directory
                local folder for downloaded files

            pattern
                pattern string to query the series,
                used by glob during the directory scan process
                and by nyaa when querrying NyaaTorrent server

            number_format
                format string for the number of the series

            directory_server
                folder for dowloaded files in the server

            max_ahead
                amount of series to querry
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

        self.max_ahead = max_ahead

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
                downloaded=True
                )

            if new_entry not in self.entries:
                logger.debug("Found file on disk '{}'".format(file_path))

                self.entries.append(new_entry)

    def set_entries_from_transmission(self, torrents):
        """ Set series entries from the Tranimission server
            The server has already been asked for the torrent list

            torrents
                the list of all torrents in the server
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
                downloading=True
                )

            if new_entry not in self.entries:
                logger.debug("Found file on torrents list '{}'".format(
                    os.path.basename(torrent)
                    ))

                self.entries.append(new_entry)

    def set_new_entries_from_nyaa(self, nyaa_connector):
        """ Set maximum max_ahead new series entries by asking the
            NyaaTorrent website

            nyaa_connector
                connector for the NyaaTorrent website
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

                return # if the nth entry doesn't exist, no reason for the n+1th to exist

            self.entries.append(SeriesEntry(
                number=number,
                file_name=name,
                tid=tid
                # this entry is neither dowloaded, nor downloading,
                # so it as to be sent to Transmission by download_new_entries
                ))

            self.debug("Adding new entry {} for '{}'".format(
                number,
                self
                ))

            # update iterator
            i += 1

    def download_new_entries(self, nyaa_connector, transmission_connector):
        """ Ask the Transmission server to start download the new entries,
            which are entries neither downloaded nor downloading

            nyaa_connector
                connector for the NyaaTorrent website

            transmission_connector
                connector for the Transmission website
        """
        for entry in self.entries:
            if not (entry.downloaded or entry.downloading):
                downloading = transmission_connector.add_torrent(
                        directory=self.directory_server,
                        torrent_url=nyaa_connector.get_url_from_id(entry.tid)
                        )

                if downloading:
                    self.logger("Set entry '{}' to download".format(entry))
                    entry.downloading = True

    def __str__(self):
        return self.name


class SeriesEntry:
    """ Class to describe a series episode
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
        """ Constructor

            number
                number of the episode

            file_name
                name of the file of the episode

            dowloaded
                the episode has been dowloaded
                and is currently in the local directory
                as well as in the Transmission server torrent list

            downloading
                the episode is currently being dowladed
                and is currently in the Transmission server torrent list

            tid
                torrent ID for the NyaaTorrent website
        """
        self.number = number
        self.file_name = file_name
        self.downloaded = downloaded
        self.downloading = downloading
        self.tid = tid

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
