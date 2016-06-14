#slack_rtmbot

 * [slack_rtmbot](#ig_skynet)
   * [Overview](#overview)
   * [Dependencies](#dependencies)
   * [Installation](#installation)
   * [Adding Plugins](#adding-plugins)


##Overview
slack_rtmbot is a framework for a Slackbot based on python and the Slack RTM API. 

slack_rtmbot is a callback based bot framework designed to be modified and extended to fit your specific needs. The plugins architecture should be familiar to anyone with knowledge to the [Slack API](https://api.slack.com) and Python. The configuration file format is YAML.

The code started as a fork of [Python rtmbot](https://github.com/slackhq/python-rtmbot) but underwent some changes to fit our specific needs.


##Dependencies

* websocket-client https://pypi.python.org/pypi/websocket-client/
* python-slackclient https://github.com/slackhq/python-slackclient

##Installation


1. Download the slack_rtmbot framework

        git clone https://github.com/andrewthetechie/slack_rtmbot.git
        cd slack_rtmbot

2. Install dependencies ([virtualenv](http://virtualenv.readthedocs.org/en/latest/) is recommended.)

        pip install -r requirements.txt

3. Configure slack_rtmbot (https://api.slack.com/bot-users)
        
        cp conf/rtmbot.conf.example conf/rtmbot.conf
        vi rtmbot.conf
          SLACK_TOKEN: "xoxb-11111111111-222222222222222"

*Note*: At this point your bot is ready to run, however no plugins are configured. Check out the [Core Plugins](https://github.com/andrewthetechie/slack_rtmbot_core_plugins) for a basic set to plugins to start with.

##Adding Plugins

Plugins can be installed as .py files in the ```plugins/``` directory OR as a .py file in any first level subdirectory. If your plugin uses multiple source files and libraries, it is recommended that you create a directory. You can install as many plugins as you like, and each will handle every event received by the bot independently. Plugin execution is threaded and non-blocking.

