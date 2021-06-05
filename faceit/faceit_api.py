import cProfile
import datetime
import io
import logging
import pstats

import requests

from config import FACEIT_API, FACEIT_API_V1
from faceit.faceit_data import FaceitData
from functions import config_functions


def profile(fnc):
    def inner(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        retval = fnc(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
        return retval

    return inner


@profile
def function_to_track():
    pass


def get_api_data():
    """
    Get data from the API to fill the Overlay
    :returns user, user_state, matches
    """
    matches = None
    logging.info("start get_api_data")
    name = config_functions.get_faceit_name_from_db()
    faceit_data = FaceitData(FACEIT_API)

    user = faceit_data.player_details(name)
    user_stats = faceit_data.player_stats(user["player_id"], "csgo")
    match = faceit_data.player_matches(user["player_id"], "csgo", return_items=50)
    if match['items']:
        try:
            matches = faceit_data.match_stats(match['items'][0]['match_id'])
        except ValueError:
            logging.error("Faceit Matches are broken !")
    else:
        matches = None
    return user, user_stats, matches, match


def get_api_data_user():
    """
    Get user data from API
    :returns user
    """
    logging.info("get_api_data_user")
    name = config_functions.get_faceit_name_from_db()
    faceit_data = FaceitData(FACEIT_API)

    user = faceit_data.player_details(name)
    return user


def get_api_user(name):
    """
    Check if the user is registered on faceit
    :returns 1 Ok
    :returns None nOk
    """
    try:
        logging.info("get_api_data_user")
        faceit_data = FaceitData(FACEIT_API)
        user = faceit_data.player_details(name)
        if user:
            return 1
    except ValueError:
        logging.error("Faceit Name is not correct !")
        return None


def get_data_from_v1_api():
    """
    Get data from v1 API
    :returns data_v1
    """
    logging.info("start get_data_from_v1_api")
    user = get_api_data_user()
    API = FACEIT_API_V1.format(user["player_id"])
    try:
        r = requests.get(API, stream=True)
        data_v1 = r.json()
        return data_v1
    except requests.exceptions.RequestException:
        logging.info("Could not get data from API_V1 with user {}".format(user))


def get_faceit_data_from_api(mode):
    """
    Get data and return the values for the Overlay
    """
    acResult = ""
    acKd = ""
    iKills = 0
    iDeath = 0
    acEloDiff = 0
    acMap = ""
    acEloToday = ""
    iElo = 0
    acScore = ""
    iWin = 0
    iLoss = 0
    iRank = 0
    iStreak = 0
    iMatches = 0
    iMatchesWon = 0
    logging.info("start get_faceit_data_from_api")
    try:
        user, user_stats, matches, match = get_api_data()
        data_v1 = get_data_from_v1_api()
        EloToday = get_elo_today_from_v1_api(data_v1)
        iElo = user["games"]["csgo"]["faceit_elo"]
        acEloToday = EloToday
        iRank = user["games"]["csgo"]["skill_level"]
        iStreak = user_stats["lifetime"]["Current Win Streak"]
        iMatches = user_stats["lifetime"]["Matches"]
        iMatchesWon = user_stats["lifetime"]["Wins"]
        if matches:
            acMap = matches["rounds"][0]["round_stats"]["Map"][3:]
            acScore = matches["rounds"][0]["round_stats"]["Score"]
            for x in matches["rounds"][0]["teams"][0]["players"]:
                if x["player_id"] == user["player_id"]:
                    iKills = x["player_stats"]["Kills"]
                    iDeath = x["player_stats"]["Deaths"]
                    acResult = x["player_stats"]["Result"]
                    acKd = x["player_stats"]["K/D Ratio"]
                    if "elo" in data_v1[0]:
                        acEloDiff = int(data_v1[0]["elo"]) - int(data_v1[1]["elo"])

            for x in matches["rounds"][0]["teams"][1]["players"]:
                if x["player_id"] == user["player_id"]:
                    iKills = x["player_stats"]["Kills"]
                    iDeath = x["player_stats"]["Deaths"]
                    acResult = x["player_stats"]["Result"]
                    acKd = x["player_stats"]["K/D Ratio"]
                    if "elo" in data_v1[0]:
                        acEloDiff = int(data_v1[0]["elo"]) - int(data_v1[1]["elo"])

        if acResult == "1":
            acResult = "W"
        else:
            acResult = "L"

        if acEloDiff > 0:
            acEloDiff = "+" + str(acEloDiff)
        if matches:
            iWin, iLoss = get_win_loss_from_api(mode, match)
    except ValueError:
        logging.error("could not get data from v1 [elo] retry")

    return iElo, acEloToday, iRank, acResult, acScore, acKd, \
           acMap, iStreak, iMatches, iMatchesWon, acEloDiff, iKills, \
           iDeath, iWin, iLoss


def get_win_loss_from_api(mode, matches):
    logging.info("start get_win_loss_from_api")
    user = get_api_data_user()
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    iCountWin = 0
    iCountLoss = 0
    for x in matches["items"]:
        date: str = str(x["finished_at"])
        dateint: int = date[0:10]
        datetime_time = datetime.datetime.fromtimestamp(int(dateint))
        datetimestr = str(datetime_time)
        if datetimestr[0:10] >= str(week_ago) and mode == 1:
            for player in x["teams"]["faction1"]["players"]:
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction1":
                    iCountWin = iCountWin + 1
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction2":
                    iCountLoss = iCountLoss + 1
            for player in x["teams"]["faction2"]["players"]:
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction2":
                    iCountWin = iCountWin + 1
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction1":
                    iCountLoss = iCountLoss + 1
        if datetimestr[0:10] == str(today) and mode == 0:
            for player in x["teams"]["faction1"]["players"]:
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction1":
                    iCountWin = iCountWin + 1
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction2":
                    iCountLoss = iCountLoss + 1
            for player in x["teams"]["faction2"]["players"]:
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction2":
                    iCountWin = iCountWin + 1
                if player["player_id"] == user["player_id"] and x["results"]["winner"] == "faction1":
                    iCountLoss = iCountLoss + 1
    return iCountWin, iCountLoss


def get_faceit_elo_data_from_api():
    """
    Get Elo from API
    """
    logging.info("start get_faceit_elo_data_from_api")
    user = get_api_data_user()

    iElo = user["games"]["csgo"]["faceit_elo"]
    return iElo


def get_elo_today_from_v1_api(data_v1):
    """
    Calculate the +- Elo in a Day
    """
    logging.info("start get_elo_today_from_v1_api")
    EloDiff = 0
    EloStart = 0
    found_data = 0
    today = datetime.date.today()
    for x in data_v1:
        date: str = str(x["date"])
        dateint: int = date[0:10]
        datetime_time = datetime.datetime.fromtimestamp(int(dateint))
        datetimestr = str(datetime_time)
        if datetimestr[0:10] != str(today) and found_data == 0:
            try:
                if "elo" in x:
                    EloStart = x["elo"]
                    found_data = 1
            except ValueError:
                logging.error("could not get data from v1 [elo] retry")

    for x in data_v1:
        date: str = str(x["date"])
        dateint: int = date[0:10]
        datetime_time = datetime.datetime.fromtimestamp(int(dateint))
        datetimestr = str(datetime_time)
        if datetimestr[0:10] == str(today):
            try:
                if "elo" in x:
                    EloDiff = int(EloStart) - int(x["elo"])
                    break
            except ValueError:
                logging.error("could not get data from v1 [elo] retry")

    if EloDiff < 0:
        EloDiff = "+" + str(abs(EloDiff))
    elif EloDiff > 0:
        EloDiff = "-" + str(abs(EloDiff))
    else:
        pass
    return EloDiff
