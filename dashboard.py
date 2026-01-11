import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
from datetime import datetime
import plotly.graph_objs as go
from time import sleep

# ===== Configuration de la page Streamlit =====
st.set_page_config(
    page_title="Dashboard ESP32",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Configuration MQTT =====
MQTT_BROKER = "40.89.171.253"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/data"

# ===== Initialisation du session_state =====
if "data" not in st.session_state:
    st.session_state.data = []

if "mqtt_client" not in st.session_state:
    st.session_state.mqtt_client = None

if "connected" not in st.session_state:
    st.session_state.connected = False

# ===== Callbacks MQTT =====
def on_connect(client, userdata, flags, rc):
    """Callback appelé lors de la connexion au broker"""
    if rc == 0:
        st.session_state.connected = True
        client.subscribe(MQTT_TOPIC)
        print(f"Connecté au broker MQTT sur le topic: {MQTT_TOPIC}")
    else:
        st.session_state.connected = False
        print(f"Échec de connexion, code: {rc}")

def on_message(client, userdata, msg):
    """Callback appelé lors de la réception d'un message"""
    try:
        payload = json.loads(msg.payload.decode())
        payload["timestamp"] = datetime.now()
        st.session_state.data.append(payload)
        # Garder seulement les 100 dernières valeurs
        if len(st.session_state.data) > 100:
            st.session_state.data = st.session_state.data[-100:]
        print(f"Message reçu: {payload}")
    except Exception as e:
        print(f"Erreur lors du traitement du message: {e}")

def on_disconnect(client, userdata, rc):
    """Callback appelé lors de la déconnexion"""
    st.session_state.connected = False
    print("Déconnecté du broker MQTT")

# ===== Initialisation de la connexion MQTT =====
if st.session_state.mqtt_client is None:
    try:
        client = mqtt.Client(client_id="streamlit_dashboard")
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        st.session_state.mqtt_client = client
        print("Tentative de connexion au broker MQTT...")
    except Exception as e:
        st.error(f"Impossible de se connecter au broker MQTT: {e}")

# ===== HEADER =====
st.title("Dashboard ESP32 - Surveillance en Temps Réel")
st.markdown("---")

# ===== SIDEBAR =====
with st.sidebar:
    st.header("Configuration")
    
    # Statut de connexion
    if st.session_state.connected:
        st.success("Connecté")
    else:
        st.error("Déconnecté")
    
    st.info(f"**Broker:** {MQTT_BROKER}\n\n**Topic:** {MQTT_TOPIC}")
    
    st.metric("Messages reçus", len(st.session_state.data))
    
    # Contrôles
    st.markdown("---")
    st.subheader("Contrôles")
    
    refresh_rate = st.slider("Rafraîchissement (secondes)", 1, 10, 2)
    
    if st.button("Effacer l'historique"):
        st.session_state.data = []
        st.success("Historique effacé !")
        sleep(1)
        st.rerun()
    
    if st.button("Reconnecter MQTT"):
        if st.session_state.mqtt_client:
            st.session_state.mqtt_client.reconnect()
        st.rerun()
    
    # Seuils d'alerte
    st.markdown("---")
    st.subheader("Seuils d'alerte")
    temp_max = st.number_input("Température max (°C)", value=50, min_value=0, max_value=100)
    flame_threshold = st.number_input("Seuil flamme", value=2000, min_value=0, max_value=4095)

# ===== CONTENU PRINCIPAL =====
if len(st.session_state.data) > 0:
    # Convertir en DataFrame
    df = pd.DataFrame(st.session_state.data)
    last_data = df.iloc[-1]
    
    # ===== MÉTRIQUES EN TEMPS RÉEL =====
    st.subheader("Mesures Actuelles")
    col1, col2, col3, col4 = st.columns(4)
    
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
    
    tab1, tab2, tab3 = st.tabs(["Température", "Humidité", "Flamme"])
    
    with tab1:
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["temperature"],
            mode='lines+markers',
            name='Température',
            line=dict(color='#FF4B4B', width=3),
            marker=dict(size=6),
            fill='tozeroy',
            fillcolor='rgba(255, 75, 75, 0.1)'
        ))
        fig_temp.add_hline(
            y=temp_max,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil max ({temp_max}°C)"
        )
        fig_temp.update_layout(
            title="Évolution de la Température",
            xaxis_title="Temps",
            yaxis_title="Température (°C)",
            hovermode='x unified',
            height=400
        )
        st.plotly_chart(fig_temp, use_container_width=True)
    
    with tab2:
        fig_hum = go.Figure()
        fig_hum.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["humidite"],
            mode='lines+markers',
            name='Humidité',
            line=dict(color='#4B8BFF', width=3),
            marker=dict(size=6),
            fill='tozeroy',
            fillcolor='rgba(75, 139, 255, 0.1)'
        ))
        fig_hum.update_layout(
            title="Évolution de l'Humidité",
            xaxis_title="Temps",
            yaxis_title="Humidité (%)",
            hovermode='x unified',
            height=400
        )
        st.plotly_chart(fig_hum, use_container_width=True)
    
    with tab3:
        fig_flame = go.Figure()
        fig_flame.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["flame"],
            mode='lines+markers',
            name='Capteur Flamme',
            line=dict(color='#FF8C00', width=3),
            marker=dict(size=6)
        ))
        fig_flame.add_hline(
            y=flame_threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil alerte ({flame_threshold})"
        )
        fig_flame.update_layout(
            title="Capteur de Flamme",
            xaxis_title="Temps",
            yaxis_title="Valeur ADC",
            hovermode='x unified',
            height=400
        )
        st.plotly_chart(fig_flame, use_container_width=True)
    
    st.markdown("---")
    
    # ===== TABLEAU DE DONNÉES =====
    st.subheader("Historique des Données")
    
    # Formatage du DataFrame pour l'affichage
    df_display = df[["timestamp", "temperature", "humidite", "flame"]].copy()
    df_display["timestamp"] = df_display["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_display.columns = ["Horodatage", "Température (°C)", "Humidité (%)", "Flamme"]
    
    st.dataframe(
        df_display.tail(20).sort_values("Horodatage", ascending=False),
        use_container_width=True,
        hide_index=True
    )
    
    # Bouton de téléchargement
    csv = df.to_csv(index=False)
    st.download_button(
        label="Télécharger les données (CSV)",
        data=csv,
        file_name=f"esp32_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

else:
    # ===== ÉTAT D'ATTENTE =====
    st.info("**En attente de données du ESP32...**")
    st.markdown("""
    ### Vérifications :
    - L'ESP32 est-il allumé et connecté au WiFi ?
    - Le code C est-il téléversé sur l'ESP32 ?
    - Le broker MQTT est-il accessible ?
    - Le topic MQTT est-il correct : `esp32/data` ?
    """)
    
    with st.spinner("Connexion en cours..."):
        sleep(2)

# ===== AUTO-REFRESH =====
sleep(refresh_rate)
st.rerun()
