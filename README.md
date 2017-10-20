# Two-bot

Two-bot is a slack bot that counts the number of times a keyword is sent in any channel to witch the bot has been invited.

It's only practical application is to be a game. The game is to call people out for leaving their keyboard unattended, by sending the keyword from their account. Two-bot can show a leaderboard-of-shame with a list of the top victims. It can also tell you the current count for a given user.

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
cp secrets_example.sh secrets.sh
editor secrets.sh # paste your API key in the obvious place
```

 - Configure the bot

```
cp config_example.sh config.sh
editor config.sh # Pick your test keyword and your test command word
```

 - Run the bot

Running `./run.sh` will source `secrets.sh` and `config.sh` and then run the bot. Make sure you have activated the venv before running, or it will probably crash.

## Licence

published under the MIT licence, see `LICENSE` (with an "S")
