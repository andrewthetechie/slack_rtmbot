#Creating Plugins

  * [Creating Plugins](#creating-plugins)
    * [Incoming data](#incoming-data)
      * [Special Methods](#special-methods)
        * [process_directmessage(data)](#process_directmessagedata)
        * [process_onstart()](#process_onstart)
    * [Outgoing data](#outgoing-data)
    * [Config Files](#config-files)
    * [Help](#help)
    * [Plugin data storage](#plugin-data-storage)


##Incoming data
Plugins are callback based and respond to any event sent via the rtm websocket. To act on an event, create a function definition called process_(api_method) that accepts a single arg. For example, to handle incoming messages:

    def process_message(data):
        print data

This will print the incoming message json (dict) to the screen where the bot is running.

Plugins having a method defined as ```catch_all(data)``` will receive ALL events from the websocket. This is useful for learning the names of events and debugging.

###Special Methods
There are two special methods that your plugin can have

####process_directmessage(data)
This is a special method that will only be called if the input is coming in the form of a direct message to the bot. This is designed as a helper so you do not have to evaluate the channel in each of your process_message() functions.

####process_onstart()
This is a special method that is called on the start of the bot. You can use this to setup any data that your plugin needs

##Outgoing data
Plugins can send messages back to any channel, including direct messages. This is done by appending a two item array to the outputs global array. The first item in the array is the channel ID and the second is the message text. Example that writes "hello world" when the plugin is started:

    outputs = []
    outputs.append(["C12345667", "hello world"])
        
*Note*: you should always create the outputs array at the start of your program, i.e. ```outputs = []```

##Config Files
You can define a special config file for your plugin. On install, it should be placed on conf/ directory and be named something unique (suggestion: your-plugin-name.conf).

You can also access the main bot config file by loading it:

    # load main config file
    config = yaml.load(file('conf/rtmbot.conf', 'r'))

##Help
Plugins can define two types of help - dm help and channel help. DM Help is commands that only work via DM, channel help those that work in an open channel

Help is defined in the process_help() function. A good example is the auth.py version of this:

    dm_help = []
    channel_help = []

    plugin_help = []
    # setup help
    dm_help.append("roles add [RoleName] [UserName] - Adds [RoleName] role to [UserName]")
    dm_help.append("roles remove [RoleName] [UserName] - Removes [RoleName] role from [UserName]")
    dm_help.append("roles list [Username]-Lists all the roles [Username] has")
    dm_help.append("roles list-roles-Lists all roles")
    dm_help.append("roles list-users-Lists all user names")
    dm_help.append("roles new [RoleName]-Creates a new role with [RoleName]")
    dm_help.append("roles create [RoleName]-Creates a new role with [RoleName]")

    plugin_help.append(dm_help)
    plugin_help.append(channel_help)
    return plugin_help
    
This would add 7 functions to the dm help and none to channel help. The key is to always return a list of two lists: [dm_help,channel_help]. If you have nothing to add to one of the two lists
you can just return an empty list.

##Plugin data storage
The data within a plugin persists for the life of the rtmbot process. If you need persistent data, you should use something like sqlite or the python pickle libraries.

