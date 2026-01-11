import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
from datetime import datetime
import plotly.graph_objs as go
from time import sleep
import json

# ===== Configuration de la page Streamlit =====
st.set_page_config(
    page_title="Dashboard ESP32 - Firebase",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Configuration Firebase =====
FIREBASE_DATABASE_URL = "https://esp32finquadri-default-rtdb.europe-west1.firebasedatabase.app"

# ===== Initialisation Firebase =====
if not firebase_admin._apps:
    try:
        # Essayer d'abord avec Streamlit Secrets (pour déploiement)
        if "firebase" in st.secrets:
            firebase_config = dict(st.secrets["firebase"])
            cred = credentials.Certificate(firebase_config)
        # Sinon utiliser le fichier local (pour développement)
        else:
            cred = credentials.Certificate("firebase-key.json")
        
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DATABASE_URL
        })
        st.session_state.firebase_connected = True
        print("Connecté à Firebase")
    except Exception as e:
        st.error(f"Erreur Firebase: {e}")
        st.session_state.firebase_connected = False

# ===== Initialisation du session_state =====
if "data" not in st.session_state:
    st.session_state.data = []

# ===== Fonction pour récupérer les données Firebase =====
def fetch_firebase_data():
    """Récupère les données depuis Firebase Realtime Database"""
    try:
        ref = db.reference('mesure')
        data = ref.order_by_key().limit_to_last(100).get()
        
        if data:
            data_list = []
            for key, value in data.items():
                timestamp_ms = value.get('timestamp', datetime.now().timestamp() * 1000)
                value['timestamp'] = datetime.fromtimestamp(timestamp_ms / 1000)
                value['temperature'] = value.get('temperature', 0)
                value['humidite'] = value.get('humidite', 0)
                value['flame'] = value.get('flame', 0)
                value['ldr'] = value.get('Ldr', 0)
                data_list.append(value)
            
            st.session_state.data = data_list
            return True
        return False
    except Exception as e:
        st.error(f"Erreur lors de la lecture Firebase: {e}")
        return False

# ===== HEADER =====
st.title("Dashboard ESP32 - Firebase Realtime")
st.markdown("---")

# ===== SIDEBAR =====
with st.sidebar:
    st.header("Configuration")

    if st.session_state.get('firebase_connected', False):
        st.success("Connecté à Firebase")
    else:
        st.error("Déconnecté")

    st.info("**Database:** Firebase Europe West 1")
    st.metric("Données chargées", len(st.session_state.data))

    st.markdown("---")
    st.subheader("Contrôles")
    refresh_rate = st.slider("Rafraîchissement (secondes)", 2, 30, 5)

    if st.button("Actualiser maintenant"):
        fetch_firebase_data()
        st.rerun()

    if st.button("Effacer l'historique"):
        st.session_state.data = []
        st.success("Historique effacé !")
        sleep(1)
        st.rerun()

    st.markdown("---")
    st.subheader("Seuils d'alerte")
    temp_max = st.number_input("Température max (°C)", value=50, min_value=0, max_value=100)
    flame_threshold = st.number_input("Seuil flamme", value=2000, min_value=0, max_value=4095)

# ===== Récupération automatique des données =====
fetch_firebase_data()

