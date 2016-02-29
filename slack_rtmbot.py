#!/usr/bin/env python

import glob
import yaml
import os
import sys
import time
import logging
import re
from threading import Thread
from logging.handlers import RotatingFileHandler
from slackclient import SlackClient


def dbg(debug_string):
    """
    Used to write debugging information if debug is set in config
    :param debug_string:
    :return:
    """
    if debug:
        main_log.info(debug_string)


class RtmBot(object):
    def __init__(self, token):
        self.last_ping = 0
        self.token = token
        self.bot_plugins = []
        self.slack_client = None
        self.dm_help = []
        self.channel_help = []

    def connect(self):
        """Convenience method that creates Server instance"""
        self.slack_client = SlackClient(self.token)
        self.slack_client.rtm_connect()

    def start(self):
        self.connect()
        self.load_plugins()
        self.on_start()
        self.load_help()
        while True:
            for reply in self.slack_client.rtm_read():
                self.input_logging(reply)
                self.input(reply)
            self.repeated_tasks()
            self.output()
            self.autoping()
            time.sleep(config['PING_INTERVAL']
                       if "PING_INTERVAL" in config else .1)

    def autoping(self):
        """
        This method keeps the bot connection alive to slack. Requires a ping every 5 seconds if there
        is no activity.
        :return:
        """
        # hardcode the interval to 3 seconds
        now = int(time.time())
        if now > self.last_ping + 3:
            self.slack_client.server.ping()
            self.last_ping = now

    def load_help(self):
        """
        calls the process_help() function in each plugin to setup the help text variables
        :return:
        """
        global channel_help
        global dm_help

        for plugin in self.bot_plugins:
            try:
                plug_help = plugin.get_help()
                if len(plug_help[0]) > 0:
                    for plugin_help in plug_help[0]:
                        self.dm_help.append(plugin_help)
                if len(plug_help[1]) > 0:
                    for plugin_help in plug_help[1]:
                        self.channel_help.append(plugin_help)
            except AttributeError:
                main_log.info(
                    "{} is a bad bad plugin and doesnt implement process_help".format(plugin))
        self.dm_help.append(
            "help - Will return a listing of commands the bot responds to")
        self.channel_help.append(
            "help - Will return a listing of commands the bot responds to")
        return

    def output_help(self, channel):
        """
        Outputs help information to the help channel passed in
        :param channel:
        :return:
        """
        message = "Help for {}\n-------------------\n".format(config[
                                                                  'BOT_NAME'])
        if len(self.dm_help) > 0:
            message = "{}DM Commands:\n-------------------\n".format(message)
            for plugin_help in self.dm_help:
                message = "{}\n{}".format(message, plugin_help)
        if len(self.channel_help) > 0:
            message = "{}\n\nChannel Commands:\n-------------------\n".format(
                message)
            for plugin_help in self.channel_help:
                message = "{}\n{}".format(message, plugin_help)
        self.slack_client.api_call(
            "chat.postMessage", channel=channel, text=message, as_user=True)
        return

    def on_start(self):
        """
        Runs the process_onstart method for each function that has it
        :return:
        """
        function_name = "process_onstart"
        for plugin in self.bot_plugins:
            plugin.do(function_name, None)

    def input(self, data):
        """
        Receives messages from the RTM api (data) and passes it to methods in the plugins based on data type
        For example, a message gets sent to process_message
        Also handles input for the help commands and routes them to output_help
        :param data:
        :return:
        """
        if "type" in data:
            function_name = "process_" + data["type"]
            dbg("got {}".format(function_name))
            if function_name == "process_message":
                match = re.findall(r"{} (help|halp|help me)".format(
                    config['BOT_NAME']), data['text'])
                if data['channel'].startswith("D"):
                    function_name = "process_directmessage"
                    match = re.findall(r"(help|halp|help me)", data['text'])
                if len(match) > 0 and data['user'] != config['BOT_USER_ID']:
                    return self.output_help(data['channel'])
            for plugin in self.bot_plugins:
                plugin.do(function_name, data)

    def output(self):
        """
        Uses the slack web API (not the RTM API) to post a message based on content of
         outputs from plugins.
         Uses the web api because the RTM api is not able to process formatted messages
        :return:
        """
        for plugin in self.bot_plugins:
            limiter = False
            for output in plugin.do_output():
                channel = self.slack_client.server.channels.find(output[0])
                if channel is not None and output[1] is not None:
                    if limiter:
                        time.sleep(.1)
                    message = output[1].encode('ascii', 'ignore')
                    # channel.send_message("{}".format(message))
                    self.slack_client.api_call(
                        "chat.postMessage", channel=output[0], text=message, as_user=True)
                    limiter = True


    def repeated_tasks(self):
        """
        Runs any repeated tasks for plugins
        :return:
        """
        for plugin in self.bot_plugins:
            plugin.do_tasks()

    def load_plugins(self):
        """
        Loads all plugins in the /plugins directory
        :return:
        """
        for plugin in glob.glob(directory + '/plugins/*'):
            sys.path.insert(0, plugin)
            sys.path.insert(0, directory + '/plugins/')
        for plugin in glob.glob(directory + '/plugins/*.py') + \
                glob.glob(directory + '/plugins/*/*.py'):
            main_log.info(plugin)
            name = plugin.split('/')[-1][:-3]
            self.bot_plugins.append(Plugin(name))

    # noinspection PyMethodMayBeStatic
    def input_logging(self, data):
        """
        If COMMAND_LOGGING is true in config, logs all input sent at the bot
        This is used more for analytics then debugging. If you want
        debugging, turn on debugging
        :param data:
        :return:
        """
        # do nothing if we havent defined command logging or it is false
        if "INPUT_LOGGING" not in config or not config['INPUT_LOGGING']:
            return

        # dont log anytyhing that is coming from the bot itself
        if "user" in data and data['user'] == config['BOT_USER_ID']:
            return

        # discard some logs that we just dont need
        if data['type'] in config['INPUT_DO_NOT_LOG_TYPES']:
            return

        input_log.info("{},{},{},{}".format(
            data['type'],
            data['user'] if "user" in data else None,
            data['channel'] if "channel" in data else None,
            data['text'] if "text" in data else None))


