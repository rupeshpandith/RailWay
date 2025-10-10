document.addEventListener('DOMContentLoaded', () => {
  const dateInput = document.querySelector('input[type="date"][name="date"]');
  if (!dateInput) {
    return;
  }

  const today = new Date();
  const formatted = today.toISOString().split('T')[0];
  dateInput.min = formatted;
  if (!dateInput.value) {
    dateInput.value = formatted;
  }
});
