import glob
import os
import re

class Series:
    """ Class to describe a series and the amount of
        entries downloaded so far
    """

    def __init__(self, directory, file_pattern,
            number_format='02',
            directory_server=None,
            max_ahead=5):
        """ Constructor

            directory
                local folder for downloaded files

            file_pattern
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

        self.directory = directory
        if directory_server is None:
            self.directory_server = directory

        else:
            self.directory_server = directory_server

        self.file_pattern = file_pattern
        self.file_pattern_format = file_pattern.format(
                number='{number:' + number_format + 'n}',
                garbage='{garbage}'
                )

        self.number_format = number_format
        self.max_ahead = max_ahead
        self.entries = []

    @property
    def max_number(self):
        if self.entries:
            return max([e.number for e in self.entries])

        return 0


    def set_entries_from_directory(self):
        """ Set series entries by walking in the directory for downloaded entries
        """
        if not os.path.isdir(self.directory):
            raise IOError("Directory not found: " + str(self.directory))

        pattern = os.path.join(
                self.directory,
                self.file_pattern
                )

        pattern_safe = pattern.replace('[', '[[]').format(
                number='*',
                garbage='*'
                )

        files = glob.glob(pattern_safe)

        if not files:
            return

        regex_number = r'(\d+)(v\d)?'.join([r'.*?'.join([re.escape(q) \
                for q in p.split('{garbage}')]) \
                for p in pattern.format(
                    number='{number}',
                    garbage='{garbage}'
                    ).split('{number}')
                ])

        for file_path in files:
            number = int(re.findall(regex_number, file_path)[0][0])
            new_entry = SeriesEntry(
                number=number,
                file_name=os.path.basename(file_path),
                downloaded=True
                )

            if new_entry not in self.entries:
                self.entries.append(new_entry)

    def set_entries_from_transmission(self, torrents):
        """ Set series entries from the Tranimission server
            The server has already been asked for the torrent list

            torrents
                the list of all torrents in the server
        """
        if not torrents:
            return

        regex_number = r'(\d+)(v\d)?'.join([r'.*?'.join([re.escape(q) \
                for q in p.split('{garbage}')]) \
                for p in self.file_pattern.format(
                    number='{number}',
                    garbage='{garbage}'
                    ).split('{number}')
                ])

        for torrent in torrents:
            try:
                # many torrents don't correspond to the ones of the series
                # we need a simple way to pass them
                number = int(re.findall(regex_number, torrent)[0][0])

            except IndexError:
                continue

            new_entry = SeriesEntry(
                number=number,
                file_name=torrent,
                downloading=True
                )

            if new_entry not in self.entries:
                self.entries.append(new_entry)

    def set_new_entries_from_nyaa(self, nyaa_connector):
        """ Set maximum max_ahead new series entries by asking the
            NyaaTorrent website

            nyaa_connector
                connector for the NyaaTorrent website
        """
        old_max_number = self.max_number
        for i in range(self.max_ahead):
            number = old_max_number + i + 1
            name = self.file_pattern_format.format(number=number, garbage='*')
            tid = nyaa_connector.get_id_from_name(name)
            if not tid:
                return # if the nth entry doesn't exist, no reason for the n+1th to exist

            self.entries.append(SeriesEntry(
                number=number,
                file_name=name,
                tid=tid
                # this entry is neither dowloaded, nor downloading,
                # so as to be send to Transmission by download_new_entries
                ))

    def download_new_entries(self, nyaa_connector, transmission_connector):
        """ Ask the Transmission server to start download the new entries,
            that is entries which are neither downloaded nor downloading

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
                    entry.downloading = True


class SeriesEntry:
    """ Class to describe a series episode
    """

    def __init__(self, number, file_name,
            downloaded=False, downloading=False, tid=''):
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
