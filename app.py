import streamlit as st
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
from sklearn.cluster import DBSCAN
from scipy.spatial import ConvexHull
import folium
from folium import plugins
import io
from geopy.distance import geodesic
import base64

# Function to calculate the area of a field in square meters using convex hull
def calculate_convex_hull_area(points):
    if len(points) < 3:  # Not enough points to form a polygon
        return 0
    try:
        hull = ConvexHull(points)
        poly = Polygon(points[hull.vertices])
        return poly.area  # Area in square degrees
    except Exception:
        return 0

# Function to calculate centroid of a set of points
def calculate_centroid(points):
    return np.mean(points, axis=0)

# Function to process the uploaded file and return the map and field areas
def process_file(file):
    # Load the CSV file
    gps_data = pd.read_csv(file)

    # Check the columns available
    st.write("Available columns:", gps_data.columns.tolist())
    
    # Use the correct column names
    if 'Timestamp' not in gps_data.columns:
        st.error("The CSV file does not contain a 'Timestamp' column.")
        return None, None
    
    gps_data = gps_data[['lat', 'lng', 'Timestamp']]
    
    # Convert Timestamp column to datetime with correct format
    gps_data['Timestamp'] = pd.to_datetime(gps_data['Timestamp'], format='%d-%m-%Y %H.%M', errors='coerce', dayfirst=True)
    
    # Drop rows where conversion failed
    gps_data = gps_data.dropna(subset=['Timestamp'])
    
    # Cluster the GPS points to identify separate fields
    coords = gps_data[['lat', 'lng']].values
    db = DBSCAN(eps=0.00008, min_samples=11).fit(coords)
    labels = db.labels_

    # Add labels to the data
    gps_data['field_id'] = labels

    # Calculate the area for each field
    fields = gps_data[gps_data['field_id'] != -1]  # Exclude noise points
    field_areas = fields.groupby('field_id').apply(
        lambda df: calculate_convex_hull_area(df[['lat', 'lng']].values))

    # Convert the area from square degrees to square meters (approximation)
    field_areas_m2 = field_areas * 0.77 * (111000 ** 2)  # rough approximation

    # Convert the area from square meters to gunthas (1 guntha = 101.17 m^2)
    field_areas_gunthas = field_areas_m2 / 101.17

    # Calculate time metrics for each field
    field_times = fields.groupby('field_id').apply(
        lambda df: (df['Timestamp'].max() - df['Timestamp'].min()).total_seconds() / 60.0
    )

    # Extract start and end dates for each field
    field_dates = fields.groupby('field_id').agg(
        start_date=('Timestamp', 'min'),
        end_date=('Timestamp', 'max')
    )

    # Filter out fields with area less than 5 gunthas
    valid_fields = field_areas_gunthas[field_areas_gunthas >= 5].index
    field_areas_gunthas = field_areas_gunthas[valid_fields]
    field_times = field_times[valid_fields]
    field_dates = field_dates.loc[valid_fields]

    # Calculate centroids of each field
    centroids = fields.groupby('field_id').apply(
        lambda df: calculate_centroid(df[['lat', 'lng']].values)
    )

    # Calculate traveling distance and time between field centroids
    travel_distances = []
    travel_times = []
    field_ids = list(valid_fields)
    
    if len(field_ids) > 1:
        for i in range(len(field_ids) - 1):
            centroid1 = centroids.loc[field_ids[i]]
            centroid2 = centroids.loc[field_ids[i + 1]]
            distance = geodesic(centroid1, centroid2).kilometers
            time = (field_dates.loc[field_ids[i + 1], 'start_date'] - field_dates.loc[field_ids[i], 'end_date']).total_seconds() / 60.0
            travel_distances.append(distance)
            travel_times.append(time)

        # Calculate distance from last point of one field to first point of the next field
        for i in range(len(field_ids) - 1):
            end_point = fields[fields['field_id'] == field_ids[i]][['lat', 'lng']].values[-1]
            start_point = fields[fields['field_id'] == field_ids[i + 1]][['lat', 'lng']].values[0]
            distance = geodesic(end_point, start_point).kilometers
            time = (field_dates.loc[field_ids[i + 1], 'start_date'] - field_dates.loc[field_ids[i], 'end_date']).total_seconds() / 60.0
            travel_distances.append(distance)
            travel_times.append(time)

        # Append NaN for the last field
        travel_distances.append(np.nan)
        travel_times.append(np.nan)
    else:
        travel_distances.append(np.nan)
        travel_times.append(np.nan)

    # Ensure lengths match for DataFrame
    if len(travel_distances) != len(field_areas_gunthas):
        travel_distances = travel_distances[:len(field_areas_gunthas)]
        travel_times = travel_times[:len(field_areas_gunthas)]

    # Combine area, time, dates, and travel metrics into a single DataFrame
    combined_df = pd.DataFrame({
        'Field ID': field_areas_gunthas.index,
        'Area (Gunthas)': field_areas_gunthas.values,
        'Time (Minutes)': field_times.values,
        'Start Date': field_dates['start_date'].values,
        'End Date': field_dates['end_date'].values,
        'Travel Distance to Next Field (km)': travel_distances,
        'Travel Time to Next Field (minutes)': travel_times
    })
    
    # Create a satellite map
    map_center = [gps_data['lat'].mean(), gps_data['lng'].mean()]
    m = folium.Map(location=map_center, zoom_start=12)
    
    # Add Mapbox satellite imagery
    mapbox_token = 'pk.eyJ1IjoiZmxhc2hvcDAwNyIsImEiOiJjbHo5NzkycmIwN2RxMmtzZHZvNWpjYmQ2In0.A_FZYl5zKjwSZpJuP_MHiA'
    folium.TileLayer(
        tiles='https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/256/{z}/{x}/{y}?access_token=' + mapbox_token,
        attr='Mapbox Satellite Imagery',
        name='Satellite',
        overlay=True,
        control=True
    ).add_to(m)
    
    # Add fullscreen control
    plugins.Fullscreen(position='topright').add_to(m)

    # Plot the points on the map
    for idx, row in gps_data.iterrows():
        color = 'blue' if row['field_id'] in valid_fields else 'red'  # Blue for fields, red for noise
        folium.CircleMarker(
            location=(row['lat'], row['lng']),
            radius=2,
            color=color,
            fill=True,
            fill_color=color
        ).add_to(m)

    return m, combined_df

