/* Page « Ajouter un livre » : scan, recherche en ligne, enregistrement. */
(function () {
  "use strict";

  var isbnInput = document.getElementById("isbn");
  var scanner = document.getElementById("scanner");
  var video = document.getElementById("preview");
  var hint = document.getElementById("scan-hint");
  var btnScan = document.getElementById("btn-scan");
  var btnStop = document.getElementById("btn-stop");
  var btnLookup = document.getElementById("btn-lookup");
  var form = document.getElementById("book-form");
  var btnSave = document.getElementById("btn-save");
  var coverUrl = document.getElementById("cover-url");
  var lastScan = 0;

  function stopScanner() {
    window.barcodeScanner.stop();
    scanner.hidden = true;
    btnScan.textContent = "📷 Scanner";
  }

  btnScan.addEventListener("click", function () {
    if (!scanner.hidden) { stopScanner(); return; }
    scanner.hidden = false;
    hint.textContent = "Démarrage de la caméra…";
    btnScan.textContent = "✋ Fermer le scanner";
    window.barcodeScanner.start(video, onBarcode).then(function () {
      hint.textContent = "Approchez le code-barres du cadre…";
    }).catch(function (error) {
      stopScanner();
      window.toast(error.message || "Caméra inaccessible", "err");
    });
  });

  btnStop.addEventListener("click", stopScanner);

  function onBarcode(code) {
    var now = Date.now();
    if (now - lastScan < 2500) { return; }   // évite les lectures en rafale
    lastScan = now;
    window.barcodeScanner.beep();
    window.bookForm.clearFiche();
    isbnInput.value = code;
    hint.textContent = "Code lu : " + code;
    lookup(code);
  }

  function lookup(code) {
    var isbn = (code || isbnInput.value || "").trim();
    if (!isbn) {
      window.toast("Tapez ou scannez un ISBN", "err");
      return;
    }
    btnLookup.disabled = true;
    btnLookup.textContent = "…";
    window.api("/api/lookup?isbn=" + encodeURIComponent(isbn)).then(function (info) {
      if (info.existing_id) {
        window.toast("Ce livre est déjà dans la bibliothèque !", "err");
        setTimeout(function () { location.href = "/livre/" + info.existing_id; }, 1200);
        return;
      }
      window.bookForm.fill(info);
      window.toast("Fiche trouvée sur " + info.source + " 🎉", "ok");
      stopScanner();
      document.getElementById("f-title").scrollIntoView({ behavior: "smooth", block: "center" });
    }).catch(function (error) {
      if (error.data && error.data.existing_id) {
        window.toast("Ce livre est déjà dans la bibliothèque !", "err");
        setTimeout(function () { location.href = "/livre/" + error.data.existing_id; }, 1200);
        return;
      }
      // Sans cela, la fiche du livre précédent resterait affichée et serait
      // enregistrée une deuxième fois sous le code-barres qu'on vient de lire.
      window.bookForm.clearFiche();
      window.toast(error.message + " — remplissez la fiche à la main", "err");
      if (error.data && error.data.isbn) { isbnInput.value = error.data.isbn; }
      document.getElementById("f-title").focus();
    }).then(function () {
      btnLookup.disabled = false;
      btnLookup.textContent = "Chercher";
    });
  }

  btnLookup.addEventListener("click", function () { lookup(); });
  isbnInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") { event.preventDefault(); lookup(); }
  });

  coverUrl.addEventListener("change", function () { window.bookForm.showCover(coverUrl.value.trim()); });

  /* Recherche par titre (quand le code-barres est abîmé ou absent) */
  var btnTitle = document.getElementById("btn-title-search");
  var titleInput = document.getElementById("title-search");
  var titleResults = document.getElementById("title-results");

  function searchByTitle() {
    var query = titleInput.value.trim();
    if (query.length < 3) { window.toast("Tapez au moins 3 lettres", "err"); return; }
    titleResults.innerHTML = "<p class='hint'>Recherche…</p>";
    window.api("/api/recherche-titre?q=" + encodeURIComponent(query)).then(function (data) {
      var results = data.results || [];
      if (!results.length) { titleResults.innerHTML = "<p class='hint'>Aucun résultat.</p>"; return; }
      titleResults.innerHTML = "";
      results.forEach(function (info) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "title-result";
        btn.innerHTML = (info.cover_url ? '<img alt="" src="' + info.cover_url + '">' : "")
          + "<span><b></b><br><i></i></span>";
        btn.querySelector("b").textContent = info.title;
        btn.querySelector("i").textContent = [info.authors, info.year].filter(Boolean).join(" · ");
        btn.addEventListener("click", function () {
          window.bookForm.fill(info);
          titleResults.innerHTML = "";
          window.toast("Fiche pré-remplie ✏️", "ok");
          document.getElementById("f-title").scrollIntoView({ behavior: "smooth", block: "center" });
        });
        titleResults.appendChild(btn);
      });
    }).catch(function (error) { window.toast(error.message, "err"); });
  }

  btnTitle.addEventListener("click", searchByTitle);
  titleInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") { event.preventDefault(); searchByTitle(); }
  });

  /* Enregistrement */
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var payload = window.bookForm.collect();
    if (!payload.title) {
      window.toast("Il manque le titre du livre", "err");
      document.getElementById("f-title").focus();
      return;
    }
    btnSave.disabled = true;
    window.api("/api/livres", { method: "POST", body: payload }).then(function (data) {
      window.toast("« " + payload.title + " » est rangé dans la bibliothèque 🎉", "ok");
      window.bookForm.reset();
      document.getElementById("save-hint").innerHTML =
        'Livre enregistré. <a href="' + data.url + '">Voir sa fiche →</a>';
      isbnInput.focus();
    }).catch(function (error) {
      if (error.data && error.data.existing_id) {
        window.toast(error.message, "err");
        setTimeout(function () { location.href = "/livre/" + error.data.existing_id; }, 1200);
        return;
      }
      window.toast(error.message, "err");
    }).then(function () { btnSave.disabled = false; });
  });

  form.addEventListener("reset", function (event) {
    event.preventDefault();
    window.bookForm.reset(true);
  });

  window.addEventListener("pagehide", function () { window.barcodeScanner.stop(); });
})();
