import streamlit as st
import pandas as pd
import requests
from scipy.stats import poisson

st.set_page_config(page_title="Pro Typy Piłkarskie", page_icon="⚽", layout="wide")

# Bezpieczne pobieranie klucza API z ustawień Streamlit
try:
    API_KEY = st.secrets["API_KEY"]
except KeyError:
    st.error("Brak klucza API! Skonfiguruj 'Secrets' w ustawieniach Streamlit.")
    st.stop()

# Konfiguracja lig (Kody dla API oraz kody dla CSV)
LIGI = {
    "Premier League": {"api": "PL", "csv": "E0"},
    "La Liga": {"api": "PD", "csv": "SP1"},
    "Bundesliga": {"api": "BL1", "csv": "D1"},
    "Serie A": {"api": "SA", "csv": "I1"},
    "Ligue 1": {"api": "FL1", "csv": "F1"}
}

# --- FUNKCJE DANYCH ---

@st.cache_data(ttl=3600) # Odświeżaj terminarz raz na godzinę
def pobierz_terminarz_api(kod_api):
    url = f"http://api.football-data.org/v4/competitions/{kod_api}/matches?status=SCHEDULED"
    headers = {"X-Auth-Token": API_KEY}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        dane = response.json()
        mecze = []
        for match in dane.get('matches', [])[:10]: # Bierzemy 10 najbliższych
            mecze.append({
                'Data': match['utcDate'][:10],
                'Gospodarz': match['homeTeam']['shortName'], # shortName daje lepsze dopasowanie do statystyk
                'Gość': match['awayTeam']['shortName']
            })
        return pd.DataFrame(mecze)
    return pd.DataFrame()

@st.cache_data(ttl=86400) # Statystyki raz na dzień
def pobierz_statystyki(kod_csv):
    url = f"https://www.football-data.co.uk/mmz4281/2324/{kod_csv}.csv"
    df = pd.read_csv(url)
    return df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]

def oblicz_poissona(home, away, df):
    try:
        avg_h = df['FTHG'].mean()
        avg_a = df['FTAG'].mean()
        
        # Zabezpieczenie na wypadek, gdy nazwa z API różni się od tej z CSV
        if home not in df['HomeTeam'].values or away not in df['AwayTeam'].values:
            return None, None, None

        h_at = df[df['HomeTeam'] == home]['FTHG'].mean() / avg_h
        h_def = df[df['HomeTeam'] == home]['FTAG'].mean() / avg_a
        a_at = df[df['AwayTeam'] == away]['FTAG'].mean() / avg_a
        a_def = df[df['AwayTeam'] == away]['FTHG'].mean() / avg_h
        
        exp_h = h_at * a_def * avg_h
        exp_a = a_at * h_def * avg_a
        
        p_h, p_a, p_d = 0, 0, 0
        for i in range(7):
            for j in range(7):
                p = poisson.pmf(i, exp_h) * poisson.pmf(j, exp_a)
                if i > j: p_h += p
                elif i < j: p_a += p
                else: p_d += p
        return p_h, p_d, p_a
    except:
        return None, None, None

# --- UI ---
st.title("📅 Terminarz i Typy (Powered by API)")

wybrana_liga = st.sidebar.selectbox("Wybierz ligę:", list(LIGI.keys()))
kody = LIGI[wybrana_liga]

with st.spinner('Pobieranie danych z serwerów...'):
    terminarz = pobierz_terminarz_api(kody['api'])
    stats = pobierz_statystyki(kody['csv'])

if not terminarz.empty:
    st.subheader(f"Najbliższe mecze: {wybrana_liga}")
    
    for _, row in terminarz.iterrows():
        gosp = row['Gospodarz']
        gosc = row['Gość']
        
        c1, c2, c3 = st.columns([2, 1, 2])
        p_h, p_d, p_a = oblicz_poissona(gosp, gosc, stats)
        
        with c1:
            st.write(f"🏠 **{gosp}**")
            if p_h: st.metric("Wygrana", f"{p_h*100:.1f}%")
        with c2:
            st.caption(row['Data'])
            if p_d: st.metric("Remis", f"{p_d*100:.1f}%")
        with c3:
            st.write(f"✈️ **{gosc}**")
            if p_a: st.metric("Wygrana", f"{p_a*100:.1f}%")
            
        if p_h is None:
            st.warning(f"Brak danych historycznych dla tych nazw: {gosp} / {gosc}. Konieczne mapowanie.")
        st.divider()
else:
    st.info("Brak zaplanowanych meczów w najbliższym czasie lub limit API został wyczerpany (10/minutę).")
