/* Sélecteur d'étiquettes (thèmes / personnages / animaux). */
(function () {
  "use strict";

  var picker = document.getElementById("tagpicker");
  if (!picker) { return; }

  function addTag(kind, name) {
    name = (name || "").trim();
    if (!name) { return; }
    var group = picker.querySelector('.tag-group[data-kind="' + kind + '"]');
    var list = group.querySelector(".tag-list");
    var existing = Array.prototype.find.call(
      list.querySelectorAll(".chip"),
      function (chip) { return chip.dataset.name.toLowerCase() === name.toLowerCase(); }
    );
    if (existing) {
      existing.classList.add("on");
      return;
    }
    var chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip kind-" + kind + " on";
    chip.dataset.name = name;
    chip.dataset.kind = kind;
    chip.textContent = name;
    list.appendChild(chip);
  }

  picker.addEventListener("click", function (event) {
    var chip = event.target.closest(".chip");
    if (chip) {
      chip.classList.toggle("on");
      return;
    }
    var addBtn = event.target.closest(".add-tag");
    if (addBtn) {
      var field = picker.querySelector('.new-tag input[data-kind="' + addBtn.dataset.kind + '"]');
      addTag(addBtn.dataset.kind, field.value);
      field.value = "";
    }
  });

  picker.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && event.target.matches(".new-tag input")) {
      event.preventDefault();
      addTag(event.target.dataset.kind, event.target.value);
      event.target.value = "";
    }
  });

  window.tagPicker = {
    selected: function () {
      return Array.prototype.map.call(
        picker.querySelectorAll(".chip.on"),
        function (chip) { return { name: chip.dataset.name, kind: chip.dataset.kind }; }
      );
    },
    clear: function () {
      picker.querySelectorAll(".chip.on").forEach(function (chip) { chip.classList.remove("on"); });
    },
    /* Active automatiquement les étiquettes qui correspondent aux catégories
       renvoyées par Google Books / Open Library. */
    suggest: function (categories) {
      (categories || []).forEach(function (raw) {
        String(raw).split(/[\/,;&]|\set\s/).forEach(function (part) {
          var word = part.trim().toLowerCase();
          if (word.length < 3) { return; }
          picker.querySelectorAll(".chip").forEach(function (chip) {
            var name = chip.dataset.name.toLowerCase();
            if (name === word || word.indexOf(name) !== -1) { chip.classList.add("on"); }
          });
        });
      });
    }
  };
})();
