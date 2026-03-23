import streamlit as st
import pandas as pd
import requests
import datetime
from scipy.stats import poisson

# Ustawienia strony - layout "centered" jest lepszy dla telefonów
st.set_page_config(page_title="Typy Piłkarskie - Mobile", page_icon="📱", layout="centered")

try:
    API_KEY = st.secrets["API_KEY"]
except KeyError:
    st.error("Brak klucza API! Uzupełnij 'Secrets' na Streamlit Cloud.")
    st.stop()

LIGI_KODY = {"PL": "E0", "PD": "SP1", "BL1": "D1", "SA": "I1", "FL1": "F1"}
LIGI_NAZWY = {
    "PL": "🇬🇧 Premier League", 
    "PD": "🇪🇸 La Liga", 
    "BL1": "🇩🇪 Bundesliga", 
    "SA": "🇮🇹 Serie A", 
    "FL1": "🇫🇷 Ligue 1"
}

# --- FUNKCJE ---

@st.cache_data(ttl=60)
def pobierz_mecze(data_str):
    url = f"http://api.football-data.org/v4/matches?competitions=PL,PD,BL1,SA,FL1&dateFrom={data_str}&dateTo={data_str}"
    headers = {"X-Auth-Token": API_KEY}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('matches', [])
    elif response.status_code == 429:
        return "LIMIT"
    return []

@st.cache_data(ttl=86400)
def pobierz_wszystkie_statystyki():
    stats = {}
    for api_kod, csv_kod in LIGI_KODY.items():
        # Używamy sezonu 25/26 (kod 2526) 
        url = f"https://www.football-data.co.uk/mmz4281/2526/{csv_kod}.csv"
        try:
            df = pd.read_csv(url)
            stats[api_kod] = df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]
        except:
            stats[api_kod] = pd.DataFrame()
    return stats

def oblicz_poissona(home, away, df):
    if df.empty or home not in df['HomeTeam'].values or away not in df['AwayTeam'].values:
        return None, None, None
        
    avg_h, avg_a = df['FTHG'].mean(), df['FTAG'].mean()
    h_at = df[df['HomeTeam'] == home]['FTHG'].mean() / avg_h
    h_def = df[df['HomeTeam'] == home]['FTAG'].mean() / avg_a
    a_at = df[df['AwayTeam'] == away]['FTAG'].mean() / avg_a
    a_def = df[df['AwayTeam'] == away]['FTHG'].mean() / avg_h
    
    exp_h, exp_a = h_at * a_def * avg_h, a_at * h_def * avg_a
    
    p_h, p_a, p_d = 0, 0, 0
    for i in range(7):
        for j in range(7):
            p = poisson.pmf(i, exp_h) * poisson.pmf(j, exp_a)
            if i > j: p_h += p
            elif i < j: p_a += p
            else: p_d += p
    return p_h, p_d, p_a

# --- INTERFEJS UŻYTKOWNIKA ---

st.title("⚽ Dashboard Typerski")

wybrana_data = st.date_input("Wybierz datę do analizy:", datetime.date.today())
data_str = wybrana_data.strftime('%Y-%m-%d')

# Dodajemy opcję debugowania dla użytkownika
debug_mode = st.checkbox("🔧 Tryb diagnostyczny (zobacz surowe dane API)")

with st.spinner('Pobieranie wyników i obliczanie szans...'):
    wszystkie_mecze = pobierz_mecze(data_str)
    stats = pobierz_wszystkie_statystyki()

if debug_mode:
    st.warning("Poniżej znajdują się surowe dane, które dostarcza API (jeśli jest tu mało meczów, wina leży po stronie terminarza/API):")
    st.write(wszystkie_mecze)

if wszystkie_mecze == "LIMIT":
    st.error("⚠️ Przekroczono limit zapytań API (10/min). Odczekaj chwilę i odśwież stronę.")
elif not wszystkie_mecze:
    st.info("W tym dniu API nie zwróciło żadnych meczów dla Top 5 lig.")
