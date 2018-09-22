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
from slackclient import SlackClient


from api import API

class TwoBot:
    """ The almighty two bot class, instantiate it, then run() it """

    SLACK_TOKEN = os.environ["TWO_SLACK_API_TOKEN"]
    KEYWORD = os.environ["TWO_KEYWORD"]
    COMMAND = os.environ["TWO_COMMAND"]
    FILENAME = "twodata.json"  # This should really be a config option

    def __init__(self):
        self.slack = SlackClient(TwoBot.SLACK_TOKEN)
        self.cache = {} # Cache for Slack API calls; (user ID) -> (Slack API response)["user"]
        self.twoinfo = None
        if not os.path.isfile(TwoBot.FILENAME):
            with open(TwoBot.FILENAME, "w+") as datafile:
                datafile.write("{}")
                datafile.close()
        with open(TwoBot.FILENAME, "r") as datafile:
            self.twoinfo = json.loads(datafile.read())
            for key in ["lasttime", "limitmsgtime", "twos"]:
                if key not in self.twoinfo:
                    self.twoinfo[key] = {}
        self.api = API(self)
        self.api.start()

    def save_data(self):
        """ Save the data in the twoinfo structure """
        with open(TwoBot.FILENAME, "w") as datafile:
            datafile.write(json.dumps(self.twoinfo))

    def is_a_user(self, user):
        """ Checks if a user is know to exist or to have existed """
        if user is None:
            return False
        if user.startswith("I-"):
            # IRC users exist only if they have been twod before
            # because there is no good way to properly check if they
            # exist
            return user in self.twoinfo["twos"]
        # For slack users, we can check if they exist.
        return self.slack.api_call(
            "users.info",
            user=user
        ).get("user") is not None

    def user_info(self, user):
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
            result = self.slack.api_call(
                "users.info",
                user=user
            ).get("user")
            result["fetched"] = time.time()
            self.cache[user] = result
            return result

    def channel_info(self, channel):
        """ Gets the channel info dict from slack for a user ID """
        return self.slack.api_call(
            "channels.info",
            channel=channel
        ).get("channel")

    def send_message(self, channel, text):
        """ Send `text` as a message to `channel` in slack """
        return self.slack.api_call(
            "chat.postMessage",
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

    def handle_command(self, msgtext, channelid):
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
                ["%s: %d" % (TwoBot.user_name(self.user_info(user)), num)
                 for user, num, _ in leaders])
            self.send_message(
                channelid, "Leaderboard of shame: %s" % (text))
        if len(parts) == 2:
            match = re.search(
                r"(?:^<(@[^>]*)>$|^([^@<>\n ]+)$)", parts[1])
            if not match:
                self.send_message(
                    channelid, "Malformed %s command, didn't recognise parameter" %
                    (TwoBot.COMMAND))
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
                if not self.is_a_user(userid):
                    self.send_message(channelid, "No such user")
                else:
                    self.send_message(channelid, "%s has a total of %d" % (
                        TwoBot.user_name(self.user_info(userid)),
                        self.twoinfo["twos"].get(TwoBot.lower_id(userid), 0)))
        if len(parts) > 2:
            self.send_message(
                channelid, "Malformed %s command, specify zero or one parameters "
                "where the optional parameter is a  \"@mention\" for slack users "
                "or \"nick\" for IRC users" % (TwoBot.COMMAND))

    def handle_keyword(self, channelid, user, userid):
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
                self.send_message(channelid, "Rate limit: %s cannot be %s'd again until %s" % (
                    TwoBot.user_name(user), TwoBot.KEYWORD, timeoutstr))
                self.save_data()
        else:
            self.twoinfo["twos"][userid] += 1
            self.twoinfo["lasttime"][userid] = now
            self.save_data()
            self.send_message(channelid, "Whoops! %s got %s'd! (total: %d)" % (
                TwoBot.user_name(user), TwoBot.KEYWORD, self.twoinfo["twos"][userid]))

    def run_once(self):
        """ Wait until a messages is available, then deal with it and return """
        data_list = self.slack.rtm_read(blocking=True)
        for data in data_list:
            # There's lots of reasons to ignore a message...
            data_type = data.get("type")
            if data_type != "message":
                # Must be of type message
                continue
            channelid = data.get("channel")
            channel = self.channel_info(channelid)
            if channel is None:
                # Must have a valid channel
                continue
            userid = data.get("user")
            user = self.user_info(userid)
            if user is None:
                if data.get('subtype') == 'bot_message' and data.get('bot_id') == 'B4ZFXE0A0':
                    # Hardcoded exception for using IRC bridge with this bot id
                    userid = "I-" + data.get("username")
                    user = self.user_info(userid)
                else:
                    # Must be from a valid user
                    continue
            msgtext = data.get("text")
            print("Message in %s, from %s: %s" %
                  (channel.get("name"), TwoBot.user_name(user), data.get("text")))

            if not msgtext:
                # Must contain some text
                continue
            msgtext = msgtext.strip()

            # At this point we have a valid message
            if msgtext.startswith(TwoBot.COMMAND):
                self.handle_command(msgtext, channelid)

            if any([
                    msgtext == TwoBot.KEYWORD,
                    msgtext == "_%s_" % (TwoBot.KEYWORD),
                    msgtext == "*%s*" % (TwoBot.KEYWORD)
                ]):
                self.handle_keyword(channelid, user, userid)

    def run(self):
        """ Run the slack bot! Unitil interrupted """
        if not self.slack.rtm_connect():
            print("Unable to connect")
        else:
            print("Connected to slack")
            while True:
                self.run_once()


if __name__ == "__main__":
    TwoBot().run()
