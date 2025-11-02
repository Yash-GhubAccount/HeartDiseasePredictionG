document.addEventListener('DOMContentLoaded', () => {
    // --- DOM ELEMENTS & STATE ---
    const pages = document.querySelectorAll('.page');
    const allNavLinks = document.querySelectorAll('a[href^="#"]');
    const homeLink = document.getElementById('home-link');
    const aboutLink = document.getElementById('about-link');
    const loginLink = document.getElementById('login-link');
    const registerLink = document.getElementById('register-link');
    //admin panel new elements 
    const publicNav = document.getElementById('nav-links');
    const patientNav = document.getElementById('patient-nav-links');
    const doctorNav = document.getElementById('doctor-nav-links');
    const adminNav = document.getElementById('admin-nav-links');
    // ...
    const userNavLinksContainer = document.getElementById('user-nav-links');
    const logoutButton = document.getElementById('logout-button');
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');

    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const predictionForm = document.getElementById('prediction-form');
    const predictionLoader = document.getElementById('prediction-loader');
    const predictionButton = document.getElementById('prediction-button');

    const resultContent = document.getElementById('result-content');
    const resultError = document.getElementById('result-error');
    const recommendationsList = document.getElementById('recommendations-list');
    const historyTableBody = document.getElementById('history-table-body');

    let userState = { token: null, role: null };
    const API_BASE_URL = 'http://127.0.0.1:5000/api';

    // Track latest request IDs to prevent race conditions
    let latestPredictionId = 0;
    let latestHistoryId = 0;
    let navigatingToResult = sessionStorage.getItem('navigatingToResult') === 'true';

    // Restore result content if it exists in session storage
    const savedResultContent = sessionStorage.getItem('resultContent');
    const savedRecommendations = sessionStorage.getItem('recommendations');
    if (savedResultContent) {
        resultContent.innerHTML = savedResultContent;
        recommendationsList.innerHTML = savedRecommendations || '';
    }

    // Logging helper: use console.debug when DEBUG is true, otherwise console.log
    // This ensures messages appear in the Console even if debug-level logs are hidden.
    const LOG = (...args) => {
        try {
            if (window.DEBUG) console.debug(...args);
            else console.log(...args);
        } catch (e) {
            // Fallback in case console methods are unavailable
            // no-op
        }
    };

    // --- ABOUT LINK SCROLL (Isolated) ---
    if (aboutLink) {
        aboutLink.addEventListener('click', (e) => {

            // First, check if the link is enabled (not disabled)
            if (!aboutLink.classList.contains('disabled-link')) {

                // 1. Prevent the link from changing the URL (no #about)
                e.preventDefault(); 

                // 2. STOP the event from bubbling up to other listeners
                //    (This is the key fix that STOPS the allNavLinks
                //    listener from firing and causing the blank page)
                e.stopPropagation(); 

                // 3. Scroll smoothly to the bottom of the page
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }, true); // The 'true' makes this listener run first
    }


    // --- NOTIFICATION HELPER ---
    // --- NOTIFICATION HELPER (Upgraded) ---
    const showNotification = (message, type = 'error') => {
        const notificationDiv = document.getElementById('notification');
        const notificationTitle = document.getElementById('notification-title');
        const notificationMessage = document.getElementById('notification-message');

        // Remove old styles
        notificationDiv.classList.remove('bg-red-100', 'border-red-400', 'text-red-700');
        notificationDiv.classList.remove('bg-green-100', 'border-green-400', 'text-green-700');

        if (type === 'success') {
            notificationTitle.textContent = 'Success!';
            notificationMessage.textContent = message;
            // Add success styles
            notificationDiv.classList.add('bg-green-100', 'border-green-400', 'text-green-700');
        } else {
            // Default to error
            notificationTitle.textContent = 'Error:';
            notificationMessage.textContent = message;
            // Add error styles
            notificationDiv.classList.add('bg-red-100', 'border-red-400', 'text-red-700');
        }

        notificationDiv.classList.remove('hidden');
        setTimeout(() => {
            notificationDiv.classList.add('hidden');
        }, 4000);
    };

    // --- API CALLS ---
    const fetchPredictionHistory = async () => {
        const requestId = ++latestHistoryId;
        if (!userState.token) return;
        historyTableBody.innerHTML = '<tr><td colspan="3" class="text-center py-4">Loading history...</td></tr>';
        try {
            const response = await fetch(`${API_BASE_URL}/history`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const historyData = await response.json();
            if (!response.ok) throw new Error(historyData.error || 'Failed to fetch history');

            if (requestId !== latestHistoryId) return;

            if (historyData.length === 0) {
                historyTableBody.innerHTML = '<tr><td colspan="3" class="text-center py-4">No prediction history found.</td></tr>';
                return;
            }

            historyTableBody.innerHTML = historyData.map(p => `
                <tr class="border-b">
                    <td class="py-3 px-4">${p.timestamp}</td>
                    <td class="py-3 px-4 font-semibold ${p.result === 'Yes' ? 'text-red-600' : 'text-green-600'}">${p.result}</td>
                    <td class="py-3 px-4">${p.probability}</td>
                </tr>
            `).join('');

        } catch (error) {
            if (requestId === latestHistoryId) {
                showNotification(error.message);
                historyTableBody.innerHTML = `<tr><td colspan="3" class="text-center py-4 text-red-600">Could not load history.</td></tr>`;
            }
        }
    };

    const fetchRecommendations = async () => {
        if (!userState.token) return;
        const container = document.getElementById('recommendations-container');
        container.innerHTML = '<p class="text-gray-500">Loading recommendations...</p>';

        try {
            const response = await fetch(`${API_BASE_URL}/recommendations`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch recommendations');

            if (data.length === 0) {
                container.innerHTML = '<p class="text-gray-500">No recommendations available yet. Make a prediction first!</p>';
                return;
            }

            container.innerHTML = data.map(pred => `
                <div class="mb-6 border-b pb-4">
                    <h3 class="text-lg font-semibold mb-2">
                        Prediction on ${pred.timestamp} →
                        <span class="${pred.result === 'Yes' ? 'text-red-600' : 'text-green-600'}">${pred.result}</span>
                    </h3>
                    <ul class="list-disc list-inside space-y-1 text-gray-700">
                        ${pred.recommendations.map(r => `<li>${r}</li>`).join('')}
                    </ul>
                </div>
            `).join('');

        } catch (error) {
            showNotification(error.message);
            container.innerHTML = '<p class="text-red-600">Could not load recommendations.</p>';
        }
    };

    // --- FETCH DOCTORS FOR APPOINTMENT FORM ---
    // --- FETCH DOCTORS FOR APPOINTMENT FORM ---
    const fetchDoctors = async () => {
        if (!userState.token) return;
        const doctorSelect = document.getElementById('doctor-select');
        doctorSelect.innerHTML = '<option value="">Loading doctors...</option>';

        try {
            const response = await fetch(`${API_BASE_URL}/doctors`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch doctors');

            if (data.length === 0) {
                doctorSelect.innerHTML = '<option value="">No doctors available</option>';
                return;
            }

            doctorSelect.innerHTML = '<option value="">Select a doctor</option>'; // Clear loading
            data.forEach(doctor => {
                const option = document.createElement('option');
                option.value = doctor.id;
                
                // --- THIS IS THE CORRECTED LINE ---
                // It correctly uses doctor.full_name
                option.textContent = doctor.name; // This will read the "John Doe (General)" value
                
                doctorSelect.appendChild(option);
            });

        } catch (error) {
            showNotification(error.message);
            doctorSelect.innerHTML = '<option value="">Error loading doctors</option>';
        }
    };

    // --- FETCH PATIENT'S APPOINTMENTS ---
    const fetchAppointments = async () => {
        if (!userState.token) return;
        const appointmentsTableBody = document.getElementById('appointments-table-body');
        appointmentsTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4">Loading appointments...</td></tr>';

        try {
            const response = await fetch(`${API_BASE_URL}/appointments`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch appointments');

            if (data.length === 0) {
                appointmentsTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4">No appointments found.</td></tr>';
                return;
            }

            appointmentsTableBody.innerHTML = data.map(appt => `
                <tr class="border-b">
                    <td class="py-3 px-4">${appt.doctor_name}</td>
                    <td class="py-3 px-4">${appt.datetime}</td>
                    <td class="py-3 px-4">${appt.reason}</td>
                    <td class="py-3 px-4 font-medium ${appt.status === 'Pending' ? 'text-yellow-600' : 'text-green-600'}">${appt.status}</td>
                </tr>
            `).join('');

        } catch (error) {
            showNotification(error.message);
            appointmentsTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-red-600">Could not load appointments.</td></tr>';
        }
    };


    // --- DOCTOR: Fetch appointments for the doctor's dashboard ---
    const fetchDoctorAppointments = async () => {
        if (!userState.token) return;
        const tableBody = document.getElementById('doctor-appointments-table-body');
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading appointments...</td></tr>';

        try {
            const response = await fetch(`${API_BASE_URL}/doctor/appointments`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch appointments');

            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No appointments found.</td></tr>';
                return;
            }

            tableBody.innerHTML = data.map(appt => `
                <tr class="border-b" id="appt-row-${appt.id}">
                    <td class="py-3 px-4">${appt.patient_name}</td>
                    <td class="py-3 px-4">${appt.datetime}</td>
                    <td class="py-3 px-4">${appt.reason}</td>
                    <td class="py-3 px-4 font-medium status-text">${appt.status}</td>
                    <td class="py-3 px-4 action-buttons">
                        ${appt.status === 'Pending' ? `
                            <button class="approve-btn bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600" data-id="${appt.id}">Approve</button>
                            <button class="reject-btn bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 ml-2" data-id="${appt.id}">Reject</button>
                        ` : `
                            <span class="text-gray-500">Handled</span>
                        `}
                    </td>
                </tr>
            `).join('');

        } catch (error) {
            showNotification(error.message);
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load appointments.</td></tr>';
        }
    };

    // --- DOCTOR: Fetch all recommendations/notes for the notes dashboard ---
    const fetchDoctorRecommendations = async () => {
        if (!userState.token) return;
        const tableBody = document.getElementById('recommendations-table-body');
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading all notes...</td></tr>';

        try {
            const response = await fetch(`${API_BASE_URL}/doctor/recommendations`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch notes');

            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No notes found. You can add notes from the "View Patient Predictions" page.</td></tr>';
                return;
            }

            tableBody.innerHTML = data.map(note => `
                <tr class="border-b">
                    <td class="py-3 px-4 font-medium">${note.patient_name}</td>
                    <td class="py-3 px-4">${note.timestamp}</td>
                    <td class="py-3 px-4 font-medium ${note.result === 'Yes' ? 'text-red-600' : 'text-green-600'}">${note.result}</td>
                    <td classs="py-3 px-4">${note.note}</td>
                    <td class="py-3 px-4">
                        <a href="#patient-history-viewer" 
                           class="edit-note-btn bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600" 
                           data-patient-id="${note.patient_id}"
                           data-patient-name="${note.patient_name}">
                           View/Edit
                        </a>
                    </td>
                </tr>
            `).join('');

        } catch (error) {
            showNotification(error.message);
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load notes.</td></tr>';
        }
    };

    // --- DOCTOR: Fetch all patients for the patient list view ---
    const fetchPatientList = async () => {
        if (!userState.token) return;
        const tableBody = document.getElementById('patient-list-table-body');
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading patients...</td></tr>';

        try {
            const response = await fetch(`${API_BASE_URL}/doctor/patients`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch patients');

            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No patients found.</td></tr>';
                return;
            }

            tableBody.innerHTML = data.map(patient => `
                <tr class="border-b">
                    <td class="py-3 px-4 font-medium">${patient.full_name}</td>
                    <td class="py-3 px-4">${patient.age || 'N/A'}</td>
                    <td class="py-3 px-4">${patient.gender || 'N/A'}</td>
                    <td class="py-3 px-4">${patient.phone || 'N/A'}</td>
                    <td class="py-3 px-4">
                        <a href="#patient-history-viewer" 
                           class="view-history-btn bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600" 
                           data-patient-id="${patient.id}"
                           data-patient-name="${patient.full_name}">View History</a>
                    </td>
                </tr>
            `).join('');

        } catch (error) {
            showNotification(error.message);
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load patients.</td></tr>';
        }
    };

    // --- DOCTOR: Fetch prediction history for a specific patient ---
    const fetchPatientHistoryForDoctor = async () => {
        const patientId = sessionStorage.getItem('selectedPatientId');
        const patientName = sessionStorage.getItem('selectedPatientName');

        const title = document.getElementById('patient-history-title');
        const tableBody = document.getElementById('doctor-patient-history-table-body');
        const detailsContainer = document.getElementById('prediction-details-container');
        
        // Clear old data
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4">Loading history...</td></tr>';
        detailsContainer.classList.add('hidden'); // Hide details section
        if (title) title.textContent = `History for: ${patientName || 'Patient'}`;
        
        if (!patientId) {
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-red-600">No patient selected. Go back to the patient list.</td></tr>';
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/doctor/patient_history/${patientId}`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch history');

            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4">No prediction history found for this patient.</td></tr>';
                return;
            }

            tableBody.innerHTML = data.map(pred => `
                <tr class="border-b">
                    <td class="py-3 px-4">${pred.timestamp}</td>
                    <td class="py-3 px-4 font-medium ${pred.result === 'Yes' ? 'text-red-600' : 'text-green-600'}">${pred.result}</td>
                    <td class="py-3 px-4">${pred.probability}</td>
                    <td class="py-3 px-4">
                        <button class="view-details-btn bg-gray-500 text-white px-3 py-1 rounded hover:bg-gray-600" 
                                data-prediction-id="${pred.id}">View Details</button>
                    </td>
                </tr>
            `).join('');

        } catch (error) {
            showNotification(error.message);
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-red-600">Could not load history.</td></tr>';
        }
    };

    // --- DOCTOR: Fetch details for a single prediction ---
    const fetchPredictionDetailsForDoctor = async (predictionId) => {
        const detailsContainer = document.getElementById('prediction-details-container');
        const detailsContent = document.getElementById('prediction-details-content');
        detailsContainer.classList.remove('hidden');
        detailsContent.innerHTML = '<p>Loading details...</p>';

        try {
            const response = await fetch(`${API_BASE_URL}/doctor/prediction_details/${predictionId}`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch details');

            // Build a readable list of the inputs
            let inputsHtml = `
                <div class="col-span-1 md:col-span-2">
                    <p class="text-lg"><strong>Result:</strong> 
                        <span class="${data.result === 'Yes' ? 'text-red-600' : 'text-green-600'}">${data.result} (${data.probability})</span>
                    </p>
                    <p class="text-sm text-gray-500">${data.timestamp}</p>
                </div>
            `;
            for (const [key, value] of Object.entries(data.inputs)) {
                inputsHtml += `
                    <div>
                        <strong class="text-gray-900">${key.replace(/_/g, ' ')}:</strong>
                        <span class="text-gray-700">${value}</span>
                    </div>
                `;
            }
            detailsContent.innerHTML = inputsHtml;

            // --- Placeholder for next step ---
            // We'll add the "Add/Edit Recommendation" form here
            // --- Add/Edit Recommendation Form ---
            const noteContainer = document.getElementById('recommendation-form-container');
            noteContainer.innerHTML = `
                <h3 class="text-xl font-semibold text-gray-800 mb-3">Add/Edit Doctor's Note</h3>
                <form id="doctor-note-form">
                    <textarea id="doctor-note-textarea" rows="4" class="w-full p-2 border border-gray-300 rounded-md" placeholder="Enter notes for the patient...">${data.doctor_note}</textarea>
                    <input type="hidden" id="note-prediction-id" value="${data.id}">
                    <button type="submit" class="mt-2 bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600">Save Note</button>
                </form>
            `;

            // Add the event listener right after creating the form
            const noteForm = document.getElementById('doctor-note-form');
            if (noteForm) {
                noteForm.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const predictionId = document.getElementById('note-prediction-id').value;
                    const note = document.getElementById('doctor-note-textarea').value;
                    const btn = noteForm.querySelector('button[type="submit"]');
                    btn.disabled = true;
                    btn.textContent = 'Saving...';

                    try {
                        const response = await fetch(`${API_BASE_URL}/doctor/prediction_note/${predictionId}`, {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${userState.token}`
                            },
                            body: JSON.stringify({ note: note })
                        });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.error || 'Failed to save note');
                        
                        showNotification('Note saved successfully!', 'success'); // <== FIXED

                    } catch (error) {
                        showNotification(error.message, 'error'); // <== FIXED
                    } finally {
                        btn.disabled = false;
                        btn.textContent = 'Save Note';
                    }
                });
            }


        } catch (error) {
            showNotification(error.message);
            detailsContent.innerHTML = `<p class="text-red-600">Could not load details.</p>`;
        }
    };

    // --- DOCTOR: Update appointment status ---
    // --- DOCTOR: Update appointment status ---
    const updateAppointmentStatus = async (appointmentId, newStatus) => {
        try {
            const response = await fetch(`${API_BASE_URL}/appointments/${appointmentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${userState.token}`
                },
                body: JSON.stringify({ status: newStatus })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Failed to update status');

            showNotification(result.message, 'success'); // <== FIXED

            // Update the UI in the table
            const row = document.getElementById(`appt-row-${appointmentId}`);
            if (row) {
                row.querySelector('.status-text').textContent = newStatus;
                row.querySelector('.action-buttons').innerHTML = `<span class="text-gray-500">Handled</span>`;
            }

        } catch (error) {
            showNotification(error.message, 'error'); // <== FIXED
        }
    };

    // --- ROUTING & UI ---
    // --- ROUTING & UI ---
    const showPage = (hash) => {
        const targetId = hash ? hash.substring(1) : 'home';
        const isLoggedIn = !!userState.token;

        // --- NEW LOGIC: Block pages if logged in ---
        // If user is LOGGED IN, block access to public-only pages
        const publicOnlyPages = ['login', 'register'];
        if (isLoggedIn && publicOnlyPages.includes(targetId)) {
            LOG('[Auth] Redirecting to dashboard - already logged in');
            // Redirect to their correct dashboard
            window.location.hash = userState.role === 'doctor' ? '#doctor-dashboard' : '#patient-dashboard';
            return; // Stop the function here
        }
        // --- END NEW LOGIC ---

        
        // --- EXISTING LOGIC: Block pages if logged out ---
        const protectedPages = [
            'patient-dashboard', 'doctor-dashboard', 'new-prediction', 
            'result', 'prediction-history', 'recommendations', 'appointments', 
            'view-predictions', 'patient-history-viewer', 'manage-recommendations', 
            'manage-appointments',
            // --- ADD THESE ---
            'admin-dashboard', 'admin-manage-users', 
            'admin-all-predictions', 'admin-all-appointments',
            'admin-view-patients', 'admin-view-doctors' // NEW
        ];        if (!isLoggedIn && protectedPages.includes(targetId)) {
            LOG('[Auth] Redirecting to login - no token');
            window.location.hash = '#login'; 
            return;
              
     
        }

        // --- EXISTING LOGIC: Handle result page ---
        const expires = parseInt(sessionStorage.getItem('navigatingToResultExpires') || '0');
        if (expires && Date.now() > expires) {
            LOG('[Navigation] Clearing expired navigatingToResult flag');
            navigatingToResult = false;
            sessionStorage.removeItem('navigatingToResult');
            sessionStorage.removeItem('navigatingToResultExpires');
        }

        if (targetId === 'result' && !resultContent.innerHTML.trim() && !navigatingToResult) {
            LOG('[Result] Redirecting to dashboard - no content and not navigating from prediction');
            window.location.hash = '#patient-dashboard';
            showNotification('Please make a prediction first', 'error');
            return;
        }

        if (targetId !== 'result' && navigatingToResult) {
            LOG('[Navigation] Clearing navigatingToResult flag');
            navigatingToResult = false;
            sessionStorage.removeItem('navigatingToResult');
            sessionStorage.removeItem('navigatingToResultExpires');
        }
        // --- END EXISTING LOGIC ---


        // Fetch data for the page (This was all here, just grouped up)
        if (targetId === 'prediction-history') {
            fetchPredictionHistory();
        }
        if (targetId === 'recommendations') {
            fetchRecommendations();
        }
        if (targetId === 'appointments') {
            fetchDoctors();
            fetchAppointments();
        }
        if (targetId === 'manage-appointments') {
            fetchDoctorAppointments();
        }
        if (targetId === 'view-predictions') {
            fetchPatientList();
        }
        if (targetId === 'patient-history-viewer') {
            fetchPatientHistoryForDoctor();
        }
        if (targetId === 'manage-recommendations') {
            fetchDoctorRecommendations();
        }
        if (targetId === 'admin-manage-users') {
            fetchAdminUsers();
        }
        if (targetId === 'admin-all-predictions') {
            fetchAdminAllPredictions();
        }
        if (targetId === 'admin-all-appointments') {
            fetchAdminAllAppointments();
        }
        if (targetId === 'admin-view-patients') {
            fetchAdminPatients(); // NEW
        }
        if (targetId === 'admin-view-doctors') {
            fetchAdminDoctors(); // NEW
        }

        // Show the correct page
        pages.forEach(page => page.classList.toggle('active-page', page.id === targetId));
        window.scrollTo(0, 0);
    };

    const updateUIForLoginState = () => {
    const isLoggedIn = !!userState.token;

    // Hide all navs first - using style.display to override Tailwind
    if(publicNav) publicNav.style.display = 'none';
    if(patientNav) patientNav.style.display = 'none';
    if(doctorNav) doctorNav.style.display = 'none';
    if(adminNav) adminNav.style.display = 'none';
    if(userNavLinksContainer) userNavLinksContainer.style.display = 'none'; // logout button

    if (isLoggedIn) {
        // Show logout button
        // The logout button is a simple div, so 'block' is fine.
        if(userNavLinksContainer) userNavLinksContainer.style.display = 'block'; 
        
        // Show the correct nav based on role
        // The nav containers are 'md:block' in the HTML, so they should be 'display: block'
        if (userState.role === 'patient') {
            if(patientNav) patientNav.style.display = 'block';
        } else if (userState.role === 'doctor') {
            if(doctorNav) doctorNav.style.display = 'block';
        } else if (userState.role === 'admin') {
            if(adminNav) adminNav.style.display = 'block';
        } else {
            // Fallback for unknown role (shouldn't happen, but good to have)
            if(publicNav) publicNav.style.display = 'block';
        }
    } else {
        // Logged Out
        if(publicNav) publicNav.style.display = 'block'; // Show public links
    }
};

    // --- SESSION MANAGEMENT ---
    const saveSession = (token, role) => {
        userState = { token, role };
        sessionStorage.setItem('session', JSON.stringify(userState));
        updateUIForLoginState();
    };

    const clearSession = () => {
        userState = { token: null, role: null };
        sessionStorage.removeItem('session');
        // Also clear prediction-related session storage on logout
        sessionStorage.clear();
        updateUIForLoginState();
    };

    const loadSession = () => {
        const session = sessionStorage.getItem('session');
        if (session) {
            userState = JSON.parse(session);
        }
        updateUIForLoginState();
    };

    // --- EVENT LISTENERS ---
    window.addEventListener('hashchange', () => showPage(window.location.hash));
    allNavLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            if (link.getAttribute('href').startsWith('#')) {
                e.preventDefault();
                window.location.hash = link.getAttribute('href');
            }
        });
    });

    logoutButton.addEventListener('click', () => {
        clearSession();
        window.location.hash = '#home';
    });

    // -------------------- PATIENT: BOOK APPOINTMENT --------------------
    const appointmentForm = document.getElementById('appointment-form');

    if (appointmentForm) {
        appointmentForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const btn = appointmentForm.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.textContent = 'Booking...';

            try {
                const formData = new FormData(appointmentForm);
                const data = Object.fromEntries(formData.entries());

                // ✅ Ensure correct payload for Flask backend
                const payload = {
                    doctor_id: parseInt(data.doctor_id, 10),
                    datetime: data.appointment_datetime, // Flask expects 'datetime'
                    reason: data.reason
                };

                // ✅ Validate date/time before submission
                const selectedDateTime = new Date(payload.datetime);
                if (isNaN(selectedDateTime.getTime())) throw new Error("Invalid date/time selected.");
                if (selectedDateTime <= new Date()) throw new Error("Appointment date and time must be in the future.");

                // ✅ Send POST request to Flask backend
                const response = await fetch(`${API_BASE_URL}/appointments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${userState.token}`
                    },
                    body: JSON.stringify(payload)
                });

                // ✅ Parse JSON safely
                let result = {};
                try {
                    result = await response.json();
                } catch {
                    console.warn('Response not valid JSON');
                }

                // ✅ Handle HTTP errors cleanly
                if (!response.ok) {
                    throw new Error(result.error || result.message || 'Booking failed');
                }

                // 🎉 SUCCESS CASE
                showNotification(result.message || 'Appointment booked successfully!', 'success');
                appointmentForm.reset();
                fetchAppointments(); // Refresh appointments list

            } catch (error) {
                // ❌ ERROR CASE
                showNotification(error.message || 'Something went wrong', 'error');
            } finally {
                // ✅ Re-enable button regardless of outcome
                btn.disabled = false;
                btn.textContent = 'Book Appointment';
            }
        });
    }


    // --- FORM SUBMISSIONS ---
    const registerRole = document.getElementById('register-role');
    const patientFields = document.getElementById('patient-fields');
    const doctorFields = document.getElementById('doctor-fields');

    if (registerRole) {
        registerRole.addEventListener('change', (e) => {
            if (e.target.value === 'doctor') {
                if(patientFields) patientFields.classList.add('hidden');
                if(doctorFields) doctorFields.classList.remove('hidden');
            } else {
                if(patientFields) patientFields.classList.remove('hidden');
                if(doctorFields) doctorFields.classList.add('hidden');
            }
        });
    }
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = registerForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        try {
            const formData = new FormData(registerForm);
            const data = Object.fromEntries(formData.entries());
            const response = await fetch(`${API_BASE_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Registration failed');
            alert('Registration successful! Please log in.');
            registerForm.reset();
            window.location.hash = '#login';
        } catch (error) {
            showNotification(error.message);
        } finally {
            btn.disabled = false;
        }
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = loginForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        try {
            const formData = new FormData(loginForm);
            const data = Object.fromEntries(formData.entries());
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Login failed');
            saveSession(result.access_token, result.userRole);
            loginForm.reset();
            // --- FIX: Added admin role redirect ---
            if (result.userRole === 'admin') {
                window.location.hash = '#admin-dashboard';
            } else if (result.userRole === 'doctor') {
                window.location.hash = '#doctor-dashboard';
            } else {
                window.location.hash = '#patient-dashboard';
            }
            // --- END FIX ---
        } catch (error) {
            showNotification(error.message);
        } finally {
            btn.disabled = false;
        }
    });

    predictionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const requestId = ++latestPredictionId;

        predictionLoader.classList.remove('hidden');
        predictionButton.disabled = true;
        predictionButton.textContent = 'Analyzing...';

        try {
            const formData = {
                "General_Health": document.getElementById('General_Health').value,
                "Checkup": document.getElementById('Checkup').value,
                "Exercise": document.querySelector('input[name="Exercise"]:checked').value,
                "Smoking_History": document.querySelector('input[name="Smoking_History"]:checked').value,
                "Alcohol_Consumption": parseInt(document.getElementById('Alcohol_Consumption').value, 10),
                "Fruit_Consumption": parseInt(document.getElementById('Fruit_Consumption').value, 10),
                "Green_Vegetables_Consumption": parseInt(document.getElementById('Green_Vegetables_Consumption').value, 10),
                "FriedPotato_Consumption": parseInt(document.getElementById('FriedPotato_Consumption').value, 10),
                "BMI": parseFloat(document.getElementById('BMI').value),
                "Sex": document.getElementById('Sex').value,
                "Age_Category": document.getElementById('Age_Category').value,
                "Diabetes": document.querySelector('input[name="Diabetes"]:checked').value,
                "Depression": document.querySelector('input[name="Depression"]:checked').value,
                "Arthritis": document.querySelector('input[name="Arthritis"]:checked').value,
                "Skin_Cancer": document.querySelector('input[name="Skin_Cancer"]:checked').value,
                "Other_Cancer": document.querySelector('input[name="Other_Cancer"]:checked').value
            };

            const response = await fetch(`${API_BASE_URL}/predict`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${userState.token}`
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.msg || data.error || 'Prediction failed');

            if (requestId === latestPredictionId) {
                LOG('[Prediction Success] Setting result content', {
                    requestId,
                    prediction: data.prediction,
                    probability: data.probability
                });

                resultError.classList.add('hidden');

                resultContent.innerHTML = `
                    <p class="text-lg text-gray-600">Based on the information provided, our model predicts:</p>
                    <p class="text-5xl font-bold my-4 ${data.prediction === 'Yes' ? 'text-red-600' : 'text-green-600'}">
                        ${data.prediction}
                    </p>
                    <p class="text-gray-500">(Probability: ${data.probability})</p>
                `;

                recommendationsList.innerHTML = data.recommendations.map(rec => `<li>${rec}</li>`).join('');

                predictionForm.reset();

                LOG('[Navigation] Setting navigatingToResult flag and saving result');
                navigatingToResult = true;
                sessionStorage.setItem('navigatingToResult', 'true');
                sessionStorage.setItem('resultContent', resultContent.innerHTML);
                sessionStorage.setItem('recommendations', recommendationsList.innerHTML);

                // Auto-clear after 5s using sessionStorage timestamp instead of setTimeout
                // (setTimeout would be lost on reload)
                sessionStorage.setItem('navigatingToResultExpires', Date.now() + 5000);

                // Use setTimeout to ensure DOM updates are flushed before navigation
                setTimeout(() => {
                    LOG('[Navigation] Redirecting to result page', {
                        hasContent: !!resultContent.innerHTML.trim(),
                        navigatingToResult
                    });
                    window.location.hash = '#result';
                }, 50);
            }
        } catch (error) {
            if (requestId === latestPredictionId) {
                LOG('[Prediction Error]', error);
                resultContent.innerHTML = '';
                resultError.classList.remove('hidden');
                showNotification(error.message);
            }
        } finally {
            if (requestId === latestPredictionId) {
                LOG('[Prediction Complete]', {
                    requestId,
                    navigatingToResult,
                    hasContent: !!resultContent.innerHTML.trim()
                });
                predictionLoader.classList.add('hidden');
                predictionButton.disabled = false;
                predictionButton.textContent = 'Get Prediction';
            }
        }
    });

            // Handle Appointment Form Submission
        appointmentForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = appointmentForm.querySelector('button[type="submit"]');
                btn.disabled = true;
                btn.textContent = 'Requesting...';

                try {
                    const formData = new FormData(appointmentForm);
                    const data = {
                        doctor_id: formData.get('doctor_id'),
                        datetime: formData.get('datetime'),
                        reason: formData.get('reason')
                    };

                    // Basic validation
                    if (!data.doctor_id) throw new Error("Please select a doctor.");
                    const selectedDateTime = new Date(data.datetime);
                    if (isNaN(selectedDateTime.getTime())) throw new Error("Invalid date/time selected.");
                    if (selectedDateTime <= new Date()) {
                       throw new Error("Appointment date and time must be in the future.");
                    }

                    const response = await fetch(`${API_BASE_URL}/appointments`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${userState.token}`
                        },
                        body: JSON.stringify(data)
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || result.message || 'Failed to book appointment');

                    showNotification('Appointment requested successfully!', 'success');
                    appointmentForm.reset(); // Clear the form
                    fetchAppointments(); // Refresh the list of appointments

                } catch (error) {
                    showNotification(error.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Request Appointment';
                }
    });

    // --- DOCTOR: Event listener for Approve/Reject buttons ---
    const doctorTableBody = document.getElementById('doctor-appointments-table-body');
    if (doctorTableBody) {
        doctorTableBody.addEventListener('click', (e) => {
            const appointmentId = e.target.dataset.id;
            if (!appointmentId) return;

            if (e.target.classList.contains('approve-btn')) {
                updateAppointmentStatus(appointmentId, 'Approved');
            } else if (e.target.classList.contains('reject-btn')) {
                updateAppointmentStatus(appointmentId, 'Rejected');
            }
        });
    }

    // --- DOCTOR: Event listener for "View History" buttons on patient list ---
    const patientListTableBody = document.getElementById('patient-list-table-body');
    if (patientListTableBody) {
        patientListTableBody.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-history-btn')) {
                const patientId = e.target.dataset.patientId;
                const patientName = e.target.dataset.patientName;
                
                // Store the selected patient's info for the next page to use
                sessionStorage.setItem('selectedPatientId', patientId);
                sessionStorage.setItem('selectedPatientName', patientName);
                
                // Manually trigger the navigation
                window.location.hash = '#patient-history-viewer';
            }
        });
    }


    // --- DOCTOR: Event listener for "View Details" on patient history page ---
    const patientHistoryTableBody = document.getElementById('doctor-patient-history-table-body');
    if (patientHistoryTableBody) {
        patientHistoryTableBody.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-details-btn')) {
                const predictionId = e.target.dataset.predictionId;
                fetchPredictionDetailsForDoctor(predictionId);
            }
        });
    }


    // --- DOCTOR: Event listener for "View/Edit" button on recommendations page ---
    const recommendationsTableBody = document.getElementById('recommendations-table-body');
    if (recommendationsTableBody) {
        recommendationsTableBody.addEventListener('click', (e) => {
            if (e.target.classList.contains('edit-note-btn')) {
                const patientId = e.target.dataset.patientId;
                const patientName = e.target.dataset.patientName;
                
                // Store the selected patient's info for the history page to use
                sessionStorage.setItem('selectedPatientId', patientId);
                sessionStorage.setItem('selectedPatientName', patientName);
                
                // Manually trigger the navigation
                window.location.hash = '#patient-history-viewer';
            }
        });
    }


    //adim api calls
    // ... before the final });

// --- ================== ---
// --- ADMIN API CALLS ---
// --- ================== ---

const fetchAdminUsers = async () => {
    if (!userState.token) return;
    const tableBody = document.getElementById('admin-users-table-body');
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading users...</td></tr>';

    try {
        const response = await fetch(`${API_BASE_URL}/admin/users`, {
            headers: { 'Authorization': `Bearer ${userState.token}` }
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to fetch users');

        if (data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No users found.</td></tr>';
            return;
        }

        tableBody.innerHTML = data.map(user => `
            <tr class="border-b">
                <td class="py-3 px-4 font-medium">${user.full_name}</td>
                <td class="py-3 px-4">${user.email}</td>
                <td class="py-3 px-4">${user.role}</td>
                <td class="py-3 px-4 text-sm">
                    ${user.details.age ? `Age: ${user.details.age}` : ''}
                    ${user.details.specialization ? `${user.details.specialization}` : ''}
                </td>
                <td class="py-3 px-4">
                    <button class="edit-user-btn bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600" 
                                data-id="${user.id}">Edit Info</button>
                    <button class="delete-user-btn bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 ml-2" 
                                data-id="${user.id}" 
                                data-name="${user.full_name}">Delete</button>
                </td>
            </tr>
        `).join('');

    } catch (error) {
        showNotification(error.message);
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load users.</td></tr>';
    }
};

// --- NEW: fetchAdminPatients ---
    const fetchAdminPatients = async () => {
        if (!userState.token) return;
        const tableBody = document.getElementById('admin-patients-table-body');
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading patients...</td></tr>';

        try {
            const response = await fetch(`${API_BASE_URL}/admin/patients`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch patients');

            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No patients found.</td></tr>';
                return;
            }

            tableBody.innerHTML = data.map(p => `
                <tr class="border-b">
                    <td class="py-3 px-4 font-medium">${p.full_name}</td>
                    <td class="py-3 px-4">${p.email}</td>
                    <td class="py-3 px-4">${p.age || 'N/A'}</td>
                    <td class="py-3 px-4">${p.gender || 'N/A'}</td>
                    <td class="py-3 px-4">${p.phone || 'N/A'}</td>
                </tr>
            `).join('');
        } catch (error) {
            showNotification(error.message);
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load patients.</td></tr>';
        }
    };
    
    // --- NEW: fetchAdminDoctors ---
    const fetchAdminDoctors = async () => {
        if (!userState.token) return;
        const tableBody = document.getElementById('admin-doctors-table-body');
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading doctors...</td></tr>';

        try {
            const response = await fetch(`${API_BASE_URL}/admin/doctors`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch doctors');

            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No doctors found.</td></tr>';
                return;
            }

            tableBody.innerHTML = data.map(d => `
                <tr class="border-b">
                    <td class="py-3 px-4 font-medium">${d.full_name}</td>
                    <td class="py-3 px-4">${d.email}</td>
                    <td class="py-3 px-4">${d.specialization || 'N/A'}</td>
                    <td class="py-3 px-4">${d.experience_years || 'N/A'}</td>
                    <td class="py-3 px-4">${d.clinic_address || 'N/A'}</td>
                </tr>
            `).join('');
        } catch (error) {
            showNotification(error.message);
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load doctors.</td></tr>';
        }
    };

const fetchAdminAllPredictions = async () => {
    if (!userState.token) return;
    const tableBody = document.getElementById('admin-predictions-table-body');
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading predictions...</td></tr>';

    try {
        const response = await fetch(`${API_BASE_URL}/admin/predictions`, {
            headers: { 'Authorization': `Bearer ${userState.token}` }
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to fetch predictions');

        if (data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No predictions found.</td></tr>';
            return;
        }

        tableBody.innerHTML = data.map(pred => `
            <tr class="border-b">
                <td class="py-3 px-4 font-medium">${pred.patient_name}</td>
                <td class="py-3 px-4">${pred.timestamp}</td>
                <td class="py-3 px-4 font-semibold ${pred.result === 'Yes' ? 'text-red-600' : 'text-green-600'}">${pred.result}</td>
                <td class="py-3 px-4">${pred.probability}</td>
                <td class="py-3 px-4">${pred.doctor_note || 'N/A'}</td>
            </tr>
        `).join('');

    } catch (error){ 
        showNotification(error.message); 
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load predictions.</td></tr>'; 
    } 
};

const fetchAdminAllAppointments = async () => {
    if (!userState.token) return;
    const tableBody = document.getElementById('admin-appointments-table-body');
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Loading appointments...</td></tr>';

    try {
        const response = await fetch(`${API_BASE_URL}/admin/appointments`, {
            headers: { 'Authorization': `Bearer ${userState.token}` }
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to fetch appointments');

        if (data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No appointments found.</td></tr>';
            return;
        }

        tableBody.innerHTML = data.map(appt => `
            <tr class="border-b">
                <td class="py-3 px-4">${appt.patient_name}</td>
                <td class="py-3 px-4">${appt.doctor_name}</td>
                <td class="py-3 px-4">${appt.datetime}</td>
                <td class="py-3 px-4">${appt.reason || 'N/A'}</td>
                <td class="py-3 px-4 font-medium ${appt.status === 'Pending' ? 'text-yellow-600' : (appt.status === 'Approved' ? 'text-green-600' : 'text-red-600')}">${appt.status}</td>
            </tr>
        `).join('');

    } catch (error) {
        showNotification(error.message);
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Could not load appointments.</td></tr>';
    }
};

// --- ADMIN EVENT LISTENERS ---

// --- MODIFIED: Modal helpers for new Edit User Modal ---
    const editUserModal = document.getElementById('admin-edit-user-modal');
    const editUserForm = document.getElementById('admin-edit-user-form');
    const cancelEditUserBtn = document.getElementById('cancel-edit-user');
    
    const editPatientFields = document.getElementById('edit-patient-fields');
    const editDoctorFields = document.getElementById('edit-doctor-fields');
    const editAdminFields = document.getElementById('edit-admin-fields');

    const showEditUserModal = async (userId) => {
        // Reset form
        editUserForm.reset();
        editPatientFields.classList.add('hidden');
        editDoctorFields.classList.add('hidden');
        editAdminFields.classList.add('hidden');
        
        try {
            // Fetch the user's full details
            const response = await fetch(`${API_BASE_URL}/admin/user/${userId}`, {
                headers: { 'Authorization': `Bearer ${userState.token}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch user details');
            
            // Populate common fields
            document.getElementById('edit-user-id').value = data.id;
            document.getElementById('edit-user-role').value = data.role;
            document.getElementById('edit-user-fullname').value = data.full_name;
            document.getElementById('edit-user-email').value = data.email;
            
            // Populate role-specific fields
            if (data.role === 'patient') {
                document.getElementById('edit-patient-age').value = data.age || '';
                document.getElementById('edit-patient-gender').value = data.gender || 'Male';
                document.getElementById('edit-patient-phone').value = data.phone || '';
                editPatientFields.classList.remove('hidden');
            } else if (data.role === 'doctor') {
                document.getElementById('edit-doctor-specialization').value = data.specialization || '';
                document.getElementById('edit-doctor-experience').value = data.experience_years || '';
                document.getElementById('edit-doctor-clinic').value = data.clinic_address || '';
                editDoctorFields.classList.remove('hidden');
            } else if (data.role === 'admin') {
                editAdminFields.classList.remove('hidden');
            }
            
            editUserModal.classList.remove('hidden');
            
        } catch (error) {
            showNotification(error.message);
        }
    };
    
    const hideEditUserModal = () => {
        editUserModal.classList.add('hidden');
    };

    if(cancelEditUserBtn) {
        cancelEditUserBtn.addEventListener('click', hideEditUserModal);
    }

    // --- MODIFIED: Form submit listener for new Edit User Modal ---
    if(editUserForm) {
        editUserForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const userId = document.getElementById('edit-user-id').value;
            const role = document.getElementById('edit-user-role').value;
            const btn = editUserForm.querySelector('button[type="submit"]');
            
            // Collect all data
            let dataToUpdate = {
                full_name: document.getElementById('edit-user-fullname').value,
                email: document.getElementById('edit-user-email').value,
            };

            const password = document.getElementById('edit-user-password').value;
            if (password) {
                dataToUpdate.password = password;
            }
            
            if (role === 'patient') {
                dataToUpdate.age = document.getElementById('edit-patient-age').value;
                dataToUpdate.gender = document.getElementById('edit-patient-gender').value;
                dataToUpdate.phone = document.getElementById('edit-patient-phone').value;
            } else if (role === 'doctor') {
                dataToUpdate.specialization = document.getElementById('edit-doctor-specialization').value;
                dataToUpdate.experience_years = document.getElementById('edit-doctor-experience').value;
                dataToUpdate.clinic_address = document.getElementById('edit-doctor-clinic').value;
            }
            
            btn.disabled = true;
            btn.textContent = 'Saving...';

            try {
                const response = await fetch(`${API_BASE_URL}/admin/user/${userId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${userState.token}`
                    },
                    body: JSON.stringify(dataToUpdate)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Failed to update user');
                
                showNotification('User updated!', 'success');
                hideEditUserModal();
                fetchAdminUsers(); // Refresh the user list
                
            } catch (error) {
                showNotification(error.message);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Save Changes';
            }
        });
    }

    // --- MODIFIED: Event listener for "Manage Users" table ---
    const userTableBody = document.getElementById('admin-users-table-body');
    if(userTableBody) {
        userTableBody.addEventListener('click', async (e) => {
            const target = e.target;
            
            // Handle Edit Button
            if (target.classList.contains('edit-user-btn')) {
                const id = target.dataset.id;
                showEditUserModal(id); // NEW function call
            }
            
            // Handle Delete Button
            if (target.classList.contains('delete-user-btn')) {
                const id = target.dataset.id;
                const name = target.dataset.name;
                
                if (confirm(`Are you sure you want to delete ${name}? This action is permanent and will delete all their associated data.`)) {
                    try {
                        const response = await fetch(`${API_BASE_URL}/admin/users/${id}`, {
                            method: 'DELETE',
                            headers: { 'Authorization': `Bearer ${userState.token}` }
                        });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.error || 'Failed to delete user');
                        
                        showNotification('User deleted successfully!', 'success');
                        fetchAdminUsers(); // Refresh the list
                    } catch (error) {
                        showNotification(error.message);
                    }
                }
            }
        });
    }

    // --- INITIALIZATION ---
    loadSession();
    showPage(window.location.hash || '#home');



    
});