else:
    mecze_po_lidze = {}
    for m in wszystkie_mecze:
        kod_ligi = m['competition']['code']
        if kod_ligi not in mecze_po_lidze:
            mecze_po_lidze[kod_ligi] = []
        mecze_po_lidze[kod_ligi].append(m)

    for kod_ligi, lista_meczow in mecze_po_lidze.items():
        st.markdown(f"<h3 style='margin-top: 20px; color: #4CAF50;'>{LIGI_NAZWY.get(kod_ligi, kod_ligi)}</h3>", unsafe_allow_html=True)
        
        for mecz in lista_meczow:
            gosp = mecz['homeTeam']['shortName']
            gosc = mecz['awayTeam']['shortName']
            status = mecz['status'] 
            czas_startu = mecz['utcDate'][11:16]
            
            gole_dom = mecz['score']['fullTime'].get('home') if mecz.get('score') and mecz.get('score').get('fullTime') else None
            gole_wyjazd = mecz['score']['fullTime'].get('away') if mecz.get('score') and mecz.get('score').get('fullTime') else None
            
            p_h, p_d, p_a = oblicz_poissona(gosp, gosc, stats.get(kod_ligi, pd.DataFrame()))
            
            # Weryfikacja typu
            typ_modelu = None
            if p_h is not None:
                if p_h > p_d and p_h > p_a: typ_modelu = '1'
                elif p_a > p_h and p_a > p_d: typ_modelu = '2'
                else: typ_modelu = 'X'

            znaczek_trafnosci = ""
            if status in ['IN_PLAY', 'PAUSED', 'FINISHED'] and gole_dom is not None:
                if gole_dom > gole_wyjazd: obecny_wynik = '1'
                elif gole_dom < gole_wyjazd: obecny_wynik = '2'
                else: obecny_wynik = 'X'
                
                if status == 'FINISHED':
                    srodek_ekranu = f"<div style='font-size: 20px; font-weight: bold;'>{gole_dom} - {gole_wyjazd}</div><div style='font-size: 10px; color: #888;'>Koniec</div>"
                    znaczek_trafnosci = "✅" if typ_modelu == obecny_wynik else "❌"
                else:
                    srodek_ekranu = f"<div style='font-size: 20px; font-weight: bold; color: #ff4b4b;'>{gole_dom} - {gole_wyjazd}</div><div style='font-size: 10px; color: #ff4b4b;'>Na żywo</div>"
                    znaczek_trafnosci = "⏳"
            else:
                srodek_ekranu = f"<div style='font-size: 16px; color: #bbb;'>{czas_startu}</div>"

            # Generowanie paska z procentami
            if p_h is not None:
                pasek_html = f"""
                <div style="display: flex; justify-content: space-around; align-items: center; background-color: #1a1a24; padding: 10px; border-radius: 8px; font-size: 14px; margin-top: 10px;">
                    <div style="{'font-weight: bold; color: #fff;' if typ_modelu=='1' else 'color: #aaa;'}">1: <span style="color: #4CAF50;">{p_h*100:.0f}%</span></div>
                    <div style="{'font-weight: bold; color: #fff;' if typ_modelu=='X' else 'color: #aaa;'}">X: <span style="color: #FFC107;">{p_d*100:.0f}%</span></div>
                    <div style="{'font-weight: bold; color: #fff;' if typ_modelu=='2' else 'color: #aaa;'}">2: <span style="color: #F44336;">{p_a*100:.0f}%</span></div>
                    <div style="margin-left: 10px; font-size: 16px;">{znaczek_trafnosci}</div>
                </div>
                """
            else:
                pasek_html = "<div style='text-align: center; font-size: 11px; color: #888; padding: 5px; margin-top: 5px;'>Brak statystyk (wymagane zmapowanie nazw)</div>"

            # GŁÓWNA ZMIANA: Karta meczu napisana w czystym HTML/CSS z wymuszonym układem poziomym (flex-direction: row)
            karta_meczu = f"""
            <div style="background-color: #2b2b36; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
                <div style="display: flex; flex-direction: row; justify-content: space-between; align-items: center;">
                    <div style="flex: 1; text-align: right; font-size: 15px; font-weight: bold; color: white;">{gosp}</div>
                    <div style="flex: 1; text-align: center;">{srodek_ekranu}</div>
                    <div style="flex: 1; text-align: left; font-size: 15px; font-weight: bold; color: white;">{gosc}</div>
                </div>
                {pasek_html}
            </div>
            """
            
            st.markdown(karta_meczu, unsafe_allow_html=True)
