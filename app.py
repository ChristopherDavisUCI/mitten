import streamlit as st
import pandas as pd
import numpy as np
from itertools import product
from name_helper import get_abbr


def combine_names(df, col_first, col_last, col_new="Name"):
    '''Create a new "Name" column that holds both the first and last names'''
    df = df.copy()
    df[col_new] = df.apply(lambda row: f"{row[col_first]} {row[col_last]}", axis=1)
    return df


div_series = pd.read_csv("data/divisions.csv", index_col=0).squeeze()
div_series.name = None
# AFC WEST -> AFC
conf_series = div_series.apply(lambda s: s.split()[0])

df_ranks = pd.read_csv("data/playoff_rankings.csv")
df_ranks["Team"] = df_ranks["teamName"].apply(get_abbr)
df_ranks = combine_names(df_ranks, "firstName", "lastName")
df_ranks["adp"] = pd.to_numeric(df_ranks["adp"], errors='coerce')
adp_dct = dict(zip(df_ranks["Name"], df_ranks["adp"]))

df_wc = pd.read_csv("data/wc_rankings.csv")
df_wc = combine_names(df_wc, "firstName", "lastName")
df_wc.set_index("Name", drop=True, inplace=True)
# Series with keys player names and values UD projected points
wc_series = df_wc["projectedPoints"]

st.set_page_config(page_title="Playoff lineups", page_icon=":material/sports_football:", layout="wide")

st.title("Playoff lineups")

st.write("(This is only tested on Chrome.)  Have Underdog email you your exposure csv file (refresh the exposure page right beforehand) and upload the csv file below.  (As far as I can tell, this is only possible from the Exposure section on Desktop, not Mobile.)")

file = st.file_uploader("Exposure csv", type="csv", accept_multiple_files=False)

st.write("The 'WC Score' value is from the Underdog wildcard projections")

# Keys are tuples of super bowl matchups (AFC, NFC), values are lists of draft boards
matchup_dct = {}

# Simple Underdog projected scores for round 1
# Key is a draft key, value is the projected score
wc_scores = {}
date_dct = {}

# Basically just to combine WR and TE
def update_position_series(pos_series):
    pos_dct = {}
    pos_dct["QB"] = pos_series.get("QB", 0)
    pos_dct["RB"] = pos_series.get("RB", 0)
    pos_dct["WR/TE"] = pos_series.get("WR", 0) + pos_series.get("TE", 0)
    return pd.Series(pos_dct)


def is_complete_lineup(total_series):
    return (
        (total_series["QB"] >= 1) and (total_series["RB"] >= 1) and (total_series["WR/TE"] >= 2) and 
        ((total_series["WR/TE"] + total_series["RB"]) >= 4)
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


def get_wc_scores(df_draft):
    # The UD projected wildcard score of the top QB plus all non-QB player scores
    qb_score = df_draft.query("Position == 'QB'")["Name"].map(lambda name: wc_series.get(name, 0)).values.max()
    wrte_scores = df_draft.query("(Position == 'WR') or (Position == 'TE')")["Name"].map(lambda name: wc_series.get(name, 0)).sort_values(ascending=False)
    wrte_score = wrte_scores[:2].sum()
    rb_scores = df_draft.query("Position == 'RB'")["Name"].map(lambda name: wc_series.get(name, 0)).sort_values(ascending=False)
    rb_score = rb_scores.max()
    wrte_flex = 0 if len(wrte_scores) < 3 else wrte_scores.values[2]
    rb_flex = 0 if len(rb_scores) < 2 else rb_scores.values[1]
    return qb_score + wrte_score + rb_score + max(wrte_flex, rb_flex)

try:
    df = pd.read_csv(file)
    df["Picked At"] = pd.to_datetime(df["Picked At"])
    df = df.sort_values("Picked At", ascending=False)
    df["Team"] = df["Team"].apply(get_abbr)
    df = combine_names(df, "First Name", "Last Name")
    
    for key, df_draft in df.groupby("Draft", sort=False):
        process_draft(df_draft, key)
        wc_scores[key] = get_wc_scores(df_draft)
        date_dct[key] = df_draft["Picked At"].iloc[0]
except ValueError:
    pass

for pair, keys in sorted(matchup_dct.items(), key= lambda tup: len(tup[1]), reverse=True):
    st.subheader(f"Matchup: {pair[0]} vs {pair[1]}, you have {len(keys)} total drafts")
    names = set() # all players drafted from these two teams
    # First pass: just find all the players
    for key in keys:
        # st.page_link(f"https://underdogfantasy.com/draft-board/{key}",  label=":blue[View full draft board]")
        df_sb = df[(df["Draft"] == key) & (df["Team"].isin(pair))]
        names.update(set(df_sb["Name"]))

    all_names = list(df_ranks.query("(Team in @pair) & ((adp < 60) | (Name in @names))")["Name"])
    all_names = sorted(all_names, key=lambda name: adp_dct[name])

    row_template_dct = {name: "" for name in all_names}
    row_template_dct["WC score"] = 0
    row_template_dct["date"] = ""
    row_template_dct["draft board"] = ""

    full_list = []

    # Second pass: make the rows of the DataFrame
    # This is probably inefficient/inelegant but I don't think there is enough to worry about it
    for key in keys:
        row_dct = row_template_dct.copy()
        for name in df[(df["Draft"] == key) & (df["Team"].isin(pair))]["Name"].values:
            row_dct[name] = "X"
        row_dct["WC score"] = round(wc_scores[key])
        row_dct["draft board"] = f"https://underdogfantasy.com/draft-board/{key}"
        row_dct["date"] = f"{date_dct[key]:%b\xa0%d}"
        
        full_list.append(row_dct)

    df_full = pd.DataFrame(full_list).sort_values("WC score", ascending=False)
    df_full.index = index=range(1, len(keys)+1)

    df_full = df_full.style.set_table_styles(
        [dict(selector="th",props=[('max-width', '40px'), ('max-height', '280px')]),
            dict(selector="th.col_heading",
                    props=[("writing-mode", "vertical-rl"), ('transform', 'rotateZ(180deg)')])]
    )

    # st.write(df_full)

    # st.dataframe(df_full)

    st.markdown(df_full.to_html(escape=False), unsafe_allow_html=True)
    

    