#!/usr/bin/env python3

import sys
import os
import importlib
import logging
import argparse
import requests
from series import Series, SeriesError
from nyaa import NyaaConnector, NyaaConnectorError
from transmission import TransmissionConnector, TransmissionConnectorError


__VERSION__ = "0.1.0"


CONFIG_FILE = 'config.py'
CONFIG_SERIES = 'SERIES'
CONFIG_TRANSMISSION = 'TRANSMISSION'
CONFIG_NYAA = 'NYAA'
CONFIG_LOGS = 'LOGS'


logger = logging.getLogger('nyaa_mission')


logging.getLogger("requests").setLevel(logging.ERROR)
requests.packages.urllib3.disable_warnings()


class NyaaMission:
    """ Class to represent a NyaaMission session
    """

    def __init__(self, config_path=None, skip_directory_check=False):
        """ Constructor

            config_path
                name and path of the config file

            skip_directory_check
                flag to bypass the scan of local directories
        """
        # config
        if config_path is None:
            config_path = CONFIG_FILE

        config_directory, config_file = os.path.split(config_path)
        sys.path.append(config_directory)
        config_name = os.path.splitext(config_file)[0]
        config = importlib.import_module(config_name)
        self.skip_directory_check = skip_directory_check

        # logs
        loglevel = getattr(config, CONFIG_LOGS, 'INFO')
        logging_level_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(logging_level_numeric, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))

        logging.basicConfig(
                format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                level=logging_level_numeric
                )

        # series
        self.series = []
        if not hasattr(config, CONFIG_SERIES):
            raise NyaaMissionConfigError(
                    "Series configuration is missing in config file"
                    )

        self.set_series(getattr(config, CONFIG_SERIES))

        # transmission
        if not hasattr(config, CONFIG_TRANSMISSION):
            raise NyaaMissionConfigError(
                    "Transmission configuration is missing in config file"
                    )

        self.set_transmission(getattr(config, CONFIG_TRANSMISSION))

        # nyaatorrent
        if not hasattr(config, CONFIG_NYAA):
            raise NyaaMissionConfigError(
                    "NyaaTorrent configuration is missing in config file"
                    )

        self.set_nyaa(getattr(config, CONFIG_NYAA))

    def set_series(self, config):
        """ Set series from config

            config
                list of series
        """
        for line in config:
            self.series.append(Series(**line))

    def set_transmission(self, config):
        """ Set Transmission connection from config
            and from the user

            config
                dictionnary of config for the Transmission server
        """
        # TODO change that
        username = input('Username: ')
        import getpass
        psd = getpass.getpass()
        self.transmission = TransmissionConnector(credentials=(username, psd), **config)
        self.transmission.set_token()

    def set_nyaa(self, config):
        """ Set NyaaTorrent connection from config

            config
                dictionnary of config for NyaaTorrent
        """
        self.nyaa = NyaaConnector(**config)

    def refresh(self):
        """ Browse files and Transmission for downloaded or downloading torrents
        """
        torrents = self.transmission.get_all_torrents()
        for series in self.series:
            series.entries = []
            if not self.skip_directory_check:
                series.set_entries_from_directory()
 
            series.set_entries_from_transmission(torrents)

    def update(self):
        """ Check new series episodes in NyaaTorrent website
        """
        for series in self.series:
            old_max = series.max_number
            series.set_new_entries_from_nyaa(self.nyaa)
            series.download_new_entries(self.nyaa, self.transmission)
            new_max = series.max_number
            amount = new_max - old_max
            if amount:
                name = os.path.basename(series.directory)
                self.logger.info("Update {}: {} new entr{}".format(
                    name,
                    amount,
                    "ies" if amount > 1 else "y"
                    ))


class NyaaMissionError(Exception):
    """ Class for general NyaaMission errors
    """


class NyaaMissionConfigError(NyaaMissionError):
    """ Class for config errors
    """


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument(
            "-c",
            "--config-file",
            help="set configuration file to use (default: " + CONFIG_FILE + ")"
            )

    parser.add_argument(
            "--skip-directory-check",
            help="don't check local directories to find downloaded series",
            action='store_true'
            )

    parser.add_argument(
            "-d",
            "--debug",
            help="debug mode",
            action='store_true'
            )

    args = parser.parse_args()

    try:
        logger.info("NyaaMission v" + __VERSION__ + " started")
        nyaa_mission = NyaaMission(args.config_file, skip_directory_check=args.skip_directory_check)
        nyaa_mission.refresh()
        nyaa_mission.update()
        logger.info("Closing")

    except (SeriesError, TransmissionConnectorError, NyaaConnectorError) as error:
        logger.critical("An error has occured\n{}".format(error))

    except:
        logger.exception("An error has occured")
