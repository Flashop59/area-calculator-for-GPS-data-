import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import io

# Define your Mapbox token
MAPBOX_TOKEN = 'pk.eyJ1IjoiZmxhc2hvcDAwNyIsImEiOiJjbHo5NzkycmIwN2RxMmtzZHZvNWpjYmQ2In0.A_FZYl5zKjwSZpJuP_MHiA'

# Create a Folium map with satellite view
def create_folium_map():
    folium_map = folium.Map(
        location=[19.580467, 74.607094],  # Replace with your initial center coordinates
        zoom_start=15,
        tiles='https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={access_token}',
        attr='Mapbox',
        id='mapbox/satellite-v9',  # This sets the map to satellite view
        access_token=MAPBOX_TOKEN
    )
    return folium_map

def process_file(uploaded_file):
    # Read the file
    gps_data = pd.read_csv(uploaded_file)

    # Parse datetime and filter necessary columns
    gps_data['Timestamp'] = pd.to_datetime(gps_data['Timestamp'], format='%d-%m-%Y %H:%M')
    gps_data = gps_data[['lat', 'lng', 'Timestamp', 'Time Difference (s)', 'Estimated Area (gunthas):']]

    # Convert the 'Timestamp' to datetime if not already
    gps_data['Timestamp'] = pd.to_datetime(gps_data['Timestamp'])

    # Calculate time and area metrics
    total_time_seconds = gps_data['Time Difference (s)'].sum()
    total_time_minutes = total_time_seconds / 60
    avg_time_diff_minutes = gps_data['Time Difference (s)'].mean() / 60

    # Create a Folium map
    folium_map = create_folium_map()

    # Add points to the map
    for index, row in gps_data.iterrows():
        folium.Marker(
            location=[row['lat'], row['lng']],
            popup=f"Time: {row['Timestamp']}, Area: {row['Estimated Area (gunthas):']} gunthas",
        ).add_to(folium_map)

    # Create a combined DataFrame for download
    combined_df = gps_data[['Timestamp', 'Estimated Area (gunthas):']]
    combined_df['Total Time (minutes)'] = total_time_minutes
    combined_df['Average Time Difference (minutes)'] = avg_time_diff_minutes

    # Save to CSV
    combined_csv = combined_df.to_csv(index=False)
    combined_csv = io.StringIO(combined_csv)

    return folium_map, total_time_minutes, avg_time_diff_minutes, combined_csv

# Streamlit app
st.title("GPS Data Analyzer")

# File upload
uploaded_file = st.file_uploader("Upload your GPS data file (CSV format)")

if uploaded_file is not None:
    # Process file and get results
    folium_map, total_time_minutes, avg_time_diff_minutes, combined_csv = process_file(uploaded_file)

    # Display map
    st_folium(folium_map, width=700, height=500)

    # Display metrics
    st.write(f"Total Time (minutes): {total_time_minutes:.2f}")
    st.write(f"Average Time Difference (minutes): {avg_time_diff_minutes:.2f}")

    # Download link for combined table
    st.download_button(
        label="Download Combined Table",
        data=combined_csv,
        file_name='combined_table.csv',
        mime='text/csv'
    )
