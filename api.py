from bottle import Bottle, response, HTTPError
from threading import Thread
from operator import itemgetter
import time
import json

class API(Bottle):
    def __init__(self, twobot, host="0.0.0.0", port=2222):
        Bottle.__init__(self)
        self.thread = Thread(name="two-bot API",target=self.worker, args=[host,port])
        self.bot = twobot

        self.route('/', callback=self.index)
        self.route('/ids', callback=self.ids)
        self.route('/twos/<user>', callback=self.twos)
        self.route('/leaderboard', callback=self.leaderboard)

        self.route('/info/<user>', callback=self.info)

    def start(self):
        self.thread.start()

    def worker(self,host,port): # run() method of thread
        self.run(host=host, port=port)

    def get_user(self, user):
        """
            Selects values from TwoBot.user_info to for use in GET /info/<user>, as TwoBot.user_info exposes too
            much information from the Slack API
        """
        info = self.bot.user_info(user)
        if info.get("irc_user", False):
            return {
                "name": info["name"],
                "id": user,
                "is_bot": True,
                "real_name": "{} (IRC)".format(info["name"])
            }
        elif info is None: return None
        else:
            return {
                "name": info["name"],
                "real_name": info["real_name"],
                "id": user,
                "is_bot": info.get("is_bot", False)
            }

    """ API endpoints """

    def index(self):
        """ GET / """
        response.content_type = "text/plain"
        return "Hello, two-bot!"

    def ids(self):
        """ GET /ids 
            application/json

            Returns a JSON array of user IDs for all the users that two-bot 
            tracks (any user that has been two'd). See GET /info/<user> for
            more information on the user ID format.
        """
        # Bottle doesn't automatically JSONify lists like it does dicts
        response.content_type = "application/json"
        return json.dumps(list(self.bot.twoinfo["twos"].keys()))

    def twos(self, user):
        """ GET /twos/<user>
            application/json

            <user>: User ID from GET /ids. Either a Slack username or
                    "I-<irc nick> (IRC)".
            Returns the number of times ("twos") and the timestamp of the last
            time ("last") a user was two'd.
        """
        if user in self.bot.twoinfo["twos"]:
            return {
                "id": user,
                "twos": self.bot.twoinfo["twos"][user],
                "last": self.bot.twoinfo["lasttime"][user]
            }
        # else...        
        raise HTTPError(status=404, body="No user with that ID")

    def leaderboard(self):
        """ GET /leaderboard
            application/json

            Returns a sorted JSON array of objects. FIRST element is the user
            with the MOST two's. Objects include:
                id: user id as per GET /ids
                name: Slack username or IRC nick (not unique)
                twos: number of times two'd
                last: timestamp of last two

        """
        response.content_type = "application/json"
        return json.dumps(sorted([{
                "id": user,
                "name": self.get_user(user)["name"],
                "twos": self.bot.twoinfo["twos"][user],
                "last": self.bot.twoinfo["lasttime"][user]
                }
                for user in self.bot.twoinfo["twos"].keys()],
            key=itemgetter("twos"), reverse=True))

    def info(self, user):
        """ GET /info/<user>
            application/json

            <user>: User ID from GET /ids. Either a Slack username or
                    "I-<irc nick> (IRC)"
            Returns information object about <user>:
                id: <user> param as called
                name: username or IRC nick
                real_name: Real name from Slack or "<irc nick> (IRC)"
                is_bot: True if either this user is an IRC user passed through
                        the IRC bridge or a Slack bot that's been two'd (rare)
        """
        return self.get_user(user)