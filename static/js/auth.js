function signInWithEmail(event) {
  event.preventDefault();
  const email = document.getElementById("emailInput").value;
  const password = document.getElementById("passwordInput").value;

  if (email && password) {
    window.location.href = "/dashboard"; // redirect to Flask route
  } else {
    document.getElementById("loginError").textContent = "Invalid login!";
  }
}

function signOutUser() {
  window.location.href = "/login";
}
