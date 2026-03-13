import streamlit as st
import pandas as pd
from scipy.stats import poisson
import datetime

st.set_page_config(page_title="Typowanie Live", page_icon="⚽", layout="wide")

# --- KONFIGURACJA LIG ---
LIGI = {
    "Premier League": "E0",
    "La Liga": "SP1",
    "Bundesliga": "D1",
    "Serie A": "I1",
    "Ligue 1": "F1"
}

@st.cache_data(ttl=3600) # Odświeżaj dane co godzinę
def pobierz_historyczne(kod):
    url = f"https://www.football-data.co.uk/mmz4281/2324/{kod}.csv"
    df = pd.read_csv(url)
    return df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]

def oblicz_szanse(home_team, away_team, df):
    avg_home_goals = df['FTHG'].mean()
    avg_away_goals = df['FTAG'].mean()

    # Siła zespołów
    h_at = df[df['HomeTeam'] == home_team]['FTHG'].mean() / avg_home_goals
    h_def = df[df['HomeTeam'] == home_team]['FTAG'].mean() / avg_away_goals
    a_at = df[df['AwayTeam'] == away_team]['FTAG'].mean() / avg_away_goals
    a_def = df[df['AwayTeam'] == away_team]['FTHG'].mean() / avg_home_goals

    exp_h = h_at * a_def * avg_home_goals
    exp_a = a_at * h_def * avg_away_goals

    prob_h, prob_a, prob_d = 0, 0, 0
    for i in range(8):
        for j in range(8):
            p = poisson.pmf(i, exp_h) * poisson.pmf(j, exp_a)
            if i > j: prob_h += p
            elif i < j: prob_a += p
            else: prob_d += p
    return prob_h, prob_d, prob_a

# --- INTERFEJS ---
st.title("📅 Terminarz i Typy na Dziś")

wybrana_liga = st.sidebar.selectbox("Wybierz ligę:", list(LIGI.keys()))
df_hist = pobierz_historyczne(LIGI[wybrana_liga])

# Sekcja: Dzisiejsze Mecze
st.subheader(f"Analiza nadchodzących spotkań: {wybrana_liga}")

# UWAGA: Ponieważ darmowe API są limitowane, tutaj symulujemy pobranie 
# "dzisiejszych" meczów z zestawienia dostępnych drużyn w bazie danych.
# W profesjonalnej wersji tu wpina się API-Football (wymaga konta).

druzyny = sorted(df_hist['HomeTeam'].unique())
dzis = datetime.date.today().strftime("%d/%m/%Y")
st.info(f"Dziś jest: {dzis}. Wybierz mecz z listy poniżej, aby zobaczyć analizę.")

# Formularz wyboru meczu z "dzisiejszej listy"
with st.expander("🔍 Wybierz mecz do analizy"):
    c1, c2 = st.columns(2)
    h_sel = c1.selectbox("Gospodarz", druzyny)
    a_sel = c2.selectbox("Gość", druzyny)

if h_sel == a_sel:
    st.warning("Wybierz dwie różne drużyny!")
else:
    p_h, p_d, p_a = oblicz_szanse(h_sel, a_sel, df_hist)
    
    # Wyświetlanie wyników w formie kart
    cols = st.columns(3)
    cols[0].metric(f"Zwycięstwo {h_sel}", f"{p_h*100:.1f}%")
    cols[1].metric("Remis", f"{p_d*100:.1f}%")
    cols[2].metric(f"Zwycięstwo {a_sel}", f"{p_a*100:.1f}%")
    
    # Prosty pasek prawdopodobieństwa
    st.progress(p_h)
