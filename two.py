#!/usr/bin/env python

import os
import re
import time
import json
from copy import copy
from operator import itemgetter
from slackclient import SlackClient

slack_token = os.environ["TWO_SLACK_API_TOKEN"]
keyword = os.environ["TWO_KEYWORD"]
sc = SlackClient(slack_token)

filename = "twodata.json"

if not os.path.isfile(filename):
    with open(filename, "w+") as datafile:
        datafile.write("{}")
        datafile.close()
with open(filename, "r") as datafile:
    twoinfo = json.loads(datafile.read())
    if "lasttime" not in twoinfo:
        twoinfo["lasttime"] = {}
    if "twos" not in twoinfo:
        twoinfo["twos"] = {}

def user_info(user):
    if user is None:
        return None
    if user.startswith("I-"):
        # IRC user
        return {"name": user[2:]}
    return sc.api_call(
        "users.info",
        user=user
    ).get("user")

def channel_info(channel):
    return sc.api_call(
        "channels.info",
        channel=channel
    ).get("channel")

def send_message(channel, text):
    return sc.api_call(
        "chat.postMessage",
        channel=channel,
        text=text
    )

def get_dict_string(d, path):
    parts = path.split(".")
    mydict = d
    for part in parts:
        if part in mydict:
            if type(mydict[part]) == dict:
                mydict = mydict[part]
            else:
                value = mydict[part]
                if isinstance(value, str):
                    if value.strip() != "":
                        return value.strip()
                    return None
        else:
            return None


def user_name(user):
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
        name = get_dict_string(user, path)
        if name is not None:
            return name
    return "<Unknown User>"

def lower_id(userid):
    if userid.startswith("I-"):
        return "I-" + userid[2:-6].lower() + " (IRC)"
    return userid

if not sc.rtm_connect():
    print("Unable to connect")
else:
    while True:
        data_list = sc.rtm_read(blocking=True)
        for data in data_list:
            data_type = data.get("type")
            if data_type == "message":
                channelid = data.get("channel")
                channel = channel_info(channelid)
                if channel is None:
                    continue
                userid = data.get("user")
                user = user_info(userid)
                if user is None:
                    if data.get('subtype') == 'bot_message' and data.get('bot_id') == 'B4ZFXE0A0':
                        userid = "I-"+data.get("username")
                        user = user_info(userid)
                    else:
                        continue
                msgtext = data.get("text")
                print("Message in %s, from %s: %s" % (channel.get("name"), user_name(user), data.get("text")))

                if not msgtext:
                    continue
                msgtext = msgtext.strip()
                if msgtext.startswith("!two"):
                    parts = [part for part in msgtext.split(" ") if part != ""]
                    if len(parts) == 1:
                        twos = twoinfo["twos"]
                        times = twoinfo["lasttime"]
                        usertimes = [(user, number, times[user]) for (user, number) in twos.items()]
                        leaders = list(reversed(sorted(usertimes, key=itemgetter(1,2))))
                        numleaders = 5
                        if len(leaders) > numleaders:
                            leaders = leaders[0:numleaders]
                        text = ", ".join(["%s: %d" % (user_name(user_info(user)), num) for user, num, _ in leaders])
                        send_message(channelid, "Leaderboard of shame: %s" % (text))
                    if len(parts) == 2:
                        match = re.search(r"(?:^<(@[^>]*)>$|^([^@<>\n ]+)$)", parts[1])
                        if not match:
                            send_message(channelid, "Malformed !two command, didn't recognise parameter")
                        else:
                            userid = match.groups()[0]
                            if userid is None:
                                userid = match.groups()[1]
                            if userid is None:
                                # uh-oh
                                continue #???
                            if userid.startswith("@U"):
                                userid = userid[1:]
                            else:
                                userid = "I-%s (IRC)"%(userid)
                            send_message(channelid, "%s has a total of %d" % (user_name(user_info(userid)), twoinfo["twos"].get(lower_id(userid), 0)))
                    if len(parts) > 2:
                        send_message(channelid, "Malformed !two command, specify zero or one parameters where the optional parameter is a  \"@mention\" for slack users or \"nick\" for IRC users")
                if msgtext == "2":
                    userid = lower_id(userid)
                    if userid not in twoinfo["twos"]:
                        twoinfo["twos"][userid] = 0
                    if userid not in twoinfo["lasttime"]:
                        twoinfo["lasttime"][userid] = 0
                    now = time.time()
                    then = twoinfo["lasttime"][userid]
                    if then+(60*10) > now:
                        # Rate limit
                        pass
                    else:
                        twoinfo["twos"][userid] += 1
                        twoinfo["lasttime"][userid] = now
                        with open(filename, "w") as datafile:
                            datafile.write(json.dumps(twoinfo))
                        send_message(channelid, "Whoops! %s got 2'd! (total: %d)" % (user_name(user), twoinfo["twos"][userid]))

