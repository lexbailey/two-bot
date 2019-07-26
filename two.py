#!/usr/bin/env python
"""
Two-bot
A slack bot for counting the number of times people have been
called out for leaving their keyboard unattended.
"""

import os
import re
import time
import json
from datetime import datetime
from operator import itemgetter
from slack import RTMClient, WebClient
import asyncio
import yaml

from api import API

class TwoBot:
    """ The almighty two bot class, instantiate it, then run() it """

    def __init__(self):
        try:
            config = yaml.load(open('config.yaml'), Loader=yaml.Loader)
        except FileNotFoundError as e:
            print("No config.yaml found - have you copied config_example.yaml to config.yaml?")
            exit(2)
        try:
            self.SLACK_TOKEN = config['slack_token']
            self.KEYWORD = str(config['keyword']) # 2 in YAML will be a number, not str
            self.COMMAND = config['command']
            self.FILENAME = config.get("data_file", "twodata.json")
            self.API_ENABLE = config.get("api_enable", False)
            self.API_ADDRESS = config.get("api_address", "0.0.0.0")
            self.API_PORT = config.get("api_port", 2222)
        except KeyError as e:
            print("Config.yaml missing some values! {}".format(e))
            exit(3)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.rtm = RTMClient(token=self.SLACK_TOKEN, run_async=True, loop=self.loop)
        self.web = WebClient(token=self.SLACK_TOKEN, run_async=True, loop=self.loop)

        self.rtm.run_on(event="message")(self.handle_message)

        self.cache = {} # Cache for Slack API calls; (user ID) -> (Slack API response)["user"]
        self.twoinfo = None
        if not os.path.isfile(self.FILENAME):
            with open(self.FILENAME, "w+") as datafile:
                datafile.write("{}")
                datafile.close()
        with open(self.FILENAME, "r") as datafile:
            self.twoinfo = json.loads(datafile.read())
            for key in ["lasttime", "limitmsgtime", "twos"]:
                if key not in self.twoinfo:
                    self.twoinfo[key] = {}
        if self.API_ENABLE:
            self.starttime = datetime.utcnow()
            print("{} {} {} starttime".format(self, type(self), self.starttime))
            self.api = API(self, host=self.API_ADDRESS, port=self.API_PORT)
            self.api.start()

    def save_data(self):
        """ Save the data in the twoinfo structure """
        with open(self.FILENAME, "w") as datafile:
            datafile.write(json.dumps(self.twoinfo))

    async def is_a_user(self, user):
        """ Checks if a user is know to exist or to have existed """
        if user is None:
            return False
        if user.startswith("I-"):
            # IRC users exist only if they have been twod before
            # because there is no good way to properly check if they
            # exist
            return user in self.twoinfo["twos"]
        # For slack users, we can check if they exist.
        return (await self.web.users_info(
            user=user
        )).get("user") is not None

    async def user_info(self, user):
        """ Gets the user info dict from slack for a user ID """
        if user is None:
            return None
        if user.startswith("I-"):
            # IRC user
            nick = user[2:]
            return {"name": nick, "irc_user":True}
        if user in self.cache and (time.time() - self.cache[user]["fetched"]) < 900: 
            # could expose cache time (900s) as a config value
            return self.cache[user]
        else:
            result = (await self.web.users_info(
                user=user
            )).get("user")
            result["fetched"] = time.time()
            self.cache[user] = result
            return result

    async def channel_info(self, channel):
        """ Gets the channel info dict from slack for a user ID """
        return (await self.web.channels_info(
            channel=channel
        )).get("channel")

    async def send_message(self, channel, text):
        """ Send `text` as a message to `channel` in slack """
        return await self.web.chat_postMessage(
            channel=channel,
            text=text
        )

    @staticmethod
    def get_dict_string(input_dict, path):
        """ Lookup a valud in the dict from a path joined with `.` """
        parts = path.split(".")
        mydict = input_dict
        for part in parts:
            if part in mydict:
                if isinstance(mydict[part], dict):
                    mydict = mydict[part]
                else:
                    value = mydict[part]
                    if isinstance(value, str):
                        if value.strip() != "":
                            return value.strip()
                        return None
            else:
                return None

    @staticmethod
    def user_name(user):
        """ Get the name of the user at it should appear in slack """
        if user is None:
            return "<Unknown User>"
        namepaths = [
            "profile.display_name_normalized",
            "profile.display_name",
            "profile.real_name_normalized",
            "profile.real_name",
            "real_name",
            "name"
        ]
        for path in namepaths:
            name = TwoBot.get_dict_string(user, path)
            if name is not None:
                return name
        return "<Unknown User>"

    @staticmethod
    def lower_id(userid):
        """ Make a user ID lower case, if it is an IRC nick style ID """
        if userid.startswith("I-"):
            return "I-" + userid[2:-6].lower() + " (IRC)"
        return userid

    async def handle_command(self, msgtext, channelid):
        """ respond to a command message """
        parts = [part for part in msgtext.split(" ") if part != ""]
        if len(parts) == 1:
            twos = self.twoinfo["twos"]
            times = self.twoinfo["lasttime"]
            usertimes = [(user, number, times[user])
                         for (user, number) in twos.items()]
            leaders = list(
                reversed(sorted(usertimes, key=itemgetter(1, 2))))
            numleaders = 5
            if len(leaders) > numleaders:
                leaders = leaders[0:numleaders]
            text = ", ".join(
                ["%s: %d" % (TwoBot.user_name(await self.user_info(user)), num)
                 for user, num, _ in leaders])
            await self.send_message(
                channelid, "Leaderboard of shame: %s" % (text))
        if len(parts) == 2:
            match = re.search(
                r"(?:^<(@[^>]*)>$|^([^@<>\n ]+)$)", parts[1])
            if not match:
                await self.send_message(
                    channelid, "Malformed %s command, didn't recognise parameter" %
                    (self.COMMAND))
            else:
                userid = match.groups()[0]
                if userid is None:
                    userid = match.groups()[1]
                if userid is None:
                    # uh-oh
                    return  # ???
                if userid.startswith("@U"):
                    userid = userid[1:]
                else:
                    userid = "I-%s (IRC)" % (userid)
                if not await self.is_a_user(userid):
                    await self.send_message(channelid, "No such user")
                else:
                    await self.send_message(channelid, "%s has a total of %d" % (
                        TwoBot.user_name(self.user_info(userid)),
                        self.twoinfo["twos"].get(TwoBot.lower_id(userid), 0)))
        if len(parts) > 2:
            await self.send_message(
                channelid, "Malformed %s command, specify zero or one parameters "
                "where the optional parameter is a  \"@mention\" for slack users "
                "or \"nick\" for IRC users" % (self.COMMAND))

    async def handle_keyword(self, channelid, user, userid):
        """ respond to the keyword """
        userid = TwoBot.lower_id(userid)
        if userid not in self.twoinfo["twos"]:
            self.twoinfo["twos"][userid] = 0
        if userid not in self.twoinfo["lasttime"]:
            self.twoinfo["lasttime"][userid] = 0
        then = self.twoinfo["lasttime"][userid]
        endtime = then + (60 * 10)
        now = time.time()
        if endtime > now:
            # Rate limit
            if userid not in self.twoinfo["limitmsgtime"]:
                self.twoinfo["limitmsgtime"][userid] = 0
            limittime = self.twoinfo["limitmsgtime"][userid]
            last = self.twoinfo["lasttime"][userid]
            if limittime < last:
                self.twoinfo["limitmsgtime"][userid] = time.time()
                endtime_rounded = ((endtime // 60)+1)*60 # Round up to next minute
                timeoutstr = datetime.fromtimestamp(endtime_rounded).strftime("%H:%M")
                await self.send_message(channelid, "Rate limit: %s cannot be %s'd again until %s" % (
                    TwoBot.user_name(user), self.KEYWORD, timeoutstr))
                self.save_data()
        else:
            self.twoinfo["twos"][userid] += 1
            self.twoinfo["lasttime"][userid] = now
            self.save_data()
            await self.send_message(channelid, "Whoops! %s got %s'd! (total: %d)" % (
                TwoBot.user_name(user), self.KEYWORD, self.twoinfo["twos"][userid]))

    async def handle_message(self, **payload):
        data = payload["data"]
        # There's lots of reasons to ignore a message...
        data_type = data.get("type")
        if data_type != "message" and data_type != None: # recent API omits "type"
            # Must be of type message
            return
        channelid = data.get("channel")
        channel = await self.channel_info(channelid)
        if channel is None:
            # Must have a valid channel
            return
        userid = data.get("user")
        user = await self.user_info(userid)
        if user is None:
            if data.get('subtype') == 'bot_message' and data.get('bot_id') == 'B4ZFXE0A0':
                # Hardcoded exception for using IRC bridge with this bot id
                userid = "I-" + data.get("username")
                user = await self.user_info(userid)
            else:
                # Must be from a valid user
                return
        msgtext = data.get("text")

        if not msgtext:
            # Must contain some text
            return
        msgtext = msgtext.strip()

        # At this point we have a valid message
        if msgtext.startswith(self.COMMAND):
            await self.handle_command(msgtext, channelid)

        if any([
                msgtext == self.KEYWORD,
                msgtext == "_%s_" % (self.KEYWORD),
                msgtext == "*%s*" % (self.KEYWORD)
            ]):
            print("Message in %s, from %s: %s" %
                    (channel.get("name"), TwoBot.user_name(user), data.get("text")))
            await self.handle_keyword(channelid, user, userid)

    def run(self):
        """ Run the slack bot! Until interrupted """
        self.loop.run_until_complete(self.rtm.start())
        self.loop.close()


if __name__ == "__main__":
    TwoBot().run()
