// Language management
// The selector is in base.html - this script just ensures cookie is set
(function() {
  'use strict';
  
  // Set cookie on page load
  var lang = window.__lang || 'pt';
  document.cookie = "lang=" + lang + ";path=/;max-age=31536000;SameSite=Lax";
  
  // Update selector value if exists
  var selector = document.getElementById('langSelector');
  if (selector) {
    selector.value = lang;
  }
})();
