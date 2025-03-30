# Ajouter aux imports existants
from scipy.interpolate import interp1d
import warnings
warnings.filterwarnings('ignore')

# Modifier la création des onglets
tabs = st.tabs(["Chargement", "Aperçu", "Desurvey", "Composites", "Statistiques", "Visualisation 3D"])

# Fonction pour le calcul du desurvey
def calculate_desurvey(collars, survey, samples, hole_id_col, depth_col):
    results = []
    for hole in collars[hole_id_col].unique():
        # Filtrer les données pour le trou courant
        hole_survey = survey[survey[hole_id_col] == hole].sort_values('depth')
        hole_samples = samples[samples[hole_id_col] == hole].sort_values(depth_col)
        collar = collars[collars[hole_id_col] == hole].iloc[0]
        
        # Créer des fonctions d'interpolation pour azimuth et dip
        depths = hole_survey['depth'].values
        azimuths = hole_survey['azimuth'].values
        dips = hole_survey['dip'].values
        
        f_azimuth = interp1d(depths, azimuths, fill_value='extrapolate')
        f_dip = interp1d(depths, dips, fill_value='extrapolate')
        
        # Calculer les coordonnées pour chaque échantillon
        for _, sample in hole_samples.iterrows():
            depth = sample[depth_col]
            azimuth = float(f_azimuth(depth))
            dip = float(f_dip(depth))
            
            # Calcul des coordonnées 3D
            dh = depth
            dx = dh * np.sin(np.radians(90 - dip)) * np.sin(np.radians(azimuth))
            dy = dh * np.sin(np.radians(90 - dip)) * np.cos(np.radians(azimuth))
            dz = dh * np.cos(np.radians(90 - dip))
            
            x = collar['east'] + dx
            y = collar['north'] + dy
            z = collar['elevation'] - dz
            
            result = sample.to_dict()
            result.update({
                'x': x,
                'y': y,
                'z': z
            })
            results.append(result)
    
    return pd.DataFrame(results)

# Fonction pour le calcul des composites
def calculate_composites(df, method, interval, min_length=0.5, weight_col=None):
    composites = []
    
    for hole in df['hole_id'].unique():
        hole_data = df[df['hole_id'] == hole].sort_values('depth_from')
        
        current_from = hole_data['depth_from'].min()
        while current_from < hole_data['depth_to'].max():
            current_to = current_from + interval
            interval_data = hole_data[
                (hole_data['depth_from'] < current_to) & 
                (hole_data['depth_to'] > current_from)
            ]
            
            if len(interval_data) > 0:
                if method == 'length_weighted':
                    weights = interval_data['length']
                elif method == 'weighted':
                    weights = interval_data[weight_col] * interval_data['length']
                else:  # arithmetic
                    weights = None
                
                composite = {
                    'hole_id': hole,
                    'from': current_from,
                    'to': current_to,
                    'length': current_to - current_from
                }
                
                # Calcul des moyennes pondérées pour chaque colonne numérique
                for col in interval_data.select_dtypes(include=[np.number]).columns:
                    if col not in ['depth_from', 'depth_to', 'length']:
                        if weights is None:
                            composite[col] = interval_data[col].mean()
                        else:
                            composite[col] = np.average(interval_data[col], weights=weights)
                
                composites.append(composite)
            
            current_from = current_to
    
    return pd.DataFrame(composites)

# Ajouter l'onglet Desurvey
with tabs[2]:
    st.header("Calcul du Desurvey")
    
    if all(v is not None for v in [st.session_state.data['collars'], 
                                  st.session_state.data['survey']]):
        
        st.subheader("Paramètres du Desurvey")
        
        desurvey_type = st.radio(
            "Données à desurveyer",
            ["Assays", "Lithology"]
        )
        
        if desurvey_type == "Assays" and st.session_state.data['assays'] is not None:
            data_to_desurvey = st.session_state.data['assays']
        elif desurvey_type == "Lithology" and st.session_state.data['lithology'] is not None:
            data_to_desurvey = st.session_state.data['lithology']
        
        if st.button("Calculer Desurvey"):
            with st.spinner("Calcul du desurvey en cours..."):
                desurvey_result = calculate_desurvey(
                    st.session_state.data['collars'],
                    st.session_state.data['survey'],
                    data_to_desurvey,
                    st.session_state.data['columns_mapping']['hole_id'],
                    'depth'
                )
                st.success("Calcul terminé!")
                st.dataframe(desurvey_result)
                
                # Bouton d'export
                csv = desurvey_result.to_csv(index=False)
                st.download_button(
                    "Télécharger résultats",
                    csv,
                    f"desurvey_{desurvey_type.lower()}.csv",
                    "text/csv"
                )

# Ajouter l'onglet Composites
with tabs[3]:
    st.header("Calcul des Composites")
    
    if st.session_state.data['assays'] is not None:
        st.subheader("Paramètres des Composites")
        
        col1, col2 = st.columns(2)
        
        with col1:
            composite_method = st.selectbox(
                "Méthode de calcul",
                ["arithmetic", "length_weighted", "weighted"]
            )
            
            if composite_method == "weighted":
                weight_column = st.selectbox(
                    "Colonne de pondération",
                    st.session_state.data['assays'].select_dtypes(include=[np.number]).columns
                )
            
        with col2:
            interval = st.number_input("Intervalle (m)", min_value=0.1, value=1.0)
            min_length = st.number_input("Longueur minimum (m)", min_value=0.1, value=0.5)
        
        if st.button("Calculer Composites"):
            with st.spinner("Calcul des composites en cours..."):
                composite_result = calculate_composites(
                    st.session_state.data['assays'],
                    composite_method,
                    interval,
                    min_length,
                    weight_column if composite_method == "weighted" else None
                )
                st.success("Calcul terminé!")
                st.dataframe(composite_result)
                
                # Bouton d'export
                csv = composite_result.to_csv(index=False)
                st.download_button(
                    "Télécharger composites",
                    csv,
                    "composites.csv",
                    "text/csv"
                )