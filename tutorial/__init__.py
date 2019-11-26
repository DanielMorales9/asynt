import argparse
import configparser
import logging
import os
import subprocess
import sys

from tutorial.runtime import Runtime, Party

FLAGS = {'debug': 'd', 'inspect': 'i', 'interactive': 'i', 'optimize': 'O',
          'dont_write_bytecode': 'B', 'no_user_site': 's', 'no_site': 'S',
          'ignore_environment': 'E', 'verbose': 'v', 'bytes_warning': 'b',
          'quiet': 'q', 'isolated': 'I', 'dev_mode': 'X dev',
          'utf8_mode': 'X utf8'}


def setup():
    """Setup a runtime."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-H', '--HELP', action='store_true', default=False, )
    parser.add_argument('-h', '--help', action='store_true', default=False,
                        help='show %s help message (if any)' % sys.argv[0])

    group = parser.add_argument_group('configuration')
    group.add_argument('-C', '--config', metavar='ini',
                       help='use ini file, defining all m parties')
    group.add_argument('-P', type=str, dest='parties', metavar='addr',
                       action='append',
                       help='use addr=host:port per party (repeat m times)')
    group.add_argument('-M', type=int, metavar='m',
                       help='use m local parties (and run all m,'
                            ' if i is not set)')
    group.add_argument('-I', '--index', type=int, metavar='i',
                       help='set index of this local party to i, 0<=i<m')
    group.add_argument('-B', '--base-port', type=int, metavar='b',
                       help='use port number b+i for party i')

    group = parser.add_argument_group('parameters')
    group.add_argument('--no-log', action='store_true', default=False,
                       help='disable logging messages')

    group = parser.add_argument_group('misc')
    group.add_argument('--output-file',
                       action='store_true',
                       default=False,
                       help='append output for '
                            'parties i>0 to party{m}_{i}.log')

    argv = sys.argv  # keep raw args
    options, args = parser.parse_known_args()
    if options.HELP:
        parser.print_help()
        sys.exit()

    if options.help:
        args += ['-h']
        print(f'Showing help message for {sys.argv[0]}, if available:\n')
    sys.argv = [sys.argv[0]] + args

    if options.no_log:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(format='{asctime} {message}', style='{',
                            level=logging.DEBUG, stream=sys.stdout)

    if options.config or options.parties:
        # use host:port for each local or remote party
        if options.config:
            addresses = get_addresses_from_config(options.config)
        else:
            addresses = get_addresses_from_parties(options.parties)
        parties, pid = create_parties(addresses, options.base_port)
        if pid is None:
            pid = options.index
    else:
        # use default port for each local party
        m = options.M or 1
        if m > 1 and options.index is None:
            run_processes(argv, m, options)

        pid = options.index or 0
        base_port = options.base_port or 11365
        addresses = [('localhost', base_port + i) for i in range(m)]
        parties, _ = create_parties(addresses)

    rt = Runtime(pid, parties, options)
    return rt


def run_processes(argv, m, options):
    # convert sys.flags into command line arguments
    FLAG_MAP = FLAGS
    if os.getenv('PYTHONHASHSEED') == '0':
        # -R flag needed only if hash randomization is not enabled by default
        FLAG_MAP['hash_randomization'] = 'R'

    def flag(a):
        return getattr(sys.flags, a, 0)

    flags = ['-' + flag(a) * c for a, c in FLAG_MAP.items() if flag(a)]
    # convert sys._xoptions into command line arguments
    xopts = ['-X' + a + ('' if c is True else '=' + c) for a, c in
             sys._xoptions.items()]
    prog, args = argv[0], argv[1:]
    for i in range(m - 1, 0, -1):
        cmd_line = [sys.executable] + flags + xopts + [prog, '-I',
                                                       str(i)] + args
        print(cmd_line)
        if options.output_file:
            with open(f'party{options.M}_{i}.log', 'a') as f:
                f.write('\n')
                f.write(f'$> {" ".join(cmd_line)}\n')
                subprocess.Popen(cmd_line, stdout=f, stderr=subprocess.STDOUT)
        else:
            subprocess.Popen(cmd_line, stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)


def get_addresses_from_config(cfg):
    # from ini configuration file
    addresses = []

    config = configparser.ConfigParser()
    config.read_file(
        open(os.path.join('.config', cfg), 'r'))
    for party in config.sections():
        host = config.get(party, 'host')
        port = config.get(party, 'port')
        addresses.append((host, port))
    return addresses


def get_addresses_from_parties(parties):
    addresses = []

    for party in parties:
        host, *port_suffix = party.rsplit(':', maxsplit=1)
        port = ' '.join(port_suffix)
        addresses.append((host, port))

    return addresses


def create_parties(addresses, base_port=None):
    pid = None
    parties = []
    for i, (host, port) in enumerate(addresses):
        if not host:
            pid = i  # empty host string for owner
            host = 'localhost'
        if base_port:
            port = base_port + i
        elif not port:
            port = 11365 + i
        else:
            port = int(port)
        parties.append(Party(i, host, port))
    return parties, pid


try:  # suppress exceptions for pydoc etc.
    asynt = setup()
except Exception as exc:
    print('runtime.setup() exception:', exc)
