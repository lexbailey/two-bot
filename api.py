from bottle import route, run, Bottle
from threading import Thread
from operator import itemgetter
import time
import json

class API(Bottle):
    def __init__(self, twobot, host="0.0.0.0", port=2222):
        Bottle.__init__(self)
        self.thread = Thread(name="two-bot API",target=self.worker, args=[host,port])
        self.bot = twobot

        self.cache = {}
        # Cache of user id -> minimal profile object

        self.route('/', callback=self.index)
        self.route('/ids', callback=self.ids)
        self.route('/twos/<user>', callback=self.twos)
        self.route('/leaderboard', callback=self.leaderboard)

        self.route('/info/<user>', callback=self.info)

    def start(self):
        self.thread.start()

    def worker(self,host,port): # run() method of thread
        print("Starting worker with args: {} {} {}".format(type(self),type(host),type(port)))
        self.run(host=host, port=port)

    def get_user(self, user):
        if user.startswith("I-"): # Not 100% sure what this means
            return {
                "name": user[2:].split(" ")[0], # Trim the (IRC) off IRC users
                "id": user,
                "is_bot": True,
                "real_name": user[2:] # Leave it in here
            }
        elif user in self.cache and age(self.cache[user]["fetched"]) > 900:
            return self.cache[user]
        else:
            result = self.bot.slack.api_call(
                "users.info",
                user=user
            ).get("user")
            self.cache[user] = {
                "name": result["name"],
                "real_name": result["real_name"],
                "id": user,
                "is_bot": result["is_bot"]
            }
            self.cache[user]["fetched"] = time.time()
            return self.cache[user]

    """ API endpoints """

    def index(self):
        return "Hello, two-bot!"

    def ids(self):
        return json.dumps(list(self.bot.twoinfo["twos"].keys()))

    def twos(self, user):
        if user in self.bot.twoinfo["twos"]:
            return json.dumps({
                "id": user,
                "twos": self.bot.twoinfo["twos"][user],
                "last": self.bot.twoinfo["lasttime"][user]
            })
        self.abort(404, "No user with that ID") # Should we just fail with 0 instead?

    def leaderboard(self):
        return json.dumps(
            sorted([{
                "id": user,
                "name": self.get_user(user)["name"],
                "twos": self.bot.twoinfo["twos"][user],
                "last": self.bot.twoinfo["lasttime"][user]
                }
                for user in self.bot.twoinfo["twos"].keys()],
            key=itemgetter("twos"), reverse=True)
        )

    def info(self, user):
        return json.dumps(self.get_user(user))

def age(date):
    """ helper method to streamline """
    return time.time() - date