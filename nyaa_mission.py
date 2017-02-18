#!/usr/bin/env python3

import sys
import os
import logging
import argparse
import getpass
from configparser import ConfigParser
import requests
from series import Series, SeriesError
from nyaa import NyaaConnector, NyaaConnectorError
from transmission import TransmissionConnector, TransmissionConnectorError


__VERSION__ = "0.1.0"


CONFIG_FILE = 'config.ini'
CONFIG_SERIES_FILE = 'series.ini'
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

    def __init__(
            self,
            config_path=None,
            config_series_path=None,
            skip_directory_check=False,
            dry_run=False
            ):
        """ Constructor

            config_path
                name and path of the config file

            skip_directory_check
                flag to bypass the scan of local directories
        """
        self.skip_directory_check = skip_directory_check
        self.dry_run = dry_run

        if config_path is None:
            config_path = CONFIG_FILE

        if config_series_path is None:
            config_series_path = CONFIG_SERIES_FILE

        # load config file
        config = ConfigParser()
        config.read(config_path)

        # directories
        self.directory_local = config.get('Directories', 'local',
                fallback='')

        self.directory_server = config.get('Directories', 'server',
                fallback=self.directory_local)

        # logs
        loglevel = config.get('Logs', 'level', fallback='INFO')
        logging_level_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(logging_level_numeric, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))

        logging.basicConfig(
                format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s',
                level=logging_level_numeric
                )

        # series
        series_config = ConfigParser()
        series_config.read(config_series_path)

        self.series = []
        self.set_series(series_config)

        # transmission
        if "Transmission" not in config:
            raise NyaaMissionConfigError(
                    "Transmission configuration is missing in config file"
                    )

        self.set_transmission(config['Transmission'])

        # nyaatorrent
        if "Nyaa" not in config:
            raise NyaaMissionConfigError(
                    "NyaaTorrent configuration is missing in config file"
                    )

        self.set_nyaa(config['Nyaa'])

    def set_series(self, config):
        """ Set series from config

            config
                list of series
        """
        for name, section in config.items():
            if name == 'DEFAULT':
                continue

            self.series.append(Series(
                name,
                directory_local_prefix=self.directory_local,
                directory_server_prefix=self.directory_server,
                **section
                ))

    def set_transmission(self, config):
        """ Set Transmission connection from config
            and from the user

            config
                dictionnary of config for the Transmission server
        """
        if 'login' in config:
            login = config.pop('login')

        else:
            login = input('Transmission server login: ')

        if 'password' in config:
            password = config.pop('password')

        else:
            password = getpass.getpass()

        self.transmission = TransmissionConnector(
                login=login,
                password=password,
                **config
                )

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
            series.download_new_entries(
                    self.nyaa,
                    self.transmission,
                    self.dry_run
                    )

            new_max = series.max_number
            amount = new_max - old_max
            if amount:
                logger.info("Update {}: {} new entr{}".format(
                    series,
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
            "-s",
            "--series-file",
            help="set series definition file to use (default: " + CONFIG_SERIES_FILE + ")"
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

    parser.add_argument(
            "--dry-run",
            help="do not download any file",
            action='store_true'
            )

    args = parser.parse_args()

    try:
        logger.info("NyaaMission v" + __VERSION__ + " started")
        nyaa_mission = NyaaMission(
                config_path=args.config_file,
                config_series_path=args.series_file,
                skip_directory_check=args.skip_directory_check,
                dry_run=args.dry_run
                )

        nyaa_mission.refresh()
        nyaa_mission.update()
        logger.info("Closing")

    except (SeriesError, TransmissionConnectorError, NyaaConnectorError) as error:
        logger.critical("An error has occured\n{}".format(error))

    except:
        logger.exception("An error has occured")
