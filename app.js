// frontend/app.js

const backendURL = "http://127.0.0.1:5000"; // Flask backend URL

// Login handler
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
      const response = await fetch(`${backendURL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (response.ok) {
        alert("Login successful!");
        window.location.href = "dashboard.html";
      } else {
        document.getElementById("loginError").innerText = data.message;
      }
    } catch (err) {
      document.getElementById("loginError").innerText = "Network error!";
    }
  });
}

// Register handler
const registerForm = document.getElementById("registerForm");
if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("name").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
      const response = await fetch(`${backendURL}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await response.json();
      if (response.ok) {
        alert("Registration successful!");
        window.location.href = "login.html";
      } else {
        document.getElementById("registerError").innerText = data.message;
      }
    } catch (err) {
      document.getElementById("registerError").innerText = "Network error!";
    }
  });
}
