# THE ULMG
A Django site for maintaining baseball data for a strat-o-matic league because the Strat software doesn't have useful player management built in.

## Features
### Rosters
* All owned players imported
* Many unowned players imported from prospect lists, recent stats, and projected stats
* Owners can protect players and add players to various rosters
* Owners can drop players to get their rosters to the appropriate size post-draft

### Drafts
* Administrators can run a draft, adding players to teams in real time
* Owners can search for players via the public site with many filters
* Administrators can add new players quickly to keep up with the draft
* Administrators can generate picks for the whole league quickly
* Handles both offseason and midseason drafts

### Trades
* Administrators can create trades, moving players and picks between teams in real time
* Owners can see old trades as well as recent trades on the public site
* An owner's roster will update immediately when trades are posted

## Contribute to the site code
### 0: prerequisites
* Running PostgreSQL instance
* Consult the `database` section in `config.dev.settings` to make sure you have a database / user set up and exported so Django can see it.
* Python3, virtualenv and virtualenvwrapper installed
* Talked to Jeremy about getting SSH access to the server

### 1: Get it started
```
mkvirtualenv ulmg
git clone https://github.com/jeremyjbowers/ulmg.git && cd ulmg
pip install -r requirements.txt
pip install -r dev.requirements.txt
add2virtualenv .
add2virtualenv config
add2virtualenv ulmg
export DJANGO_SETTINGS_MODULE=config.dev.settings
```

### 2: Pull and load data
```
fab get_data
django-admin migrate
django-admin reload
```

### 3: Preserve your data changes
```
django-admin dumpdata ulmg > data/fixtures/ulmg.json
git add .
git commit -m "data updated"
git push origin master
```

### 4: Deploy changes
```
fab deploy
```

If data changes:
```
fab mgmt:reload
```
WARNING: Do not run reload on the server if you have not pulled updated data recently. You might overwrite a change made on the server not represented on your local database, e.g., a recent trade, a correction to a player, or some other update.


## Coming Features
### Slack integration
* [slack slash commands](https://api.slack.com/slash-commands)