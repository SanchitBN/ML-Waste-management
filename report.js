const geminiApiKey = 'YOUR_GEMINI_API_KEY'; // Add your Gemini API key here
const googleMapsApiKey = 'YOUR_GOOGLE_MAPS_API_KEY'; // Add your Google Maps API key here

let previewContainer = document.getElementById('preview-container');
let locationInput = document.getElementById('location');
let typeInput = document.getElementById('type');
let amountInput = document.getElementById('amount');
let verifyButton = document.getElementById('verifyButton');
let submitButton = document.getElementById('submitButton');
let recentReportsContainer = document.getElementById('recentReports');
let reportForm = document.getElementById('reportForm');
let wasteImageInput = document.getElementById('waste-image');

let file = null;
let verificationResult = null;

const searchBoxInput = document.getElementById('location');

// Initialize Google Places API SearchBox
let searchBox;

function initMap() {
  const input = document.getElementById("location");
  searchBox = new google.maps.places.SearchBox(input);

  searchBox.addListener("places_changed", function() {
    const places = searchBox.getPlaces();
    if (places && places.length > 0) {
      const place = places[0];
      locationInput.value = place.formatted_address;
    }
  });
}

// File upload handler
wasteImageInput.addEventListener('change', (e) => {
  const selectedFile = e.target.files[0];
  file = selectedFile;
  const reader = new FileReader();
  
  reader.onload = () => {
    const imgElement = document.createElement('img');
    imgElement.src = reader.result;
    previewContainer.innerHTML = '';
    previewContainer.appendChild(imgElement);
  };
  
  reader.readAsDataURL(selectedFile);
});

// Verify waste
verifyButton.addEventListener('click', async () => {
  if (!file) return alert('Please upload an image.');

  verifyButton.textContent = 'Verifying...';
  verifyButton.disabled = true;

  try {
    const base64Data = await readFileAsBase64(file);
    
    const response = await fetch('http://localhost:5000/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: base64Data })
    });

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (jsonErr) {
      throw new Error('Invalid JSON response: ' + text);
    }

    if (response.ok && data.success) {
      verificationResult = data.result;
      typeInput.value = verificationResult.wasteType;
      amountInput.value = verificationResult.quantity;

      alert(`Waste type: ${verificationResult.wasteType}\nAmount: ${verificationResult.quantity} kg\nConfidence: ${(verificationResult.confidence * 100).toFixed(2)}%`);
      submitButton.disabled = false;
    } else {
      throw new Error(data.error || 'Verification failed');
    }

  } catch (error) {
    console.error(error);
    alert('An error occurred during verification:\n' + error.message);
  }

  verifyButton.textContent = 'Verify Waste';
  verifyButton.disabled = false;
});


// Submit report
reportForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const email = localStorage.getItem('userEmail'); // getting email from localStorage

  const reportData = {
    location: locationInput.value,
    wasteType: typeInput.value,
    amount: amountInput.value,
    email: email  // this must NOT be null
  };

  console.log("Report data to send:", reportData);  // <--- Debug log

  const response = await fetch('http://localhost:5000/submit-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reportData)
  });

  const data = await response.json();
  if (data.success) {
    alert('Report submitted successfully!');
    loadRecentReports();
  } else {
    alert('Failed to submit report: ' + data.error);
  }
});

// Load recent reports
async function loadRecentReports() {
  const response = await fetch('http://localhost:5000/recent-reports');
  const data = await response.json();
  const reports = data.reports;

  recentReportsContainer.innerHTML = '<h2>Recent Reports</h2>';
  reports.forEach(report => {
    const div = document.createElement('div');
    div.classList.add('report-item');
    div.innerHTML = `<span>${report.location}</span> <span>${report.wasteType}</span> <span>${report.amount}</span> <span>${report.date}</span>`;
    recentReportsContainer.appendChild(div);
  });
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]; // strip the prefix
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
// Initialize map on load
window.onload = initMap;
