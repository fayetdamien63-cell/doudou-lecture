/* Fiche d'un livre : prêt, retour, modification, suppression. */
(function () {
  "use strict";

  var detail = document.querySelector(".book-detail");
  if (!detail) { return; }
  var bookId = detail.dataset.bookId;

  /* --- Prêt --- */
  var loanForm = document.getElementById("loan-form");
  if (loanForm) {
    window.api("/api/eleves").then(function (data) {
      var list = document.getElementById("students");
      (data.students || []).forEach(function (name) {
        var option = document.createElement("option");
        option.value = name;
        list.appendChild(option);
      });
    }).catch(function () { /* la liste de suggestions n'est pas indispensable */ });

    loanForm.addEventListener("submit", function (event) {
      event.preventDefault();
      var payload = {
        book_id: parseInt(bookId, 10),
        student: document.getElementById("student").value.trim(),
        classroom: document.getElementById("classroom").value.trim(),
        loaned_on: document.getElementById("loaned_on").value,
        due_on: document.getElementById("due_on").value
      };
      if (!payload.student) { window.toast("Il manque le prénom de l'élève", "err"); return; }
      window.api("/api/emprunts", { method: "POST", body: payload }).then(function () {
        window.toast("Bonne lecture " + payload.student + " ! 🎒", "ok");
        setTimeout(function () { location.reload(); }, 700);
      }).catch(function (error) { window.toast(error.message, "err"); });
    });
  }

  /* --- Retour --- */
  var btnReturn = document.getElementById("btn-return");
  if (btnReturn) {
    btnReturn.addEventListener("click", function () {
      window.api("/api/emprunts/" + btnReturn.dataset.loanId + "/retour", { method: "POST", body: {} })
        .then(function () {
          window.toast("Merci, le livre est de retour ✅", "ok");
          setTimeout(function () { location.reload(); }, 700);
        }).catch(function (error) { window.toast(error.message, "err"); });
    });
  }

  /* --- Modification --- */
  var form = document.getElementById("book-form");
  var coverUrl = document.getElementById("cover-url");
  if (coverUrl) {
    coverUrl.addEventListener("change", function () {
      window.bookForm.showCover(coverUrl.value.trim());
    });
  }
  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var payload = window.bookForm.collect();
      if (!payload.title) { window.toast("Il manque le titre du livre", "err"); return; }
      window.api("/api/livres/" + bookId, { method: "PUT", body: payload }).then(function () {
        window.toast("Fiche mise à jour ✏️", "ok");
        setTimeout(function () { location.reload(); }, 600);
      }).catch(function (error) { window.toast(error.message, "err"); });
    });
  }

  /* --- Suppression --- */
  var btnDelete = document.getElementById("btn-delete");
  if (btnDelete) {
    btnDelete.addEventListener("click", function () {
      if (!confirm("Supprimer définitivement ce livre et son historique de prêts ?")) { return; }
      window.api("/api/livres/" + bookId, { method: "DELETE" }).then(function () {
        location.href = "/";
      }).catch(function (error) { window.toast(error.message, "err"); });
    });
  }
})();
