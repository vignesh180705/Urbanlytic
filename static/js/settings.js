async function updateProfile() {
  const name = document.getElementById("settingsName").value.trim();
  const email = document.getElementById("settingsEmail").value.trim();
  const phone = document.getElementById("settingsPhone").value.trim();
  const msgBox = document.getElementById("profileMessage");

  msgBox.textContent = "Updating profile...";
  msgBox.className = "message-box";

  try {
    const response = await fetch("/update_profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, phone }),
    });

    const result = await response.json();
    console.log(result);
    if (result.status === "success") {
      msgBox.textContent = "Profile updated successfully!";
      msgBox.classList.add("success");
    } else {
    msgBox.innerHTML = (result.detail).replace(/\n/g, '<br>');
    msgBox.classList.add("error");
    }
  } catch (err) {
    console.error(err);
    msgBox.textContent = "Something went wrong. Try again later.";
    msgBox.classList.add("error");
  }
}

async function changePassword() {
  const currentPassword = document.getElementById("currentPassword").value;
  const newPassword = document.getElementById("newPassword").value;
  const confirmPassword = document.getElementById("confirmPassword").value;
  const msgBox = document.getElementById("passwordMessage");

  msgBox.textContent = "Updating password...";
  msgBox.className = "message-box";

  try {
    const response = await fetch("/change_password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }),
    });

    const result = await response.json();

    if (result.status === "success") {
      msgBox.textContent = "Password changed successfully!";
      msgBox.classList.add("success");

      // Reset password fields
      document.getElementById("currentPassword").value = "";
      document.getElementById("newPassword").value = "";
      document.getElementById("confirmPassword").value = "";
    } else {
      msgBox.innerHTML = (result.detail).replace(/\n/g, '<br>');
      msgBox.classList.add("error");
    }
  } catch (err) {
    console.error(err);
    msgBox.textContent = "Something went wrong. Try again later.";
    msgBox.classList.add("error");
  }
}