class Plugin(object):
    def __init__(self, name):
        self.name = name
        self.module = __import__(name)
        self.outputs = []
        self.repeated_tasks = []
        self.config_tasks()
        if name in config:
            main_log.info("config found for: " + name)
            self.module.config = config[name]
        if 'setup' in dir(self.module):
            self.module.setup()

    # noinspection PyMethodMayBeStatic
    def plugin_worker(self, function_name, data):
        """
        Method used to thread plugins
        :param function_name:
        :param data:
        :return:
        """
        try:
            if function_name == "process_onstart":
                eval("self.module." + function_name)()
            elif data['user'] != config['BOT_USER_ID']:
                eval("self.module." + function_name)(data)
        except KeyError:
            eval("self.module." + function_name)()

    def get_help(self):
        """
        Runs the "process_help" function from a plugin and returns the output
        :return:
        """
        function_name = "process_help"
        return eval("self.module." + function_name)()

    def config_tasks(self):
        """
        Grabs the repeated_tasks list from the plugin and stores it in the
        repeated_tasks table
        :return:
        """
        if 'repeated_tasks' in dir(self.module):
            for interval, task_function in self.module.repeated_tasks:
                self.repeated_tasks.append(RepeatedTask(interval, eval("self.module.{}".format(task_function))))

    def do_tasks(self):
        for task in self.repeated_tasks:
            if task.check():
                try:
                    t = Thread(target=self.plugin_worker, args=(task.task_function(), None))
                    t.start()
                except:
                    main_log.error("Error when trying to start thread for task {}".format(task.__repr__()))

    def do(self, function_name, data):
        """
        Runs a plugin if it has a function to match the data being passed to it
        :param function_name:
        :param data:
        :return:
        """
        if function_name in dir(self.module):
            try:
                # stars a thread for this call to a plugin
                t = Thread(target=self.plugin_worker, args=(function_name, data))
                t.start()
            except:
                dbg("problem in module {} {}".format(function_name, data))
        if "catch_all" in dir(self.module):
            try:
                self.module.catch_all(data)
            except:
                dbg("problem in catch all")

    def do_output(self):
        output = []
        while True:
            if 'outputs' in dir(self.module):
                if len(self.module.outputs) > 0:
                    main_log.info("output from {}".format(self.module))
                    output.append(self.module.outputs.pop(0))
                else:
                    break
            else:
                self.module.outputs = []
        return output

    def do_dm_help(self):
        this_dm_help = []
        while True:
            if 'dm_help' in dir(self.module):
                if self.module.dm_help and len(self.module.dm_help) > 0:
                    main_log.info("dm_help from {}".format(self.module))
                    this_dm_help.append(self.module.dm_help.pop(0))
                else:
                    break
            else:
                self.module.dm_help = []
        return this_dm_help

    def do_channel_help(self):
        this_channel_help = []
        while True:
            if 'dm_help' in dir(self.module):
                if self.module.channel_help and len(self.module.channel_help) > 0:
                    main_log.info("channel_help from {}".format(self.module))
                    dm_help.append(self.module.channel_help.pop(0))
                else:
                    break
            else:
                self.module.channel_help = []
        return this_channel_help


