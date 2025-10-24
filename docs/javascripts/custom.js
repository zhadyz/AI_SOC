// Custom JavaScript for AI-SOC Documentation

// Make logo link to onyxlab.ai instead of home page
document.addEventListener('DOMContentLoaded', function() {
  const logoLink = document.querySelector('.md-header__button.md-logo');
  if (logoLink) {
    logoLink.setAttribute('href', 'https://onyxlab.ai');
    logoLink.setAttribute('target', '_blank');
    logoLink.setAttribute('rel', 'noopener noreferrer');
  }
});
