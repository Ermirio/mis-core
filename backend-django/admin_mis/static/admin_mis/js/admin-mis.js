/* admin-mis.js — atalhos UX leves para o admin do MIS Core. */
(function () {
  "use strict";

  // Atalho "/" foca o campo de busca da changelist (#searchbar) — só fora de input.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    var sb = document.getElementById("searchbar");
    if (sb) {
      e.preventDefault();
      sb.focus();
      sb.select && sb.select();
    }
  });

  // Ctrl+S no change_form salva (clica no input default do submit-row).
  document.addEventListener("keydown", function (e) {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "s") return;
    var save = document.querySelector(".submit-row input[type=submit].default");
    if (save) {
      e.preventDefault();
      save.click();
    }
  });

  // Mostra a versão do admin no console como sanity-check.
  var meta = document.querySelector('meta[name="mis-version"]');
  var git = document.querySelector('meta[name="mis-git"]');
  if (meta || git) {
    /* eslint-disable no-console */
    console.info(
      "%c[MIS Admin] v" + (meta && meta.content) + "  ·  " + (git && git.content),
      "color:#3f5b7c;font-weight:600;"
    );
    /* eslint-enable no-console */
  }
})();
