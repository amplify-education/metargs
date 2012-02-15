#This file is part of metargs
#
#Copyright (c) 2012 Wireless Generation, Inc.
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

from ConfigParser import SafeConfigParser
from argparse import ArgumentParser, Namespace


class ConfigArgumentError(Exception):
    pass


def separate_names(names):
    """
    Split a set of names for an option into configuration names,
    positional argument names, and optional argument names.

    An argument is optional if it starts with '-',
    configuration if it contains ':',
    and positional otherwise
    """
    configs = []
    args = []
    options = []

    for name in names:
        if name.startswith('-'):
            options.append(name)
        elif ':' in name:
            configs.append(name.split(':'))
        else:
            args.append(name)

    return configs, args, options

class MissingConfigArgumentError(Exception):
    def __init__(self, option):
        formatted_options = ', '.join(':'.join(opt) for opt in option.config_paths)
        Exception.__init__(self, 'No configuration value found for required Option(%s)' % 
            formatted_options)

class Option(object):
    """
    An object that encapsulates a description of a configuration option.

    All non-keyword arguments are taken to be names for the option.
        * -x, --xxx are treated as optional commandline names
        * foo:bar is read from the configuration file, section [foo], value bar
        * otherwise, it's treated as a required commandline argument

    Valid keyword arguments are the keyword arguments from argparse.ArgumentParser.add_argument, except the following:
        * split_char: The string used to split a list of arguments read from the
            configuration file, if nargs is not None. Default is ','
    """

    _defaults = {
        'action': 'store',
        'split_char': ',',
    }

    def __init__(self, *names, **kwargs):

        def read_with_default(key):
            return kwargs.get(key, self._defaults.get(key))

        self.action = read_with_default('action')
        self.nargs = read_with_default('nargs')
        self.const = read_with_default('const')
        self.default = read_with_default('default')
        self.type = read_with_default('type')
        self.choices = read_with_default('choices')
        self.required = read_with_default('required')
        self.help = read_with_default('help')
        self.metavar = read_with_default('metavar')
        self.dest = read_with_default('dest')
        self.split_char = read_with_default('split_char')

        self.config_paths, self.args, self.options = separate_names(names)

    def __eq__(self, other):
        return (isinstance(other, Option) and
                other.action == self.action and
                other.nargs == self.nargs and
                other.const == self.const and
                other.default == self.default and
                other.type == self.type and
                other.choices == self.choices and
                other.required == self.required and
                other.help == self.help and
                other.metavar == self.metavar and
                other.dest == self.dest and
                other.split_char == self.split_char and
                other.config_paths == self.config_paths and
                other.args == self.args and
                other.options == self.options)

    def _get_value(self, value):
        """
        Interpret value using the specified type of the Option
        """
        if self.type is None:
            return value

        if not callable(self.type):
            formatted_names = " ".join(
                self.args +
                self.options +
                [':'.join(cp) for cp in self.config_paths]
            )
            raise ConfigArgumentError("type is not callable for Option(%s)" % formatted_names)
        return self.type(value)

    def _check_value(self, value):
        """
        Verify that value is allowed for the Option
        """
        if self.choices is not None and value not in self.choices:
            raise ConfigArgumentError("invalid choice: %s (choose from %s)" %
                (value, ", ".join(repr(c) for c in self.choices)))

    def _read_config_paths(self, config_parser):
        """
        From the supplied config_parser, read out the first configuration option
        that is available, and return the (value, section, name) tuple.

        If none of the options are in the file, return None, None, None
        """
        for section, name in self.config_paths:
            if config_parser.has_option(section, name):
                return config_parser.get(section, name), section, name

        return None, None, None

    def from_config(self, config_parser):
        """
        Read the value for this Option from config_parser, and return it.
        If no value is found and the value is required, return a
        MissingConfigArgumentError (to be raised later), otherwise return
        the specified default.
        """
        val, section, name = self._read_config_paths(config_parser)
        if val is None:
            if self.required:
                return MissingConfigArgumentError(self)
            else:
                return self.default

        if self.nargs is not None:
            value = [self._get_value(v.strip()) for v in val.split(self.split_char)]

            if self.nargs == '+':
                if len(value) == 0:
                    raise ConfigArgumentError(
                        "Require at least one value in [%s] %s, because nargs='+'"
                        % (section, name))
            elif self.nargs == '*':
                pass
            else:
                if len(value) != int(self.nargs):
                    raise ConfigArgumentError(
                        "Require exactly %s values in [%s] %s, because nargs=%s"
                        % (self.nargs, section, name, self.nargs))

            for v in value:
                self._check_value(v)
        else:
            value = self._get_value(val)
            self._check_value(value)

        return value

    def add_to_parser(self, argparser, from_config, namespace=None):
        """
        Add this Option to argparser, with from_config as the default.
        If there is no commandline specified form this Option, add
        from_config to the specified namespace instead.
        """
        if not (self.args or self.options):
            if namespace is not None:
                for path in self.config_paths:
                    setattr(namespace, "_".join(path), from_config)
            return 

        kwargs = {}

        def add_if_not_none(name, value):
            if value is None:
                return
            kwargs[name] = value

        add_if_not_none('action', self.action)
        add_if_not_none('nargs', self.nargs)
        add_if_not_none('const', self.const)
        add_if_not_none('default', from_config)
        add_if_not_none('type', self.type)
        add_if_not_none('choices', self.choices)
        add_if_not_none('required', self.required)
        add_if_not_none('help', self.help)
        add_if_not_none('metavar', self.metavar)
        add_if_not_none('dest', self.dest)

        argparser.add_argument(*(self.args + self.options), **kwargs)


