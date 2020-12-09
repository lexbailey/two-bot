# Two-bot

Two-bot is a slack bot that counts the number of times a keyword is sent in any channel to witch the bot has been invited.

It's only practical application is to be a game. The game is to call people out for leaving their keyboard unattended, by sending the keyword from their account. Two-bot can show a leaderboard-of-shame with a list of the top victims. It can also tell you the current count for a given user.

## This repo is no longer maintained

I have moved on from where I was when I cared about maintaining this code. Other forks are available, which may or may not be better maintained than this version.

## Installation

 - Clone the repo

```
git clone git@github.com:danieljabailey/two-bot.git
```

 - Initialise the venv

```
cd two-bot
./initvenv.sh
source venv/bin/activate # or similar, for your shell (e.g. activate.fish)
```
(This will create a venv and install the dependencies in the venv)

 - Get a bot api key for testing (and optionally another for production)

This is done by going to the new bot page for your slack workspace `https://<workspace-name>.slack.com/services/new/bot`
Pick a username and create the bot user, then copy the api key...

```
cp config_example.yaml config.yaml
editor config.yaml # paste your api key in the obvious place, and choose a keyword and command
```

 - Run the bot

Running `./run.sh` will activate the venv and run the bot.

## REST API
You can get real-time access to the current two statistics via the provided REST API. It runs on `0.0.0.0:2222` by default, but you can change this in the config (or disable it entirely). Below are the methods you can use:

### GET /ids
Returns JSON array of *user IDs* for all the users tracked by two-bot (any user that has been two'd).
User IDs are Slack usernames unless they are forwarded from IRC, in which case they are `I-<irc nick> (IRC)`.
### GET /leaderboard
Returns a JSON array of objects, in descending order of two's (**first** element is the object with the **most** two's).
Objects include:
 - `id`: user ID as per **GET /ids**.
 - `name`: Slack username or IRC nick
 - `twos`: number of times two'd
 - `last`: timestamp of last two
### GET /info/<id>
Returns in-deptth information about the user with id `<id>`, as JSON object:
 - `id`: `<id>` as in URL
 - `name`: username or IRC nick
 - `real_name`: Real name from Slack or `<irc nick> (IRC)`.
 - `is_bot`: True if either this user is an IRC user passed through the IRC bridge or a Slack bot that's been two'd.
### GET /twos/<id>
Returns information about when this user was last two'd, as JSON object:
 - `id`: `<id>` as in URL
 - `twos`: number of times two'd
 - `last`: timestamp of last two

Will fail with `404 not found` if an ID is passed that doesn't match a user (Even if that user is in Slack).
### GET /uptime
Returns information about how long the application has been running, as JSON object:
 - `starttime`: timestamp of when the application was started (UTC, in floating-point seconds)
 - `starttime_s`: ISO representation of `starttime`
 - `duration`: Seconds since `starttime` (floating-point)

## Licence

published under the MIT licence, see `LICENSE` (with an "S")