# ===== CONTENU PRINCIPAL =====
if len(st.session_state.data) > 0:
    df = pd.DataFrame(st.session_state.data)
    last_data = df.iloc[-1]

    # ===== MÉTRIQUES EN TEMPS RÉEL =====
    st.subheader("Mesures Actuelles")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        temp_delta = None
        if len(df) > 1:
            temp_delta = last_data["temperature"] - df.iloc[-2]["temperature"]
        st.metric(
            label="Température",
            value=f"{last_data['temperature']:.1f} °C",
            delta=f"{temp_delta:.1f} °C" if temp_delta is not None else None
        )

    with col2:
        hum_delta = None
        if len(df) > 1:
            hum_delta = last_data["humidite"] - df.iloc[-2]["humidite"]
        st.metric(
            label="Humidité",
            value=f"{last_data['humidite']:.1f} %",
            delta=f"{hum_delta:.1f} %" if hum_delta is not None else None
        )

    with col3:
        st.metric(
            label="Capteur Flamme",
            value=f"{last_data['flame']}",
            delta="ALERTE!" if last_data['flame'] < flame_threshold else "OK",
            delta_color="inverse"
        )

    with col4:
        st.metric(
            label="LDR (Luminosité)",
            value=f"{last_data['ldr']}"
        )

    with col5:
        st.metric(
            label="Dernière mise à jour",
            value=last_data["timestamp"].strftime("%H:%M:%S")
        )

    st.markdown("---")

    # ===== SYSTÈME D'ALERTES =====
    st.subheader("État du Système")
    alert_col1, alert_col2, alert_col3 = st.columns(3)

    with alert_col1:
        if last_data["flame"] < flame_threshold:
            st.error("**FLAMME DÉTECTÉE !**")
        else:
            st.success("Pas de flamme")

    with alert_col2:
        if last_data["temperature"] >= temp_max:
            st.warning(f"**Température élevée** ({last_data['temperature']:.1f}°C)")
        else:
            st.success("Température normale")

    with alert_col3:
        if last_data["humidite"] > 80:
            st.info("Humidité élevée")
        elif last_data["humidite"] < 30:
            st.warning("Humidité faible")
        else:
            st.success("Humidité normale")

    st.markdown("---")

    # ===== GRAPHIQUES =====
    st.subheader("Évolution des Mesures")
    tab1, tab2, tab3, tab4 = st.tabs(["Température", "Humidité", "Flamme", "LDR"])

    with tab1:
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=df["timestamp"], y=df["temperature"],
            mode='lines+markers', name='Température',
            line=dict(color='#FF4B4B', width=3), marker=dict(size=6),
            fill='tozeroy', fillcolor='rgba(255, 75, 75, 0.1)'
        ))
        fig_temp.add_hline(y=temp_max, line_dash="dash", line_color="red",
                          annotation_text=f"Seuil max ({temp_max}°C)")
        fig_temp.update_layout(title="Évolution de la Température",
                              xaxis_title="Temps", yaxis_title="Température (°C)",
                              hovermode='x unified', height=400)
        st.plotly_chart(fig_temp, use_container_width=True)

    with tab2:
        fig_hum = go.Figure()
        fig_hum.add_trace(go.Scatter(
            x=df["timestamp"], y=df["humidite"],
            mode='lines+markers', name='Humidité',
            line=dict(color='#4B8BFF', width=3), marker=dict(size=6),
            fill='tozeroy', fillcolor='rgba(75, 139, 255, 0.1)'
        ))
        fig_hum.update_layout(title="Évolution de l'Humidité",
                             xaxis_title="Temps", yaxis_title="Humidité (%)",
                             hovermode='x unified', height=400)
        st.plotly_chart(fig_hum, use_container_width=True)

    with tab3:
        fig_flame = go.Figure()
        fig_flame.add_trace(go.Scatter(
            x=df["timestamp"], y=df["flame"],
            mode='lines+markers', name='Capteur Flamme',
            line=dict(color='#FF8C00', width=3), marker=dict(size=6)
        ))
        fig_flame.add_hline(y=flame_threshold, line_dash="dash", line_color="red",
                           annotation_text=f"Seuil alerte ({flame_threshold})")
        fig_flame.update_layout(title="Capteur de Flamme",
                               xaxis_title="Temps", yaxis_title="Valeur ADC",
                               hovermode='x unified', height=400)
        st.plotly_chart(fig_flame, use_container_width=True)

    with tab4:
        fig_ldr = go.Figure()
        fig_ldr.add_trace(go.Scatter(
            x=df["timestamp"], y=df["ldr"],
            mode='lines+markers', name='LDR (Luminosité)',
            line=dict(color='#FFD700', width=3), marker=dict(size=6),
            fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'
        ))
        fig_ldr.update_layout(title="Évolution de la Luminosité (LDR)",
                             xaxis_title="Temps", yaxis_title="Valeur ADC",
                             hovermode='x unified', height=400)
        st.plotly_chart(fig_ldr, use_container_width=True)

    st.markdown("---")

    # ===== TABLEAU DE DONNÉES =====
    st.subheader("Historique des Données")
    df_display = df[["timestamp", "temperature", "humidite", "flame", "ldr"]].copy()
    df_display["timestamp"] = df_display["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_display.columns = ["Horodatage", "Température (°C)", "Humidité (%)", "Flamme", "LDR"]

    st.dataframe(
        df_display.tail(20).sort_values("Horodatage", ascending=False),
        use_container_width=True, hide_index=True
    )

    csv = df.to_csv(index=False)
    st.download_button(
        label="Télécharger les données (CSV)",
        data=csv,
        file_name=f"esp32_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

else:
    st.info("**En attente de données Firebase...**")
    st.markdown("""
    ### Vérifications :
    - L'ESP32 envoie-t-il des données à Firebase ?
    - Le fichier `firebase-key.json` est-il présent ?
    - L'URL de la database est-elle correcte ?
    - Les règles Firebase autorisent-elles la lecture ?
    """)
    with st.spinner("Connexion en cours..."):
        sleep(2)

# ===== AUTO-REFRESH =====
sleep(refresh_rate)
st.rerun()
