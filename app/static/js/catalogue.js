/* Recherche en direct dans le catalogue (sans recharger la page). */
(function () {
  "use strict";

  var form = document.getElementById("search-form");
  if (!form) { return; }

  var input = document.getElementById("q");
  var tagInput = document.getElementById("tag-input");
  var grid = document.getElementById("grid");
  var empty = document.getElementById("empty");
  var count = document.getElementById("count");
  var clearBtn = document.getElementById("clear-q");
  var chips = document.getElementById("chips");

  function escapeHtml(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function cardHtml(book) {
    var cover = book.cover
      ? '<img src="/covers/' + encodeURIComponent(book.cover) + '" alt="" loading="lazy">'
      : '<span class="cover-fallback" aria-hidden="true">📖</span>';
    var badge = "";
    if (book.loan) {
      badge = '<span class="badge ' + (book.loan.late ? "badge-late" : "badge-out") + '">'
        + (book.loan.late ? "⏰ " : "🎒 ") + escapeHtml(book.loan.student) + "</span>";
    }
    var tags = (book.tags || []).slice(0, 3).map(function (t) {
      return '<span class="mini-chip kind-' + escapeHtml(t.kind) + '">' + escapeHtml(t.name) + "</span>";
    }).join("");
    return '<a class="book-card" href="/livre/' + book.id + '">'
      + '<div class="cover">' + cover + badge + "</div>"
      + "<h2>" + escapeHtml(book.title) + "</h2>"
      + '<p class="authors">' + escapeHtml(book.authors || "—") + "</p>"
      + (tags ? '<p class="card-tags">' + tags + "</p>" : "")
      + "</a>";
  }

  function currentUrl(base) {
    var params = new URLSearchParams(new FormData(form));
    var query = [];
    params.forEach(function (value, key) { if (value) { query.push(key + "=" + encodeURIComponent(value)); } });
    return base + (query.length ? "?" + query.join("&") : "");
  }

  var refresh = window.debounce(function () {
    grid.setAttribute("aria-busy", "true");
    window.api(currentUrl("/api/livres")).then(function (data) {
      var books = data.books || [];
      grid.innerHTML = books.map(cardHtml).join("");
      count.textContent = books.length + " livre" + (books.length > 1 ? "s" : "");
      empty.hidden = books.length > 0;
      grid.removeAttribute("aria-busy");
      history.replaceState(null, "", currentUrl("/"));
    }).catch(function (error) {
      grid.removeAttribute("aria-busy");
      window.toast(error.message, "err");
    });
  }, 250);

  input.addEventListener("input", function () {
    clearBtn.hidden = !input.value;
    refresh();
  });
  clearBtn.hidden = !input.value;
  clearBtn.addEventListener("click", function () {
    input.value = "";
    clearBtn.hidden = true;
    input.focus();
    refresh();
  });

  form.addEventListener("submit", function (event) { event.preventDefault(); refresh(); });
  form.querySelectorAll("select").forEach(function (select) {
    select.addEventListener("change", refresh);
  });

  if (chips) {
    chips.addEventListener("click", function (event) {
      var chip = event.target.closest(".chip");
      if (!chip) { return; }
      var value = chip.dataset.tag;
      var already = chip.classList.contains("on") && value;
      tagInput.value = already ? "" : value;
      chips.querySelectorAll(".chip").forEach(function (c) {
        c.classList.toggle("on", c.dataset.tag === tagInput.value);
      });
      refresh();
    });
  }
})();
