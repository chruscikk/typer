import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from scipy.stats import poisson

st.set_page_config(page_title="Auto-Typowanie 2026", layout="wide")

# Mapowanie lig na FBRef (identyfikatory w ich URL)
LIGI_URLS = {
    "Premier League": "9/schedule/Premier-League-Scores-and-Fixtures",
    "La Liga": "12/schedule/La-Liga-Scores-and-Fixtures",
    "Bundesliga": "20/schedule/Bundesliga-Scores-and-Fixtures",
    "Serie A": "11/schedule/Serie-A-Scores-and-Fixtures",
    "Ligue 1": "13/schedule/Ligue-1-Scores-and-Fixtures"
}

# --- FUNKCJE DANYCH ---

@st.cache_data(ttl=3600)
def pobierz_terminarz(path):
    url = f"https://fbref.com/en/comps/{path}"
    try:
        # Udajemy przeglądarkę, żeby nas nie zablokowali
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        tables = pd.read_html(response.text)
        df = tables[0] # Zazwyczaj pierwsza tabela to terminarz
        # Filtrujemy tylko nadchodzące mecze (te bez wyniku)
        nadchodzace = df[df['Score'].isna() & df['Home'].notna()]
        return nadchodzace[['Date', 'Time', 'Home', 'Away']].head(10) # Bierzemy 10 najbliższych
    except:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def pobierz_statystyki_historyczne(kod_ligi):
    # Dane do modelu pobieramy z football-data.co.uk (stabilne CSV)
    url = f"https://www.football-data.co.uk/mmz4281/2324/{kod_ligi}.csv"
    df = pd.read_csv(url)
    return df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]

def model_poisson(home, away, df_stats):
    # Mapowanie nazw (FBRef vs Football-Data może wymagać drobnych korekt, 
    # ale dla uproszczenia zakładamy zgodność lub manualny wybór)
    try:
        avg_h = df_stats['FTHG'].mean()
        avg_a = df_stats['FTAG'].mean()
        
        h_at = df_stats[df_stats['HomeTeam'] == home]['FTHG'].mean() / avg_h
        h_def = df_stats[df_stats['HomeTeam'] == home]['FTAG'].mean() / avg_a
        a_at = df_stats[df_stats['AwayTeam'] == away]['FTAG'].mean() / avg_a
        a_def = df_stats[df_stats['AwayTeam'] == away]['FTHG'].mean() / avg_h
        
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
st.title("🚀 Automatyczny Terminarz i Typy")

liga_nazwa = st.sidebar.selectbox("Wybierz ligę:", list(LIGI_URLS.keys()))
kod_fd = {"Premier League":"E0", "La Liga":"SP1", "Bundesliga":"D1", "Serie A":"I1", "Ligue 1":"F1"}[liga_nazwa]

with st.spinner('Pobieranie terminarza z FBRef...'):
    terminarz = pobierz_terminarz(LIGI_URLS[liga_nazwa])
    stats = pobierz_statystyki_historyczne(kod_fd)

if not terminarz.empty:
    st.subheader(f"Najbliższe mecze: {liga_nazwa}")
    
    for _, row in terminarz.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 2])
            
            p_h, p_d, p_a = model_poisson(row['Home'], row['Away'], stats)
            
            with col1:
                st.write(f"**{row['Home']}**")
                if p_h: st.caption(f"Szansa: {p_h*100:.0f}%")
            
            with col2:
                st.write(f"vs")
                st.caption(f"{row['Date']}")
            
            with col3:
                st.write(f"**{row['Away']}**")
                if p_a: st.caption(f"Szansa: {p_a*100:.0f}%")
            
            if p_h:
                st.progress(p_h)
            st.divider()
else:
    st.error("Nie udało się pobrać terminarza. Spróbuj wybrać inną ligę lub sprawdź połączenie.")

st.info("💡 Uwaga: Nazwy drużyn w terminarzu i statystykach mogą się różnić (np. 'Man Utd' vs 'Manchester United'). W takim przypadku model wymaga mapowania nazw.")
