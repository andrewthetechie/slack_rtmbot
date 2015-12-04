#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True

import glob
import yaml
import os
import sys
import time
import logging
import re
from threading import Thread

from slackclient import SlackClient


def dbg(debug_string):
    """
    Used to write debugging information if debug is set in config
    :param debug_string:
    :return:
    """
    if debug:
        logging.info(debug_string)


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
                self.input(reply)
            self.output()
            self.autoping()
            time.sleep(config['PING_INTERVAL'] or .1)

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
            plug_help = None
            try:
                plug_help = plugin.get_help()
                if len(plug_help[0]) > 0:
                    for help in plug_help[0]:
                        self.dm_help.append(help)
                if len(plug_help[1]) > 0:
                    for help in plug_help[1]:
                        self.channel_help.append(help)
            except AttributeError:
                logging.info(
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
            for help in self.dm_help:
                message = "{}\n{}".format(message, help)
        if len(self.channel_help) > 0:
            message = "{}\n\nChannel Commands:\n-------------------\n".format(
                message)
            for help in self.channel_help:
                message = "{}\n{}".format(message, help)
        self.slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=message,
            as_user=True)
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
            match = None
            if function_name == "process_message":
                match = re.findall(
                    r"{} (help|halp|help me)".format(
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
                if channel is not None and output[1] != None:
                    if limiter == True:
                        time.sleep(.1)
                        limiter = False
                    message = output[1].encode('ascii', 'ignore')
                    # channel.send_message("{}".format(message))
                    self.slack_client.api_call(
                        "chat.postMessage", channel=output[0], text=message, as_user=True)
                    limiter = True

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
            logging.info(plugin)
            name = plugin.split('/')[-1][:-3]
#            try:
            self.bot_plugins.append(Plugin(name))
#            except:


class Plugin(object):

    def __init__(self, name, plugin_config={}):
        self.name = name
        self.module = __import__(name)
        self.outputs = []
        if name in config:
            logging.info("config found for: " + name)
            self.module.config = config[name]
        if 'setup' in dir(self.module):
            self.module.setup()

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
            return

    def get_help(self):
        """
        Runs the "process_help" function from a plugin and returns the output
        :return:
        """
        function_name = "process_help"
        return eval("self.module." + function_name)()

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
                t = Thread(
                    target=self.plugin_worker, args=(
                        function_name, data))

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
                    logging.info("output from {}".format(self.module))
                    output.append(self.module.outputs.pop(0))
                else:
                    break
            else:
                self.module.outputs = []
        return output

    def do_dm_help(self):
        dm_help = []
        while True:
            if 'dm_help' in dir(self.module):
                if self.module.dm_help and len(self.module.dm_help) > 0:
                    logging.info("dm_help from {}".format(self.module))
                    dm_help.append(self.module.dm_help.pop(0))
                else:
                    break
            else:
                self.module.dm_help = []
        return dm_help

    def do_channel_help(self):
        channel_help = []
        while True:
            if 'dm_help' in dir(self.module):
                if self.module.channel_help and len(
                        self.module.channel_help) > 0:
                    logging.info("channel_help from {}".format(self.module))
                    dm_help.append(self.module.channel_help.pop(0))
                else:
                    break
            else:
                self.module.channel_help = []
        return channel_help


class UnknownChannel(Exception):
    pass


def main_loop():
    """
    Starts up the main bot loop and listens for a keyboard interrupt to quit it
    :return:
    """
    log_file = config['LOGPATH'] + config['LOGFILE'] or "bot.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s %(message)s')
    logging.info(directory)
    try:
        bot.start()
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        logging.exception('OOPS')


if __name__ == "__main__":
    directory = os.path.dirname(sys.argv[0])
    if not directory.startswith('/'):
        directory = os.path.abspath("{}/{}".format(os.getcwd(),
                                                   directory
                                                   ))

    config = yaml.load(file('conf/rtmbot.conf', 'r'))
    debug = config["DEBUG"]
    bot = RtmBot(config["SLACK_TOKEN"])
    site_plugins = []
    files_currently_downloading = []
    job_hash = {}

    if "DAEMON" in config:
        if config["DAEMON"]:
            import daemon
            with daemon.DaemonContext():
                main_loop()
    main_loop()