# Function to generate a download link for the map
def get_map_download_link(map_obj, filename='map.html'):
    # Save the map to an HTML file
    map_html = map_obj._repr_html_()
    b64 = base64.b64encode(map_html.encode()).decode()
    href = f'<a href="data:file/html;base64,{b64}" download="{filename}">Download Map</a>'
    return href

# Streamlit app
st.title("Field Area and Time Calculation from GPS Data")

# Display logo
st.markdown("""
    <style>
        .header { display: flex; align-items: center; }
        .header img { height: 60px; margin-right: 20px; }
    </style>
    <div class="header">
        <img src="https://i.imgur.com/q7XmNAh.jpg" alt="Logo">
        <h1>Field Area and Time Calculation from GPS Data</h1>
    </div>
""", unsafe_allow_html=True)

st.write("Upload a CSV file with 'lat', 'lng', and 'Timestamp' columns to calculate field areas and visualize them on a satellite map.")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    st.write("Processing file...")
    folium_map, combined_df = process_file(uploaded_file)
    
    if folium_map is not None:
        st.write("Field Areas, Times, Dates, and Travel Metrics:", combined_df)
        st.write("Download the combined data as a CSV file:")
        
        # Provide download link
        csv = combined_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name='field_areas_times_dates_and_travel_metrics.csv',
            mime='text/csv'
        )
        
        # Provide download link for map
        map_download_link = get_map_download_link(folium_map)
        st.markdown(map_download_link, unsafe_allow_html=True)
    else:
        st.error("Failed to process the file.")
