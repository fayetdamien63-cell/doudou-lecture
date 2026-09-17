/* Lecture du code-barres avec la caméra du téléphone.
 *
 * 1. On utilise d'abord l'API native BarcodeDetector (Chrome / Android) :
 *    rapide et sans aucune bibliothèque à charger.
 * 2. Sinon on charge ZXing (iOS / Firefox) depuis le fichier local
 *    static/js/vendor/zxing.min.js s'il existe, sinon depuis un CDN.
 *
 * ⚠️ La caméra n'est accessible qu'en HTTPS (ou sur http://localhost) :
 *    c'est justement ce que fournit le tunnel Cloudflare.
 */
(function () {
  "use strict";

  var FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "isbn"];
  var stream = null;
  var detectorLoop = null;
  var zxingReader = null;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = function () { reject(new Error("Chargement impossible : " + src)); };
      document.head.appendChild(script);
    });
  }

  function loadZxing() {
    if (window.ZXing) { return Promise.resolve(); }
    return loadScript("/static/js/vendor/zxing.min.js").catch(function () {
      return loadScript("https://cdn.jsdelivr.net/npm/@zxing/library@0.21.3/umd/index.min.js");
    });
  }

  function startNative(video, onResult) {
    var detector = new window.BarcodeDetector({
      formats: FORMATS.filter(function (f) { return f !== "isbn"; })
    });
    var busy = false;
    detectorLoop = setInterval(function () {
      if (busy || video.readyState < 2) { return; }
      busy = true;
      detector.detect(video).then(function (codes) {
        busy = false;
        if (codes && codes.length) { onResult(codes[0].rawValue); }
      }).catch(function () { busy = false; });
    }, 350);
  }

  function startZxing(video, onResult) {
    return loadZxing().then(function () {
      zxingReader = new window.ZXing.BrowserMultiFormatReader();
      return zxingReader.decodeFromConstraints(
        { video: { facingMode: { ideal: "environment" } } },
        video,
        function (result) { if (result) { onResult(result.getText()); } }
      );
    });
  }

  window.barcodeScanner = {
    supported: function () {
      return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    },

    start: function (video, onResult) {
      var self = this;
      if (!self.supported()) {
        return Promise.reject(new Error(
          "La caméra n'est pas disponible. Sur iPhone/Android, ouvrez le site en https://"
        ));
      }
      if (window.BarcodeDetector) {
        return navigator.mediaDevices
          .getUserMedia({ video: { facingMode: { ideal: "environment" } } })
          .then(function (media) {
            stream = media;
            video.srcObject = media;
            return video.play();
          })
          .then(function () { startNative(video, onResult); });
      }
      return startZxing(video, onResult);
    },

    stop: function () {
      if (detectorLoop) { clearInterval(detectorLoop); detectorLoop = null; }
      if (zxingReader) {
        try { zxingReader.reset(); } catch (e) { /* rien */ }
        zxingReader = null;
      }
      if (stream) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
      }
    },

    beep: function () {
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) { return; }
        var ctx = new Ctx();
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.frequency.value = 880;
        gain.gain.value = 0.12;
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        setTimeout(function () { osc.stop(); ctx.close(); }, 140);
      } catch (e) { /* le son n'est pas indispensable */ }
      if (navigator.vibrate) { navigator.vibrate(60); }
    }
  };
})();
