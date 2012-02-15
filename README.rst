Metargs
-------

Metargs is a library that aims to combine the functionality of
argparse for defining commandline arguments and options with
that of ConfigParser for reading data from configuration files.

Usage
=====

Example::

    from metargs import ConfigBackedArgumentParser, Option

    parser = ConfigBackedArgumentParser('/etc/foo.conf')
    parser.extend_options(
        Option('config:only', help='Read the 'only' configuration value from the '
            'section [config]. Leave it as a string. Default to None),
        Option('config:option', '-o', '--option',
            help='Add an optional value that reads from [config] 'option', but also '
                 'from the --option command line argument'),
        Option('argument', help='A command line only argument')
    )

    args = parser.parse_args()
    print args.config_only
    print args.option
    print args.argument

The Option class is designed to take all of the same arguments as argparse.ArgumentParser.add_argument. It will interpret any arguments that contain ':' as <section>:<key> values
to read from the configuration file.
