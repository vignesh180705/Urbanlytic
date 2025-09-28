const eyes = document.querySelectorAll('.eye');
const passwords = document.querySelectorAll('.password');
eyes.forEach((eye, index) => {
  eye.addEventListener('click', () => {
    const password = passwords[index];
    if (password.type === "password") {
      password.type = "text";
      eye.classList.remove('bi-eye-slash');
      eye.classList.add('bi-eye');
    } else {
      password.type = "password";
      eye.classList.remove('bi-eye');
      eye.classList.add('bi-eye-slash');
    }
  });
});