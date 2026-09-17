/* Outils communs : petits messages et appels API. */
(function () {
  "use strict";

  window.toast = function (message, kind) {
    var box = document.getElementById("toasts");
    if (!box) { return; }
    var el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.textContent = message;
    box.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 300);
    }, kind === "err" ? 5000 : 3000);
  };

  window.api = function (url, options) {
    options = options || {};
    var config = {
      method: options.method || "GET",
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    };
    if (options.body !== undefined) {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(options.body);
    }
    return fetch(url, config).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var error = new Error(data.error || "Erreur réseau (" + response.status + ")");
          error.data = data;
          error.status = response.status;
          throw error;
        }
        return data;
      });
    });
  };

  window.debounce = function (fn, delay) {
    var timer;
    return function () {
      var args = arguments, self = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(self, args); }, delay);
    };
  };
})();
