const API = "/api";


function getToken() {
    return localStorage.getItem("token");
}


function authHeaders() {
    return {
        "Authorization": `Bearer ${getToken()}`
    };
}


/* ---------------- REGISTER ---------------- */

const registerForm = document.getElementById("registerForm");

if (registerForm) {

    const role = document.getElementById("role");

    role.addEventListener("change", () => {

        document.getElementById("doctorFields").style.display =
            role.value === "doctor" ? "block" : "none";

    });

    registerForm.addEventListener("submit", async (event) => {

        event.preventDefault();

        const selectedRole = role.value;

        const body = {
            name: document.getElementById("name").value,
            email: document.getElementById("email").value,
            password: document.getElementById("password").value,
            role: selectedRole
        };

        if (selectedRole === "doctor") {

            body.specialization =
                document.getElementById("specialization").value;

            body.experience =
                Number(document.getElementById("experience").value);

            body.consultation_fee =
                Number(document.getElementById("fee").value);
        }

        const response = await fetch(
            `${API}/auth/register`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            }
        );

        const data = await response.json();

        const message = document.getElementById("message");

        if (!response.ok) {
            message.textContent = data.detail || "Registration failed";
            return;
        }

        message.textContent = "Registration successful!";

        setTimeout(() => {
            window.location.href = "/login";
        }, 700);

    });
}


/* ---------------- LOGIN ---------------- */

const loginForm = document.getElementById("loginForm");

if (loginForm) {

    loginForm.addEventListener("submit", async (event) => {

        event.preventDefault();

        const response = await fetch(
            `${API}/auth/login`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: document.getElementById("email").value,
                    password: document.getElementById("password").value
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            document.getElementById("message").textContent =
                data.detail || "Login failed";
            return;
        }

        localStorage.setItem(
            "token",
            data.access_token
        );

        window.location.href = "/dashboard";
    });
}


/* ---------------- DASHBOARD ---------------- */

if (window.location.pathname === "/dashboard") {

    if (!getToken()) {
        window.location.href = "/login";
    } else {
        loadUser();
        loadDoctors();
        loadAppointments();
    }
}


async function loadUser() {

    const response = await fetch(
        `${API}/auth/me`,
        {
            headers: authHeaders()
        }
    );

    if (!response.ok) {
        logout();
        return;
    }

    const user = await response.json();

    document.getElementById("welcome").textContent =
        `Welcome, ${user.name}`;
}


/* ---------------- DOCTORS ---------------- */

async function loadDoctors() {

    const search =
        document.getElementById("doctorSearch")?.value || "";

    const sort =
        document.getElementById("sortDoctors")?.value ||
        "experience";

    const response = await fetch(
        `${API}/doctors?search=${encodeURIComponent(search)}&sort=${sort}&order=desc`
    );

    const doctors = await response.json();

    const container =
        document.getElementById("doctors");

    if (!container) return;

    container.innerHTML = "";

    doctors.forEach(doctor => {

        const card = document.createElement("div");

        card.className = "card";

        card.innerHTML = `
            <h3>Dr. ${doctor.user_id}</h3>

            <p>
                <strong>${doctor.specialization}</strong>
            </p>

            <p>
                Experience: ${doctor.experience} years
            </p>

            <p>
                Fee: ₹${doctor.consultation_fee}
            </p>

            <button
                class="primary-button"
                onclick="bookAppointment(${doctor.id})"
            >
                Book Appointment
            </button>
        `;

        container.appendChild(card);

    });
}


/* ---------------- BOOK ---------------- */

async function bookAppointment(doctorId) {

    const startTime = prompt(
        "Enter appointment time (YYYY-MM-DDTHH:MM)"
    );

    if (!startTime) return;

    const response = await fetch(
        `${API}/appointments?doctor_id=${doctorId}&start_time=${encodeURIComponent(startTime)}`,
        {
            method: "POST",
            headers: authHeaders()
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Booking failed");
        return;
    }

    alert("Appointment booked successfully!");

    loadAppointments();
}


/* ---------------- APPOINTMENTS ---------------- */

async function loadAppointments() {

    const response = await fetch(
        `${API}/appointments?page=1&limit=20&sort=start_time&order=asc`,
        {
            headers: authHeaders()
        }
    );

    if (!response.ok) return;

    const appointments = await response.json();

    const container =
        document.getElementById("appointments");

    if (!container) return;

    container.innerHTML = "";

    if (appointments.length === 0) {

        container.innerHTML =
            "<p>No appointments found.</p>";

        return;
    }

    appointments.forEach(appointment => {

        const card = document.createElement("div");

        card.className = "appointment";

        card.innerHTML = `
            <div>
                <strong>Doctor #${appointment.doctor_id}</strong>
                <p>
                    ${new Date(
                        appointment.start_time
                    ).toLocaleString()}
                </p>

                <span>
                    ${appointment.status}
                </span>
            </div>

            ${
                appointment.status === "booked"
                ? `
                    <button
                        onclick="cancelAppointment(${appointment.id})"
                    >
                        Cancel
                    </button>

                    <button
                        onclick="rescheduleAppointment(${appointment.id})"
                    >
                        Reschedule
                    </button>
                `
                : ""
            }
        `;

        container.appendChild(card);

    });
}


/* ---------------- CANCEL ---------------- */

async function cancelAppointment(id) {

    if (!confirm("Cancel this appointment?")) return;

    const response = await fetch(
        `${API}/appointments/${id}/cancel`,
        {
            method: "PATCH",
            headers: authHeaders()
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Cancellation failed");
        return;
    }

    alert(`Appointment ${data.status}`);

    loadAppointments();
}


/* ---------------- RESCHEDULE ---------------- */

async function rescheduleAppointment(id) {

    const newTime = prompt(
        "New time (YYYY-MM-DDTHH:MM)"
    );

    if (!newTime) return;

    const response = await fetch(
        `${API}/appointments/${id}/reschedule?new_start_time=${encodeURIComponent(newTime)}`,
        {
            method: "PATCH",
            headers: authHeaders()
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Rescheduling failed");
        return;
    }

    alert("Appointment rescheduled!");

    loadAppointments();
}


/* ---------------- LOGOUT ---------------- */

function logout() {

    localStorage.removeItem("token");

    window.location.href = "/login";
}