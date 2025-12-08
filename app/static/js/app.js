function copyLink() {
  const input = document.getElementById('share-link');
  if (!input) return;
  input.select();
  input.setSelectionRange(0, 99999);
  navigator.clipboard.writeText(input.value).then(() => {
    const badge = document.getElementById('copy-feedback');
    if (badge) {
      badge.textContent = 'Ссылка скопирована';
      badge.style.opacity = '1';
      setTimeout(() => (badge.style.opacity = '0'), 1500);
    }
  });
}

function downloadQR() {
  const img = document.getElementById('qr-image');
  if (!img) return;
  const link = document.createElement('a');
  link.href = img.src;
  link.download = 'payment-qr.png';
  link.click();
}

window.copyLink = copyLink;
window.downloadQR = downloadQR;
