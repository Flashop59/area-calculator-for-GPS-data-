import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from datetime import datetime
from geopy.distance import geodesic

# Function to process the uploaded file and calculate areas, times, distances, and traveling times
def process_file(file):
    gps_data = pd.read_csv(file)
    gps_data.columns = gps_data.columns.str.strip()

    # Convert 'Timestamp' to datetime
    gps_data['Timestamp'] = pd.to_datetime(gps_data['Timestamp'], format='%d-%m-%Y %H:%M', errors='coerce')
    gps_data = gps_data.dropna(subset=['Timestamp'])

    # Group by 'Point' to get areas and times for each field
    grouped = gps_data.groupby('Point')
    field_areas_gunthas = grouped['Estimated Area (gunthas):'].first().fillna(0).tolist()
    dates = grouped['Timestamp'].min().dt.date.tolist()
    times = grouped['Time Difference (s)'].sum() / 60  # Convert seconds to minutes
    total_times = times.tolist()
    time_diffs = grouped['Time Difference (s)'].mean() / 60  # Average time difference in minutes
    avg_time_diffs = time_diffs.tolist()

    # Ensure all lists are of the same length
    min_length = min(len(field_areas_gunthas), len(dates), len(total_times), len(avg_time_diffs))

    field_areas_gunthas = field_areas_gunthas[:min_length]
    dates = dates[:min_length]
    total_times = total_times[:min_length]
    avg_time_diffs = avg_time_diffs[:min_length]

    # Calculate travel distances and times between consecutive points
    travel_distances = []
    travel_times = []

    for i in range(len(dates) - 1):
        point1 = gps_data[gps_data['Point'] == i+1][['lat', 'lng']].iloc[-1]
        point2 = gps_data[gps_data['Point'] == i+2][['lat', 'lng']].iloc[0]
        distance = geodesic((point1['lat'], point1['lng']), (point2['lat'], point2['lng'])).meters
        travel_distances.append(distance)
        
        time1 = gps_data[gps_data['Point'] == i+1]['Timestamp'].iloc[-1]
        time2 = gps_data[gps_data['Point'] == i+2]['Timestamp'].iloc[0]
        time_diff = (time2 - time1).total_seconds() / 60  # Convert seconds to minutes
        travel_times.append(time_diff)

    travel_distances.append(0)  # No travel distance after the last point
    travel_times.append(0)      # No travel time after the last point

    # Ensure travel distances and travel times are the same length as other lists
    travel_distances = travel_distances[:min_length]
    travel_times = travel_times[:min_length]

    # Create a combined DataFrame
    combined_df = pd.DataFrame({
        'Field': range(1, min_length + 1),
        'Date': dates,
        'Area (gunthas)': field_areas_gunthas,
        'Total Time (minutes)': total_times,
        'Avg Time Diff (minutes)': avg_time_diffs,
        'Travel Distance (meters)': travel_distances,
        'Travel Time (minutes)': travel_times
    })

    # Create a folium map with satellite imagery
    m = folium.Map(location=[gps_data['lat'].mean(), gps_data['lng'].mean()], zoom_start=15, tiles='OpenStreetMap')
    folium.TileLayer('Stamen Terrain').add_to(m)
    folium.TileLayer('Stamen Toner').add_to(m)
    folium.TileLayer('Stamen Watercolor').add_to(m)
    folium.TileLayer('cartodb positron').add_to(m)
    folium.TileLayer('cartodb dark_matter').add_to(m)
    folium.TileLayer(
        tiles='https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        max_zoom=20,
        subdomains=['mt0', 'mt1', 'mt2', 'mt3']
    ).add_to(m)

    for _, row in gps_data.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=3,
            color='red' if row['State'] == 'STOP' else 'blue',
            fill=True
        ).add_to(m)

    return m, combined_df

# Streamlit app
st.title('Field Area and Time Calculator with Satellite Map')

# File uploader with session state handling
uploaded_file = st.file_uploader("Upload GPS data CSV", type="csv", key='file_uploader')

if uploaded_file is not None:
    if 'processed_data' not in st.session_state:
        folium_map, combined_df = process_file(uploaded_file)
        st.session_state['folium_map'] = folium_map
        st.session_state['combined_df'] = combined_df
    else:
        folium_map = st.session_state['folium_map']
        combined_df = st.session_state['combined_df']

    # Display map
    st.subheader("Map of Field Operations")
    st_folium(folium_map, width=800, height=600)

    # Display combined data
    st.subheader("Field Data")
    st.write(combined_df)

    # Download combined data
    csv = combined_df.to_csv(index=False).encode()
    st.download_button(label="Download Combined Data as CSV", data=csv, file_name='combined_data.csv', mime='text/csv')
