/* Liste des emprunts : bouton « rendu ». */
(function () {
  "use strict";

  document.querySelectorAll(".btn-return").forEach(function (btn) {
    btn.addEventListener("click", function () {
      btn.disabled = true;
      window.api("/api/emprunts/" + btn.dataset.loanId + "/retour", { method: "POST", body: {} })
        .then(function () {
          window.toast("Livre rendu ✅", "ok");
          var row = btn.closest(".loan");
          row.style.opacity = "0.4";
          setTimeout(function () { location.reload(); }, 700);
        }).catch(function (error) {
          btn.disabled = false;
          window.toast(error.message, "err");
        });
    });
  });
})();
