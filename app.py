import folium
import pandas as pd
import streamlit as st

def process_file(uploaded_file):
    # Read the file
    gps_data = pd.read_excel(uploaded_file)
    
    # Ensure 'Timestamp' column is in datetime format
    gps_data['Timestamp'] = pd.to_datetime(gps_data['Timestamp'], format='%d-%m-%Y %H:%M')
    
    # Calculate field areas and time metrics
    field_areas_gunthas = gps_data['Estimated Area (gunthas):'].dropna().astype(float).tolist()
    total_time_minutes = gps_data['Time (min):'].dropna().astype(float).sum()
    avg_time_diff_minutes = gps_data['Time Difference (s)'].mean() / 60
    
    # Calculate distance and time between fields
    gps_data['distance_next_field'] = gps_data['LatLong Distance (m)'].shift(-1).fillna(0)
    gps_data['time_next_field'] = gps_data['Time Difference (s)'].shift(-1).fillna(0) / 60
    
    # Map settings
    map_center = [gps_data['lat'].mean(), gps_data['lng'].mean()]
    map_token = 'YOUR_MAPBOX_TOKEN'  # Replace with your Mapbox token
    
    # Create a Folium map with Mapbox satellite tiles
    m = folium.Map(
        location=map_center,
        zoom_start=12,
        tiles=f'https://api.mapbox.com/styles/v1/{map_token}/tiles/{{z}}/{{x}}/{{y}}?access_token={map_token}',
        attr='Mapbox'
    )
    
    # Add points to the map
    for i, row in gps_data.iterrows():
        folium.Marker(
            location=[row['lat'], row['lng']],
            popup=f"Time: {row['Timestamp']}<br>Speed: {row['Speed (km/hr)']} km/hr",
            icon=folium.Icon(color='blue')
        ).add_to(m)
    
    # Create a DataFrame to display
    data = {
        'Field Index': range(1, len(field_areas_gunthas) + 1),
        'Estimated Area (gunthas)': field_areas_gunthas,
        'Total Time (minutes)': [total_time_minutes] * len(field_areas_gunthas),
        'Avg Time Difference (minutes)': [avg_time_diff_minutes] * len(field_areas_gunthas),
        'Distance to Next Field (m)': gps_data['distance_next_field'],
        'Time to Next Field (minutes)': gps_data['time_next_field']
    }
    
    combined_df = pd.DataFrame(data)
    
    return m, combined_df

# Streamlit interface
st.title("GPS Data Analysis")

uploaded_file = st.file_uploader("Upload GPS Data File", type="xlsx")

if uploaded_file:
    folium_map, combined_df = process_file(uploaded_file)
    
    st.write("Map with GPS Data")
    st.markdown(folium_map._repr_html_(), unsafe_allow_html=True)
    
    st.write("Data Summary")
    st.dataframe(combined_df)
    
    # Download the combined DataFrame
    st.download_button(
        label="Download CSV",
        data=combined_df.to_csv(index=False).encode('utf-8'),
        file_name='combined_data.csv',
        mime='text/csv'
    )
