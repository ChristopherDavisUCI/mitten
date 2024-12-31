import streamlit as st
import pandas as pd
from itertools import product

div_series = pd.read_csv("data/divisions.csv", index_col=0).squeeze()
div_series.name = None
# AFC WEST -> AFC
conf_series = div_series.apply(lambda s: s.split()[0])

st.set_page_config(page_title="Playoff lineups", page_icon=":material/sports_football:")

st.title("Playoff lineups")

st.write("Have Underdog email you your exposure csv file and upload it below.")

file = st.file_uploader("Exposure csv", type="csv", accept_multiple_files=False)

# Keys are tuples of super bowl matchups (AFC, NFC), values are lists of draft boards
matchup_dct = {}

# Basically just to combine WR and TE
def update_position_series(pos_series):
    pos_dct = {}
    pos_dct["QB"] = pos_series.get("QB", 0)
    pos_dct["RB"] = pos_series.get("RB", 0)
    pos_dct["WR/TE"] = pos_series.get("WR", 0) + pos_dct.get("TE", 0)
    return pd.Series(pos_dct)


def is_complete_lineup(total_series):
    return (
        (total_series["QB"] >= 1) and (total_series["RB"] >= 1) and (total_series["WR/TE"] >= 2) and 
        ((total_series["WR/TE"] + total_series["WR/TE"]) >= 4)
    )


def process_draft(df_draft, key):
    # The team_specific dictionary will be something like "KC": {"QB": 1, "RB": 4}
    team_specific = {}
    teams = []
    # this dictionary will indicate which teams appear from each conference
    conferences = {"AFC": [], "NFC": []}

    for team, df_team in df_draft.groupby("Team"):
        teams.append(team)
        conferences[conf_series[team]].append(team)
        team_specific[team] = update_position_series(df_team["Position"].value_counts())
    
    for pair in product(conferences["AFC"], conferences["NFC"]):
        # Will list the total number of QB, RB, and WR/TE
        total_series = team_specific[pair[0]] + team_specific[pair[1]]
        if is_complete_lineup(total_series):
            try:
                matchup_dct[pair].append(key)
            except KeyError:
                matchup_dct[pair] = [key]

try:
    df = pd.read_csv(file)
    df["Team"] = df["Team"].replace({"LAR": "LA"})
    
    for key, df_draft in df.groupby("Draft"):
        process_draft(df_draft, key)
except ValueError:
    pass

for pair, keys in sorted(matchup_dct.items(), key= lambda tup: len(tup[1]), reverse=True):
    st.header(f"Matchup: {pair[0]} vs {pair[1]}, you have {len(keys)} total drafts")
    for key in keys:
        st.page_link(f"https://underdogfantasy.com/draft-board/{key}",  label=":blue[View full draft board]")
        df_sb = df[(df["Draft"] == key) & (df["Team"].isin(pair))].copy().sort_values("Pick Number")
        names = []
        for first_name, last_name in zip(df_sb["First Name"].values, df_sb["Last Name"].values):
            names.append(f"{first_name} {last_name}")
        st.write(", ".join(names))
        st.write("")