class ConfigBackedArgumentParser(object):
    """
    This is an argument parser that uses configuration files to provide default values
    that can be overridden by commandline arguments.

    def_cfg_loc: The default location for the config file.
    config_short_flag: The short commandline flag to use when specifying the config file
    config_long_flag: The long commandline flag to use when specifying the config file
    config_help: The help message for the config file commandline flag
    config_metavar: The metavar for the config file commandline option
    parser_args: A list of arguments to pass to the ArgumentParser used for commandline
        argument parsing
    parser_kwargs; A dictionary of keyword arguments to pass to the ArgumentParser
        used for commandline argument parsing
    """
    def __init__(self,
            def_cfg_loc=None,
            config_short_flag='-c',
            config_long_flag='--config',
            config_help="Path to the config file",
            config_metavar="CFG",
            *parser_args, **parser_kwargs):
        
        self.def_cfg_loc = def_cfg_loc
        self.config_short_flag = config_short_flag
        self.config_long_flag = config_long_flag
        self.config_help = config_help
        self.config_metavar = config_metavar
        self.parser_args = parser_args
        self.parser_kwargs = parser_kwargs
        self.options = []
        self.additional_configs = []

    def _read_config_args(self, args=None):
        """
        Read arguments from the config file. Returns a dictionary mapping Options
        to the values read from the config file for them.
        """
        parser = ArgumentParser(add_help=False, *self.parser_args, **self.parser_kwargs)
        self._add_config_arg(parser)
        opts, left = parser.parse_known_args(args)

        config = SafeConfigParser()
        if opts.config is not None:
            config.read(opts.config)
        
        for cfg in self.additional_configs:
            config.read(cfg)

        config_vals = {}
        for opt in self.options:
            config_vals[opt] = opt.from_config(config)

        return config_vals

    def _add_config_arg(self, parser):
        """
        Add the configuration file commandline argument to the specified argument parser
        """
        parser.add_argument(
            self.config_short_flag,
            self.config_long_flag,
            default=self.def_cfg_loc,
            help=self.config_help,
            metavar=self.config_metavar,
            dest='config')

    def _add_options(self, parser, args=None, namespace=None):
        """
        Add all Options to the specified parser, with defaults from the config file
        """
        config_vals = self._read_config_args(args)
        for opt in self.options:
            opt.add_to_parser(parser, from_config=config_vals.get(opt), namespace=namespace)

    def _setup_parser(self, parser, args=None):
        """
        Sets up parser to be used with the config arguments, and returns a namespace
        that can be passed to parser.parse_args or parser.parse_known_args
        """
        self._add_config_arg(parser)

        namespace = Namespace()
        self._add_options(parser, args, namespace)
        return namespace

    def _check_required_config(self, args):
        """
        If any of the specified arguments are required, and weren't available
        either from the config file or the commandline, raise the MissingConfigArgumentError
        """
        for attr, value in vars(args).items():
            if isinstance(value, MissingConfigArgumentError):
                raise value

    def parse_known_args(self, args=None):
        """
        Parse all known arguments from args (or from sys.argv), returning a tuple
        of (the parsed arguments, the remaining arguments)
        """
        parser = ArgumentParser(*self.parser_args, **self.parser_kwargs)
        namespace = self._setup_parser(parser, args)
        args, rest = parser.parse_known_args(args, namespace)
        self._check_required_config(args)
        return args, rest

    def parse_args(self, args=None):
        """
        Parse all the arguments from args (or from sys.argv), returning the parsed
        arguments, or raising an exception if there are unknown arguments
        """
        parser = ArgumentParser(*self.parser_args, **self.parser_kwargs)
        namespace = self._setup_parser(parser, args)
        args = parser.parse_args(args, namespace)
        self._check_required_config(args)
        return args

    def bootstrap_parse(self, args=None):
        """
        Parse all of the known arguments from args (or from sys.argv), except
        the --help argument. Returns the parsed arguments
        """
        parser = ArgumentParser(add_help=False, *self.parser_args, **self.parser_kwargs)
        namespace = self._setup_parser(parser, args)
        args = parser.parse_known_args(args, namespace)[0]
        self._check_required_config(args)
        return args
    
    def append_option(self, option):
        """
        Add a single option to this parser, if the option hasn't already been added
        """
        if option not in self.options:
            self.options.append(option)
    
    def extend_options(self, options):
        """
        Add a list of options to this parser, ignoring any that have already been added
        """
        for option in options:
            if option not in self.options:
                self.options.append(option)