class RepeatedTask(object):
    def __init__(self, interval, task_function):
        self.task_function = task_function
        self.interval = interval
        self.lastrun = 0

    def __str__(self):
        """
        Returns a string representation of the task object
        Function, Interval, LastRun
        :return: string
        """
        return "{} {} {}".format(self.task_function, self.interval, self.lastrun)

    def __repr__(self):
        """
        Returns a string representation of the task object
        Function, Interval, LastRun
        :return: string
        """
        return self.__str__()

    def check(self):
        """
        Checks if interval has passed since last run
        Returns true if so, false if otherwise
        :return: boolean
        """
        return self.lastrun + self.interval < time.time()

    def task_function(self):
        return self.task_function


class UnknownChannel(Exception):
    pass


def setup_logger(logger_name, log_file, level=logging.INFO):
    l = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(asctime)s : %(message)s')
    file_handler = RotatingFileHandler(log_file, mode='a', maxBytes=(
        config['LOGGING_MAX_SIZE'] if "LOGGING_MAX_SIZE" in config else 10485760),
                                       backupCount=config[
                                           'LOGGING_LOGS_TO_KEEP'] if "LOGGING_LOGS_TO_KEEP" in config else 5
                                       )
    file_handler.setFormatter(formatter)

    l.setLevel(level)
    l.addHandler(file_handler)


def main_loop():
    """
    Starts up the main bot loop and listens for a keyboard interrupt to quit it
    :return:
    """

    try:
        bot.start()
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        main_log.exception('OOPS')


if __name__ == "__main__":
    directory = os.path.dirname(sys.argv[0])
    if not directory.startswith('/'):
        directory = os.path.abspath("{}/{}".format(os.getcwd(),
                                                   directory
                                                   ))

    config = yaml.load(file('conf/rtmbot.conf', 'r'))
    debug = config["DEBUG"] if "DEBUG" in config else False
    input_logging = config[
        'INPUT_LOGGING'] if "INPUT_LOGGING" in config else False
    bot = RtmBot(config["SLACK_TOKEN"])
    site_plugins = []

    main_log_file = config[
                        'LOGPATH'] + config['LOGFILE'] if "LOGPATH" in config and "LOGFILE" else "bot.log"

    setup_logger("main_logs", main_log_file, logging.INFO)
    main_log = logging.getLogger('main_logs')

    if input_logging:
        input_log_file = config['LOGPATH'] + config[
            'INPUT_LOGFILE'] if "LOGPATH" in config and "INPUT_LOGFILE" else "inputs.log"
        setup_logger("input_logs", input_log_file, logging.INFO)
        input_log = logging.getLogger('input_logs')

    main_loop()
