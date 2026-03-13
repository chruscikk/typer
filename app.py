import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="Football Predictor PRO", page_icon="⚽")

st.title("⚽ Typowanie Wyników: Top Ligi Europy")
st.markdown("Dane pobierane są na bieżąco z darmowych arkuszy *football-data.co.uk*.")

# Konfiguracja lig
LIGI = {
    "Premier League (Anglia)": "E0",
    "La Liga (Hiszpania)": "SP1",
    "Bundesliga (Niemcy)": "D1",
    "Serie A (Włochy)": "I1",
    "Ligue 1 (Francja)": "F1"
}

# 1. Wybór ligi
wybrana_liga = st.sidebar.selectbox("Wybierz ligę:", list(LIGI.keys()))
kod_ligi = LIGI[wybrana_liga]

@st.cache_data
def pobierz_dane(kod):
    url = f"https://www.football-data.co.uk/mmz4281/2324/{kod}.csv"
    data = pd.read_csv(url)
    # Filtrujemy tylko potrzebne kolumny
    return data[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]

try:
    df = pobierz_dane(kod_ligi)
    druzyny = sorted(df['HomeTeam'].unique())

    # 2. Wybór drużyn
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Gospodarz", druzyny, index=0)
    with col2:
        away_team = st.selectbox("Gość", druzyny, index=1)

    # 3. Logika obliczeń (Uproszczony Poisson)
    # Średnie goli w całej lidze
    avg_home_goals = df['FTHG'].mean()
    avg_away_goals = df['FTAG'].mean()

    # Siła gospodarza u siebie
    home_attack = df[df['HomeTeam'] == home_team]['FTHG'].mean() / avg_home_goals
    home_defense = df[df['HomeTeam'] == home_team]['FTAG'].mean() / avg_away_goals

    # Siła gościa na wyjeździe
    away_attack = df[df['AwayTeam'] == away_team]['FTAG'].mean() / avg_away_goals
    away_defense = df[df['AwayTeam'] == away_team]['FTHG'].mean() / avg_home_goals

    # Przewidywana liczba goli
    exp_home = home_attack * away_defense * avg_home_goals
    exp_away = away_attack * home_defense * avg_away_goals

    # 4. Wyświetlanie wyników
    st.divider()
    st.subheader(f"Prognoza: {home_team} vs {away_team}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Przewidywane gole (G)", f"{exp_home:.2f}")
    c2.metric("Przewidywane gole (P)", f"{exp_away:.2f}")
    
    # Obliczanie prawdopodobieństwa (Poisson)
    prob_home = 0
    prob_away = 0
    prob_draw = 0
    
    for i in range(10):
        for j in range(10):
            p = poisson.pmf(i, exp_home) * poisson.pmf(j, exp_away)
            if i > j: prob_home += p
            elif i < j: prob_away += p
            else: prob_draw += p

    st.write(f"**Szansa na wygraną {home_team}:** {prob_home*100:.1f}%")
    st.write(f"**Szansa na remis:** {prob_draw*100:.1f}%")
    st.write(f"**Szansa na wygraną {away_team}:** {prob_away*100:.1f}%")

except Exception as e:
    st.error("Błąd podczas pobierania danych. Spróbuj wybrać inną ligę.")
