import pandas as pd
import folium
from folium import plugins
import streamlit as st
from io import StringIO
import numpy as np

# Define the Mapbox token
MAPBOX_TOKEN = 'pk.eyJ1IjoiZmxhc2hvcDAwNyIsImEiOiJjbHo5NzkycmIwN2RxMmtzZHZvNWpjYmQ2In0.A_FZYl5zKjwSZpJuP_MHiA'

def process_file(file):
    # Read the file into a DataFrame
    df = pd.read_csv(file)
    
    # Display column names
    st.write(f"Columns in the file: {df.columns.tolist()}")

    # Handle timestamp format
    try:
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%d-%m-%Y %H:%M', errors='coerce')
    except Exception as e:
        st.error(f"Error parsing dates: {e}")
        return None, None, None, None
    
    # Filter necessary columns
    gps_data = df[['lat', 'lng', 'Timestamp']].dropna()
    
    # Calculate time metrics
    gps_data['Time Difference (s)'] = gps_data['Timestamp'].diff().dt.total_seconds().fillna(0)
    total_time_seconds = gps_data['Time Difference (s)'].sum()
    total_time_minutes = total_time_seconds / 60
    
    # Create folium map
    m = folium.Map(
        location=[gps_data['lat'].mean(), gps_data['lng'].mean()],
        zoom_start=15,
        tiles=f'https://api.mapbox.com/styles/v1/{MAPBOX_TOKEN}/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}',
    )
    
    # Add markers to map
    for idx, row in gps_data.iterrows():
        folium.Marker([row['lat'], row['lng']], popup=row['Timestamp']).add_to(m)
    
    # Prepare area and time metrics
    field_areas = df[['Estimated Area (gunthas):', 'Time (min):']].dropna()
    
    # Combine time and area metrics into one table
    combined_metrics = field_areas.copy()
    combined_metrics.columns = ['Area (gunthas)', 'Time (min)']
    
    # Save the table to a CSV
    csv_data = combined_metrics.to_csv(index=False)
    st.download_button(
        label="Download Metrics as CSV",
        data=csv_data,
        file_name='field_metrics.csv',
        mime='text/csv'
    )

    return m, total_time_minutes, combined_metrics

st.title('Field Analysis App')
uploaded_file = st.file_uploader("Choose a CSV file")

if uploaded_file is not None:
    folium_map, total_time_minutes, combined_metrics = process_file(uploaded_file)
    
    if folium_map:
        # Display the map
        st.write(f"Total time taken (minutes): {total_time_minutes:.2f}")
        st.write("Metrics Table:")
        st.dataframe(combined_metrics)
        
        # Convert folium map to HTML
        map_html = folium_map._repr_html_()
        st.components.v1.html(map_html, height=500)
