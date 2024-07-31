const map = L.map('map').setView([20.5937, 78.9629], 6); // Center on India

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

document.getElementById('fileInput').addEventListener('change', handleFileSelect);

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: function(results) {
            processCSVData(results.data);
        }
    });
}

function processCSVData(data) {
    // Example: Add markers to the map
    data.forEach(row => {
        const lat = parseFloat(row.lat);
        const lng = parseFloat(row.lng);

        if (!isNaN(lat) && !isNaN(lng)) {
            L.marker([lat, lng]).addTo(map)
                .bindPopup(`<b>Timestamp:</b> ${row.Timestamp}`)
                .openPopup();
        }
    });
}
