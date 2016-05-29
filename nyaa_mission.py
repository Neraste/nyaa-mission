#!/usr/bin/env python3

import sys
import os
import importlib
import logging
import argparse
import requests
from series import Series
from nyaa import NyaaConnector
from transmission import TransmissionConnector


__VERSION__ = "0.1.0"


CONFIG_FILE = 'config.py'
CONFIG_SERIES = 'SERIES'
CONFIG_TRANSMISSION = 'TRANSMISSION'
CONFIG_NYAA = 'NYAA'
CONFIG_LOGS = 'LOGS'


logging.getLogger("requests").setLevel(logging.ERROR)
requests.packages.urllib3.disable_warnings()


class NyaaMission:
    """ Class to represent a NyaaMission session
    """

    def __init__(self, config_path=None, skip_directory_check=False):
        # config
        if config_path is None:
            config_path = CONFIG_FILE

        config_directory, config_file = os.path.split(config_path)
        sys.path.append(config_directory)
        config_name = os.path.splitext(config_file)[0]
        config = importlib.import_module(config_name)
        
        self.skip_directory_check = skip_directory_check

        # logs
        self.logging = logging
        loglevel = getattr(config, CONFIG_LOGS, 'INFO')
        logging_level_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(logging_level_numeric, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))

        self.logging.basicConfig(
                format='[%(asctime)s][%(levelname)s] %(message)s',
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
        """ Set series
        """
        for line in config:
            self.series.append(Series(**line))

    def set_transmission(self, config):
        """ Set Transmission connection
        """
        username = input('Username: ')
        import getpass
        psd = getpass.getpass()
        self.transmission = TransmissionConnector(credentials=(username, psd), **config)
        self.transmission.set_token()

    def set_nyaa(self, config):
        """ Set NyaaTorrent connection
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
        """ Check new series episodes en NyaaTorrent website
        """
        for series in self.series:
            old_max = series.max_number
            series.set_new_entries_from_nyaa(self.nyaa)
            series.download_new_entries(self.nyaa, self.transmission)
            new_max = series.max_number
            amount = new_max - old_max
            if amount:
                name = os.path.basename(series.directory)
                self.logging.info("Update {}: {} new entr{}".format(
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
            help="don't walk in directories to find downloaded series",
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
        nyaa_mission = NyaaMission(args.config_file, skip_directory_check=args.skip_directory_check)
        nyaa_mission.logging.info("NyaaMission v" + __VERSION__ + " started")
        nyaa_mission.refresh()
        nyaa_mission.update()
        nyaa_mission.logging.info("Closing")

    except Exception as error:
        if args.debug:
            logging.exception("An error has occured")

        else:
            logging.critical("An error has occured\n" + str(error))
