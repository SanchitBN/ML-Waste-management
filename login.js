// login.js

async function loginUser(event) {
  event.preventDefault();

  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value.trim();
  const errorDiv = document.getElementById("loginError");

  try {
    const response = await fetch("http://127.0.0.1:5000/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (response.ok) {
      // ✅ Save email in localStorage
      localStorage.setItem("userEmail", data.email);

      // ✅ Redirect to dashboard/home
      window.location.href = `home.html?email=${encodeURIComponent(email)}`;
    } else {
      // Show error message
      errorDiv.textContent = data.message || "Login failed. Please try again.";
    }
  } catch (err) {
    errorDiv.textContent = "Network error. Please check your connection.";
    console.error("Login error:", err);
  }
}
