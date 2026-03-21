import streamlit as st
import pandas as pd
import requests
import datetime
from scipy.stats import poisson

st.set_page_config(page_title="Dzisiejsze Mecze - Typy Live", page_icon="⚽", layout="centered")

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

@st.cache_data(ttl=60) # Odświeżamy częściej (co 60 sekund), żeby mieć aktualne wyniki na żywo!
def pobierz_mecze_na_dzis():
    dzis = datetime.date.today().strftime('%Y-%m-%d')
    url = f"http://api.football-data.org/v4/matches?dateFrom={dzis}&dateTo={dzis}"
    headers = {"X-Auth-Token": API_KEY}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('matches', [])
    return []

@st.cache_data(ttl=86400)
def pobierz_wszystkie_statystyki():
    stats = {}
    for api_kod, csv_kod in LIGI_KODY.items():
        url = f"https://www.football-data.co.uk/mmz4281/2324/{csv_kod}.csv"
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

st.title("📅 Dashboard Piłkarski LIVE")
dzis_str = datetime.date.today().strftime('%d.%m.%Y')
st.markdown(f"**Mecze i weryfikacja typów na dzień:** {dzis_str}")

with st.spinner('Pobieranie aktualnych wyników i statystyk...'):
    wszystkie_mecze = pobierz_mecze_na_dzis()
    stats = pobierz_wszystkie_statystyki()

mecze_top5 = [m for m in wszystkie_mecze if m['competition']['code'] in LIGI_KODY.keys()]

if not mecze_top5:
    st.info("Dzisiaj nie gra żadna z topowych 5 lig europejskich.")
else:
    mecze_po_lidze = {}
    for m in mecze_top5:
        kod_ligi = m['competition']['code']
        if kod_ligi not in mecze_po_lidze:
            mecze_po_lidze[kod_ligi] = []
        mecze_po_lidze[kod_ligi].append(m)

    for kod_ligi, lista_meczow in mecze_po_lidze.items():
        st.write("")
        st.subheader(LIGI_NAZWY[kod_ligi])
        
        for mecz in lista_meczow:
            gosp = mecz['homeTeam']['shortName']
            gosc = mecz['awayTeam']['shortName']
            status = mecz['status'] # SCHEDULED, IN_PLAY, PAUSED, FINISHED
            czas_startu = mecz['utcDate'][11:16]
            
            # Pobieranie wyników, jeśli mecz trwa lub się zakończył
            gole_dom = mecz['score']['fullTime']['home']
            gole_wyjazd = mecz['score']['fullTime']['away']
            
            p_h, p_d, p_a = oblicz_poissona(gosp, gosc, stats[kod_ligi])
            
            # 1. Określanie typu modelu (co ma najwyższy %)
            typ_modelu = None
            if p_h is not None:
                if p_h > p_d and p_h > p_a: typ_modelu = '1'
                elif p_a > p_h and p_a > p_d: typ_modelu = '2'
                else: typ_modelu = 'X'

            # 2. Status meczu i sprawdzanie typu
            srodek_ekranu = f"<div style='text-align: center; color: gray; margin-top: 5px;'>{czas_startu}</div>"
            znaczek_trafnosci = ""

            if status in ['IN_PLAY', 'PAUSED', 'FINISHED'] and gole_dom is not None and gole_wyjazd is not None:
                # Ustalenie bieżącego wyniku na boisku
                if gole_dom > gole_wyjazd: obecny_wynik = '1'
                elif gole_dom < gole_wyjazd: obecny_wynik = '2'
                else: obecny_wynik = 'X'
                
                # Ustalanie etykiety statusu
                if status == 'FINISHED':
                    etykieta = "<span style='color: gray; font-size: 12px;'>Koniec</span>"
                    # Weryfikacja typu
                    if typ_modelu == obecny_wynik:
                        znaczek_trafnosci = "✅ <span style='color: #4CAF50; font-size: 14px;'>Typ Trafiony!</span>"
                    else:
                        znaczek_trafnosci = "❌ <span style='color: #F44336; font-size: 14px;'>Typ Nietrafiony</span>"
                else:
                    etykieta = "<span style='color: red; font-size: 12px; font-weight: bold;'>Na żywo</span>"
                    # Na żywo - czy typ aktualnie "wchodzi"
                    if typ_modelu == obecny_wynik:
                        znaczek_trafnosci = "⏳ <span style='color: #FFC107; font-size: 14px;'>Typ aktualnie wchodzi...</span>"
                    else:
                        znaczek_trafnosci = "⏳ <span style='color: gray; font-size: 14px;'>Typ na razie przegrywa...</span>"

                # Podmiana środka ekranu na wynik meczu
                srodek_ekranu = f"""
                <div style='text-align: center;'>
                    <span style='font-size: 24px; font-weight: bold;'>{gole_dom} - {gole_wyjazd}</span><br>
                    {etykieta}
                </div>
                """

            # 3. Rysowanie interfejsu (Karty Meczowe)
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 3])
                with col1:
                    st.markdown(f"<h4 style='text-align: right;'>{gosp}</h4>", unsafe_allow_html=True)
                with col2:
                    st.markdown(srodek_ekranu, unsafe_allow_html=True)
                with col3:
                    st.markdown(f"<h4>{gosc}</h4>", unsafe_allow_html=True)
                    
                if p_h is not None:
                    # Dodanie pogrubienia dla najwyższego prawdopodobieństwa (naszego typu)
                    waga_1 = "font-weight: bold; text-decoration: underline;" if typ_modelu == '1' else ""
                    waga_x = "font-weight: bold; text-decoration: underline;" if typ_modelu == 'X' else ""
                    waga_2 = "font-weight: bold; text-decoration: underline;" if typ_modelu == '2' else ""

                    pasek_html = f"""
                    <div style='display: flex; justify-content: space-between; align-items: center; background-color: #1e1e1e; color: white; padding: 10px; border-radius: 8px; margin-bottom: 25px;'>
                        <div style='display: flex; gap: 20px; font-size: 16px;'>
                            <div style='{waga_1}'><b>1:</b> <span style='color: #4CAF50;'>{p_h*100:.0f}%</span></div>
                            <div style='{waga_x}'><b>X:</b> <span style='color: #FFC107;'>{p_d*100:.0f}%</span></div>
                            <div style='{waga_2}'><b>2:</b> <span style='color: #F44336;'>{p_a*100:.0f}%</span></div>
                        </div>
                        <div>{znaczek_trafnosci}</div>
                    </div>
                    """
                    st.markdown(pasek_html, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='text-align: center; font-size: 12px; color: gray; margin-bottom: 25px;'>
                        Brak statystyk dla tych drużyn. Wymagane mapowanie nazw.
                    </div>""", unsafe_allow_html=True)
