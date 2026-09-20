/* Lecture / remplissage du formulaire de fiche livre (ajout et modification). */
(function () {
  "use strict";

  function value(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : "";
  }

  function number(id) {
    var raw = value(id).replace(/[^0-9]/g, "");
    return raw ? parseInt(raw, 10) : null;
  }

  window.bookForm = {
    collect: function () {
      return {
        isbn: value("isbn"),
        title: value("f-title"),
        authors: value("f-authors"),
        publisher: value("f-publisher"),
        year: value("f-year"),
        summary: value("f-summary"),
        page_count: number("f-pages"),
        age_min: number("f-agemin"),
        age_max: number("f-agemax"),
        location: value("f-location"),
        cover_url: value("cover-url"),
        tags: window.tagPicker ? window.tagPicker.selected() : []
      };
    },

    /* Champs décrivant le livre lui-même : ils doivent disparaître dès qu'on
       passe à un autre livre, sans quoi la fiche précédente resterait en place
       et serait enregistrée une seconde fois. Le rangement n'en fait pas
       partie : on range en général toute une pile au même endroit. */
    FICHE: ["f-title", "f-authors", "f-publisher", "f-year", "f-summary",
            "f-pages", "f-agemin", "f-agemax", "cover-url"],

    clearFiche: function () {
      this.FICHE.forEach(function (id) {
        var el = document.getElementById(id);
        if (el) { el.value = ""; }
      });
      if (window.tagPicker) { window.tagPicker.clear(); }
      this.showCover("");
    },

    fill: function (info) {
      this.clearFiche();
      var map = {
        "f-title": info.title, "f-authors": info.authors, "f-publisher": info.publisher,
        "f-year": info.year, "f-summary": info.summary,
        "f-pages": info.page_count || "", "cover-url": info.cover_url || "",
        "isbn": info.isbn || ""
      };
      Object.keys(map).forEach(function (id) {
        var el = document.getElementById(id);
        if (el && map[id]) { el.value = map[id]; }
      });
      this.showCover(info.cover_url);
      if (window.tagPicker) { window.tagPicker.suggest(info.categories); }
    },

    showCover: function (url) {
      var img = document.getElementById("cover-img");
      var placeholder = document.getElementById("cover-empty");
      if (!img) { return; }
      if (url) {
        img.src = url;
        img.hidden = false;
        img.onerror = function () { img.hidden = true; if (placeholder) { placeholder.hidden = false; } };
        if (placeholder) { placeholder.hidden = true; }
      } else {
        img.hidden = true;
        if (placeholder) { placeholder.hidden = false; }
      }
    },

    /* `tout` à vrai vide aussi le rangement (bouton « Vider le formulaire ») ;
       après un enregistrement on le conserve pour enchaîner la pile de livres. */
    reset: function (tout) {
      this.clearFiche();
      var el = document.getElementById("isbn");
      if (el) { el.value = ""; }
      if (tout) {
        var lieu = document.getElementById("f-location");
        if (lieu) { lieu.value = ""; }
      }
    }
  };
})();
